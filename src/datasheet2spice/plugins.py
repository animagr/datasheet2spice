"""Simple plugin registry for emitters, extractors, and validators."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any, Callable, Protocol

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


@dataclass(slots=True)
class Registry:
    emitters: dict[str, Emitter]
    extractors: dict[str, Extractor]
    validators: dict[str, Validator]

    def register_emitter(self, emitter: Emitter) -> None:
        self.emitters[emitter.name] = emitter

    def register_extractor(self, extractor: Extractor) -> None:
        self.extractors[extractor.name] = extractor

    def register_validator(self, validator: Validator) -> None:
        self.validators[validator.name] = validator


registry = Registry(emitters={}, extractors={}, validators={})
plugin_load_errors: list[str] = []


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


def validator(name: str) -> Callable[[type], type]:
    def decorate(cls: type) -> type:
        instance = cls()
        instance.name = name
        registry.register_validator(instance)
        return cls

    return decorate


def load_builtin_plugins() -> None:
    # Import side effects register emitters.
    from .emitters import abm as _abm  # noqa: F401
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
