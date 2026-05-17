"""Heuristic MOSFET datasheet PDF extractor.

The extractor is intentionally conservative: it produces a traceable starter
project and a list of findings, not a claim that the whole PDF was understood.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from ..schema import DeviceProject


@dataclass(slots=True)
class Finding:
    field: str
    value: Any
    unit: str
    confidence: float
    page: int | None
    snippet: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "value": self.value,
            "unit": self.unit,
            "confidence": self.confidence,
            "page": self.page,
            "snippet": self.snippet,
        }


def extract_mosfet_project_from_pdf(pdf: str | Path) -> dict[str, Any]:
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError("PDF extraction requires PyMuPDF. Install with: python -m pip install datasheet2spice[pdf]") from exc

    path = Path(pdf)
    pages: list[str] = []
    with fitz.open(str(path)) as doc:
        for page in doc:
            pages.append(page.get_text("text"))
    return extract_mosfet_project_from_text(pages, source=str(path), fallback_part=path.stem)


def extract_mosfet_project_from_text(
    pages: str | list[str],
    source: str = "",
    fallback_part: str = "MOSFET",
) -> dict[str, Any]:
    page_texts = [pages] if isinstance(pages, str) else pages
    text = "\n".join(page_texts)
    flat = _normalize(text)
    lines_by_page = [_clean_lines(page) for page in page_texts]
    findings: list[Finding] = []
    warnings: list[str] = []

    part_number = _extract_part_number(flat, fallback_part)
    vendor = "ROHM" if re.search(r"\bROHM\b", flat, flags=re.I) else ""
    device_type = "n_sic_mosfet" if re.search(r"\bSiC\b", flat, flags=re.I) else "n_power_mosfet"
    project = DeviceProject.new(part_number, datasheet=source, vendor=vendor)
    project.data["device"]["type"] = device_type
    project.data["device"]["description"] = "Auto-extracted starter project; review all values before use."

    ratings: dict[str, Any] = {}
    static: dict[str, Any] = {}
    dynamic: dict[str, Any] = {}
    parasitics: dict[str, Any] = {"ld_nh": 2.0, "ls_nh": 1.0, "lg_nh": 0.2, "rg_ext_ohm": 4.7}

    vdss = _regex_number(flat, r"\bVDSS\b\s+([0-9.]+)\s*V", "ratings.vdss_v", "V", findings, 0.82)
    if vdss is None:
        vdss = _regex_number(flat, r"Drain\s*[- ]\s*source voltage\s+VDSS\s+([0-9.]+)\s+V", "ratings.vdss_v", "V", findings, 0.78)
    ratings["vdss_v"] = vdss or 100.0
    if vdss is None:
        warnings.append("ratings.vdss_v not found; defaulted to 100 V.")

    id_cont = _regex_number(flat, r"\bID\b\s+\*?\d*\s+([0-9.]+)\s*A", "ratings.id_cont_a", "A", findings, 0.65)
    if id_cont is not None:
        ratings["id_cont_a"] = id_cont
    vgs_on = _line_value_after(lines_by_page, "VGS_on", "ratings.vgs_on_v", "V", findings, 0.86)
    ratings["vgs_on_v"] = vgs_on or 10.0
    vgs_pair = re.search(r"VGS\s*=\s*\+?([0-9.]+)\s*V\s*/\s*(-?[0-9.]+)\s*V", flat, flags=re.I)
    if vgs_pair:
        ratings["vgs_off_v"] = float(vgs_pair.group(2))
        findings.append(_finding_from_match("ratings.vgs_off_v", ratings["vgs_off_v"], "V", 0.82, None, flat, vgs_pair))
    else:
        ratings["vgs_off_v"] = 0.0
        warnings.append("ratings.vgs_off_v not found; defaulted to 0 V.")

    vth = _extract_temp_table_before(lines_by_page, "Gate threshold voltage")
    if vth:
        static["vgs_th_v"] = vth
        findings.append(Finding("static.vgs_th_v", vth, "V", 0.82, None, "temperature-keyed values near Gate threshold voltage"))
    else:
        static["vgs_th_v"] = {"25": 3.0}
        warnings.append("static.vgs_th_v not found; defaulted to 3.0 V at 25 C.")

    rds = _extract_temp_table_before(lines_by_page, "RDS(on)")
    if rds:
        static["rds_on_mohm"] = rds
        findings.append(Finding("static.rds_on_mohm", rds, "mohm", 0.78, None, "temperature-keyed values near RDS(on)"))
    else:
        static["rds_on_mohm"] = {"25": 10.0}
        warnings.append("static.rds_on_mohm not found; defaulted to 10 mohm at 25 C.")

    static["gfs_s"] = _line_value_after(lines_by_page, "gfs", "static.gfs_s", "S", findings, 0.72) or 20.0
    static["rg_int_ohm"] = _line_value_after(lines_by_page, "RG", "static.rg_int_ohm", "ohm", findings, 0.7) or 1.0

    ciss = _line_value_after(lines_by_page, "Ciss", "dynamic.capacitance.ciss_pf", "pF", findings, 0.82)
    crss = _line_value_after(lines_by_page, "Crss", "dynamic.capacitance.crss_pf", "pF", findings, 0.82)
    coss = _value_before_marker_with_unit(lines_by_page, "Output capacitance", "pF", "dynamic.capacitance.coss_pf", findings, 0.62)
    if ciss is None:
        ciss = 1000.0
        warnings.append("Ciss not found; defaulted to 1000 pF.")
    if coss is None:
        coss = max(ciss * 0.08, 10.0)
        warnings.append("Coss not found; estimated from Ciss.")
    if crss is None:
        crss = max(ciss * 0.005, 1.0)
        warnings.append("Crss not found; estimated from Ciss.")
    dynamic["capacitance"] = _capacitance_curve_from_single_point(float(ciss), float(coss), float(crss), float(ratings["vdss_v"]))

    qg = _line_value_after(lines_by_page, "Qg", "dynamic.gate_charge.qg_nc", "nC", findings, 0.76)
    qgd = _line_value_after(lines_by_page, "Qgd", "dynamic.gate_charge.qgd_nc", "nC", findings, 0.76)
    qgs = _value_before_marker(lines_by_page, "Gate - Drain charge", "dynamic.gate_charge.qgs_nc", "nC", findings, 0.55)
    dynamic["gate_charge"] = {k: v for k, v in {"qg_nc": qg, "qgs_nc": qgs, "qgd_nc": qgd}.items() if v is not None}

    ids_ref = float(ratings.get("id_cont_a") or 50.0)
    dynamic["channel_fit"] = {"idsat_reference_a": ids_ref, "vgs_reference_v": float(ratings["vgs_on_v"])}
    trr = _line_value_after(lines_by_page, "trr", "dynamic.body_diode.trr_ns", "ns", findings, 0.72)
    irrm = _line_value_after(lines_by_page, "Irrm", "dynamic.body_diode.irrm_a", "A", findings, 0.62)
    qrr = _value_after_marker_before_unit(lines_by_page, "Qrr", "nC", "dynamic.body_diode.qrr_nc", findings, 0.58)
    vsd = _first_value_before_marker(lines_by_page, "Forward voltage", "dynamic.body_diode.vsd_25c_typ_v", "V", findings, 0.52)
    dynamic["body_diode"] = {
        "vsd_25c_typ_v": vsd or 1.0,
        "trr_ns": trr or 30.0,
        "qrr_nc": qrr or 0.0,
        "irrm_a": irrm or 0.0,
    }

    project.data.update(
        {
            "ratings": ratings,
            "static": static,
            "dynamic": dynamic,
            "parasitics": parasitics,
            "provenance": [
                {
                    "source": source,
                    "kind": "pdf_text_auto_extract",
                    "note": "Heuristic PDF text extraction. Review confidence, snippets, and all generated values.",
                }
            ],
        }
    )
    return {"project": project, "findings": [item.as_dict() for item in findings], "warnings": warnings}


def _capacitance_curve_from_single_point(ciss: float, coss: float, crss: float, vdss: float) -> dict[str, list[float]]:
    high_v = max(min(vdss * 2 / 3, 1000.0), 50.0)
    vds = [0.1, 1.0, 10.0, high_v / 4, high_v]
    crss_low = max(crss * 40, crss + 1.0)
    coss_low = max(coss * 20, crss_low * 1.4, coss)
    ciss_low = max(ciss * 1.15, ciss + crss_low - crss)
    return {
        "vds_v": vds,
        "ciss_pf": [ciss_low, ciss * 1.12, ciss * 1.06, ciss * 1.02, ciss],
        "coss_pf": [coss_low, coss * 8, coss * 3.5, coss * 1.5, coss],
        "crss_pf": [crss_low, crss * 25, crss * 8, crss * 2, crss],
    }


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("μ", "u").replace("Ω", "ohm")).strip()


def _extract_part_number(flat: str, fallback: str) -> str:
    candidates = re.findall(r"\b(?:[A-Z]{1,4}-)?S\d{3,6}\b", flat)
    if candidates:
        return candidates[0].replace("TK-", "")
    cleaned = Path(fallback).stem.upper().replace("-", "_").replace(" ", "_")
    return re.sub(r"[^A-Z0-9_]", "", cleaned) or "MOSFET"


def _regex_number(
    flat: str,
    pattern: str,
    field: str,
    unit: str,
    findings: list[Finding],
    confidence: float,
) -> float | None:
    match = re.search(pattern, flat, flags=re.I)
    if not match:
        return None
    value = float(match.group(1))
    findings.append(_finding_from_match(field, value, unit, confidence, None, flat, match))
    return value


def _finding_from_match(field: str, value: Any, unit: str, confidence: float, page: int | None, flat: str, match: re.Match[str]) -> Finding:
    start = max(0, match.start() - 80)
    end = min(len(flat), match.end() + 80)
    return Finding(field, value, unit, confidence, page, flat[start:end])


def _line_value_after(
    lines_by_page: list[list[str]],
    marker: str,
    field: str,
    unit: str,
    findings: list[Finding],
    confidence: float,
) -> float | None:
    for page_no, lines in enumerate(lines_by_page, start=1):
        for idx, line in enumerate(lines):
            if _line_matches_marker(line, marker):
                value = _first_dash_value(lines, idx, min(len(lines), idx + 18))
                if value is not None:
                    findings.append(Finding(field, value, unit, confidence, page_no, _snippet(lines, idx)))
                    return value
    return None


def _value_before_marker(
    lines_by_page: list[list[str]],
    marker: str,
    field: str,
    unit: str,
    findings: list[Finding],
    confidence: float,
) -> float | None:
    for page_no, lines in enumerate(lines_by_page, start=1):
        for idx, line in enumerate(lines):
            if _line_matches_marker(line, marker):
                for j in range(idx - 1, max(-1, idx - 12), -1):
                    if _is_number(lines[j]):
                        value = float(lines[j])
                        findings.append(Finding(field, value, unit, confidence, page_no, _snippet(lines, idx)))
                        return value
    return None


def _value_before_marker_with_unit(
    lines_by_page: list[list[str]],
    marker: str,
    unit_marker: str,
    field: str,
    findings: list[Finding],
    confidence: float,
) -> float | None:
    for page_no, lines in enumerate(lines_by_page, start=1):
        for idx, line in enumerate(lines):
            if _line_matches_marker(line, marker):
                for j in range(idx - 1, max(-1, idx - 50), -1):
                    if unit_marker.lower() in lines[j].lower():
                        for k in range(j - 1, max(-1, j - 8), -1):
                            if _is_number(lines[k]):
                                value = float(lines[k])
                                findings.append(Finding(field, value, unit_marker, confidence, page_no, _snippet(lines, idx)))
                                return value
    return None


def _value_before_unit(
    lines_by_page: list[list[str]],
    unit_marker: str,
    field: str,
    findings: list[Finding],
    confidence: float,
) -> float | None:
    for page_no, lines in enumerate(lines_by_page, start=1):
        for idx, line in enumerate(lines):
            if line.strip().lower() == unit_marker.lower():
                for j in range(idx - 1, max(-1, idx - 8), -1):
                    if _is_number(lines[j]):
                        value = float(lines[j])
                        findings.append(Finding(field, value, unit_marker, confidence, page_no, _snippet(lines, idx)))
                        return value
    return None


def _value_after_marker_before_unit(
    lines_by_page: list[list[str]],
    marker: str,
    unit_marker: str,
    field: str,
    findings: list[Finding],
    confidence: float,
) -> float | None:
    for page_no, lines in enumerate(lines_by_page, start=1):
        for idx, line in enumerate(lines):
            if not _line_matches_marker(line, marker):
                continue
            for unit_idx in range(idx + 1, min(len(lines), idx + 35)):
                if lines[unit_idx].strip().lower() != unit_marker.lower():
                    continue
                candidates = [float(lines[j]) for j in range(idx + 1, unit_idx) if _is_number(lines[j])]
                if candidates:
                    value = candidates[-1]
                    findings.append(Finding(field, value, unit_marker, confidence, page_no, _snippet(lines, idx)))
                    return value
    return None


def _first_value_before_marker(
    lines_by_page: list[list[str]],
    marker: str,
    field: str,
    unit: str,
    findings: list[Finding],
    confidence: float,
) -> float | None:
    for page_no, lines in enumerate(lines_by_page, start=1):
        for idx, line in enumerate(lines):
            if not _line_matches_marker(line, marker):
                continue
            candidates: list[float] = []
            for j in range(idx - 1, max(-1, idx - 16), -1):
                if _is_number(lines[j]):
                    candidates.append(float(lines[j]))
                    continue
                if lines[j].strip() == "-" or re.search(r"Tvj\s*=", lines[j], flags=re.I):
                    continue
                if candidates:
                    break
            if candidates:
                value = list(reversed(candidates))[0]
                findings.append(Finding(field, value, unit, confidence, page_no, _snippet(lines, idx)))
                return value
    return None


def _first_dash_value(lines: list[str], start: int, end: int) -> float | None:
    for i in range(start + 1, end):
        if _is_number(lines[i]):
            return float(lines[i])
    return None


def _extract_temp_table_before(lines_by_page: list[list[str]], marker: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for lines in lines_by_page:
        marker_indexes = [i for i, line in enumerate(lines) if marker.lower() in line.lower()]
        for marker_idx in marker_indexes:
            for idx in range(max(0, marker_idx - 18), marker_idx):
                temp = _temp_from_line(lines[idx])
                if temp is None:
                    continue
                typ = _typ_after_temp(lines, idx, marker_idx)
                if typ is not None:
                    values[str(int(temp))] = typ
    return values


def _temp_from_line(line: str) -> float | None:
    match = re.search(r"Tvj\s*=\s*(-?[0-9.]+)", line.replace(" ", ""), flags=re.I)
    if match:
        return float(match.group(1))
    return None


def _typ_after_temp(lines: list[str], idx: int, marker_idx: int) -> float | None:
    nums: list[float] = []
    for line in lines[idx + 1 : min(marker_idx, idx + 8)]:
        if _is_number(line):
            nums.append(float(line))
        elif line.strip() == "-":
            continue
        elif nums:
            break
    if len(nums) >= 3:
        return nums[1]
    if nums:
        return nums[0]
    return None


def _is_number(text: str) -> bool:
    return bool(re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?", text.strip()))


def _line_matches_marker(line: str, marker: str) -> bool:
    clean_line = re.sub(r"[^A-Za-z0-9]+", "", line).lower()
    clean_marker = re.sub(r"[^A-Za-z0-9]+", "", marker).lower()
    if len(clean_marker) <= 5 and clean_marker.isalnum():
        return clean_line == clean_marker
    return marker.lower() in line.lower()


def _snippet(lines: list[str], idx: int) -> str:
    return " | ".join(lines[max(0, idx - 4) : min(len(lines), idx + 8)])
