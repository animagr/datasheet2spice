"""Lightweight PDF table structure recognition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any


@dataclass(slots=True)
class TableCandidate:
    page: int
    bbox: tuple[float, float, float, float]
    rows: list[list[str]]
    score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "bbox": [round(v, 2) for v in self.bbox],
            "rows": self.rows,
            "score": round(self.score, 3),
        }


def extract_pdf_tables(pdf: str | Path, max_tables: int = 12) -> list[dict[str, Any]]:
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Table extraction requires PyMuPDF.") from exc

    tables: list[TableCandidate] = []
    with fitz.open(str(pdf)) as doc:
        for page_index, page in enumerate(doc, start=1):
            words = page.get_text("words")
            rows = _group_words_into_rows(words)
            for segment in _split_row_segments(rows):
                table = _segment_to_table(page_index, segment)
                if table and len(table.rows) >= 3 and table.score > 0.25:
                    tables.append(table)
    tables.sort(key=lambda item: item.score, reverse=True)
    return [item.as_dict() for item in tables[:max_tables]]


def _group_words_into_rows(words: list[tuple]) -> list[list[tuple]]:
    rows: list[list[tuple]] = []
    for word in sorted(words, key=lambda item: ((item[1] + item[3]) / 2, item[0])):
        y = (word[1] + word[3]) / 2
        placed = False
        for row in rows:
            row_y = median((item[1] + item[3]) / 2 for item in row)
            if abs(row_y - y) <= 4.0:
                row.append(word)
                placed = True
                break
        if not placed:
            rows.append([word])
    return [sorted(row, key=lambda item: item[0]) for row in rows if len(row) >= 2]


def _split_row_segments(rows: list[list[tuple]]) -> list[list[list[tuple]]]:
    if not rows:
        return []
    segments: list[list[list[tuple]]] = []
    current: list[list[tuple]] = []
    last_y: float | None = None
    for row in rows:
        y = median((item[1] + item[3]) / 2 for item in row)
        if last_y is not None and y - last_y > 18 and len(current) >= 3:
            segments.append(current)
            current = []
        current.append(row)
        last_y = y
    if len(current) >= 3:
        segments.append(current)
    return segments


def _segment_to_table(page: int, segment: list[list[tuple]]) -> TableCandidate | None:
    x_values = [item[0] for row in segment for item in row]
    if len(x_values) < 8:
        return None
    columns = _cluster_x_values(x_values)
    if len(columns) < 3:
        return None

    rows: list[list[str]] = []
    x0 = min(item[0] for row in segment for item in row)
    y0 = min(item[1] for row in segment for item in row)
    x1 = max(item[2] for row in segment for item in row)
    y1 = max(item[3] for row in segment for item in row)
    for row in segment:
        cells = ["" for _ in columns]
        for word in row:
            col = min(range(len(columns)), key=lambda idx: abs(columns[idx] - word[0]))
            cells[col] = (cells[col] + " " + word[4]).strip()
        rows.append(_trim_cells(cells))
    rows = [row for row in rows if sum(bool(cell) for cell in row) >= 2]
    if len(rows) < 3:
        return None
    density = sum(sum(bool(cell) for cell in row) for row in rows) / (len(rows) * max(len(row) for row in rows))
    keyword_score = _keyword_score(rows)
    score = min(1.0, 0.15 + density * 0.55 + keyword_score * 0.3)
    return TableCandidate(page=page, bbox=(x0, y0, x1, y1), rows=rows, score=score)


def _cluster_x_values(values: list[float], tolerance: float = 22.0) -> list[float]:
    clusters: list[list[float]] = []
    for value in sorted(values):
        if not clusters or abs(median(clusters[-1]) - value) > tolerance:
            clusters.append([value])
        else:
            clusters[-1].append(value)
    return [median(cluster) for cluster in clusters]


def _trim_cells(cells: list[str]) -> list[str]:
    while cells and not cells[0]:
        cells.pop(0)
    while cells and not cells[-1]:
        cells.pop()
    return cells


def _keyword_score(rows: list[list[str]]) -> float:
    text = " ".join(cell for row in rows for cell in row).lower()
    hits = 0
    for keyword in ["parameter", "symbol", "conditions", "values", "typ", "max", "unit", "vds", "vgs", "ciss", "rds"]:
        if keyword in text:
            hits += 1
    return min(1.0, hits / 8)
