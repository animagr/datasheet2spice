"""Quality gates for extraction accuracy and model benchmark evidence."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any

from .dialects import ALL_DIALECTS
from .plugins import load_plugins, registry
from .schema import DeviceProject
from .validate import run_ltspice


@dataclass(slots=True)
class FieldScore:
    field: str
    expected: Any
    actual: Any
    passed: bool
    abs_error: float | None
    rel_error: float | None
    tolerance: dict[str, float]
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "expected": self.expected,
            "actual": self.actual,
            "passed": self.passed,
            "abs_error": self.abs_error,
            "rel_error": self.rel_error,
            "tolerance": self.tolerance,
            "note": self.note,
        }


def load_case(path: str | Path) -> dict[str, Any]:
    """Load one validation case or a manifest containing one case."""

    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if "cases" in data:
        if len(data["cases"]) != 1:
            raise ValueError("manifest contains multiple cases; choose one case file or split the manifest")
        return dict(data["cases"][0])
    return dict(data)


def load_manifest(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if "cases" not in data:
        data = {"schema": "datasheet2spice-validation-v1", "cases": [data]}
    return data


def score_project_against_case(project: DeviceProject, case: dict[str, Any]) -> dict[str, Any]:
    """Score extracted project values against a golden datasheet case."""

    expectations = case.get("expected", {})
    field_scores = [_score_field(project, field, spec) for field, spec in sorted(expectations.items())]
    passed = sum(1 for item in field_scores if item.passed)
    total = len(field_scores)
    score = (passed / total) if total else 0.0
    required_fields = set(case.get("required_fields", []))
    required_failed = [item.field for item in field_scores if item.field in required_fields and not item.passed]
    status = "pass" if total and passed == total else "fail"
    if required_failed:
        status = "fail_required"
    return {
        "case_id": case.get("id", project.part_number),
        "part_number": project.part_number,
        "component_profile": project.get_path("component", "profile", default=""),
        "score": round(score, 4),
        "passed_fields": passed,
        "total_fields": total,
        "status": status,
        "required_failed": required_failed,
        "fields": [item.as_dict() for item in field_scores],
    }


def benchmark_project_models(
    project: DeviceProject,
    out_dir: str | Path,
    *,
    models: list[str],
    dialects: list[str],
    ltspice_exe: str | Path | None = None,
    timeout_s: int = 120,
) -> dict[str, Any]:
    """Generate model decks and optionally run LTspice benchmark smoke tests.

    The benchmark is intentionally simulator-agnostic at the result schema
    level. Today it can execute LTspice decks when ``ltspice_exe`` is supplied;
    otherwise it records generation-only evidence that CI can still compare.
    """

    load_plugins()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    dialect_list = list(ALL_DIALECTS) if dialects == ["all"] else dialects
    started = time.perf_counter()

    for model in models:
        if model not in registry.emitters:
            raise ValueError(f"unknown emitter: {model}")
        emitter = registry.emitters[model]
        for dialect in dialect_list:
            generated = emitter.emit(project, dialect=dialect)
            for filename, content in generated.items():
                path = out / model / dialect / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
                record = {
                    "model": model,
                    "dialect": dialect,
                    "filename": filename,
                    "path": str(path),
                    "kind": "deck" if filename.lower().endswith(".cir") else "model",
                    "bytes": len(content.encode("utf-8")),
                    "status": "generated",
                }
                if record["kind"] == "deck" and dialect == "ltspice" and ltspice_exe:
                    sim_start = time.perf_counter()
                    sim = run_ltspice(ltspice_exe, path, timeout_s=timeout_s)
                    record.update(
                        {
                            "status": "simulated",
                            "elapsed_s": round(time.perf_counter() - sim_start, 4),
                            "returncode": sim["returncode"],
                            "fatal": sim["fatal"],
                            "warnings": sim["warnings"],
                            "log_path": sim["log_path"],
                        }
                    )
                records.append(record)

    summary = _summarize_benchmark(records)
    result = {
        "schema": "datasheet2spice-benchmark-v1",
        "part_number": project.part_number,
        "models": models,
        "dialects": dialect_list,
        "total_elapsed_s": round(time.perf_counter() - started, 4),
        "summary": summary,
        "records": records,
    }
    (out / "benchmark_report.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "benchmark_report.md").write_text(render_benchmark_report(result), encoding="utf-8")
    return result


def render_score_report(result: dict[str, Any]) -> str:
    lines = [
        f"# Extraction Score: {result['case_id']}",
        "",
        f"- Part: `{result['part_number']}`",
        f"- Score: `{result['passed_fields']}/{result['total_fields']}` ({result['score']:.1%})",
        f"- Status: `{result['status']}`",
        "",
        "| Field | Expected | Actual | Result | Error |",
        "| --- | ---: | ---: | --- | ---: |",
    ]
    for field in result["fields"]:
        error = "" if field["abs_error"] is None else f"{field['abs_error']:.6g}"
        outcome = "pass" if field["passed"] else "fail"
        lines.append(f"| `{field['field']}` | `{field['expected']}` | `{field['actual']}` | {outcome} | {error} |")
    lines.append("")
    return "\n".join(lines)


def render_benchmark_report(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        f"# Model Benchmark: {result['part_number']}",
        "",
        f"- Models: `{', '.join(result['models'])}`",
        f"- Dialects: `{', '.join(result['dialects'])}`",
        f"- Generated files: `{summary['generated_files']}`",
        f"- Simulated decks: `{summary['simulated_decks']}`",
        f"- Failed simulations: `{summary['failed_simulations']}`",
        f"- Total elapsed: `{result['total_elapsed_s']} s`",
        "",
        "| Model | Dialect | File | Kind | Status | Time (s) | Warnings |",
        "| --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for record in result["records"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{record['model']}`",
                    f"`{record['dialect']}`",
                    f"`{record['filename']}`",
                    record["kind"],
                    record["status"],
                    str(record.get("elapsed_s", "")),
                    str(record.get("warnings", "")),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def _score_field(project: DeviceProject, field: str, spec: Any) -> FieldScore:
    if not isinstance(spec, dict):
        spec = {"value": spec}
    expected = spec.get("value")
    actual = project.get_path(*field.split("."), default=None)
    tolerance = {
        "abs_tol": float(spec.get("abs_tol", 0.0) or 0.0),
        "rel_tol": float(spec.get("rel_tol", 0.0) or 0.0),
    }
    if actual is None:
        return FieldScore(field, expected, actual, False, None, None, tolerance, "missing")
    if isinstance(expected, str):
        passed = str(actual).strip().lower() == expected.strip().lower()
        return FieldScore(field, expected, actual, passed, None, None, tolerance)
    try:
        actual_float = float(actual)
        expected_float = float(expected)
    except (TypeError, ValueError):
        passed = actual == expected
        return FieldScore(field, expected, actual, passed, None, None, tolerance)
    abs_error = abs(actual_float - expected_float)
    rel_error = abs_error / max(abs(expected_float), 1e-30)
    allowed = max(tolerance["abs_tol"], tolerance["rel_tol"] * abs(expected_float))
    passed = abs_error <= allowed
    return FieldScore(field, expected, actual, passed, abs_error, rel_error, tolerance)


def _summarize_benchmark(records: list[dict[str, Any]]) -> dict[str, Any]:
    simulated = [item for item in records if item["status"] == "simulated"]
    failed = [item for item in simulated if item.get("returncode") or item.get("fatal")]
    elapsed = [float(item["elapsed_s"]) for item in simulated if "elapsed_s" in item]
    return {
        "generated_files": len(records),
        "generated_decks": sum(1 for item in records if item["kind"] == "deck"),
        "simulated_decks": len(simulated),
        "failed_simulations": len(failed),
        "max_elapsed_s": round(max(elapsed), 4) if elapsed else None,
        "mean_elapsed_s": round(sum(elapsed) / len(elapsed), 4) if elapsed else None,
    }
