"""Automatic vector-curve digitization helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from statistics import median
from typing import Any


DEFAULT_VDS_POINTS = [
    0.1,
    0.2,
    0.5,
    1.0,
    2.0,
    5.0,
    10.0,
    20.0,
    50.0,
    100.0,
    200.0,
    500.0,
    800.0,
    1000.0,
]


@dataclass(slots=True)
class CurveSet:
    kind: str
    page: int
    plot_rect: tuple[float, float, float, float]
    data: dict[str, list[float]]
    confidence: float
    notes: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "page": self.page,
            "plot_rect": [round(v, 2) for v in self.plot_rect],
            "data": self.data,
            "confidence": round(self.confidence, 3),
            "notes": self.notes,
        }


def digitize_capacitance_curves_from_pdf(pdf: str | Path, x_values: list[float] | None = None) -> dict[str, Any] | None:
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Curve digitization requires PyMuPDF.") from exc

    x_values = x_values or DEFAULT_VDS_POINTS
    with fitz.open(str(pdf)) as doc:
        for page_index, page in enumerate(doc):
            text = page.get_text("text")
            if not _looks_like_capacitance_page(text):
                continue
            labels = _label_centers(page)
            rect = _detect_plot_rect(page, labels)
            if rect is None:
                continue
            curve_drawings = _candidate_curve_drawings(page, rect)
            if len(curve_drawings) < 3:
                continue
            curve_drawings = sorted(curve_drawings[:3], key=lambda item: _median_y(item[1]))
            names = ["ciss_pf", "coss_pf", "crss_pf"]
            data: dict[str, list[float]] = {"vds_v": x_values}
            for name, (_, points) in zip(names, curve_drawings):
                data[name] = [round(_y_to_value(_y_at_x(points, _x_from_value(x, rect)), rect), 3) for x in x_values]
            result = CurveSet(
                kind="capacitance",
                page=page_index + 1,
                plot_rect=rect,
                data=data,
                confidence=0.78 if len(curve_drawings) >= 3 else 0.55,
                notes=[
                    "Detected vector Ciss/Coss/Crss curves on a log-log capacitance plot.",
                    "Axis ranges assumed as VDS 0.1-1000 V and capacitance 1-100000 pF.",
                ],
            )
            return result.as_dict()
    return None


def _looks_like_capacitance_page(text: str) -> bool:
    lower = text.lower()
    return all(token in lower for token in ["ciss", "coss", "crss"]) and "capacitance" in lower


def _label_centers(page: Any) -> dict[str, tuple[float, float]]:
    labels: dict[str, tuple[float, float]] = {}
    for word in page.get_text("words"):
        label = str(word[4]).lower()
        if label in {"ciss", "coss", "crss"}:
            labels[label] = ((word[0] + word[2]) / 2, (word[1] + word[3]) / 2)
    return labels


def _detect_plot_rect(page: Any, labels: dict[str, tuple[float, float]]) -> tuple[float, float, float, float] | None:
    if len(labels) < 3:
        return None
    drawings = page.get_drawings()
    label_points = list(labels.values())
    candidates: list[tuple[float, tuple[float, float, float, float]]] = []
    for drawing in drawings:
        rect = drawing.get("rect")
        if rect is None:
            continue
        x0, y0, x1, y1 = float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)
        width = x1 - x0
        height = y1 - y0
        if not (100 <= width <= 260 and 100 <= height <= 240):
            continue
        inside = sum(1 for x, y in label_points if x0 <= x <= x1 and y0 <= y <= y1)
        if inside < 3:
            continue
        score = inside + (width * height) / 100000.0
        candidates.append((score, (x0, y0, x1, y1)))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _candidate_curve_drawings(page: Any, rect: tuple[float, float, float, float]) -> list[tuple[Any, list[tuple[float, float]]]]:
    candidates: list[tuple[Any, list[tuple[float, float]]]] = []
    for drawing in page.get_drawings():
        width = float(drawing.get("width") or 0.0)
        color = drawing.get("color")
        if width < 0.8 or color not in {(0.0, 0.0, 0.0), None}:
            continue
        points = _sample_drawing(drawing, rect)
        if len(points) >= 40 and _x_span(points) > (rect[2] - rect[0]) * 0.6:
            candidates.append((drawing, points))
    candidates.sort(key=lambda item: (-_x_span(item[1]), _median_y(item[1])))
    return candidates


def _sample_drawing(draw: dict[str, Any], rect: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    x0, y_top, x1, y_bot = rect
    points: list[tuple[float, float]] = []
    for item in draw.get("items", []):
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
    return sorted(points)


def _x_span(points: list[tuple[float, float]]) -> float:
    if not points:
        return 0.0
    return max(x for x, _ in points) - min(x for x, _ in points)


def _median_y(points: list[tuple[float, float]]) -> float:
    return median(y for _, y in points) if points else float("inf")


def _x_from_value(value: float, rect: tuple[float, float, float, float]) -> float:
    x0, _, x1, _ = rect
    return x0 + (math.log10(value) - math.log10(0.1)) / (math.log10(1000.0) - math.log10(0.1)) * (x1 - x0)


def _y_to_value(y: float, rect: tuple[float, float, float, float]) -> float:
    _, y_top, _, y_bot = rect
    log_y = math.log10(1.0) + (y_bot - y) / (y_bot - y_top) * (math.log10(100000.0) - math.log10(1.0))
    return 10**log_y


def _y_at_x(points: list[tuple[float, float]], x: float) -> float:
    if not points:
        raise ValueError("cannot interpolate empty curve")
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            if abs(x1 - x0) < 1e-12:
                return (y0 + y1) / 2
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return min(points, key=lambda item: abs(item[0] - x))[1]
