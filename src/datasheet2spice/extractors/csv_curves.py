"""CSV curve import helpers.

This supports CSV files exported by WebPlotDigitizer, StarryDigitizer, or
hand-cleaned spreadsheets. No digitizer code is bundled.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from ..plugins import extractor


@dataclass(slots=True)
class WpdCapacitanceImport:
    data: dict[str, list[float]]
    warnings: list[str]


def read_capacitance_csv(path: str | Path) -> dict[str, list[float]]:
    rows = list(csv.DictReader(Path(path).read_text(encoding="utf-8-sig").splitlines()))
    required = ["vds_v", "ciss_pf", "coss_pf", "crss_pf"]
    if not rows:
        raise ValueError("empty CSV")
    missing = [name for name in required if name not in rows[0]]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")
    return {name: [float(row[name]) for row in rows] for name in required}


def read_wpd_capacitance_csv(path: str | Path) -> dict[str, list[float]]:
    """Read native WebPlotDigitizer side-by-side Ciss/Coss/Crss CSV output."""

    return read_wpd_capacitance_csv_with_warnings(path).data


def read_wpd_capacitance_csv_with_warnings(path: str | Path) -> WpdCapacitanceImport:
    rows = list(csv.reader(Path(path).read_text(encoding="utf-8-sig").splitlines()))
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if len(rows) < 3:
        raise ValueError("WebPlotDigitizer CSV requires dataset header, X/Y header, and at least one data row")

    dataset_row = [cell.strip().lower() for cell in rows[0]]
    axis_row = [cell.strip().lower() for cell in rows[1]]
    datasets = _wpd_dataset_columns(dataset_row, axis_row)
    missing = [name for name in ("ciss", "coss", "crss") if name not in datasets]
    if missing:
        raise ValueError(f"missing WebPlotDigitizer datasets: {', '.join(missing)}")

    curves: dict[str, tuple[list[float], list[float]]] = {}
    for name in ("ciss", "coss", "crss"):
        x_col, y_col = datasets[name]
        xs: list[float] = []
        ys: list[float] = []
        for row_number, row in enumerate(rows[2:], start=3):
            try:
                x_value = _cell_float(row, x_col)
                y_value = _cell_float(row, y_col)
            except ValueError as exc:
                raise ValueError(f"invalid {name} value on row {row_number}: {exc}") from exc
            xs.append(x_value)
            ys.append(y_value)
        curves[name] = (xs, ys)

    vds = curves["ciss"][0]
    data = {
        "vds_v": vds,
        "ciss_pf": curves["ciss"][1],
        "coss_pf": curves["coss"][1],
        "crss_pf": curves["crss"][1],
    }
    _validate_imported_capacitance(data)
    warnings = _wpd_x_axis_warnings(vds, curves)
    return WpdCapacitanceImport(data=data, warnings=warnings)


def _wpd_dataset_columns(dataset_row: list[str], axis_row: list[str]) -> dict[str, tuple[int, int]]:
    columns: dict[str, dict[str, int]] = {}
    current = ""
    for index, axis in enumerate(axis_row):
        if index < len(dataset_row) and dataset_row[index]:
            current = dataset_row[index]
        if current in {"ciss", "coss", "crss"} and axis in {"x", "y"}:
            columns.setdefault(current, {})[axis] = index
    return {name: (axes["x"], axes["y"]) for name, axes in columns.items() if "x" in axes and "y" in axes}


def _cell_float(row: list[str], index: int) -> float:
    if index >= len(row) or not row[index].strip():
        raise ValueError("missing numeric cell")
    return float(row[index])


def _validate_imported_capacitance(data: dict[str, list[float]]) -> None:
    lengths = {len(values) for values in data.values()}
    if lengths != {next(iter(lengths), 0)}:
        raise ValueError("imported capacitance arrays must have matching lengths")
    if not data["vds_v"]:
        raise ValueError("empty WebPlotDigitizer capacitance data")
    if any(b <= a for a, b in zip(data["vds_v"], data["vds_v"][1:])):
        raise ValueError("ciss X values must be strictly increasing")
    for name in ("ciss_pf", "coss_pf", "crss_pf"):
        if any(value <= 0 for value in data[name]):
            raise ValueError(f"{name} values must be positive")
    for index, (ciss, coss, crss) in enumerate(zip(data["ciss_pf"], data["coss_pf"], data["crss_pf"])):
        if ciss < crss:
            raise ValueError(f"ciss_pf must be >= crss_pf at index {index}")
        if coss < crss:
            raise ValueError(f"coss_pf must be >= crss_pf at index {index}")


def _wpd_x_axis_warnings(master_vds: list[float], curves: dict[str, tuple[list[float], list[float]]]) -> list[str]:
    warnings: list[str] = []
    for name in ("coss", "crss"):
        other_vds = curves[name][0]
        for index, (master, other) in enumerate(zip(master_vds, other_vds)):
            denominator = max(abs(master), 1e-12)
            rel_diff = abs(other - master) / denominator
            if rel_diff > 0.05:
                warnings.append(f"{name} X differs from ciss X by more than 5% at index {index}; ciss X was used.")
                break
    return warnings


@extractor("capacitance-csv")
class CapacitanceCsvExtractor:
    name = "capacitance-csv"

    def extract(self, path: str | Path) -> dict[str, list[float]]:
        return read_capacitance_csv(path)


@extractor("wpd-capacitance-csv")
class WpdCapacitanceCsvExtractor:
    name = "wpd-capacitance-csv"

    def extract(self, path: str | Path) -> dict[str, list[float]]:
        return read_wpd_capacitance_csv(path)
