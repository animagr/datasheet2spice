"""Runtime mode capability descriptions.

The project intentionally supports multiple backends behind the same frontend
contract:

- browser-pages: static browser files plus JavaScript/WASM helpers,
- local-python: the high-fidelity local service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import API_CONTRACT


@dataclass(frozen=True, slots=True)
class RuntimeMode:
    name: str
    label: str
    deployment: str
    summary: str
    features: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "deployment": self.deployment,
            "summary": self.summary,
            "features": list(self.features),
            "limitations": list(self.limitations),
        }


BROWSER_PAGES = RuntimeMode(
    name="browser-pages",
    label="Static Browser Mode",
    deployment="Static browser files",
    summary="No-install review and starter model generation in the browser.",
    features=(
        "pdf_text_extraction",
        "manual_review",
        "starter_model_generation",
        "zip_download",
        "indexeddb_project_cache",
        "future_wasm_fitters",
    ),
    limitations=(
        "no_local_simulator_execution",
        "limited_scanned_pdf_ocr",
        "limited_long_running_batch_jobs",
        "no_server_side_file_storage",
    ),
)


LOCAL_PYTHON = RuntimeMode(
    name="local-python",
    label="Local Python Backend",
    deployment="User workstation",
    summary="High-fidelity extraction, evidence rendering, digitization, fitting, and simulator adapters.",
    features=(
        "pymupdf_text_extraction",
        "pdf_evidence_screenshots",
        "table_candidate_recognition",
        "vector_curve_digitization",
        "raster_curve_digitization",
        "parameter_fitting",
        "model_quality_evaluation",
        "optional_simulator_smoke_tests",
    ),
    limitations=(
        "requires_local_install",
        "optional_dependencies_have_their_own_licenses",
    ),
)


RUNTIME_MODES = (BROWSER_PAGES, LOCAL_PYTHON)


def runtime_matrix() -> dict[str, Any]:
    return {
        "contract": API_CONTRACT,
        "modes": [mode.to_dict() for mode in RUNTIME_MODES],
    }


def local_runtime_capabilities() -> dict[str, Any]:
    return {
        "active_mode": LOCAL_PYTHON.name,
        "contract": API_CONTRACT,
        "available_modes": [BROWSER_PAGES.name, LOCAL_PYTHON.name],
        "runtime": LOCAL_PYTHON.to_dict(),
    }
