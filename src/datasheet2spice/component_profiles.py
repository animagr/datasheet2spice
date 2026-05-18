"""Built-in component family profiles.

Profiles describe what a component family expects from extraction, fitting, and
model generation. They deliberately stay metadata-first so the browser
workbench and local backend can make the same routing decisions without
importing heavy extractor dependencies.
"""

from __future__ import annotations

from typing import Any

from .plugins import component_profile


@component_profile("mosfet.power")
class PowerMosfetProfile:
    label = "Power MOSFET / SiC MOSFET"
    family = "mosfet"
    component_types = ("n_power_mosfet", "n_sic_mosfet", "p_power_mosfet")
    supported_models = ("vdmos-static-fast", "abm-basic")
    browser_scope = "Project review and starter model export without remote code loading."
    local_scope = "PDF screenshots, table recognition, raster digitization, fitting, and quality scoring."

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "family": self.family,
            "component_types": list(self.component_types),
            "supported_models": list(self.supported_models),
            "required_sections": [
                "ratings",
                "static",
                "dynamic.capacitance",
                "dynamic.gate_charge",
                "dynamic.body_diode",
                "parasitics",
            ],
            "browser_scope": self.browser_scope,
            "local_scope": self.local_scope,
            "next_profiles": ["diode.power", "igbt.power", "bjt.signal"],
        }


@component_profile("diode.power")
class PowerDiodeProfile:
    label = "Power Diode / Schottky / SiC Diode"
    family = "diode"
    component_types = ("power_diode", "fast_recovery_diode", "schottky_diode", "sic_schottky_diode")
    supported_models = ("diode-basic", "diode-abm-dynamic")
    browser_scope = "Project review and starter diode model export without remote code loading."
    local_scope = "PDF screenshots, table recognition, curve digitization, fitting, and quality scoring."

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "family": self.family,
            "component_types": list(self.component_types),
            "supported_models": list(self.supported_models),
            "required_sections": [
                "ratings",
                "static.forward_voltage",
                "static.leakage",
                "dynamic.junction_capacitance",
                "dynamic.reverse_recovery",
                "thermal",
                "parasitics",
            ],
            "browser_scope": self.browser_scope,
            "local_scope": self.local_scope,
            "next_profiles": ["mosfet.power", "igbt.power", "bjt.signal"],
        }
