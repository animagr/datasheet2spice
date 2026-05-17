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
        for idx, finding in enumerate(findings, start=1):
            item = _render_finding_clip(doc, asset_dir, prefix, finding, idx)
            if item:
                evidence.append(item)

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


FIELD_SEARCH_TERMS = {
    "ratings.vdss_v": ["VDSS", "Drain - Source voltage"],
    "ratings.id_cont_a": ["ID", "Drain current"],
    "ratings.vgs_on_v": ["VGS_on", "Recommended turn-on gate"],
    "ratings.vgs_off_v": ["VGS = +18V / -2V", "VGS"],
    "static.vgs_th_v": ["Gate threshold voltage", "VGS (th)", "VGS(th)"],
    "static.rds_on_mohm": ["RDS(on)", "on-state resistance"],
    "static.gfs_s": ["Transconductance", "gfs"],
    "static.rg_int_ohm": ["Gate input resistance", "RG"],
    "dynamic.capacitance.ciss_pf": ["Input capacitance", "Ciss"],
    "dynamic.capacitance.coss_pf": ["Output capacitance", "Coss"],
    "dynamic.capacitance.crss_pf": ["Reverse transfer capacitance", "Crss"],
    "dynamic.gate_charge.qg_nc": ["Total Gate charge", "Qg"],
    "dynamic.gate_charge.qgs_nc": ["Gate - Source charge", "Qgs"],
    "dynamic.gate_charge.qgd_nc": ["Gate - Drain charge", "Qgd"],
    "dynamic.body_diode.trr_ns": ["Reverse recovery time", "trr"],
    "dynamic.body_diode.qrr_nc": ["Reverse recovery charge", "Qrr"],
    "dynamic.body_diode.irrm_a": ["Peak reverse recovery current", "Irrm"],
    "dynamic.body_diode.vsd_25c_typ_v": ["Forward voltage", "VSD"],
}


def _render_finding_clip(
    doc: Any,
    out_dir: Path,
    url_prefix: str,
    finding: dict[str, Any],
    index: int,
) -> dict[str, Any] | None:
    located = _locate_finding_rect(doc, finding)
    if located is None:
        return None
    page_no, rect = located
    field = str(finding.get("field") or f"finding_{index}")
    filename = f"field_{index:02d}_{_slug(field)}_p{page_no}.png"
    item = _render_clip(doc, out_dir, url_prefix, page_no, rect, filename, zoom=2.6, pad=0.0)
    if not item:
        return None
    item.update(
        {
            "kind": "field_finding",
            "field": field,
            "label": field,
            "value": finding.get("value"),
            "unit": finding.get("unit"),
            "confidence": finding.get("confidence"),
        }
    )
    return item


def _locate_finding_rect(doc: Any, finding: dict[str, Any]) -> tuple[int, tuple[float, float, float, float]] | None:
    for page_no in _candidate_pages_for_finding(doc, finding):
        page = doc[page_no - 1]
        rect = _best_rect_on_page(page, finding)
        if rect is not None:
            return page_no, _row_crop_rect(page, rect)
    return None


def _candidate_pages_for_finding(doc: Any, finding: dict[str, Any]) -> list[int]:
    page = finding.get("page")
    if page:
        page_no = int(page)
        if 1 <= page_no <= len(doc):
            return [page_no] + [idx for idx in range(1, len(doc) + 1) if idx != page_no]
    snippet = str(finding.get("snippet") or "")
    tokens = _snippet_tokens(snippet)
    scores: list[tuple[int, int]] = []
    if tokens:
        for idx, pdf_page in enumerate(doc, start=1):
            text = _normalize_text(pdf_page.get_text("text"))
            score = sum(1 for token in tokens if token in text)
            if score:
                scores.append((score, idx))
    scores.sort(reverse=True)
    ranked = [idx for _, idx in scores[:4]]
    return ranked + [idx for idx in range(1, len(doc) + 1) if idx not in ranked]


def _best_rect_on_page(page: Any, finding: dict[str, Any]) -> Any | None:
    terms = _search_terms_for_finding(finding)
    page_text = _normalize_text(page.get_text("text"))
    best_rect = None
    best_score = -1
    for term in terms:
        if not term or _normalize_text(term) not in page_text:
            continue
        for rect in page.search_for(term):
            score = len(str(term)) * 2
            value_rect = _nearest_value_rect(page, rect, finding)
            if value_rect is not None:
                rect = rect | value_rect
                score += 80 - min(60, int(abs(value_rect.y0 - rect.y0)))
            if score > best_score:
                best_score = score
                best_rect = rect
    if best_rect is not None:
        return best_rect
    for value_term in _value_terms(finding):
        rects = page.search_for(value_term)
        if rects:
            return rects[0]
    return None


def _nearest_value_rect(page: Any, anchor: Any, finding: dict[str, Any]) -> Any | None:
    value_rects = []
    for term in _value_terms(finding):
        value_rects.extend(page.search_for(term))
    if not value_rects:
        return None
    center_y = (anchor.y0 + anchor.y1) / 2
    center_x = (anchor.x0 + anchor.x1) / 2
    return min(value_rects, key=lambda rect: abs(((rect.y0 + rect.y1) / 2) - center_y) * 3 + abs(((rect.x0 + rect.x1) / 2) - center_x))


def _row_crop_rect(page: Any, rect: Any) -> tuple[float, float, float, float]:
    page_rect = page.rect
    y_center = (rect.y0 + rect.y1) / 2
    top = max(page_rect.y0, y_center - 34)
    bottom = min(page_rect.y1, y_center + 42)
    if bottom - top < 58:
        bottom = min(page_rect.y1, top + 58)
    x0 = max(page_rect.x0 + 28, rect.x0 - 90)
    x1 = min(page_rect.x1 - 28, rect.x1 + 130)
    if x1 - x0 < 260:
        center_x = (rect.x0 + rect.x1) / 2
        x0 = max(page_rect.x0 + 28, center_x - 130)
        x1 = min(page_rect.x1 - 28, center_x + 130)
    if x1 - x0 > 320:
        center_x = (rect.x0 + rect.x1) / 2
        x0 = max(page_rect.x0 + 28, center_x - 160)
        x1 = min(page_rect.x1 - 28, center_x + 160)
    return (x0, top, x1, bottom)


def _search_terms_for_finding(finding: dict[str, Any]) -> list[str]:
    field = str(finding.get("field") or "")
    terms = list(FIELD_SEARCH_TERMS.get(field, []))
    snippet = str(finding.get("snippet") or "")
    for token in _snippet_tokens(snippet)[:6]:
        if token.upper() == token or len(token) > 5:
            terms.append(token)
    return _dedupe_terms(terms)


def _value_terms(finding: dict[str, Any]) -> list[str]:
    value = finding.get("value")
    unit = str(finding.get("unit") or "")
    terms: list[str] = []
    if isinstance(value, (int, float)):
        number = int(value) if float(value).is_integer() else value
        terms.extend([str(number), f"{number}{unit}", f"{number} {unit}"])
    elif isinstance(value, dict):
        terms.extend(str(v) for v in value.values())
    else:
        terms.append(str(value))
    return _dedupe_terms([term for term in terms if term and term != "{}"])


def _snippet_tokens(snippet: str) -> list[str]:
    normalized = _normalize_text(snippet)
    return [token for token in normalized.split() if len(token) >= 3][:24]


def _normalize_text(text: str) -> str:
    return " ".join(str(text).replace("μ", "u").replace("Ω", "ohm").split()).lower()


def _dedupe_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        key = _normalize_text(term)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(str(term))
    return result


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value)[:48].strip("_") or "field"


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
