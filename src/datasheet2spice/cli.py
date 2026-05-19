"""Command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .dialects import ALL_DIALECTS, SUPPORTED_DIALECTS
from .plugins import load_plugins, plugin_load_errors, registry
from .quality import benchmark_project_models, load_case, render_score_report, score_project_against_case
from .report import render_report
from .schema import DeviceProject
from .validate import validate_project, run_ltspice
from .extractors.csv_curves import read_capacitance_csv, read_wpd_capacitance_csv_with_warnings


def _load_project(path: Path) -> DeviceProject:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if "electrical_typ" in data and "device" in data and "schema_version" not in data:
        project = DeviceProject.from_legacy_s4661(data)
        project.path = path
        return project
    project = DeviceProject(data=data, path=path)
    project.validate()
    return project


def cmd_init(args: argparse.Namespace) -> int:
    project = DeviceProject.new(args.part_number, datasheet=args.datasheet, vendor=args.vendor)
    out = Path(args.out or f"{args.part_number}.device.json")
    project.save(out)
    print(out)
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    legacy = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
    project = DeviceProject.from_legacy_s4661(legacy)
    project.save(args.out)
    print(args.out)
    return 0


def cmd_emit(args: argparse.Namespace) -> int:
    load_plugins()
    project = _load_project(Path(args.project))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    models = ["vdmos-static-fast", "abm-basic"] if args.all else [args.model]
    dialects = list(ALL_DIALECTS) if args.dialect == "all" else [args.dialect]
    if any(model in {"vdmos-static-fast", "abm-basic"} for model in models):
        errors = validate_project(project)
        if errors:
            for err in errors:
                print(f"ERROR: {err}", file=sys.stderr)
            return 1
    written: list[Path] = []
    for model in models:
        if model not in registry.emitters:
            known = ", ".join(sorted(registry.emitters)) or "none"
            failures = "; ".join(plugin_load_errors)
            detail = f" Known emitters: {known}."
            if failures:
                detail += f" Plugin load failures: {failures}."
            raise SystemExit(f"unknown emitter: {model}.{detail}")
        emitter = registry.emitters[model]
        for dialect in dialects:
            files = emitter.emit(project, dialect=dialect)
            for name, content in files.items():
                path = out / name
                path.write_text(content, encoding="utf-8", newline="\n")
                written.append(path)
    for path in written:
        print(path)
    return 0


def cmd_import_capacitance_csv(args: argparse.Namespace) -> int:
    project = _load_project(Path(args.project))
    caps = read_capacitance_csv(args.csv)
    project.data.setdefault("dynamic", {})["capacitance"] = caps
    project.data.setdefault("provenance", []).append(
        {
            "source": str(args.csv),
            "kind": "digitized_capacitance_csv",
            "note": "Imported Ciss/Coss/Crss curves from CSV columns vds_v,ciss_pf,coss_pf,crss_pf.",
        }
    )
    out = Path(args.out) if args.out else Path(args.project)
    project.save(out)
    print(out)
    return 0


def cmd_import_wpd_capacitance_csv(args: argparse.Namespace) -> int:
    project = _load_project(Path(args.project))
    imported = read_wpd_capacitance_csv_with_warnings(args.csv)
    project.data.setdefault("dynamic", {})["capacitance"] = imported.data
    note = "Imported WebPlotDigitizer side-by-side Ciss/Coss/Crss datasets; first X column used as shared VDS axis."
    if imported.warnings:
        note += " Warnings: " + " ".join(imported.warnings)
    project.data.setdefault("provenance", []).append(
        {
            "source": str(args.csv),
            "kind": "webplotdigitizer_capacitance_csv",
            "note": note,
        }
    )
    out = Path(args.out) if args.out else Path(args.project)
    project.save(out)
    for warning in imported.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    print(out)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    project = _load_project(Path(args.project))
    errors = validate_project(project)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print("schema ok")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    project = _load_project(Path(args.project))
    text = render_report(project)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(args.out)
    else:
        print(text)
    return 0


def cmd_plugins(args: argparse.Namespace) -> int:
    loaded = load_plugins()
    print("component profiles:")
    for name in sorted(registry.component_profiles):
        print(f"  - {name}")
    print("emitters:")
    for name in sorted(registry.emitters):
        print(f"  - {name}")
    print("extractors:")
    for name in sorted(registry.extractors):
        print(f"  - {name}")
    print("fitters:")
    for name in sorted(registry.fitters):
        print(f"  - {name}")
    print("tool panels:")
    for name in sorted(registry.tool_panels):
        print(f"  - {name}")
    print("validators:")
    for name in sorted(registry.validators):
        print(f"  - {name}")
    if loaded:
        print("entrypoints:")
        for name in loaded:
            print(f"  - {name}")
    if plugin_load_errors:
        print("entrypoint errors:")
        for err in plugin_load_errors:
            print(f"  - {err}")
    return 0


def cmd_run_ltspice(args: argparse.Namespace) -> int:
    result = run_ltspice(args.ltspice, args.deck, timeout_s=args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["returncode"] or result["fatal"] else 0


def cmd_score_case(args: argparse.Namespace) -> int:
    project = _load_project(Path(args.project))
    case = load_case(args.case)
    result = score_project_against_case(project, case)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else render_score_report(result)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(args.out)
    else:
        print(text, end="")
    return 0 if result["status"] == "pass" else 1


def cmd_benchmark_model(args: argparse.Namespace) -> int:
    project = _load_project(Path(args.project))
    dialects = list(ALL_DIALECTS) if args.dialect == "all" else [args.dialect]
    models = args.model
    if args.run_ltspice and not args.ltspice:
        print("ERROR: --ltspice is required with --run-ltspice", file=sys.stderr)
        return 1
    result = benchmark_project_models(
        project,
        args.out,
        models=models,
        dialects=dialects,
        ltspice_exe=args.ltspice if args.run_ltspice else None,
        timeout_s=args.timeout,
    )
    print(Path(args.out) / "benchmark_report.json")
    return 1 if result["summary"]["failed_simulations"] else 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .webapp import serve

    serve(host=args.host, port=args.port, out_dir=args.out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="datasheet2spice")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create an empty project file")
    p.add_argument("part_number")
    p.add_argument("datasheet", nargs="?")
    p.add_argument("--vendor", default="")
    p.add_argument("--out")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("convert-legacy-s4661", help="convert the prototype S4661 JSON into v1 schema")
    p.add_argument("input")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("emit", help="emit SPICE models and starter decks")
    p.add_argument("project")
    p.add_argument("--out", default="build")
    p.add_argument("--model", default="abm-basic", help="emitter id; third-party plugin emitters require explicit plugin opt-in")
    p.add_argument("--dialect", choices=[*SUPPORTED_DIALECTS, "all"], default="ltspice")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_emit)

    p = sub.add_parser("import-capacitance-csv", help="import digitized Ciss/Coss/Crss curves into a project")
    p.add_argument("project")
    p.add_argument("csv")
    p.add_argument("--out", help="output project path; defaults to overwriting the input project")
    p.set_defaults(func=cmd_import_capacitance_csv)

    p = sub.add_parser("import-wpd-capacitance-csv", help="import native WebPlotDigitizer Ciss/Coss/Crss CSV into a project")
    p.add_argument("project")
    p.add_argument("csv")
    p.add_argument("--out", help="output project path; defaults to overwriting the input project")
    p.set_defaults(func=cmd_import_wpd_capacitance_csv)

    p = sub.add_parser("validate", help="validate a project schema")
    p.add_argument("project")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("report", help="render a markdown report")
    p.add_argument("project")
    p.add_argument("--out")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("plugins", help="list registered plugins")
    p.set_defaults(func=cmd_plugins)

    p = sub.add_parser("run-ltspice", help="run LTspice in batch mode on a generated deck")
    p.add_argument("deck")
    p.add_argument("--ltspice", required=True)
    p.add_argument("--timeout", type=int, default=120)
    p.set_defaults(func=cmd_run_ltspice)

    p = sub.add_parser("score-case", help="score a project against a golden validation case")
    p.add_argument("project")
    p.add_argument("case")
    p.add_argument("--out")
    p.add_argument("--format", choices=["json", "md"], default="json")
    p.set_defaults(func=cmd_score_case)

    p = sub.add_parser("benchmark-model", help="generate models and record simulator benchmark evidence")
    p.add_argument("project")
    p.add_argument("--out", default="build/benchmark")
    p.add_argument("--model", action="append", required=True, help="model emitter id; repeat for multiple emitters")
    p.add_argument("--dialect", choices=[*SUPPORTED_DIALECTS, "all"], default="ltspice")
    p.add_argument("--run-ltspice", action="store_true", help="run generated LTspice decks when dialect is ltspice")
    p.add_argument("--ltspice", help="path to LTspice executable")
    p.add_argument("--timeout", type=int, default=120)
    p.set_defaults(func=cmd_benchmark_model)

    p = sub.add_parser("serve", help="run the local browser PDF extraction workbench")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--out", default="build/webapp")
    p.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
