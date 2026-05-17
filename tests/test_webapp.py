from pathlib import Path
import tempfile
import unittest

from datasheet2spice.schema import DeviceProject
from datasheet2spice.webapp import generate_model_bundle


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
            self.assertIn("DEMO_SIC_1200_models.zip", names)
            self.assertIn("fit_evaluation.json", names)
            self.assertIn("evaluation", result)


if __name__ == "__main__":
    unittest.main()
