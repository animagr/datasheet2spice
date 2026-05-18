import tempfile
import unittest
from pathlib import Path

from datasheet2spice.plugins import load_builtin_plugins, module_catalog, registry
from datasheet2spice.schema import DeviceProject
from datasheet2spice.service import generate_model_bundle
from datasheet2spice.extractors.pdf_diode import (
    _apply_pdf_series_result,
    _apply_series_table_values,
    extract_diode_project_from_text,
)


ROOT = Path(__file__).resolve().parents[1]


class DiodeSupportTests(unittest.TestCase):
    def setUp(self):
        load_builtin_plugins()
        self.project = DeviceProject.new("DEMO_DIODE_650", profile="diode.power")
        self.project.data["ratings"] = {"vrrm_v": 650, "if_av_a": 20, "ifsm_a": 180}
        self.project.data["static"] = {
            "forward_voltage": {"vf_v": 1.7, "if_a": 20},
            "leakage": {"ir_ua": 50},
        }
        self.project.data["dynamic"] = {
            "junction_capacitance": {"cj0_pf": 120},
            "reverse_recovery": {"trr_ns": 35, "qrr_nc": 150},
        }
        self.project.data["parasitics"] = {"la_nh": 1.2, "lk_nh": 1.0, "ra_ohm": 0.002, "rk_ohm": 0.002}

    def test_diode_profile_registered(self):
        self.assertIn("diode.power", registry.component_profiles)
        profile = registry.component_profiles["diode.power"].describe()
        self.assertEqual(profile["family"], "diode")
        self.assertIn("diode-basic", profile["supported_models"])

    def test_diode_emitter_generates_portable_model(self):
        for dialect in ["common", "ltspice", "ngspice", "pspice", "hspice", "xyce", "qspice"]:
            with self.subTest(dialect=dialect):
                files = registry.emitters["diode-basic"].emit(self.project, dialect)
                joined = "\n".join(files.values())
                self.assertIn(".subckt DEMO_DIODE_650 A K", joined)
                self.assertIn(".model DEMO_DIODE_650_DIODE D", joined)
                self.assertIn("BV=650", joined)
                self.assertTrue(any("reverse_recovery_diode" in name for name in files))

    def test_diode_bundle_skips_mosfet_capacitance_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_model_bundle(self.project, tmp, ["diode-basic"], ["common"])
        self.assertTrue(result["ok"], result.get("errors"))
        names = {item["name"] for item in result["files"]}
        self.assertIn("DEMO_DIODE_650_diode.lib", names)
        self.assertIn("DEMO_DIODE_650_models.zip", names)

    def test_module_catalog_lists_diode_modules(self):
        catalog = module_catalog(include_entrypoints=False)
        module_ids = {module["id"] for module in catalog["modules"]}
        self.assertIn("diode.power", module_ids)
        self.assertIn("diode-basic", module_ids)

    def test_diode_text_extractor_builds_project(self):
        result = extract_diode_project_from_text(
            """
            DEMO-D650 SiC Schottky Diode
            VRRM 650 V
            IF(AV) 20 A
            IFSM 180 A
            VF 1.7 V
            IR 50 uA
            Cj 120 pF
            trr 12 ns
            Qrr 0 nC
            """,
            source="demo.pdf",
            fallback_part="demo_diode",
        )
        project = result["project"]
        self.assertEqual(project.data["component"]["profile"], "diode.power")
        self.assertEqual(project.data["ratings"]["vrrm_v"], 650)
        self.assertEqual(project.data["dynamic"]["junction_capacitance"]["cj0_pf"], 120)
        fields = {finding["field"] for finding in result["findings"]}
        self.assertIn("static.forward_voltage.vf_v", fields)

    def test_series_table_selects_target_part_column(self):
        project = DeviceProject.new("B5819WS", profile="diode.power")
        project.data["ratings"] = {"vrrm_v": 600, "if_av_a": 1.0}
        project.data["static"] = {"forward_voltage": {"vf_v": 1.2, "if_a": 1.0}, "leakage": {"ir_ua": 10}}
        project.data["dynamic"] = {"junction_capacitance": {"cj0_pf": 80}, "reverse_recovery": {"trr_ns": 20, "qrr_nc": 0}}
        project.data["thermal"] = {}
        tables = [
            {
                "page": 1,
                "rows": [
                    ["PARAMETER", "SYMBOL", "UNIT", "B5817WS", "B5818WS", "B5819WS"],
                    ["Maximum Repetitive Peak Reverse Voltage", "VRRM", "V", "20", "30", "40"],
                    ["Maximum Average Forward Rectified Current", "IF(AV)", "A", "1.0"],
                    ["Non-repetitive Peak Forward Surge Current", "IFSM", "A", "10"],
                ],
            },
            {
                "page": 2,
                "rows": [
                    ["PARAMETER", "TEST CONDITIONS", "SYMBOL", "UNIT", "B5817WS", "B5818WS", "B5819WS"],
                    ["IF=1.0A", "VF1", "", "0.45", "0.55", "0.6"],
                    ["IR1", "mA", "1.0"],
                    ["Typical junction capacitance", "VR=4.0V,f=1MHz", "CJ", "pF", "120"],
                ],
            },
        ]
        findings: list[dict] = []
        warnings: list[str] = []
        _apply_series_table_values(project, findings, warnings, tables)
        self.assertEqual(project.data["device"]["series_parts"], ["B5817WS", "B5818WS", "B5819WS"])
        self.assertEqual(project.data["ratings"]["vrrm_v"], 40)
        self.assertEqual(project.data["ratings"]["ifsm_a"], 10)
        self.assertEqual(project.data["static"]["forward_voltage"]["vf_v"], 0.6)
        self.assertEqual(project.data["static"]["leakage"]["ir_ua"], 1000)
        self.assertEqual(project.data["dynamic"]["junction_capacitance"]["cj0_pf"], 120)

    def test_series_pdf_result_requires_selection_when_filename_has_no_part(self):
        result = self._series_pdf_result("datasheet")
        self.assertEqual(result["series"]["parts"], ["B5817WS", "B5818WS", "B5819WS"])
        self.assertIsNone(result["series"]["default_part"])
        self.assertFalse(result["series"]["has_default"])
        self.assertEqual(result["project"].data["device"]["part_number"], "B5817WS")
        self.assertEqual(len(result["variant_projects"]), 3)
        by_part = {project["device"]["part_number"]: project for project in result["variant_projects"]}
        self.assertEqual(by_part["B5819WS"]["ratings"]["vrrm_v"], 40)
        self.assertEqual(by_part["B5818WS"]["static"]["forward_voltage"]["vf_v"], 0.55)
        self.assertTrue(any("filename does not identify a default part" in warning for warning in result["warnings"]))

    def test_series_pdf_result_uses_filename_default_part(self):
        result = self._series_pdf_result("B5819WS")
        self.assertEqual(result["series"]["default_part"], "B5819WS")
        self.assertTrue(result["series"]["has_default"])
        self.assertEqual(result["project"].data["device"]["part_number"], "B5819WS")
        self.assertEqual(result["project"].data["ratings"]["vrrm_v"], 40)

    def _series_pdf_result(self, fallback_part: str) -> dict:
        project = DeviceProject.new("B5817WS", profile="diode.power")
        project.data["ratings"] = {"vrrm_v": 600, "if_av_a": 1.0}
        project.data["static"] = {"forward_voltage": {"vf_v": 1.2, "if_a": 1.0}, "leakage": {"ir_ua": 10}}
        project.data["dynamic"] = {"junction_capacitance": {"cj0_pf": 80}, "reverse_recovery": {"trr_ns": 20, "qrr_nc": 0}}
        project.data["thermal"] = {}
        result = {"project": project, "findings": [], "warnings": [], "tables": [], "curve_digitization": None}
        _apply_pdf_series_result(result, self._b5819ws_tables(), fallback_part)
        return result

    def _b5819ws_tables(self) -> list[dict]:
        return [
            {
                "page": 1,
                "rows": [
                    ["PARAMETER", "SYMBOL", "UNIT", "B5817WS", "B5818WS", "B5819WS"],
                    ["Maximum Repetitive Peak Reverse Voltage", "VRRM", "V", "20", "30", "40"],
                    ["Maximum Average Forward Rectified Current", "IF(AV)", "A", "1.0"],
                    ["Non-repetitive Peak Forward Surge Current", "IFSM", "A", "10"],
                ],
            },
            {
                "page": 2,
                "rows": [
                    ["PARAMETER", "TEST CONDITIONS", "SYMBOL", "UNIT", "B5817WS", "B5818WS", "B5819WS"],
                    ["IF=1.0A", "VF1", "", "0.45", "0.55", "0.6"],
                    ["IR1", "mA", "1.0"],
                    ["Typical junction capacitance", "VR=4.0V,f=1MHz", "CJ", "pF", "120"],
                ],
            },
        ]

    def test_diode_example_loads_and_emits(self):
        project = DeviceProject.load(ROOT / "examples" / "demo_sic_diode" / "device.json")
        files = registry.emitters["diode-basic"].emit(project, "common")
        self.assertIn("DEMO_DIODE_650_diode.lib", files)


if __name__ == "__main__":
    unittest.main()
