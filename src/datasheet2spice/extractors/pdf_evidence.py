"""PDF screenshot evidence rendering for human review."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


def render_pdf_evidence_images(
    pdf: str | Path,
    out_dir: str | Path,
    url_prefix: str,
    findings: Iterable[dict[str, Any]] = (),
    tables: Iterable[dict[str, Any]] = (),
    curve_digitization: dict[str, Any] | None = None,
    max_tables: int = 4,
    max_pages: int = 4,
) -> list[dict[str, Any]]:
    """Render compact datasheet screenshots that explain extracted values.

    Coordinates in the returned evidence list use PDF page coordinates. The
    rendered image URLs are served by the local workbench only; they are not
    embedded into the device JSON model.
    """

    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("PDF evidence rendering requires PyMuPDF.") from exc

    pdf_path = Path(pdf)
    asset_dir = Path(out_dir)
    asset_dir.mkdir(parents=True, exist_ok=True)
    prefix = url_prefix.rstrip("/")
    evidence: list[dict[str, Any]] = []
    rendered_pages: set[int] = set()

    with fitz.open(str(pdf_path)) as doc:
        if curve_digitization and curve_digitization.get("plot_rect"):
            page_no = int(curve_digitization["page"])
            item = _render_clip(
                doc,
                asset_dir,
                prefix,
                page_no,
                tuple(float(v) for v in curve_digitization["plot_rect"]),
                f"curve_capacitance_p{page_no}.png",
                zoom=2.8,
                pad=8.0,
            )
            if item:
                item.update(
                    {
                        "kind": "curve_plot",
                        "label": "Ciss/Coss/Crss capacitance plot",
                        "confidence": curve_digitization.get("confidence"),
                    }
                )
                evidence.append(item)

        for idx, table in enumerate(list(tables)[:max_tables], start=1):
            if not table.get("bbox") or not table.get("page"):
                continue
            page_no = int(table["page"])
            item = _render_clip(
                doc,
                asset_dir,
                prefix,
                page_no,
                tuple(float(v) for v in table["bbox"]),
                f"table_{idx}_p{page_no}.png",
                zoom=2.4,
                pad=6.0,
            )
            if item:
                item.update(
                    {
                        "kind": "table_candidate",
                        "label": f"Table candidate {idx}",
                        "score": table.get("score"),
                    }
                )
                evidence.append(item)

        for page_no in _finding_pages(findings, max_pages=max_pages):
            if page_no in rendered_pages:
                continue
            rendered_pages.add(page_no)
            item = _render_page(doc, asset_dir, prefix, page_no, f"page_{page_no}_context.png", zoom=0.72)
            if item:
                item.update({"kind": "page_context", "label": f"Source page {page_no}"})
                evidence.append(item)

    return evidence


def _finding_pages(findings: Iterable[dict[str, Any]], max_pages: int) -> list[int]:
    pages: list[int] = []
    for finding in findings:
        page = finding.get("page")
        if page is None:
            continue
        page_no = int(page)
        if page_no not in pages:
            pages.append(page_no)
        if len(pages) >= max_pages:
            break
    return pages


def _render_clip(
    doc: Any,
    out_dir: Path,
    url_prefix: str,
    page_no: int,
    bbox: tuple[float, float, float, float],
    filename: str,
    zoom: float,
    pad: float,
) -> dict[str, Any] | None:
    if page_no < 1 or page_no > len(doc):
        return None
    page = doc[page_no - 1]
    rect = _padded_rect(page, bbox, pad)
    path = out_dir / filename
    pix = page.get_pixmap(matrix=_matrix(doc, zoom), clip=rect, alpha=False)
    pix.save(str(path))
    return {
        "page": page_no,
        "bbox": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
        "filename": filename,
        "url": f"{url_prefix}/{filename}",
        "width": pix.width,
        "height": pix.height,
    }


def _render_page(doc: Any, out_dir: Path, url_prefix: str, page_no: int, filename: str, zoom: float) -> dict[str, Any] | None:
    if page_no < 1 or page_no > len(doc):
        return None
    page = doc[page_no - 1]
    path = out_dir / filename
    pix = page.get_pixmap(matrix=_matrix(doc, zoom), alpha=False)
    pix.save(str(path))
    rect = page.rect
    return {
        "page": page_no,
        "bbox": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
        "filename": filename,
        "url": f"{url_prefix}/{filename}",
        "width": pix.width,
        "height": pix.height,
    }


def _matrix(doc: Any, zoom: float) -> Any:
    import fitz  # type: ignore

    return fitz.Matrix(zoom, zoom)


def _padded_rect(page: Any, bbox: tuple[float, float, float, float], pad: float) -> Any:
    import fitz  # type: ignore

    page_rect = page.rect
    rect = fitz.Rect(bbox)
    rect.x0 = max(page_rect.x0, rect.x0 - pad)
    rect.y0 = max(page_rect.y0, rect.y0 - pad)
    rect.x1 = min(page_rect.x1, rect.x1 + pad)
    rect.y1 = min(page_rect.y1, rect.y1 + pad)
    return rect
