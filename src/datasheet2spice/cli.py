"""Command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .plugins import load_plugins, plugin_load_errors, registry
from .report import render_report
from .schema import DeviceProject
from .validate import validate_project, run_ltspice
from .extractors.csv_curves import read_capacitance_csv


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
    dialects = ["common", "ltspice", "ngspice"] if args.dialect == "all" else [args.dialect]
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
    print("emitters:")
    for name in sorted(registry.emitters):
        print(f"  - {name}")
    print("extractors:")
    for name in sorted(registry.extractors):
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
    p.add_argument("--model", default="abm-basic", help="emitter id, including third-party plugin emitters")
    p.add_argument("--dialect", choices=["common", "ltspice", "ngspice", "all"], default="ltspice")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_emit)

    p = sub.add_parser("import-capacitance-csv", help="import digitized Ciss/Coss/Crss curves into a project")
    p.add_argument("project")
    p.add_argument("csv")
    p.add_argument("--out", help="output project path; defaults to overwriting the input project")
    p.set_defaults(func=cmd_import_capacitance_csv)

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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
