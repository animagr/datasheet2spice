from pathlib import Path
import tempfile
import unittest

import datasheet2spice.cli as cli
from datasheet2spice.plugins import registry


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "demo_sic_mosfet" / "device.json"


class CliTests(unittest.TestCase):
    def test_validate(self):
        self.assertEqual(cli.main(["validate", str(DEMO)]), 0)

    def test_emit_all(self):
        with tempfile.TemporaryDirectory() as td:
            rc = cli.main(["emit", str(DEMO), "--out", td, "--all", "--dialect", "all"])
            self.assertEqual(rc, 0)
            paths = {p.name for p in Path(td).iterdir()}
            self.assertIn("DEMO_SIC_1200_abm_ltspice.lib", paths)
            self.assertIn("DEMO_SIC_1200_vdmos_ltspice.lib", paths)

    def test_import_capacitance_csv(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "device.json"
            csv = Path(td) / "caps.csv"
            project.write_text(DEMO.read_text(encoding="utf-8"), encoding="utf-8")
            csv.write_text(
                "vds_v,ciss_pf,coss_pf,crss_pf\n"
                "0,1000,900,300\n"
                "100,820,240,35\n",
                encoding="utf-8",
            )
            rc = cli.main(["import-capacitance-csv", str(project), str(csv)])
            self.assertEqual(rc, 0)
            text = project.read_text(encoding="utf-8")
            self.assertIn('"vds_v": [', text)
            self.assertIn('"digitized_capacitance_csv"', text)

    def test_emit_accepts_plugin_model_id(self):
        class FakeEmitter:
            name = "fake-model"

            def emit(self, project, dialect):
                return {"fake.lib": f"* {project.model_name} {dialect}\n"}

        original = cli.load_plugins
        try:
            cli.load_plugins = lambda: registry.register_emitter(FakeEmitter()) or []
            with tempfile.TemporaryDirectory() as td:
                rc = cli.main(["emit", str(DEMO), "--out", td, "--model", "fake-model", "--dialect", "common"])
                self.assertEqual(rc, 0)
                self.assertTrue((Path(td) / "fake.lib").exists())
        finally:
            cli.load_plugins = original
            registry.emitters.pop("fake-model", None)


if __name__ == "__main__":
    unittest.main()
