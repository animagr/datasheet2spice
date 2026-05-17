"""Validation helpers."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Any

from .schema import DeviceProject, SchemaError


def validate_project(project: DeviceProject) -> list[str]:
    errors: list[str] = []
    try:
        project.validate()
    except SchemaError as exc:
        errors.append(str(exc))
    caps = project.get_path("dynamic", "capacitance", default=None)
    if not caps:
        errors.append("dynamic.capacitance is required for built-in VDMOS and ABM emitters")
    elif not isinstance(caps, dict):
        errors.append("dynamic.capacitance must be an object")
    else:
        _validate_capacitance(caps, errors)
    _validate_positive_map(project.get_path("static", "rds_on_mohm", default={}), "static.rds_on_mohm", errors)
    _validate_positive_map(project.get_path("static", "vgs_th_v", default={}), "static.vgs_th_v", errors)
    vdss = project.get_path("ratings", "vdss_v", default=None)
    if vdss is not None and _as_float(vdss) <= 0:
        errors.append("ratings.vdss_v must be positive")
    return errors


def _validate_capacitance(caps: dict[str, Any], errors: list[str]) -> None:
    required = ["vds_v", "ciss_pf", "coss_pf", "crss_pf"]
    missing = [name for name in required if name not in caps]
    if missing:
        errors.append("dynamic.capacitance missing arrays: " + ", ".join(missing))
        return
    values: dict[str, list[float]] = {}
    for name in required:
        if not isinstance(caps[name], list):
            errors.append(f"dynamic.capacitance.{name} must be an array")
            return
        try:
            values[name] = [_as_float(item) for item in caps[name]]
        except (TypeError, ValueError):
            errors.append(f"dynamic.capacitance.{name} contains non-numeric values")
            return
    lengths = {len(values[name]) for name in required}
    if len(lengths) != 1:
        errors.append("dynamic.capacitance arrays must have matching lengths")
        return
    if not values["vds_v"]:
        errors.append("dynamic.capacitance arrays must not be empty")
        return
    if any(v < 0 for v in values["vds_v"]):
        errors.append("dynamic.capacitance.vds_v must be non-negative")
    if any(b <= a for a, b in zip(values["vds_v"], values["vds_v"][1:])):
        errors.append("dynamic.capacitance.vds_v must be strictly increasing")
    for name in ["ciss_pf", "coss_pf", "crss_pf"]:
        if any(v <= 0 for v in values[name]):
            errors.append(f"dynamic.capacitance.{name} must be positive")
    for idx, (ciss, coss, crss) in enumerate(zip(values["ciss_pf"], values["coss_pf"], values["crss_pf"])):
        if ciss < crss:
            errors.append(f"dynamic.capacitance ciss_pf must be >= crss_pf at index {idx}")
        if coss < crss:
            errors.append(f"dynamic.capacitance coss_pf must be >= crss_pf at index {idx}")


def _validate_positive_map(value: Any, name: str, errors: list[str]) -> None:
    if value in ({}, None):
        return
    if not isinstance(value, dict):
        errors.append(f"{name} must be an object keyed by temperature")
        return
    for key, item in value.items():
        try:
            number = _as_float(item)
        except (TypeError, ValueError):
            errors.append(f"{name}.{key} must be numeric")
            continue
        if number <= 0:
            errors.append(f"{name}.{key} must be positive")


def _as_float(value: Any) -> float:
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        raise ValueError("not finite")
    return number


def run_ltspice(ltspice_exe: str | Path, deck: str | Path, timeout_s: int = 120) -> dict[str, Any]:
    exe = str(ltspice_exe)
    deck_path = Path(deck)
    proc = subprocess.run([exe, "-b", str(deck_path)], capture_output=True, text=True, timeout=timeout_s, check=False)
    log_path = deck_path.with_suffix(".log")
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "log_path": str(log_path),
        "raw_path": str(deck_path.with_suffix(".raw")),
        "log": log,
        "fatal": bool(re.search(r"\b(error|fatal)\b", log, flags=re.IGNORECASE)),
        "warnings": len(re.findall(r"\bwarning\b", log, flags=re.IGNORECASE)),
    }
