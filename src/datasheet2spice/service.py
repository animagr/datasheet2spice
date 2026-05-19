"""Backend service functions shared by HTTP, CLI, and future adapters."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any
import zipfile

from .evaluation import evaluate_project_model
from .contracts import service_contract
from .extractors.curve_digitizer import DEFAULT_VDS_POINTS
from .extractors.pdf_diode import extract_diode_project_from_pdf
from .extractors.pdf_evidence import render_pdf_evidence_images
from .extractors.pdf_mosfet import extract_mosfet_project_from_pdf
from .extractors.raster_digitizer import digitize_raster_curve_from_pdf
from .fitting import fit_project_parameters
from .plugins import load_plugins, module_catalog, registry
from .report import render_report
from .schema import DeviceProject
from .validate import validate_project


def backend_capabilities() -> dict[str, Any]:
    from .runtime import local_runtime_capabilities

    capabilities = local_runtime_capabilities()
    capabilities["service_contract"] = service_contract()
    capabilities["module_catalog"] = module_catalog(include_entrypoints=False)
    return capabilities


def extract_pdf_to_session(
    pdf_path: str | Path,
    session_dir: str | Path,
    asset_url_prefix: str,
    component_profile: str = "mosfet.power",
) -> dict[str, Any]:
    """Extract a component project from a PDF and persist review artifacts.

    The local HTTP workbench calls this function today. A future REST server or
    desktop wrapper can call the same function without depending on
    ``BaseHTTPRequestHandler``.
    """

    pdf = Path(pdf_path)
    session = Path(session_dir)
    session.mkdir(parents=True, exist_ok=True)
    if component_profile == "diode.power":
        result = extract_diode_project_from_pdf(pdf)
    else:
        result = extract_mosfet_project_from_pdf(pdf)
    project: DeviceProject = result["project"]
    evidence = render_pdf_evidence_images(
        pdf,
        session / "assets",
        asset_url_prefix,
        findings=result["findings"],
        tables=result.get("tables", []),
        curve_digitization=result.get("curve_digitization"),
    )
    response = {
        "session": session.name,
        "filename": pdf.name,
        "project": project.data,
        "project_path": "",
        "findings": result["findings"],
        "warnings": result["warnings"],
        "tables": result.get("tables", []),
        "curve_digitization": result.get("curve_digitization"),
        "evidence": evidence,
        "fit": fit_project_parameters(project)["fits"],
        "evaluation": evaluate_project_model(project),
        "series": result.get("series"),
        "variant_projects": result.get("variant_projects", []),
        "series_variants": result.get("series_variants", []),
    }
    _write_extract_result(response, session, project)
    return response


def save_project_review(project: DeviceProject, session_dir: str | Path) -> dict[str, Any]:
    """Persist the current reviewed project JSON in session and by-part folders."""

    session = Path(session_dir)
    session.mkdir(parents=True, exist_ok=True)
    paths = _save_project_files(project, session)
    response_path = session / "extract_result.json"
    if response_path.exists():
        response = json.loads(response_path.read_text(encoding="utf-8-sig"))
        response["project"] = project.data
        _write_extract_result(response, session, project)
        paths = response.get("save_paths", paths)
    return {
        "ok": True,
        "project": project.data,
        "save_paths": _stringify_paths(paths),
    }


def fit_project_for_response(project: DeviceProject) -> dict[str, Any]:
    fit = fit_project_parameters(project)
    fitted = DeviceProject(data=fit["project"])
    return {
        "ok": True,
        "project": fit["project"],
        "fit": fit["fits"],
        "evaluation": evaluate_project_model(fitted),
    }


def digitize_raster_curve(
    pdf_path: str | Path,
    page: int,
    plot_rect: list[float],
    *,
    curve_name: str = "curve",
    x_range: tuple[float, float] = (0.1, 1000.0),
    y_range: tuple[float, float] = (1.0, 100000.0),
    x_values: list[float] | None = None,
    x_log: bool = True,
    y_log: bool = True,
    threshold: int = 110,
    initial_y_fraction: float | None = None,
) -> dict[str, Any]:
    return digitize_raster_curve_from_pdf(
        pdf_path,
        page,
        plot_rect,
        curve_name=curve_name,
        x_range=x_range,
        y_range=y_range,
        x_values=x_values or list(DEFAULT_VDS_POINTS),
        x_log=x_log,
        y_log=y_log,
        threshold=threshold,
        initial_y_fraction=initial_y_fraction,
    )


def generate_model_bundle(project: DeviceProject, out_dir: str | Path, models: list[str], dialects: list[str]) -> dict[str, Any]:
    load_plugins()
    errors = validate_project(project)
    if any(model in {"vdmos-static-fast", "abm-basic"} for model in models) and errors:
        return {"ok": False, "errors": errors, "files": []}

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, str]] = []
    for model in models:
        if model not in registry.emitters:
            return {"ok": False, "errors": [f"unknown emitter: {model}"], "files": []}
        for dialect in dialects:
            emitted = registry.emitters[model].emit(project, dialect=dialect)
            for name, content in emitted.items():
                path = out / name
                path.write_text(content, encoding="utf-8", newline="\n")
                files.append({"name": name, "path": str(path), "content": content})
    project_json = out / f"{project.model_name}.device.json"
    project_json.write_text(json.dumps(project.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files.append({"name": project_json.name, "path": str(project_json), "content": project_json.read_text(encoding="utf-8")})
    report = render_report(project)
    report_path = out / "report.md"
    report_path.write_text(report + "\n", encoding="utf-8")
    files.append({"name": "report.md", "path": str(report_path), "content": report})
    fit = fit_project_parameters(project)
    evaluation = evaluate_project_model(project)
    analysis_path = out / "fit_evaluation.json"
    analysis_path.write_text(json.dumps({"fit": fit["fits"], "evaluation": evaluation}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files.append({"name": "fit_evaluation.json", "path": str(analysis_path), "content": analysis_path.read_text(encoding="utf-8")})

    zip_path = out / f"{project.model_name}_models.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in files:
            zf.write(item["path"], arcname=item["name"])
    files.append({"name": zip_path.name, "path": str(zip_path), "content": ""})
    session = out.parent.name
    part_generated = _part_dir(out.parent, project) / "generated"
    _mirror_files(files, part_generated)
    return {
        "ok": True,
        "errors": [],
        "files": files,
        "download_url": f"/download/{session}/{zip_path.name}",
        "report": report,
        "fit": fit["fits"],
        "evaluation": evaluation,
        "output_paths": {
            "session_generated": str(out),
            "part_generated": str(part_generated),
        },
    }


def generate_model_bundle_for_projects(
    projects: list[DeviceProject],
    out_dir: str | Path,
    models: list[str],
    dialects: list[str],
) -> dict[str, Any]:
    """Generate one ZIP bundle containing model files for multiple projects."""

    if not projects:
        return {"ok": False, "errors": ["no projects selected"], "files": []}
    load_plugins()
    for model in models:
        if model not in registry.emitters:
            return {"ok": False, "errors": [f"unknown emitter: {model}"], "files": []}
    for project in projects:
        errors = validate_project(project)
        if any(model in {"vdmos-static-fast", "abm-basic"} for model in models) and errors:
            return {"ok": False, "errors": [f"{project.part_number}: {error}" for error in errors], "files": []}

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, str]] = []
    for project in projects:
        folder = project.model_name
        project_dir = out / folder
        project_dir.mkdir(parents=True, exist_ok=True)
        for model in models:
            for dialect in dialects:
                emitted = registry.emitters[model].emit(project, dialect=dialect)
                for name, content in emitted.items():
                    path = project_dir / name
                    path.write_text(content, encoding="utf-8", newline="\n")
                    files.append({"name": f"{folder}/{name}", "path": str(path), "content": content})
        project_json = project_dir / f"{project.model_name}.device.json"
        project_json.write_text(json.dumps(project.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        files.append({"name": f"{folder}/{project_json.name}", "path": str(project_json), "content": project_json.read_text(encoding="utf-8")})
        report = render_report(project)
        report_path = project_dir / "report.md"
        report_path.write_text(report + "\n", encoding="utf-8")
        files.append({"name": f"{folder}/report.md", "path": str(report_path), "content": report})

    summary = {
        "parts": [project.part_number for project in projects],
        "models": models,
        "dialects": dialects,
    }
    summary_path = out / "series_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files.append({"name": "series_summary.json", "path": str(summary_path), "content": summary_path.read_text(encoding="utf-8")})

    zip_name = f"{projects[0].model_name}_series_models.zip" if len(projects) == 1 else "series_models.zip"
    zip_path = out / zip_name
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in files:
            zf.write(item["path"], arcname=item["name"])
    files.append({"name": zip_path.name, "path": str(zip_path), "content": ""})
    session = out.parent.name
    return {
        "ok": True,
        "errors": [],
        "files": files,
        "download_url": f"/download/{session}/{zip_path.name}",
        "report": f"Generated model bundle for {len(projects)} project(s).",
        "fit": [],
        "evaluation": None,
    }


def _part_dir(session: Path, project: DeviceProject) -> Path:
    return _parts_root(session) / project.model_name


def _parts_root(session: Path) -> Path:
    if session.parent.name == "webapp" and session.parent.parent.name == "build":
        return session.parent.parent.parent / "parts"
    return session.parent / "parts"


def _save_project_files(project: DeviceProject, session: Path) -> dict[str, Path]:
    session_project = session / f"{project.model_name}.device.json"
    part_dir = _part_dir(session, project)
    part_dir.mkdir(parents=True, exist_ok=True)
    part_project = part_dir / f"{project.model_name}.device.json"
    project.save(session_project)
    project.save(part_project)
    return {
        "session_project": session_project,
        "part_project": part_project,
        "part_dir": part_dir,
    }


def _write_extract_result(response: dict[str, Any], session: Path, project: DeviceProject) -> None:
    paths = _save_project_files(project, session)
    response["project_path"] = str(paths["session_project"])
    response["save_paths"] = _stringify_paths(paths)
    session_result = session / "extract_result.json"
    part_result = paths["part_dir"] / "extract_result.json"
    response["save_paths"]["session_extract_result"] = str(session_result)
    response["save_paths"]["part_extract_result"] = str(part_result)
    text = json.dumps(response, ensure_ascii=False, indent=2) + "\n"
    session_result.write_text(text, encoding="utf-8")
    part_result.write_text(text, encoding="utf-8")


def _stringify_paths(paths: dict[str, Path] | dict[str, str]) -> dict[str, str]:
    return {key: str(value) for key, value in paths.items()}


def _mirror_files(files: list[dict[str, str]], destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for item in files:
        source = Path(item["path"])
        if source.exists() and source.is_file():
            target = destination / item["name"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
