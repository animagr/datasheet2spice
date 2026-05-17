"""Raster plot digitization for scanned datasheet figures.

The implementation is deliberately calibration-first. It does not guess axis
ranges from OCR yet; callers provide the plot rectangle and axis ranges, then
this module extracts a smooth single curve from dark pixels inside that region.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import math
from pathlib import Path
from statistics import median
from typing import Any, Sequence

from .curve_digitizer import DEFAULT_VDS_POINTS


@dataclass(slots=True)
class RasterDigitizationResult:
    curve_name: str
    x_unit: str
    y_unit: str
    points: list[dict[str, float]]
    confidence: float
    metrics: dict[str, float | int]
    image_size: tuple[int, int]
    plot_rect_px: tuple[int, int, int, int]
    notes: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": "raster_curve_digitization",
            "curve_name": self.curve_name,
            "x_unit": self.x_unit,
            "y_unit": self.y_unit,
            "points": self.points,
            "confidence": round(self.confidence, 3),
            "metrics": self.metrics,
            "image_size": list(self.image_size),
            "plot_rect_px": list(self.plot_rect_px),
            "data": {
                "x": [point["x"] for point in self.points],
                self.curve_name: [point["y"] for point in self.points],
            },
            "notes": self.notes,
        }


def digitize_raster_curve_from_pdf(
    pdf: str | Path,
    page: int,
    plot_rect: Sequence[float],
    *,
    curve_name: str = "curve",
    x_range: tuple[float, float] = (0.1, 1000.0),
    y_range: tuple[float, float] = (1.0, 100000.0),
    x_values: Sequence[float] | None = None,
    x_log: bool = True,
    y_log: bool = True,
    threshold: int = 110,
    initial_y_fraction: float | None = None,
    zoom: float = 3.0,
) -> dict[str, Any]:
    """Render a PDF plot rectangle and digitize one scanned curve from it."""

    try:
        import fitz  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Raster digitization requires PyMuPDF and Pillow.") from exc

    rect = fitz.Rect(tuple(float(v) for v in plot_rect))
    with fitz.open(str(pdf)) as doc:
        if page < 1 or page > len(doc):
            raise ValueError(f"page {page} is outside PDF page range")
        pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
        image = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
    result = digitize_raster_curve_from_image(
        image,
        plot_rect_px=(0, 0, image.width - 1, image.height - 1),
        curve_name=curve_name,
        x_range=x_range,
        y_range=y_range,
        x_values=x_values,
        x_log=x_log,
        y_log=y_log,
        threshold=threshold,
        initial_y_fraction=initial_y_fraction,
    )
    result["pdf_page"] = page
    result["pdf_plot_rect"] = [round(float(v), 2) for v in plot_rect]
    return result


def digitize_raster_curve_from_image(
    image: str | Path | Any,
    *,
    plot_rect_px: Sequence[int | float] | None = None,
    curve_name: str = "curve",
    x_unit: str = "V",
    y_unit: str = "",
    x_range: tuple[float, float] = (0.1, 1000.0),
    y_range: tuple[float, float] = (1.0, 100000.0),
    x_values: Sequence[float] | None = None,
    x_log: bool = True,
    y_log: bool = True,
    threshold: int = 110,
    initial_y_fraction: float | None = None,
    search_window_px: int = 3,
) -> dict[str, Any]:
    """Digitize one dark curve from a calibrated raster plot image.

    `plot_rect_px` is `(left, top, right, bottom)` in image pixels. If omitted,
    the full image is treated as the calibrated plot region.
    """

    try:
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Raster digitization requires Pillow and NumPy.") from exc

    pil_image = Image.open(image).convert("RGB") if isinstance(image, (str, Path)) else image.convert("RGB")
    width, height = pil_image.size
    rect = _clamp_rect(plot_rect_px or (0, 0, width - 1, height - 1), width, height)
    left, top, right, bottom = rect
    plot = np.asarray(pil_image, dtype=np.float32)[top : bottom + 1, left : right + 1, :]
    if plot.size == 0:
        raise ValueError("plot rectangle is empty")

    gray = plot[:, :, 0] * 0.299 + plot[:, :, 1] * 0.587 + plot[:, :, 2] * 0.114
    mask = gray <= float(threshold)
    mask = _suppress_axes_and_grid(mask)
    plot_h, plot_w = mask.shape
    values = [float(v) for v in (x_values or DEFAULT_VDS_POINTS)]
    initial_y_px = None if initial_y_fraction is None else max(0.0, min(1.0, initial_y_fraction)) * (plot_h - 1)

    raw_points: list[tuple[float, float, int, float] | None] = []
    prev_y: float | None = None
    gaps = 0
    for x_value in values:
        px = _axis_value_to_pixel(x_value, x_range, plot_w, x_log)
        y_px = _trace_y_at_x(mask, px, search_window_px, prev_y, initial_y_px)
        if y_px is None:
            raw_points.append(None)
            gaps += 1
            continue
        prev_y = y_px
        y_value = _pixel_to_axis_value(y_px, y_range, plot_h, y_log)
        raw_points.append((x_value, y_value, int(round(px)), y_px))

    smoothed = _valid_points(raw_points)
    points = [
        {"x": round(x, 6), "y": round(y, 6), "x_px": float(x_px + left), "y_px": round(y_px + top, 3)}
        for x, y, x_px, y_px in smoothed
    ]
    coverage = len(points) / max(1, len(values))
    continuity = 1.0 - gaps / max(1, len(values) - 1)
    dark_fraction = float(mask.mean())
    density_score = min(1.0, dark_fraction / 0.025) if dark_fraction > 0 else 0.0
    confidence = max(0.0, min(0.95, coverage * 0.72 + continuity * 0.2 + density_score * 0.08))
    notes = [
        "Raster digitization used calibrated axes and dark-pixel curve tracing.",
        "Long horizontal/vertical rows were suppressed as likely axes or grid lines.",
    ]
    if coverage < 0.8:
        notes.append("Low coverage: use a tighter plot rectangle, adjust threshold, or isolate the target curve color.")

    return RasterDigitizationResult(
        curve_name=curve_name,
        x_unit=x_unit,
        y_unit=y_unit,
        points=points,
        confidence=confidence,
        metrics={
            "requested_points": len(values),
            "extracted_points": len(points),
            "coverage": round(coverage, 3),
            "gaps": gaps,
            "dark_pixel_fraction": round(dark_fraction, 5),
            "threshold": int(threshold),
        },
        image_size=(width, height),
        plot_rect_px=rect,
        notes=notes,
    ).as_dict()


def _clamp_rect(rect: Sequence[int | float], width: int, height: int) -> tuple[int, int, int, int]:
    if len(rect) != 4:
        raise ValueError("plot rectangle must have four values")
    left, top, right, bottom = [int(round(float(v))) for v in rect]
    left = max(0, min(width - 1, left))
    right = max(0, min(width - 1, right))
    top = max(0, min(height - 1, top))
    bottom = max(0, min(height - 1, bottom))
    if right <= left or bottom <= top:
        raise ValueError("plot rectangle must have positive width and height")
    return left, top, right, bottom


def _suppress_axes_and_grid(mask: Any) -> Any:
    import numpy as np  # type: ignore

    clean = mask.copy()
    if clean.shape[0] < 4 or clean.shape[1] < 4:
        return clean
    row_coverage = clean.mean(axis=1)
    col_coverage = clean.mean(axis=0)
    clean[row_coverage > 0.35, :] = False
    clean[:, col_coverage > 0.35] = False
    clean[:2, :] = False
    clean[-2:, :] = False
    clean[:, :2] = False
    clean[:, -2:] = False
    return np.asarray(clean, dtype=bool)


def _axis_value_to_pixel(value: float, axis_range: tuple[float, float], size: int, log_scale: bool) -> float:
    lo, hi = axis_range
    if log_scale:
        if value <= 0 or lo <= 0 or hi <= 0:
            raise ValueError("log-scale axis values must be positive")
        t = (math.log10(value) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
    else:
        t = (value - lo) / (hi - lo)
    return max(0.0, min(size - 1.0, t * (size - 1)))


def _pixel_to_axis_value(pixel: float, axis_range: tuple[float, float], size: int, log_scale: bool) -> float:
    lo, hi = axis_range
    t = 1.0 - max(0.0, min(size - 1.0, pixel)) / max(1, size - 1)
    if log_scale:
        if lo <= 0 or hi <= 0:
            raise ValueError("log-scale axis values must be positive")
        return 10 ** (math.log10(lo) + t * (math.log10(hi) - math.log10(lo)))
    return lo + t * (hi - lo)


def _trace_y_at_x(mask: Any, x_px: float, search_window: int, previous_y: float | None, initial_y: float | None) -> float | None:
    import numpy as np  # type: ignore

    x = int(round(x_px))
    left = max(0, x - search_window)
    right = min(mask.shape[1] - 1, x + search_window)
    column_window = mask[:, left : right + 1]
    rows = np.where(column_window.any(axis=1))[0]
    if rows.size == 0:
        return None
    runs = _row_runs([int(row) for row in rows])
    target = previous_y if previous_y is not None else initial_y
    if target is None:
        target = median((start + end) / 2 for start, end in runs)
    start, end = min(runs, key=lambda run: (abs(((run[0] + run[1]) / 2) - float(target)), -(run[1] - run[0])))
    return (start + end) / 2


def _row_runs(rows: list[int]) -> list[tuple[int, int]]:
    if not rows:
        return []
    runs: list[tuple[int, int]] = []
    start = rows[0]
    prev = rows[0]
    for row in rows[1:]:
        if row <= prev + 1:
            prev = row
            continue
        runs.append((start, prev))
        start = row
        prev = row
    runs.append((start, prev))
    return runs


def _valid_points(points: list[tuple[float, float, int, float] | None]) -> list[tuple[float, float, int, float]]:
    return [point for point in points if point is not None]
