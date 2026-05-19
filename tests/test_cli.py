from pathlib import Path
import tempfile
import unittest

import datasheet2spice.cli as cli
from datasheet2spice.plugins import registry


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "demo_sic_mosfet" / "device.json"
DIODE = ROOT / "examples" / "demo_sic_diode" / "device.json"
DIODE_CASE = ROOT / "validation" / "golden" / "demo_sic_diode.case.json"


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
            self.assertIn("DEMO_SIC_1200_abm_pspice.lib", paths)
            self.assertIn("DEMO_SIC_1200_vdmos_hspice.lib", paths)

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

    def test_import_wpd_capacitance_csv(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "device.json"
            csv = Path(td) / "wpd.csv"
            project.write_text(DEMO.read_text(encoding="utf-8"), encoding="utf-8")
            csv.write_text(
                "ciss,,coss,,crss,\n"
                "X,Y,X,Y,X,Y\n"
                "0.1,1000,0.1,900,0.1,300\n"
                "100,820,100,240,100,35\n",
                encoding="utf-8",
            )
            rc = cli.main(["import-wpd-capacitance-csv", str(project), str(csv)])
            self.assertEqual(rc, 0)
            text = project.read_text(encoding="utf-8")
            self.assertIn('"vds_v": [', text)
            self.assertIn('"ciss_pf": [', text)
            self.assertIn('"webplotdigitizer_capacitance_csv"', text)

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

    def test_score_case(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "score.json"
            rc = cli.main(["score-case", str(DIODE), str(DIODE_CASE), "--out", str(out)])
            self.assertEqual(rc, 0)
            self.assertIn('"status": "pass"', out.read_text(encoding="utf-8"))

    def test_benchmark_model_generation_only(self):
        with tempfile.TemporaryDirectory() as td:
            rc = cli.main(
                [
                    "benchmark-model",
                    str(DIODE),
                    "--out",
                    td,
                    "--model",
                    "diode-basic",
                    "--model",
                    "diode-abm-dynamic",
                    "--dialect",
                    "common",
                ]
            )
            self.assertEqual(rc, 0)
            report = Path(td) / "benchmark_report.json"
            self.assertTrue(report.exists())
            self.assertIn("diode-abm-dynamic", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
