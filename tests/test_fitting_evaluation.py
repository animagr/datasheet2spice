from pathlib import Path
import unittest

from datasheet2spice.evaluation import evaluate_project_model
from datasheet2spice.fitting import fit_project_parameters
from datasheet2spice.schema import DeviceProject


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "demo_sic_mosfet" / "device.json"


class FittingEvaluationTests(unittest.TestCase):
    def test_fit_project_parameters_adds_model_fits(self):
        project = DeviceProject.load(DEMO)
        result = fit_project_parameters(project)
        self.assertEqual({item["model"] for item in result["fits"]}, {"vdmos-static-fast", "abm-basic"})
        self.assertIn("fits", project.data["models"])
        self.assertIn("KID", project.data["models"]["fits"]["abm-basic"]["parameters"])

    def test_evaluate_project_model_scores_demo(self):
        project = DeviceProject.load(DEMO)
        result = evaluate_project_model(project)
        self.assertGreaterEqual(result["overall_score"], 60)
        self.assertIn(result["grade"], {"starter", "reviewable"})


if __name__ == "__main__":
    unittest.main()
