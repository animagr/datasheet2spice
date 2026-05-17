"""Project schema helpers.

The schema is intentionally JSON-first to keep the core package dependency-free.
YAML support can be added by a plugin without changing the data model.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


JsonDict = dict[str, Any]


class SchemaError(ValueError):
    """Raised when a project file is missing required fields."""


@dataclass(slots=True)
class DeviceProject:
    """A datasheet-driven device modeling project."""

    data: JsonDict
    path: Path | None = None

    @classmethod
    def load(cls, path: str | Path) -> "DeviceProject":
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        project = cls(data=data, path=p)
        project.validate()
        return project

    @classmethod
    def new(cls, part_number: str, datasheet: str | None = None, vendor: str | None = None) -> "DeviceProject":
        data: JsonDict = {
            "schema_version": "1.0",
            "device": {
                "part_number": part_number,
                "vendor": vendor or "",
                "type": "n_power_mosfet",
                "datasheet": datasheet or "",
            },
            "ratings": {},
            "static": {},
            "dynamic": {},
            "curves": {},
            "parasitics": {},
            "models": {},
            "provenance": [],
        }
        return cls(data=data)

    def save(self, path: str | Path | None = None) -> Path:
        p = Path(path) if path else self.path
        if p is None:
            raise SchemaError("no output path provided")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.path = p
        return p

    def validate(self) -> None:
        required = ["device"]
        for key in required:
            if key not in self.data:
                raise SchemaError(f"missing required top-level field: {key}")
        device = self.data.get("device", {})
        if not isinstance(device, dict):
            raise SchemaError("device must be an object")
        if not (device.get("part_number") or self.data.get("device_name")):
            raise SchemaError("device.part_number is required")

    @property
    def part_number(self) -> str:
        return str(self.data.get("device", {}).get("part_number") or self.data.get("device") or "DEVICE")

    @property
    def model_name(self) -> str:
        raw = self.part_number.replace("-", "_").replace(" ", "_")
        return "".join(ch for ch in raw if ch.isalnum() or ch == "_")

    def get_path(self, *keys: str, default: Any = None) -> Any:
        cur: Any = self.data
        for key in keys:
            if not isinstance(cur, dict) or key not in cur:
                return default
            cur = cur[key]
        return cur

    def require_path(self, *keys: str) -> Any:
        value = self.get_path(*keys, default=None)
        if value is None:
            raise SchemaError("missing required field: " + ".".join(keys))
        return value

    @classmethod
    def from_legacy_s4661(cls, data: JsonDict) -> "DeviceProject":
        """Convert the prototype S4661 JSON format into the v1 project schema."""

        electrical = data.get("electrical_typ", {})
        caps = data.get("capacitance_digitized", {})
        paras = data.get("default_parasitics", {})
        device = data.get("device", "DEVICE")
        project = cls.new(
            part_number=str(device),
            datasheet=data.get("datasheet"),
            vendor="ROHM" if str(device).upper().startswith("S") else "",
        )
        project.data.update(
            {
                "device": {
                    "part_number": str(device),
                    "vendor": "ROHM",
                    "type": "n_sic_mosfet",
                    "description": data.get("description", ""),
                    "datasheet": data.get("datasheet", ""),
                    "datasheet_rev": data.get("datasheet_rev", ""),
                },
                "ratings": data.get("ratings", {}),
                "static": {
                    "vgs_th_v": electrical.get("vgs_th_v", {}),
                    "rds_on_mohm": electrical.get("rds_on_mohm", {}),
                    "gfs_s": electrical.get("gfs_s"),
                    "rg_int_ohm": electrical.get("rg_int_ohm", 0.0),
                    "idss": {
                        "idss_25c_typ_ua": electrical.get("idss_25c_typ_ua"),
                        "idss_25c_max_ua": electrical.get("idss_25c_max_ua"),
                    },
                },
                "dynamic": {
                    "capacitance": caps,
                    "gate_charge": {
                        "qg_nc": electrical.get("qg_nc"),
                        "qgs_nc": electrical.get("qgs_nc"),
                        "qgd_nc": electrical.get("qgd_nc"),
                    },
                    "switching": {
                        "td_on_ns": electrical.get("td_on_ns"),
                        "tr_ns": electrical.get("tr_ns"),
                        "td_off_ns": electrical.get("td_off_ns"),
                        "tf_ns": electrical.get("tf_ns"),
                        "eon_uj": electrical.get("eon_uj"),
                        "eoff_uj": electrical.get("eoff_uj"),
                        "condition": electrical.get("switching_condition", ""),
                    },
                    "channel_fit": electrical.get("channel_fit", {}),
                    "body_diode": electrical.get("body_diode", {}),
                },
                "parasitics": paras,
                "models": {},
                "provenance": [
                    {
                        "source": data.get("datasheet", ""),
                        "note": "Converted from prototype S4661 parameter JSON.",
                    }
                ],
            }
        )
        project.validate()
        return project
