"""Supported SPICE netlist dialect names."""

from __future__ import annotations


SUPPORTED_DIALECTS = ("common", "ltspice", "ngspice", "pspice", "hspice", "xyce", "qspice")
ALL_DIALECTS = SUPPORTED_DIALECTS

DIALECT_LABELS = {
    "common": "portable common SPICE",
    "ltspice": "LTspice",
    "ngspice": "ngspice",
    "pspice": "PSpice",
    "hspice": "HSPICE",
    "xyce": "Xyce",
    "qspice": "QSPICE experimental",
}


def dialect_suffix(dialect: str) -> str:
    return "" if dialect == "common" else f"_{dialect}"

