from pathlib import Path
import tempfile
import unittest

from datasheet2spice.plugins import load_builtin_plugins, registry
from datasheet2spice.schema import DeviceProject
from datasheet2spice.validate import validate_project


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "demo_sic_mosfet" / "device.json"


class SchemaEmitterTests(unittest.TestCase):
    def setUp(self):
        load_builtin_plugins()
        self.project = DeviceProject.load(DEMO)

    def test_demo_schema_loads(self):
        self.assertEqual(self.project.part_number, "DEMO_SIC_1200")

    def test_emitters_registered(self):
        self.assertIn("abm-basic", registry.emitters)
        self.assertIn("diode-basic", registry.emitters)
        self.assertIn("diode-abm-dynamic", registry.emitters)
        self.assertIn("vdmos-static-fast", registry.emitters)
        self.assertIn("capacitance-csv", registry.extractors)
        self.assertIn("schema", registry.validators)

    def test_emit_abm_ltspice(self):
        files = registry.emitters["abm-basic"].emit(self.project, "ltspice")
        joined = "\n".join(files.values())
        self.assertIn(".subckt DEMO_SIC_1200", joined)
        self.assertIn("Bch", joined)

    def test_emit_abm_major_dialects(self):
        expectations = {
            "pspice": "VALUE =",
            "hspice": "CUR='",
            "xyce": "Bch",
            "qspice": "Bch",
        }
        for dialect, marker in expectations.items():
            with self.subTest(dialect=dialect):
                files = registry.emitters["abm-basic"].emit(self.project, dialect)
                joined = "\n".join(files.values())
                self.assertIn(marker, joined)
                self.assertTrue(any(f"_abm_{dialect}.lib" in name for name in files))

    def test_emit_vdmos(self):
        files = registry.emitters["vdmos-static-fast"].emit(self.project, "ltspice")
        joined = "\n".join(files.values())
        self.assertIn(".model DEMO_SIC_1200_VDMOS VDMOS", joined)

    def test_emit_vdmos_portable_fallback_for_non_native_dialects(self):
        for dialect in ["common", "pspice", "hspice", "xyce", "qspice"]:
            with self.subTest(dialect=dialect):
                files = registry.emitters["vdmos-static-fast"].emit(self.project, dialect)
                joined = "\n".join(files.values())
                self.assertIn("portable MOS fallback", joined)
                self.assertIn(".subckt DEMO_SIC_1200_VDMOS D G S", joined)
                self.assertIn("XQ drain gate 0 DEMO_SIC_1200_VDMOS", joined)

    def test_validate_rejects_bad_capacitance(self):
        project = DeviceProject.new("BAD")
        project.data["dynamic"]["capacitance"] = {
            "vds_v": [10, 5],
            "ciss_pf": [10, 10],
            "coss_pf": [1, 1],
            "crss_pf": [2, 2],
        }
        errors = validate_project(project)
        self.assertIn("dynamic.capacitance.vds_v must be strictly increasing", errors)
        self.assertIn("dynamic.capacitance coss_pf must be >= crss_pf at index 0", errors)

    def test_validate_requires_capacitance(self):
        errors = validate_project(DeviceProject.new("EMPTY"))
        self.assertIn("dynamic.capacitance is required for built-in VDMOS and ABM emitters", errors)


if __name__ == "__main__":
    unittest.main()
