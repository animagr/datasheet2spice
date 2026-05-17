#!/usr/bin/env python3
"""Extract S4661 Fig.19 capacitance curves from PDF vector paths.

This is intentionally device-specific: the page number, plot rectangle, and
drawing indices are tied to TK-S4661_Rev.T17.2.pdf. It documents how the CSV in
the workspace was produced and gives a template for future datasheets that keep
curves as vector paths.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import fitz


PDF = Path("TK-S4661_Rev.T17.2.pdf")
OUT = Path("S4661_fig19_capacitance_vector_points.csv")
PAGE_INDEX = 10

# Plot rectangle in PDF points: Fig.19 axes.
X0, Y_TOP, X1, Y_BOT = 113.4, 143.53, 278.23, 318.57
VMIN, VMAX = 0.1, 1000.0
CMIN, CMAX = 1.0, 100000.0

# PyMuPDF drawing indices for Ciss, Coss, Crss on page 11.
CURVES = {"ciss_pf": 16, "coss_pf": 17, "crss_pf": 18}
VDS_POINTS = [
    0.1,
    0.15,
    0.2,
    0.3,
    0.5,
    0.7,
    1,
    1.5,
    2,
    3,
    5,
    7,
    10,
    15,
    20,
    30,
    50,
    70,
    100,
    150,
    200,
    300,
    500,
    700,
    800,
    1000,
]


def x_from_v(vds: float) -> float:
    log_x = (math.log10(vds) - math.log10(VMIN)) / (math.log10(VMAX) - math.log10(VMIN))
    return X0 + log_x * (X1 - X0)


def cap_from_y(y: float) -> float:
    log_c = math.log10(CMIN) + (Y_BOT - y) / (Y_BOT - Y_TOP) * (
        math.log10(CMAX) - math.log10(CMIN)
    )
    return 10**log_c


def bezier(p0, p1, p2, p3, t: float) -> tuple[float, float]:
    u = 1 - t
    x = u**3 * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t**3 * p3.x
    y = u**3 * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t**3 * p3.y
    return x, y


def sample_drawing(draw, samples_per_segment: int = 80) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for item in draw["items"]:
        if item[0] == "c":
            _, p0, p1, p2, p3 = item
            for k in range(samples_per_segment):
                x, y = bezier(p0, p1, p2, p3, k / samples_per_segment)
                if X0 <= x <= X1 and Y_TOP <= y <= Y_BOT:
                    points.append((x, y))
        elif item[0] == "l":
            _, p0, p1 = item
            for k in range(samples_per_segment):
                t = k / samples_per_segment
                x = p0.x + (p1.x - p0.x) * t
                y = p0.y + (p1.y - p0.y) * t
                if X0 <= x <= X1 and Y_TOP <= y <= Y_BOT:
                    points.append((x, y))
    points.sort()
    return points


def y_at_x(points: list[tuple[float, float]], x: float) -> float:
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            if abs(x1 - x0) < 1e-12:
                return (y0 + y1) / 2
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return min(points, key=lambda p: abs(p[0] - x))[1]


def main() -> None:
    page = fitz.open(PDF)[PAGE_INDEX]
    drawings = page.get_drawings()
    extracted: dict[str, list[float]] = {"vds_v": VDS_POINTS}

    for name, drawing_index in CURVES.items():
        points = sample_drawing(drawings[drawing_index])
        extracted[name] = [
            round(cap_from_y(y_at_x(points, x_from_v(vds))), 2) for vds in VDS_POINTS
        ]

    with OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["vds_v", "ciss_pf", "coss_pf", "crss_pf"])
        for row in zip(
            extracted["vds_v"],
            extracted["ciss_pf"],
            extracted["coss_pf"],
            extracted["crss_pf"],
        ):
            writer.writerow(row)

    print(json.dumps(extracted, indent=2))
    print(OUT)


if __name__ == "__main__":
    main()
