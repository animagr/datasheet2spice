"""Small unit parsing helpers used by extractors and tests."""

from __future__ import annotations

import re


SCALE = {
    "": 1.0,
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "µ": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "K": 1e3,
    "meg": 1e6,
    "Meg": 1e6,
    "M": 1e6,
    "g": 1e9,
    "G": 1e9,
}


def parse_number(value: str | int | float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = value.strip().replace("Ω", "").replace("ohm", "").replace("Ohm", "")
    text = text.replace("μ", "µ")
    match = re.match(r"^\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*([a-zA-Zµ]*)", text)
    if not match:
        raise ValueError(f"cannot parse numeric value: {value!r}")
    number = float(match.group(1))
    suffix = match.group(2)
    return number * SCALE.get(suffix, SCALE.get(suffix[:1], 1.0))


def spice_float(value: float, unit_suffix: str = "") -> str:
    return f"{value:g}{unit_suffix}"
