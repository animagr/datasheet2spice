"""Model quality and extraction coverage evaluation."""

from __future__ import annotations

from typing import Any

from .fitting import fit_abm_basic, fit_vdmos_static
from .schema import DeviceProject
from .validate import validate_project


def evaluate_project_model(project: DeviceProject) -> dict[str, Any]:
    if project.get_path("component", "family", default="mosfet") == "diode":
        return _evaluate_diode_project(project)
    errors = validate_project(project)
    static_score = _presence_score(
        project,
        [
            ("ratings", "vdss_v"),
            ("ratings", "vgs_on_v"),
            ("static", "vgs_th_v"),
            ("static", "rds_on_mohm"),
            ("static", "gfs_s"),
            ("static", "rg_int_ohm"),
        ],
    )
    dynamic_score = _presence_score(
        project,
        [
            ("dynamic", "capacitance"),
            ("dynamic", "gate_charge"),
            ("dynamic", "channel_fit"),
            ("dynamic", "body_diode"),
        ],
    )
    cap_score, cap_notes = _capacitance_score(project)
    fit_notes: list[str] = []
    fit_score = 0.5
    try:
        abm = fit_abm_basic(project)
        qgd_err = abm.metrics.get("qgd_rel_error", 0.0)
        fit_score = max(0.0, 1.0 - min(qgd_err, 1.0))
        if qgd_err > 0.5:
            fit_notes.append("Qgd predicted from capacitance is far from datasheet Qgd; use curve digitization or fit CGD_SCALE.")
    except Exception as exc:
        fit_notes.append(f"ABM fit failed: {exc}")
    try:
        fit_vdmos_static(project)
    except Exception as exc:
        fit_notes.append(f"VDMOS fit failed: {exc}")
        fit_score *= 0.8
    validation_score = 0.0 if errors else 1.0
    overall = round(100 * (0.25 * static_score + 0.25 * dynamic_score + 0.2 * cap_score + 0.2 * fit_score + 0.1 * validation_score))
    return {
        "overall_score": overall,
        "scores": {
            "static_coverage": round(static_score, 3),
            "dynamic_coverage": round(dynamic_score, 3),
            "capacitance_consistency": round(cap_score, 3),
            "fit_consistency": round(fit_score, 3),
            "schema_validity": round(validation_score, 3),
        },
        "errors": errors,
        "notes": cap_notes + fit_notes,
        "grade": _grade(overall),
    }


def _evaluate_diode_project(project: DeviceProject) -> dict[str, Any]:
    errors = validate_project(project)
    static_score = _presence_score(
        project,
        [
            ("ratings", "vrrm_v"),
            ("ratings", "if_av_a"),
            ("static", "forward_voltage"),
            ("static", "leakage"),
        ],
    )
    dynamic_score = _presence_score(
        project,
        [
            ("dynamic", "junction_capacitance"),
            ("dynamic", "reverse_recovery"),
            ("parasitics", "la_nh"),
            ("parasitics", "lk_nh"),
        ],
    )
    validation_score = 0.0 if errors else 1.0
    notes: list[str] = []
    if project.get_path("dynamic", "junction_capacitance", default=None) in (None, {}, []):
        notes.append("No diode junction-capacitance value or curve is available.")
    if project.get_path("dynamic", "reverse_recovery", default=None) in (None, {}, []):
        notes.append("No reverse-recovery data is available; Schottky devices may still be acceptable.")
    overall = round(100 * (0.45 * static_score + 0.35 * dynamic_score + 0.2 * validation_score))
    return {
        "overall_score": overall,
        "scores": {
            "static_coverage": round(static_score, 3),
            "dynamic_coverage": round(dynamic_score, 3),
            "schema_validity": round(validation_score, 3),
        },
        "errors": errors,
        "notes": notes,
        "grade": _grade(overall),
    }


def _presence_score(project: DeviceProject, paths: list[tuple[str, ...]]) -> float:
    present = 0
    for path in paths:
        value = project.get_path(*path, default=None)
        if value not in (None, {}, []):
            present += 1
    return present / len(paths)


def _capacitance_score(project: DeviceProject) -> tuple[float, list[str]]:
    caps = project.get_path("dynamic", "capacitance", default={})
    notes: list[str] = []
    if not caps:
        return 0.0, ["No capacitance curve is available."]
    vds = [float(v) for v in caps.get("vds_v", [])]
    ciss = [float(v) for v in caps.get("ciss_pf", [])]
    coss = [float(v) for v in caps.get("coss_pf", [])]
    crss = [float(v) for v in caps.get("crss_pf", [])]
    score = 1.0
    if len(vds) < 5:
        score -= 0.25
        notes.append("Capacitance curve has fewer than five points.")
    if any(b <= a for a, b in zip(vds, vds[1:])):
        score -= 0.35
        notes.append("VDS axis is not strictly increasing.")
    for name, values in [("Coss", coss), ("Crss", crss)]:
        if any(b > a * 1.25 for a, b in zip(values, values[1:])):
            score -= 0.15
            notes.append(f"{name} is not mostly decreasing with VDS.")
    if any(ci < cg for ci, cg in zip(ciss, crss)):
        score -= 0.25
        notes.append("Ciss is below Crss at one or more points.")
    if any(co < cg for co, cg in zip(coss, crss)):
        score -= 0.25
        notes.append("Coss is below Crss at one or more points.")
    return max(0.0, score), notes


def _grade(score: int) -> str:
    if score >= 85:
        return "reviewable"
    if score >= 65:
        return "starter"
    if score >= 40:
        return "rough"
    return "incomplete"
