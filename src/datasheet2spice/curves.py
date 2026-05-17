"""Curve helpers."""

from __future__ import annotations

from typing import Iterable


def ensure_same_length(*vectors: Iterable[float]) -> None:
    lengths = {len(list(v)) for v in vectors}
    if len(lengths) > 1:
        raise ValueError(f"curve vectors have different lengths: {sorted(lengths)}")


def table_pairs(xs: list[float], ys: list[float], suffix: str = "") -> str:
    if len(xs) != len(ys):
        raise ValueError("table x/y lengths do not match")
    return ", ".join(f"{x:g},{y:g}{suffix}" for x, y in zip(xs, ys))


def split_capacitances(caps: dict) -> dict[str, list[float]]:
    vds = caps.get("vds_v", [])
    ciss = caps.get("ciss_pf", [])
    coss = caps.get("coss_pf", [])
    crss = caps.get("crss_pf", [])
    if not (vds and ciss and coss and crss):
        raise ValueError("capacitance curve requires vds_v, ciss_pf, coss_pf, crss_pf")
    if len({len(vds), len(ciss), len(coss), len(crss)}) != 1:
        raise ValueError("capacitance curve arrays must have the same length")
    return {
        "vds_v": [float(x) for x in vds],
        "cgs_pf": [max(float(a) - float(b), 1e-6) for a, b in zip(ciss, crss)],
        "cgd_pf": [max(float(x), 1e-6) for x in crss],
        "cds_pf": [max(float(a) - float(b), 1e-6) for a, b in zip(coss, crss)],
    }
