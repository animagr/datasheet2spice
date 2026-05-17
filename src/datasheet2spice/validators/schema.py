"""Schema validator plugin."""

from __future__ import annotations

from ..plugins import validator
from ..schema import DeviceProject
from ..validate import validate_project


@validator("schema")
class SchemaValidator:
    name = "schema"

    def validate(self, project: DeviceProject) -> list[str]:
        return validate_project(project)
