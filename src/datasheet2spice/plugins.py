"""Plugin registry for modeling, extraction, validation, and UI extensions."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any, Callable, Protocol

from .contracts import ModuleManifest, module_manifest
from .schema import DeviceProject


class Emitter(Protocol):
    name: str

    def emit(self, project: DeviceProject, dialect: str) -> dict[str, str]:
        """Return mapping of filename to content."""


class Extractor(Protocol):
    name: str

    def extract(self, *args: Any, **kwargs: Any) -> Any:
        """Extract data from a source."""


class Validator(Protocol):
    name: str

    def validate(self, project: DeviceProject) -> list[str]:
        """Return validation errors."""


class ComponentProfile(Protocol):
    name: str
    label: str
    family: str

    def describe(self) -> dict[str, Any]:
        """Return JSON-serializable profile metadata."""


class Fitter(Protocol):
    name: str

    def fit(self, project: DeviceProject) -> Any:
        """Fit model parameters from project data."""


class ToolPanel(Protocol):
    name: str
    label: str

    def describe(self) -> dict[str, Any]:
        """Return JSON-serializable UI/tool metadata."""


@dataclass(slots=True)
class Registry:
    modules: dict[str, ModuleManifest]
    component_profiles: dict[str, ComponentProfile]
    emitters: dict[str, Emitter]
    extractors: dict[str, Extractor]
    fitters: dict[str, Fitter]
    tool_panels: dict[str, ToolPanel]
    validators: dict[str, Validator]

    def register_module(self, manifest: ModuleManifest) -> None:
        self.modules[manifest.id] = manifest

    def register_component_profile(self, profile: ComponentProfile) -> None:
        self.component_profiles[profile.name] = profile
        self.register_module(_manifest_from_plugin("component-profile", profile.name, profile, capabilities=("describe",)))

    def register_emitter(self, emitter: Emitter) -> None:
        self.emitters[emitter.name] = emitter
        self.register_module(_manifest_from_plugin("model-emitter", emitter.name, emitter, capabilities=("emit",)))

    def register_extractor(self, extractor: Extractor) -> None:
        self.extractors[extractor.name] = extractor
        self.register_module(_manifest_from_plugin("extractor", extractor.name, extractor, capabilities=("extract",)))

    def register_fitter(self, fitter: Fitter) -> None:
        self.fitters[fitter.name] = fitter
        self.register_module(_manifest_from_plugin("fitter", fitter.name, fitter, capabilities=("fit",)))

    def register_tool_panel(self, panel: ToolPanel) -> None:
        self.tool_panels[panel.name] = panel
        self.register_module(_manifest_from_plugin("tool-panel", panel.name, panel, capabilities=("describe",)))

    def register_validator(self, validator: Validator) -> None:
        self.validators[validator.name] = validator
        self.register_module(_manifest_from_plugin("validator", validator.name, validator, capabilities=("validate",)))


registry = Registry(modules={}, component_profiles={}, emitters={}, extractors={}, fitters={}, tool_panels={}, validators={})
plugin_load_errors: list[str] = []


def component_profile(name: str) -> Callable[[type], type]:
    def decorate(cls: type) -> type:
        instance = cls()
        instance.name = name
        registry.register_component_profile(instance)
        return cls

    return decorate


def emitter(name: str) -> Callable[[type], type]:
    def decorate(cls: type) -> type:
        instance = cls()
        instance.name = name
        registry.register_emitter(instance)
        return cls

    return decorate


def extractor(name: str) -> Callable[[type], type]:
    def decorate(cls: type) -> type:
        instance = cls()
        instance.name = name
        registry.register_extractor(instance)
        return cls

    return decorate


def fitter(name: str) -> Callable[[type], type]:
    def decorate(cls: type) -> type:
        instance = cls()
        instance.name = name
        registry.register_fitter(instance)
        return cls

    return decorate


def tool_panel(name: str) -> Callable[[type], type]:
    def decorate(cls: type) -> type:
        instance = cls()
        instance.name = name
        registry.register_tool_panel(instance)
        return cls

    return decorate


def validator(name: str) -> Callable[[type], type]:
    def decorate(cls: type) -> type:
        instance = cls()
        instance.name = name
        registry.register_validator(instance)
        return cls

    return decorate


def load_builtin_plugins() -> None:
    # Import side effects register emitters.
    from . import component_profiles as _component_profiles  # noqa: F401
    from .emitters import abm as _abm  # noqa: F401
    from .emitters import diode as _diode  # noqa: F401
    from .emitters import vdmos as _vdmos  # noqa: F401
    from .extractors import csv_curves as _csv_curves  # noqa: F401
    from .validators import schema as _schema_validator  # noqa: F401


def load_entrypoint_plugins(group: str = "datasheet2spice.plugins") -> list[str]:
    """Load third-party plugin modules declared as Python entry points.

    Entry points may either import a module for decorator side effects or return a
    callable that performs explicit registration. The returned list contains the
    entry point names that loaded successfully.
    """

    loaded: list[str] = []
    plugin_load_errors.clear()
    discovered = entry_points()
    selected = discovered.select(group=group) if hasattr(discovered, "select") else discovered.get(group, [])
    for ep in selected:
        try:
            plugin = ep.load()
            if callable(plugin):
                plugin(registry)
            loaded.append(ep.name)
        except Exception as exc:  # pragma: no cover - exact plugin failures are external
            plugin_load_errors.append(f"{ep.name}: {type(exc).__name__}: {exc}")
    return loaded


def load_plugins(include_entrypoints: bool = True) -> list[str]:
    """Load built-in plugins and optionally installed third-party plugins."""

    load_builtin_plugins()
    return load_entrypoint_plugins() if include_entrypoints else []


def module_catalog(include_entrypoints: bool = False) -> dict[str, Any]:
    """Return JSON-serializable manifests for registered modules."""

    load_plugins(include_entrypoints=include_entrypoints)
    return {
        "contract": "datasheet2spice-module-v1",
        "modules": [registry.modules[name].to_dict() for name in sorted(registry.modules)],
    }


def _manifest_from_plugin(kind: str, name: str, instance: object, capabilities: tuple[str, ...]) -> ModuleManifest:
    explicit = getattr(instance, "manifest", None)
    if callable(explicit):
        candidate = explicit()
        if isinstance(candidate, ModuleManifest):
            return candidate
        if isinstance(candidate, dict):
            return ModuleManifest(
                id=str(candidate["id"]),
                kind=str(candidate["kind"]),
                label=str(candidate["label"]),
                version=str(candidate.get("version", "0.1.0")),
                description=str(candidate.get("description", "")),
                component_profiles=tuple(candidate.get("component_profiles", ())),
                runtime_modes=tuple(candidate.get("runtime_modes", ("browser-pages", "local-python"))),
                capabilities=tuple(candidate.get("capabilities", capabilities)),
                dependencies=tuple(candidate.get("dependencies", ())),
                contract=str(candidate.get("contract", "datasheet2spice-module-v1")),
            )
    label = str(getattr(instance, "label", name))
    description = str(getattr(instance, "description", ""))
    component_profiles = tuple(getattr(instance, "component_profiles", ()) or ())
    runtime_modes = tuple(getattr(instance, "runtime_modes", ("browser-pages", "local-python")) or ())
    return module_manifest(
        name,
        kind,
        label,
        description=description,
        component_profiles=component_profiles,
        runtime_modes=runtime_modes,
        capabilities=capabilities,
    )
