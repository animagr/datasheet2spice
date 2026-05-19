from pathlib import Path
import tempfile
import unittest

from datasheet2spice.schema import DeviceProject
from datasheet2spice.service import save_project_review
from datasheet2spice.webapp import INDEX_HTML, generate_model_bundle


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "demo_sic_mosfet" / "device.json"


class WebAppTests(unittest.TestCase):
    def test_generate_model_bundle(self):
        project = DeviceProject.load(DEMO)
        with tempfile.TemporaryDirectory() as td:
            result = generate_model_bundle(project, Path(td) / "session" / "generated", ["abm-basic"], ["ltspice"])
            self.assertTrue(result["ok"])
            names = {item["name"] for item in result["files"]}
            self.assertIn("DEMO_SIC_1200_abm_ltspice.lib", names)
            self.assertIn("DEMO_SIC_1200.device.json", names)
            self.assertIn("DEMO_SIC_1200_models.zip", names)
            self.assertIn("fit_evaluation.json", names)
            self.assertIn("evaluation", result)
            self.assertTrue((Path(td) / "parts" / "DEMO_SIC_1200" / "generated" / "DEMO_SIC_1200.device.json").exists())

    def test_save_project_review_writes_by_part_copy(self):
        project = DeviceProject.load(DEMO)
        with tempfile.TemporaryDirectory() as td:
            result = save_project_review(project, Path(td) / "session")
            self.assertTrue(result["ok"])
            paths = result["save_paths"]
            self.assertTrue(Path(paths["session_project"]).exists())
            self.assertTrue(Path(paths["part_project"]).exists())
            self.assertEqual(Path(paths["part_project"]).parent.name, "DEMO_SIC_1200")

    def test_local_workbench_has_wpd_import_control(self):
        self.assertIn("Import WPD CSV", INDEX_HTML)
        self.assertIn("/api/import-wpd-capacitance", INDEX_HTML)
        self.assertIn("wpdCsv", INDEX_HTML)


if __name__ == "__main__":
    unittest.main()
