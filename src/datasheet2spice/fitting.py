"""Parameter fitting helpers for starter MOSFET models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .schema import DeviceProject


@dataclass(slots=True)
class FitResult:
    model: str
    parameters: dict[str, float]
    metrics: dict[str, float]
    notes: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "parameters": self.parameters,
            "metrics": self.metrics,
            "notes": self.notes,
        }


def fit_project_parameters(project: DeviceProject) -> dict[str, Any]:
    """Fit model starter parameters from the currently extracted project data."""

    results = [fit_vdmos_static(project), fit_abm_basic(project)]
    project.data.setdefault("models", {}).setdefault("fits", {})
    for result in results:
        project.data["models"]["fits"][result.model] = result.as_dict()
    return {"fits": [result.as_dict() for result in results], "project": project.data}


def fit_vdmos_static(project: DeviceProject) -> FitResult:
    static = project.get_path("static", default={})
    dynamic = project.get_path("dynamic", default={})
    ratings = project.get_path("ratings", default={})
    caps = dynamic.get("capacitance", {})
    body = dynamic.get("body_diode", {})
    vth = _temp_value(static.get("vgs_th_v", {}), 25, 4.0)
    rds_mohm = _temp_value(static.get("rds_on_mohm", {}), 25, 20.0)
    rds = rds_mohm * 1e-3
    gfs = float(static.get("gfs_s", 20.0) or 20.0)
    crss = [float(v) for v in caps.get("crss_pf", [10.0])]
    ciss = [float(v) for v in caps.get("ciss_pf", [1000.0])]
    coss = [float(v) for v in caps.get("coss_pf", [100.0])]
    params = {
        "Vto": vth,
        "Kp": max(gfs * gfs * rds / 2, 0.1),
        "Rd": max(rds * 0.45, 1e-6),
        "Rs": max(rds * 0.45, 1e-6),
        "Rg": float(static.get("rg_int_ohm", 0.0) or 0.0),
        "Cgdmax_pF": max(crss),
        "Cgdmin_pF": min(crss[-3:]) if len(crss) >= 3 else min(crss),
        "Cgs_pF": max(ciss[-1] - crss[-1], 1.0),
        "Cjo_pF": max(coss[-1] - crss[-1], 1.0),
        "BV": float(ratings.get("vdss_v", 100.0) or 100.0),
        "Tt_ns": _reverse_recovery_tt(body),
    }
    return FitResult(
        model="vdmos-static-fast",
        parameters=params,
        metrics={"rds_on_25_mohm": rds_mohm, "gfs_s": gfs},
        notes=["Closed-form starter fit from RDS(on), gfs, threshold voltage, capacitance, and diode recovery."],
    )


def fit_abm_basic(project: DeviceProject) -> FitResult:
    static = project.get_path("static", default={})
    dynamic = project.get_path("dynamic", default={})
    caps = dynamic.get("capacitance", {})
    gate_charge = dynamic.get("gate_charge", {})
    channel = dynamic.get("channel_fit", {})
    vgs_on = float(project.get_path("ratings", "vgs_on_v", default=10.0) or 10.0)
    ids_ref = float(channel.get("idsat_reference_a") or project.get_path("ratings", "id_cont_a", default=50.0) or 50.0)
    vgs_ref = float(channel.get("vgs_reference_v") or vgs_on)
    vth = _temp_value(static.get("vgs_th_v", {}), 25, 4.0)
    kid = ids_ref / max((vgs_ref - vth) ** 2, 1e-6)
    vds = [float(v) for v in caps.get("vds_v", [])]
    crss = [float(v) for v in caps.get("crss_pf", [])]
    ciss = [float(v) for v in caps.get("ciss_pf", [])]
    qgd_est = _integral_nc(vds, crss)
    cgs_curve = [max(ci - cg, 0.0) for ci, cg in zip(ciss, crss)]
    qgs_est = _integral_nc(vds[: min(3, len(vds))], cgs_curve[: min(3, len(cgs_curve))]) if cgs_curve else 0.0
    qgd_target = _float_or_zero(gate_charge.get("qgd_nc"))
    qgs_target = _float_or_zero(gate_charge.get("qgs_nc"))
    qg_target = _float_or_zero(gate_charge.get("qg_nc"))
    cgd_scale = qgd_target / qgd_est if qgd_target > 0 and qgd_est > 0 else 1.0
    cgs_scale = qgs_target / qgs_est if qgs_target > 0 and qgs_est > 0 else 1.0
    params = {
        "KID": kid,
        "IDSAT_REFERENCE_A": ids_ref,
        "VGS_REFERENCE_V": vgs_ref,
        "CGD_SCALE": _clamp(cgd_scale, 0.05, 20.0),
        "CGS_SCALE": _clamp(cgs_scale, 0.05, 20.0),
        "CDS_SCALE": 1.0,
    }
    metrics = {
        "qgd_est_nc": qgd_est,
        "qgd_target_nc": qgd_target,
        "qgd_rel_error": _rel_error(qgd_est, qgd_target),
        "qg_target_nc": qg_target,
    }
    return FitResult(
        model="abm-basic",
        parameters=params,
        metrics=metrics,
        notes=[
            "KID fitted from one Idsat/Vgs point and threshold voltage.",
            "CGD/CGS scale factors are recommendations; inspect waveforms before committing them.",
        ],
    )


def _integral_nc(x_values: list[float], c_pf: list[float]) -> float:
    if len(x_values) < 2 or len(c_pf) < 2:
        return 0.0
    total_pf_v = 0.0
    for x0, x1, c0, c1 in zip(x_values, x_values[1:], c_pf, c_pf[1:]):
        total_pf_v += (x1 - x0) * (c0 + c1) / 2
    return total_pf_v * 0.001


def _temp_value(values: dict[str, Any], temp: int, default: float) -> float:
    if not values:
        return default
    key = str(temp)
    if key in values:
        return float(values[key])
    return float(next(iter(values.values())))


def _reverse_recovery_tt(body: dict[str, Any]) -> float:
    qrr = _float_or_zero(body.get("qrr_nc"))
    if qrr > 0:
        return qrr / 68.0
    trr = _float_or_zero(body.get("trr_ns"))
    return trr or 20.0


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _rel_error(value: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return abs(value - target) / target


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)
