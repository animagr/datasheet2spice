"""CSV curve import helpers.

This supports CSV files exported by WebPlotDigitizer, StarryDigitizer, or
hand-cleaned spreadsheets. No digitizer code is bundled.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..plugins import extractor


def read_capacitance_csv(path: str | Path) -> dict[str, list[float]]:
    rows = list(csv.DictReader(Path(path).read_text(encoding="utf-8-sig").splitlines()))
    required = ["vds_v", "ciss_pf", "coss_pf", "crss_pf"]
    if not rows:
        raise ValueError("empty CSV")
    missing = [name for name in required if name not in rows[0]]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")
    return {name: [float(row[name]) for row in rows] for name in required}


@extractor("capacitance-csv")
class CapacitanceCsvExtractor:
    name = "capacitance-csv"

    def extract(self, path: str | Path) -> dict[str, list[float]]:
        return read_capacitance_csv(path)
