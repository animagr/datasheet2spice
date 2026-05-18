"""Stable JSON-first contracts for backends, modules, and workbench adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Literal


API_CONTRACT = "datasheet2spice-api-v1"
MODULE_CONTRACT = "datasheet2spice-module-v1"

JsonDict = dict[str, Any]
ModuleKind = Literal[
    "component-profile",
    "extractor",
    "model-emitter",
    "fitter",
    "validator",
    "tool-panel",
    "backend-adapter",
]

MODULE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,80}$")


@dataclass(frozen=True, slots=True)
class ModuleManifest:
    """Small manifest every extension should be able to expose."""

    id: str
    kind: str
    label: str
    version: str = "0.1.0"
    description: str = ""
    component_profiles: tuple[str, ...] = ()
    runtime_modes: tuple[str, ...] = ("browser-pages", "local-python")
    capabilities: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    contract: str = MODULE_CONTRACT

    def validate(self) -> None:
        validate_module_manifest(self)

    def to_dict(self) -> JsonDict:
        data = {
            "contract": self.contract,
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "version": self.version,
            "description": self.description,
            "component_profiles": list(self.component_profiles),
            "runtime_modes": list(self.runtime_modes),
            "capabilities": list(self.capabilities),
            "dependencies": list(self.dependencies),
        }
        validate_module_manifest(data)
        return data


@dataclass(frozen=True, slots=True)
class ServiceOperation:
    """Operation exposed by a backend adapter."""

    name: str
    summary: str
    runtimes: tuple[str, ...]
    request: str
    response: str

    def to_dict(self) -> JsonDict:
        return {
            "name": self.name,
            "summary": self.summary,
            "runtimes": list(self.runtimes),
            "request": self.request,
            "response": self.response,
        }


@dataclass(slots=True)
class ExtractionRequest:
    source_name: str
    component_profile: str = "mosfet.power"
    options: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "source_name": self.source_name,
            "component_profile": self.component_profile,
            "options": self.options,
        }


@dataclass(slots=True)
class ModelBuildRequest:
    project: JsonDict
    models: list[str]
    dialects: list[str]
    options: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "project": self.project,
            "models": self.models,
            "dialects": self.dialects,
            "options": self.options,
        }


def validate_module_manifest(manifest: ModuleManifest | JsonDict) -> None:
    data = _module_manifest_data(manifest) if isinstance(manifest, ModuleManifest) else manifest
    required = ("contract", "id", "kind", "label", "version", "runtime_modes", "capabilities")
    for key in required:
        if key not in data:
            raise ValueError(f"module manifest missing required field: {key}")
    if data["contract"] != MODULE_CONTRACT:
        raise ValueError(f"unsupported module contract: {data['contract']}")
    if not MODULE_ID_RE.fullmatch(str(data["id"])):
        raise ValueError(f"invalid module id: {data['id']}")
    if not str(data["label"]).strip():
        raise ValueError("module label is required")
    if not isinstance(data["runtime_modes"], list | tuple):
        raise ValueError("runtime_modes must be a list")
    if not isinstance(data["capabilities"], list | tuple):
        raise ValueError("capabilities must be a list")


def _module_manifest_data(manifest: ModuleManifest) -> JsonDict:
    return {
        "contract": manifest.contract,
        "id": manifest.id,
        "kind": manifest.kind,
        "label": manifest.label,
        "version": manifest.version,
        "description": manifest.description,
        "component_profiles": manifest.component_profiles,
        "runtime_modes": manifest.runtime_modes,
        "capabilities": manifest.capabilities,
        "dependencies": manifest.dependencies,
    }


def service_contract() -> JsonDict:
    operations = (
        ServiceOperation(
            name="capabilities",
            summary="Return backend runtime mode, API contract, and available modules.",
            runtimes=("browser-pages", "local-python", "remote-api"),
            request="none",
            response="RuntimeCapabilities",
        ),
        ServiceOperation(
            name="extractPdf",
            summary="Extract a starter ComponentProject and review evidence from a PDF.",
            runtimes=("browser-pages", "local-python", "remote-api"),
            request="ExtractionRequest + PDF bytes",
            response="ExtractionResult",
        ),
        ServiceOperation(
            name="fitModel",
            summary="Fit starter parameters and return project updates plus quality metrics.",
            runtimes=("local-python", "remote-api"),
            request="ComponentProject",
            response="FitResult",
        ),
        ServiceOperation(
            name="emitModelBundle",
            summary="Generate model files, reports, and downloadable bundle content.",
            runtimes=("browser-pages", "local-python", "remote-api"),
            request="ModelBuildRequest",
            response="ModelBundleResult",
        ),
        ServiceOperation(
            name="digitizeCurve",
            summary="Digitize a reviewed plot region into curve points.",
            runtimes=("browser-pages", "local-python", "remote-api"),
            request="CurveDigitizationRequest",
            response="CurveDigitizationResult",
        ),
        ServiceOperation(
            name="runValidation",
            summary="Validate schema, model readiness, and optional simulator smoke tests.",
            runtimes=("browser-pages", "local-python", "remote-api"),
            request="ComponentProject",
            response="ValidationResult",
        ),
    )
    return {
        "contract": API_CONTRACT,
        "module_contract": MODULE_CONTRACT,
        "operations": [operation.to_dict() for operation in operations],
    }


def module_manifest(
    module_id: str,
    kind: str,
    label: str,
    *,
    version: str = "0.1.0",
    description: str = "",
    component_profiles: tuple[str, ...] = (),
    runtime_modes: tuple[str, ...] = ("browser-pages", "local-python"),
    capabilities: tuple[str, ...] = (),
    dependencies: tuple[str, ...] = (),
) -> ModuleManifest:
    manifest = ModuleManifest(
        id=module_id,
        kind=kind,
        label=label,
        version=version,
        description=description,
        component_profiles=component_profiles,
        runtime_modes=runtime_modes,
        capabilities=capabilities,
        dependencies=dependencies,
    )
    manifest.validate()
    return manifest
