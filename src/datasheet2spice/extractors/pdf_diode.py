"""Heuristic power diode datasheet PDF extractor."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Any

from ..schema import DeviceProject
from .pdf_mosfet import Finding
from .pdf_tables import extract_pdf_tables


def extract_diode_project_from_pdf(pdf: str | Path) -> dict[str, Any]:
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError("PDF extraction requires PyMuPDF. Install with: python -m pip install datasheet2spice[pdf]") from exc

    path = Path(pdf)
    pages: list[str] = []
    with fitz.open(str(path)) as doc:
        for page in doc:
            pages.append(page.get_text("text"))
    result = extract_diode_project_from_text(pages, source=str(path), fallback_part=path.stem)
    tables = extract_pdf_tables(path)
    result["tables"] = tables
    _apply_pdf_series_result(result, tables, path.stem)
    result["curve_digitization"] = None
    return result


def extract_diode_project_from_text(
    pages: str | list[str],
    source: str = "",
    fallback_part: str = "DIODE",
) -> dict[str, Any]:
    page_texts = [pages] if isinstance(pages, str) else pages
    flat_pages = [_normalize(page) for page in page_texts]
    flat = " ".join(flat_pages)
    findings: list[Finding] = []
    warnings: list[str] = []

    series_parts = _series_candidates(flat)
    part_number = _extract_part_number(flat, fallback_part)
    vendor = _extract_vendor(flat)
    if re.search(r"\bSiC\b", flat, flags=re.I):
        device_type = "sic_schottky_diode"
    elif re.search(r"Schottky", flat, flags=re.I):
        device_type = "schottky_diode"
    else:
        device_type = "power_diode"
    project = DeviceProject.new(part_number, datasheet=source, vendor=vendor, device_type=device_type, profile="diode.power")
    project.data["device"]["description"] = "Auto-extracted diode starter project; review all values before use."
    if series_parts:
        project.data["device"]["series_parts"] = series_parts

    vrrm = _regex_number(
        flat_pages,
        r"(?:\bVRRM\b|repetitive peak reverse voltage|reverse voltage)[^0-9]{0,120}([0-9.]+)\s*V",
        "ratings.vrrm_v",
        "V",
        findings,
        0.72,
    )
    if_av = _regex_number(
        flat_pages,
        r"(?:\bIF\(AV\)|\bIFAV\b|average forward current)[^0-9]{0,120}([0-9.]+)\s*A",
        "ratings.if_av_a",
        "A",
        findings,
        0.68,
    )
    ifsm = _regex_number(
        flat_pages,
        r"(?:\bIFSM\b|surge forward current)[^0-9]{0,120}([0-9.]+)\s*A",
        "ratings.ifsm_a",
        "A",
        findings,
        0.58,
    )
    vf = _regex_number(
        flat_pages,
        r"(?:\bVF\b|forward voltage)[^0-9]{0,120}([0-9.]+)\s*V",
        "static.forward_voltage.vf_v",
        "V",
        findings,
        0.62,
    )
    ir = _regex_number(
        flat_pages,
        r"(?:\bIR\b|reverse current|leakage current)[^0-9]{0,120}([0-9.]+)\s*uA",
        "static.leakage.ir_ua",
        "uA",
        findings,
        0.52,
    )
    cj = _regex_number(
        flat_pages,
        r"(?:\bCj\b|\bCt\b|junction capacitance|total capacitance)[^0-9]{0,120}([0-9.]+)\s*pF",
        "dynamic.junction_capacitance.cj0_pf",
        "pF",
        findings,
        0.58,
    )
    trr = _regex_number(
        flat_pages,
        r"(?:\btrr\b|reverse recovery time)[^0-9]{0,120}([0-9.]+)\s*ns",
        "dynamic.reverse_recovery.trr_ns",
        "ns",
        findings,
        0.52,
    )
    qrr = _regex_number(
        flat_pages,
        r"(?:\bQrr\b|reverse recovery charge)[^0-9]{0,120}([0-9.]+)\s*nC",
        "dynamic.reverse_recovery.qrr_nc",
        "nC",
        findings,
        0.52,
    )
    rth = _regex_number(
        flat_pages,
        r"(?:\bRth\(j[- ]?c\)\b|thermal resistance)[^0-9]{0,120}([0-9.]+)",
        "thermal.rth_jc_c_per_w",
        "C/W",
        findings,
        0.45,
    )

    if vrrm is None:
        vrrm = 600.0
        warnings.append("ratings.vrrm_v not found; defaulted to 600 V.")
    if if_av is None:
        if_av = 10.0
        warnings.append("ratings.if_av_a not found; defaulted to 10 A.")
    if vf is None:
        vf = 1.2
        warnings.append("static.forward_voltage.vf_v not found; defaulted to 1.2 V.")
    if cj is None:
        cj = 80.0
        warnings.append("dynamic.junction_capacitance.cj0_pf not found; defaulted to 80 pF.")

    project.data.update(
        {
            "ratings": {"vrrm_v": vrrm, "if_av_a": if_av, "ifsm_a": ifsm or if_av * 8},
            "static": {
                "forward_voltage": {"vf_v": vf, "if_a": if_av},
                "leakage": {"ir_ua": ir or 10.0},
            },
            "dynamic": {
                "junction_capacitance": {"cj0_pf": cj},
                "reverse_recovery": {"trr_ns": trr or 20.0, "qrr_nc": qrr or 0.0},
            },
            "thermal": {"rth_jc_c_per_w": rth or 1.5},
            "parasitics": {"la_nh": 1.0, "lk_nh": 1.0, "ra_ohm": 0.001, "rk_ohm": 0.001},
            "provenance": [
                {
                    "source": source,
                    "kind": "pdf_text_auto_extract",
                    "note": "Heuristic diode PDF text extraction. Review confidence, snippets, and all generated values.",
                }
            ],
        }
    )
    result = {"project": project, "findings": [item.as_dict() for item in findings], "warnings": warnings, "tables": [], "curve_digitization": None}
    _apply_text_series_result(result, series_parts, fallback_part)
    return result


def _apply_pdf_series_result(result: dict[str, Any], tables: list[dict[str, Any]], fallback_part: str) -> None:
    series_parts = _series_parts_from_tables(tables) or result["project"].data.get("device", {}).get("series_parts", [])
    if not series_parts:
        _apply_series_table_values(result["project"], result["findings"], result["warnings"], tables)
        return

    default_part = _default_part_from_fallback(fallback_part, series_parts)
    variants: list[dict[str, Any]] = []
    for part in series_parts:
        project = _clone_project_for_part(result["project"], part, series_parts)
        findings = deepcopy(result["findings"])
        warnings = deepcopy(result["warnings"])
        _apply_series_table_values(project, findings, warnings, tables)
        variants.append(
            {
                "part_number": part,
                "project": project.data,
                "findings": findings,
                "warnings": warnings,
                "is_default": part == default_part,
            }
        )

    selected = next((item for item in variants if item["part_number"] == default_part), variants[0])
    result["project"] = DeviceProject(data=deepcopy(selected["project"]))
    result["findings"] = deepcopy(selected["findings"])
    result["warnings"] = deepcopy(selected["warnings"])
    if default_part is None and len(series_parts) > 1:
        result["warnings"].append("Series datasheet detected, but the filename does not identify a default part. Select a part before generation.")
    _attach_series_metadata(result, series_parts, default_part, selected["part_number"], variants)


def _apply_text_series_result(result: dict[str, Any], series_parts: list[str], fallback_part: str) -> None:
    if not series_parts:
        return
    default_part = _default_part_from_fallback(fallback_part, series_parts)
    variants: list[dict[str, Any]] = []
    for part in series_parts:
        project = _clone_project_for_part(result["project"], part, series_parts)
        variants.append(
            {
                "part_number": part,
                "project": project.data,
                "findings": deepcopy(result["findings"]),
                "warnings": deepcopy(result["warnings"]),
                "is_default": part == default_part,
            }
        )
    selected = next((item for item in variants if item["part_number"] == default_part), variants[0])
    result["project"] = DeviceProject(data=deepcopy(selected["project"]))
    if default_part is None and len(series_parts) > 1:
        result["warnings"].append("Series datasheet detected, but the filename does not identify a default part. Select a part before generation.")
    _attach_series_metadata(result, series_parts, default_part, selected["part_number"], variants)


def _attach_series_metadata(
    result: dict[str, Any],
    series_parts: list[str],
    default_part: str | None,
    selected_part: str,
    variants: list[dict[str, Any]],
) -> None:
    projects = [item["project"] for item in variants]
    result["series"] = {
        "parts": series_parts,
        "default_part": default_part,
        "selected_part": selected_part,
        "has_default": default_part is not None,
        "summary": _series_summary(projects),
    }
    result["variant_projects"] = projects
    result["series_variants"] = variants


def _clone_project_for_part(project: DeviceProject, part: str, series_parts: list[str]) -> DeviceProject:
    cloned = DeviceProject(data=deepcopy(project.data))
    cloned.data.setdefault("device", {})["part_number"] = part
    cloned.data.setdefault("device", {})["series_parts"] = series_parts
    return cloned


def _default_part_from_fallback(fallback_part: str, series_parts: list[str]) -> str | None:
    fallback_clean = _clean_name(Path(fallback_part).stem)
    fallback_candidates = _series_candidates(fallback_clean)
    if len(fallback_candidates) == 1 and fallback_candidates[0] in series_parts:
        return fallback_candidates[0]
    if fallback_clean in series_parts:
        return fallback_clean
    return None


def _series_summary(projects: list[dict[str, Any]]) -> dict[str, Any]:
    paths = [
        ("ratings", "vrrm_v"),
        ("ratings", "if_av_a"),
        ("ratings", "ifsm_a"),
        ("static", "forward_voltage", "vf_v"),
        ("static", "leakage", "ir_ua"),
        ("dynamic", "junction_capacitance", "cj0_pf"),
        ("thermal", "rth_jc_c_per_w"),
    ]
    common: dict[str, Any] = {}
    varying: dict[str, dict[str, Any]] = {}
    for path in paths:
        key = ".".join(path)
        values = {project.get("device", {}).get("part_number", f"part_{idx}"): _get_path(project, path) for idx, project in enumerate(projects)}
        unique = {json_key(value) for value in values.values()}
        if len(unique) == 1:
            common[key] = next(iter(values.values()))
        else:
            varying[key] = values
    return {"common": common, "varying": varying}


def _get_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    cur: Any = data
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def json_key(value: Any) -> str:
    return repr(value)


def _apply_series_table_values(
    project: DeviceProject,
    findings: list[dict[str, Any]],
    warnings: list[str],
    tables: list[dict[str, Any]],
) -> None:
    target = _clean_name(project.part_number)
    series_parts = _series_parts_from_tables(tables)
    if series_parts:
        project.data.setdefault("device", {})["series_parts"] = series_parts
    if len(series_parts) > 1 and target not in series_parts:
        warnings.append(f"Series datasheet detected ({', '.join(series_parts)}); using {project.part_number}. Rename the PDF or set device.part_number to select a different column.")

    specs = [
        {
            "field": "ratings.vrrm_v",
            "path": ("ratings", "vrrm_v"),
            "markers": ("VRRM", "Maximum Repetitive Peak Reverse Voltage"),
            "unit": "V",
            "confidence": 0.86,
        },
        {
            "field": "ratings.if_av_a",
            "path": ("ratings", "if_av_a"),
            "markers": ("IF(AV)", "Average Forward Rectified Current", "Average Forward Current"),
            "unit": "A",
            "confidence": 0.82,
        },
        {
            "field": "ratings.ifsm_a",
            "path": ("ratings", "ifsm_a"),
            "markers": ("IFSM", "Peak Forward Surge Current"),
            "unit": "A",
            "confidence": 0.76,
        },
        {
            "field": "static.forward_voltage.vf_v",
            "path": ("static", "forward_voltage", "vf_v"),
            "markers": ("VF1", "IF=1.0A", "Maximum instantaneous forward voltage"),
            "unit": "V",
            "confidence": 0.8,
            "also_set": ("static", "forward_voltage", "if_a", 1.0),
        },
        {
            "field": "static.leakage.ir_ua",
            "path": ("static", "leakage", "ir_ua"),
            "markers": ("IR1", "Maximum DC reverse current"),
            "unit": "uA",
            "source_unit": "mA",
            "scale": 1000.0,
            "confidence": 0.72,
        },
        {
            "field": "dynamic.junction_capacitance.cj0_pf",
            "path": ("dynamic", "junction_capacitance", "cj0_pf"),
            "markers": ("CJ", "Typical junction capacitance"),
            "unit": "pF",
            "confidence": 0.72,
        },
        {
            "field": "thermal.rth_jc_c_per_w",
            "path": ("thermal", "rth_jc_c_per_w"),
            "markers": ("RJA", "Rth", "Thermal Resistance"),
            "unit": "C/W",
            "confidence": 0.68,
        },
    ]

    for spec in specs:
        hit = _series_table_value(tables, target, tuple(spec["markers"]))
        if not hit:
            continue
        value, page, snippet = hit
        value *= float(spec.get("scale", 1.0))
        _set_path(project.data, spec["path"], value)
        if "also_set" in spec:
            also = spec["also_set"]
            _set_path(project.data, also[:3], also[3])
        _replace_warning(warnings, str(spec["path"][-1]))
        _upsert_finding(
            findings,
            {
                "field": spec["field"],
                "value": value,
                "unit": spec["unit"],
                "confidence": spec["confidence"],
                "page": page,
                "snippet": snippet,
            },
        )


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00b5", "u").replace("\u03bc", "u").replace("\u6e2d", "u")).strip()


def _extract_part_number(flat: str, fallback: str) -> str:
    fallback_clean = _clean_name(Path(fallback).stem)
    candidates = _series_candidates(flat)
    fallback_candidates = _series_candidates(fallback_clean)
    if len(fallback_candidates) == 1 and (not candidates or fallback_candidates[0] in candidates):
        return fallback_candidates[0]
    if fallback_clean in candidates:
        return fallback_clean
    if candidates:
        return candidates[0]
    if fallback_clean and fallback_clean not in {"DIODE", "DEVICE", "UPLOAD"}:
        return fallback_clean
    candidates = re.findall(r"\b[A-Z]{1,8}[-_ ]?[A-Z0-9]{3,}[-_.A-Z0-9]*\b", flat)
    ignored = {"DIODE", "SCHOTTKY", "RECTIFIER", "ABSOLUTE", "MAXIMUM", "ELECTRICAL"}
    for candidate in candidates:
        cleaned = _clean_name(candidate)
        if cleaned and cleaned not in ignored:
            return cleaned
    return _clean_name(fallback) or "DIODE"


def _series_candidates(flat: str) -> list[str]:
    pattern = r"\b(?:[A-Z]{1,6}\d{2,6}[A-Z0-9]{0,8}|\dN\d{3,5}[A-Z0-9]*)\b"
    candidates = [_clean_name(item) for item in re.findall(pattern, flat, flags=re.I)]
    return _dedupe([item for item in candidates if len(item) >= 5 and not item.endswith("REF")])


def _series_parts_from_tables(tables: list[dict[str, Any]]) -> list[str]:
    parts: list[str] = []
    for table in tables:
        for row in table.get("rows", []):
            parts.extend(_series_candidates(" ".join(str(cell) for cell in row)))
    return _dedupe(parts)


def _series_table_value(tables: list[dict[str, Any]], target: str, markers: tuple[str, ...]) -> tuple[float, int | None, str] | None:
    for table in tables:
        headers = _series_parts_from_table(table)
        target_idx = headers.index(target) if target in headers else None
        for row in table.get("rows", []):
            row_text = " ".join(str(cell) for cell in row)
            if not _row_has_marker(row_text, markers):
                continue
            values = _numeric_tokens(row_text)
            if not values:
                continue
            if target_idx is not None and len(headers) > 1 and len(values) >= len(headers):
                value = values[-len(headers) + target_idx]
            else:
                value = values[-1]
            return value, table.get("page"), row_text
    return None


def _series_parts_from_table(table: dict[str, Any]) -> list[str]:
    for row in table.get("rows", []):
        parts = _series_candidates(" ".join(str(cell) for cell in row))
        if len(parts) > 1:
            return parts
    return []


def _row_has_marker(row_text: str, markers: tuple[str, ...]) -> bool:
    normalized = _marker_text(row_text)
    return any(_marker_text(marker) in normalized for marker in markers)


def _marker_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text).lower())


def _numeric_tokens(text: str) -> list[float]:
    return [float(item) for item in re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?![A-Za-z])", text)]


def _set_path(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    cur: dict[str, Any] = data
    for key in path[:-1]:
        next_value = cur.setdefault(key, {})
        if not isinstance(next_value, dict):
            next_value = {}
            cur[key] = next_value
        cur = next_value
    cur[path[-1]] = value


def _upsert_finding(findings: list[dict[str, Any]], finding: dict[str, Any]) -> None:
    for idx, existing in enumerate(findings):
        if existing.get("field") == finding["field"]:
            findings[idx] = finding
            return
    findings.append(finding)


def _replace_warning(warnings: list[str], field_tail: str) -> None:
    warnings[:] = [warning for warning in warnings if field_tail not in warning]


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _extract_vendor(flat: str) -> str:
    for vendor in ("ROHM", "Infineon", "Vishay", "STMicroelectronics", "onsemi", "Wolfspeed"):
        if re.search(rf"\b{re.escape(vendor)}\b", flat, flags=re.I):
            return vendor
    return ""


def _regex_number(
    flat_pages: list[str],
    pattern: str,
    field: str,
    unit: str,
    findings: list[Finding],
    confidence: float,
) -> float | None:
    for page_no, page in enumerate(flat_pages, start=1):
        match = re.search(pattern, page, flags=re.I)
        if not match:
            continue
        value = float(match.group(1))
        start = max(0, match.start() - 80)
        end = min(len(page), match.end() + 80)
        findings.append(Finding(field, value, unit, confidence, page_no, page[start:end]))
        return value
    return None


def _clean_name(text: str) -> str:
    return re.sub(r"[^A-Z0-9_]", "_", str(text).upper()).strip("_")
