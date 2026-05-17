"""Optional PyMuPDF-based vector curve extraction.

This module imports PyMuPDF only inside functions. PyMuPDF/MuPDF is AGPL-3.0
or commercially licensed, so projects with different licensing needs can avoid
installing this optional plugin.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any


def extract_loglog_curve_points(
    pdf: str | Path,
    page_index: int,
    drawing_index: int,
    plot_rect: tuple[float, float, float, float],
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    x_values: list[float],
) -> list[float]:
    import fitz  # type: ignore

    with fitz.open(str(pdf)) as doc:
        page = doc[page_index]
        drawings = page.get_drawings()
        drawing = drawings[drawing_index]
    points = _sample_drawing(drawing, plot_rect)
    if not points:
        raise ValueError("selected drawing did not contain curve points inside plot_rect")
    return [_y_value(_y_at_x(points, _x_from_value(x, plot_rect, x_range)), plot_rect, y_range) for x in x_values]


def _x_from_value(value: float, rect: tuple[float, float, float, float], x_range: tuple[float, float]) -> float:
    x0, _, x1, _ = rect
    vmin, vmax = x_range
    return x0 + (math.log10(value) - math.log10(vmin)) / (math.log10(vmax) - math.log10(vmin)) * (x1 - x0)


def _y_value(y: float, rect: tuple[float, float, float, float], y_range: tuple[float, float]) -> float:
    _, y_top, _, y_bot = rect
    ymin, ymax = y_range
    log_y = math.log10(ymin) + (y_bot - y) / (y_bot - y_top) * (math.log10(ymax) - math.log10(ymin))
    return 10**log_y


def _sample_drawing(draw: dict[str, Any], rect: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    x0, y_top, x1, y_bot = rect
    points: list[tuple[float, float]] = []
    for item in draw["items"]:
        if item[0] == "c":
            _, p0, p1, p2, p3 = item
            for k in range(80):
                t = k / 80
                u = 1 - t
                x = u**3 * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t**3 * p3.x
                y = u**3 * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t**3 * p3.y
                if x0 <= x <= x1 and y_top <= y <= y_bot:
                    points.append((x, y))
        elif item[0] == "l":
            _, p0, p1 = item
            for k in range(80):
                t = k / 80
                x = p0.x + (p1.x - p0.x) * t
                y = p0.y + (p1.y - p0.y) * t
                if x0 <= x <= x1 and y_top <= y <= y_bot:
                    points.append((x, y))
    points.sort()
    return points


def _y_at_x(points: list[tuple[float, float]], x: float) -> float:
    if not points:
        raise ValueError("cannot interpolate an empty point set")
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            if abs(x1 - x0) < 1e-12:
                return (y0 + y1) / 2
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return min(points, key=lambda p: abs(p[0] - x))[1]
