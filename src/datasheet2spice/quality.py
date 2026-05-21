"""Quality gates for extraction accuracy and model benchmark evidence."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import time
from typing import Any

from .dialects import ALL_DIALECTS
from .plugins import load_plugins, registry
from .schema import DeviceProject
from .validate import run_ltspice


_SPICE_NUMBER_RE = re.compile(
    r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?:meg|[fpnumkgt])?",
    flags=re.IGNORECASE,
)

_SI_MULTIPLIERS = {
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "meg": 1e6,
    "g": 1e9,
    "t": 1e12,
}

_SWITCHING_MEASURE_BLOCK = """\
* datasheet2spice switching benchmark metrics
.meas tran d2s_vg_on_avg AVG V(gate) FROM=5u TO=20u
.meas tran d2s_vg_off_avg AVG V(gate) FROM=21.5u TO=24.8u
.meas tran d2s_il_on_avg AVG I(Lload) FROM=5u TO=20u
.meas tran d2s_il_peak MAX I(Lload) FROM=0.1u TO=26.4u
.meas tran d2s_vds_on_avg AVG V(drain) FROM=5u TO=20u
.meas tran d2s_vds_on_min MIN V(drain) FROM=5u TO=20u
.meas tran d2s_vds_off_max MAX V(drain) FROM=21.5u TO=24.8u
.meas tran d2s_vds_off_min MIN V(drain) FROM=21.5u TO=24.8u
.meas tran d2s_vds_reon_max MAX V(drain) FROM=25.2u TO=26.4u
"""


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
    measure_switching: bool = False,
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
                switching_instrumented = False
                if measure_switching and dialect == "ltspice" and _is_switching_benchmark_deck(project, filename, content):
                    content = instrument_switching_benchmark_deck(content)
                    switching_instrumented = True
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
                if switching_instrumented:
                    record["switching_instrumented"] = True
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
                    if switching_instrumented:
                        measurements = parse_ltspice_measurements(sim["log"])
                        record["measurements"] = measurements
                        record["switching"] = evaluate_switching_measurements(measurements, project)
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


def instrument_switching_benchmark_deck(content: str) -> str:
    """Insert LTspice .meas lines into a generated MOSFET switching deck."""

    if "datasheet2spice switching benchmark metrics" in content:
        return content
    block = "\n" + _SWITCHING_MEASURE_BLOCK
    matches = list(re.finditer(r"(?im)^\s*\.end\s*$", content))
    if not matches:
        return content.rstrip() + block + ".end\n"
    end = matches[-1]
    return content[: end.start()].rstrip() + block + content[end.start() :]


def parse_ltspice_measurements(log: str, *, prefix: str | None = "d2s_") -> dict[str, float]:
    """Parse numeric .meas results from an LTspice log.

    LTspice has used more than one text layout across versions. This parser
    accepts both ``name: expr=value`` rows and ``Measurement: name`` blocks.
    Names are lower-cased so benchmark records stay stable across platforms.
    By default it keeps only datasheet2spice benchmark names so ordinary log
    lines such as ``temp=27`` are not mistaken for measurements.
    """

    measurements: dict[str, float] = {}
    active_name: str | None = None
    for line in log.splitlines():
        header = re.match(r"\s*Measurement:\s*([A-Za-z_][\w.]*)", line, flags=re.IGNORECASE)
        if header:
            name = header.group(1).lower()
            active_name = name if prefix is None or name.startswith(prefix) else None
            continue

        named = re.match(r"\s*([A-Za-z_][\w.]*)\s*(?::|=)\s*(.+)", line)
        if named:
            name = named.group(1).lower()
            if prefix is not None and not name.startswith(prefix):
                continue
            value = _parse_measurement_tail(named.group(2))
            if value is not None:
                measurements[name] = value
                active_name = None
            continue

        if active_name and "=" in line:
            value = _parse_measurement_tail(line)
            if value is not None:
                measurements[active_name] = value
                active_name = None
    return measurements


def evaluate_switching_measurements(measurements: dict[str, float], project: DeviceProject) -> dict[str, Any]:
    """Classify MOSFET double-pulse metrics into pass/review/fail buckets."""

    m = {key.lower(): float(value) for key, value in measurements.items()}
    required = [
        "d2s_vg_on_avg",
        "d2s_il_on_avg",
        "d2s_vds_on_avg",
        "d2s_vds_reon_max",
        "d2s_vds_off_max",
        "d2s_vds_off_min",
    ]
    hard_flags: list[str] = []
    review_flags: list[str] = []
    missing = [name for name in required if name not in m]
    if missing:
        hard_flags.append("missing_switching_measurements:" + ",".join(missing))

    ratings = project.get_path("ratings", default={})
    static = project.get_path("static", default={})
    vdss = float(ratings.get("vdss_v", 1200.0) or 1200.0)
    vbus = min(vdss * 2 / 3, 800.0)
    v_on = float(ratings.get("vgs_on_v", 18.0) or 18.0)
    v_off = float(ratings.get("vgs_off_v", 0.0) or 0.0)
    id_cont = float(ratings.get("id_cont_a", 0.0) or 0.0)
    rds_map = static.get("rds_on_mohm", {}) if isinstance(static, dict) else {}
    rds_on = float(rds_map.get("25", next(iter(rds_map.values()), 20.0)) or 20.0) * 1e-3

    gate_on_min = max(v_on * 0.65, v_on - 5.0)
    current_min = max(1.0, min(id_cont * 0.05, 10.0)) if id_cont > 0 else 1.0
    vds_on_limit = max(10.0, min(vbus * 0.15, max(id_cont * rds_on * 4.0, 20.0) if id_cont > 0 else 20.0))
    overshoot_limit = min(vdss * 1.05, vbus * 1.45)
    ringing_review_limit = max(40.0, vbus * 0.25)
    ringing_fail_limit = max(120.0, vbus * 0.75)

    if "d2s_vg_on_avg" in m and m["d2s_vg_on_avg"] < gate_on_min:
        hard_flags.append("gate_drive_did_not_reach_on_level")
    if "d2s_vg_off_avg" in m and m["d2s_vg_off_avg"] > max(v_off + 3.0, v_on * 0.2):
        review_flags.append("gate_drive_slow_or_incomplete_turn_off")
    if "d2s_il_on_avg" in m and abs(m["d2s_il_on_avg"]) < current_min:
        hard_flags.append("device_did_not_build_load_current")
    if "d2s_vds_on_avg" in m and m["d2s_vds_on_avg"] > vds_on_limit:
        hard_flags.append("device_did_not_pull_drain_low")
    if "d2s_vds_reon_max" in m and m["d2s_vds_reon_max"] > vds_on_limit:
        hard_flags.append("second_turn_on_did_not_pull_drain_low")
    if "d2s_vds_off_max" in m and m["d2s_vds_off_max"] > overshoot_limit:
        hard_flags.append("excessive_turn_off_overshoot")
    if "d2s_vds_off_max" in m and "d2s_vds_off_min" in m:
        vds_off_pp = max(0.0, m["d2s_vds_off_max"] - m["d2s_vds_off_min"])
        if vds_off_pp > ringing_fail_limit:
            hard_flags.append("severe_turn_off_ringing")
        elif vds_off_pp > ringing_review_limit:
            review_flags.append("turn_off_ringing_review")
    else:
        vds_off_pp = None

    status = "pass"
    if hard_flags:
        status = "fail"
    elif review_flags:
        status = "review"

    return {
        "status": status,
        "hard_flags": hard_flags,
        "review_flags": review_flags,
        "derived": {
            "vbus_v": round(vbus, 6),
            "vds_off_pp_v": round(vds_off_pp, 6) if vds_off_pp is not None else None,
            "vds_reon_max_v": round(m["d2s_vds_reon_max"], 6) if "d2s_vds_reon_max" in m else None,
        },
        "limits": {
            "gate_on_min_v": round(gate_on_min, 6),
            "current_min_a": round(current_min, 6),
            "vds_on_avg_max_v": round(vds_on_limit, 6),
            "turn_off_overshoot_max_v": round(overshoot_limit, 6),
            "ringing_review_pp_v": round(ringing_review_limit, 6),
            "ringing_fail_pp_v": round(ringing_fail_limit, 6),
        },
    }


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
        f"- Switching checks: `{summary.get('switching_checks', 0)}`",
        f"- Failed switching checks: `{summary.get('failed_switching_checks', 0)}`",
        f"- Total elapsed: `{result['total_elapsed_s']} s`",
        "",
        "| Model | Dialect | File | Kind | Status | Time (s) | Warnings | Switching |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for record in result["records"]:
        switching = record.get("switching", {}).get("status", "")
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
                    switching,
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
    switching = [item for item in records if "switching" in item]
    failed_switching = [item for item in switching if item["switching"]["status"] == "fail"]
    review_switching = [item for item in switching if item["switching"]["status"] == "review"]
    return {
        "generated_files": len(records),
        "generated_decks": sum(1 for item in records if item["kind"] == "deck"),
        "simulated_decks": len(simulated),
        "failed_simulations": len(failed),
        "switching_checks": len(switching),
        "failed_switching_checks": len(failed_switching),
        "review_switching_checks": len(review_switching),
        "max_elapsed_s": round(max(elapsed), 4) if elapsed else None,
        "mean_elapsed_s": round(sum(elapsed) / len(elapsed), 4) if elapsed else None,
    }


def _is_switching_benchmark_deck(project: DeviceProject, filename: str, content: str) -> bool:
    if project.get_path("component", "family", default="mosfet") != "mosfet":
        return False
    lower_name = filename.lower()
    lower_content = content.lower()
    return lower_name.endswith(".cir") and "double_pulse" in lower_name and "v(gate)" in lower_content and "i(lload)" in lower_content


def _parse_measurement_tail(text: str) -> float | None:
    tail = text.split("=", 1)[1] if "=" in text else text
    match = _SPICE_NUMBER_RE.search(tail)
    if not match:
        return None
    return _parse_spice_number(match.group(0))


def _parse_spice_number(text: str) -> float:
    raw = text.strip()
    lower = raw.lower()
    for suffix in ("meg", "f", "p", "n", "u", "m", "k", "g", "t"):
        if lower.endswith(suffix):
            return float(raw[: -len(suffix)]) * _SI_MULTIPLIERS[suffix]
    return float(raw)
