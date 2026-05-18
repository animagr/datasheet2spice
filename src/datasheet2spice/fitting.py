"""Parameter fitting helpers for starter MOSFET models."""

from __future__ import annotations

from dataclasses import dataclass
import math
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

    if project.get_path("component", "family", default="mosfet") == "diode":
        results = [fit_diode_basic(project), fit_diode_abm_dynamic(project)]
    else:
        results = [fit_vdmos_static(project), fit_abm_basic(project)]
    project.data.setdefault("models", {}).setdefault("fits", {})
    for result in results:
        project.data["models"]["fits"][result.model] = result.as_dict()
    return {"fits": [result.as_dict() for result in results], "project": project.data}


def fit_diode_basic(project: DeviceProject) -> FitResult:
    ratings = project.get_path("ratings", default={})
    forward = project.get_path("static", "forward_voltage", default={})
    capacitance = project.get_path("dynamic", "junction_capacitance", default={})
    recovery = project.get_path("dynamic", "reverse_recovery", default={})

    vrrm = _first_number(ratings, ("vrrm_v", "vr_v", "vbr_v"), 600.0)
    if_ref = _first_number(ratings, ("if_av_a", "if_cont_a", "if_a"), 10.0)
    if_ref = _first_number(forward, ("if_a", "test_current_a"), if_ref)
    vf = _first_number(forward, ("vf_v", "typ_v", "typ", "max_v", "max", "25"), 1.0)
    cj0 = _first_number(capacitance, ("cj0_pf", "cj_pf", "ct_pf", "cjo_pf"), 50.0)
    trr = _first_number(recovery, ("trr_ns", "trr_typ_ns", "trr_max_ns"), 20.0)
    qrr = _first_number(recovery, ("qrr_nc", "qrr_typ_nc", "qrr_max_nc"), 0.0)

    n = 1.8
    rs = max((vf / max(if_ref, 1e-9)) * 0.08, 1e-6)
    exponent = min(max((vf - if_ref * rs) / (n * 0.025852), 1.0), 80.0)
    saturation = min(max(if_ref / max(math.exp(exponent) - 1.0, 1e-30), 1e-18), 1e-3)
    tt_ns = max(qrr / max(if_ref, 1e-9), trr * 0.35) if qrr > 0 else trr

    return FitResult(
        model="diode-basic",
        parameters={
            "IS": saturation,
            "N": n,
            "RS": rs,
            "CJO_pF": max(cj0, 0.01),
            "TT_ns": max(tt_ns, 0.001),
            "BV": max(vrrm, 1.0),
        },
        metrics={"vf_reference_v": vf, "if_reference_a": if_ref, "qrr_nc": qrr, "trr_ns": trr},
        notes=["Closed-form starter fit from forward voltage, reference current, junction capacitance, and recovery data."],
    )


def fit_diode_abm_dynamic(project: DeviceProject) -> FitResult:
    ratings = project.get_path("ratings", default={})
    forward = project.get_path("static", "forward_voltage", default={})
    capacitance = project.get_path("dynamic", "junction_capacitance", default={})
    recovery = project.get_path("dynamic", "reverse_recovery", default={})

    if_ref = _first_number(ratings, ("if_av_a", "if_cont_a", "if_a"), 10.0)
    if_ref = max(_first_number(forward, ("if_a", "test_current_a"), if_ref), 1e-9)
    cj0 = max(_first_number(capacitance, ("cj0_pf", "cj_pf", "ct_pf", "cjo_pf"), 50.0), 0.01)
    trr = max(_first_number(recovery, ("trr_ns", "trr_typ_ns", "trr_max_ns"), 20.0), 0.001)
    qrr = max(_first_number(recovery, ("qrr_nc", "qrr_typ_nc", "qrr_max_nc"), 0.0), 0.0)
    irrm = _first_number(recovery, ("irrm_a", "irrm_typ_a", "irrm_max_a"), math.nan)
    tau_ns = max(qrr / if_ref, trr * 0.35) if qrr > 0 else trr
    if not math.isfinite(irrm) or irrm <= 0:
        irrm = (2.0 * qrr / trr) if qrr > 0 else if_ref
    rr_scale = _clamp(irrm / if_ref, 0.05, 10.0)

    return FitResult(
        model="diode-abm-dynamic",
        parameters={
            "CJO_pF": cj0,
            "CJ_SCALE": 1.0,
            "VJ": 0.8,
            "M": 0.45,
            "TAU_ns": max(tau_ns, 0.001),
            "QRR_nC": qrr,
            "TRR_ns": trr,
            "IRRM_A": max(irrm, 0.0),
            "RR_SCALE": rr_scale,
        },
        metrics={
            "if_reference_a": if_ref,
            "qrr_nc": qrr,
            "trr_ns": trr,
            "irrm_a": max(irrm, 0.0),
        },
        notes=[
            "Dynamic ABM starter fit uses a nonlinear Cj(VR) current and a one-state reverse-recovery charge approximation.",
            "Tune TAU_ns, RR_SCALE, and CJ_SCALE against datasheet or measured reverse-recovery waveforms before design use.",
        ],
    )


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


def _first_number(values: Any, keys: tuple[str, ...], default: float) -> float:
    if isinstance(values, dict):
        for key in keys:
            if key in values:
                return _safe_float(values[key], default)
        return default
    return _safe_float(values, default)


def _safe_float(value: Any, default: float) -> float:
    if isinstance(value, dict):
        for key in ("typ", "typical", "max", "25", "value"):
            if key in value:
                parsed = _safe_float(value[key], math.nan)
                if math.isfinite(parsed):
                    return parsed
        return default
    if isinstance(value, list):
        for item in value:
            parsed = _safe_float(item, math.nan)
            if math.isfinite(parsed):
                return parsed
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


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
