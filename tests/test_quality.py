import json
from pathlib import Path
import tempfile
import unittest

from datasheet2spice.quality import (
    benchmark_project_models,
    load_manifest,
    render_score_report,
    score_project_against_case,
)
from datasheet2spice.schema import DeviceProject


ROOT = Path(__file__).resolve().parents[1]
DIODE = ROOT / "examples" / "demo_sic_diode" / "device.json"
DIODE_CASE = ROOT / "validation" / "golden" / "demo_sic_diode.case.json"
PUBLIC_MANIFEST = ROOT / "validation" / "public_datasheet_cases.json"


class QualityTests(unittest.TestCase):
    def test_score_project_against_case_passes_demo(self):
        project = DeviceProject.load(DIODE)
        case = json.loads(DIODE_CASE.read_text(encoding="utf-8"))
        result = score_project_against_case(project, case)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["passed_fields"], result["total_fields"])
        report = render_score_report(result)
        self.assertIn("Extraction Score", report)
        self.assertIn("dynamic.reverse_recovery.qrr_nc", report)

    def test_score_project_against_case_flags_bad_value(self):
        project = DeviceProject.load(DIODE)
        project.data["ratings"]["vrrm_v"] = 500
        case = json.loads(DIODE_CASE.read_text(encoding="utf-8"))
        result = score_project_against_case(project, case)
        self.assertEqual(result["status"], "fail_required")
        self.assertIn("ratings.vrrm_v", result["required_failed"])

    def test_benchmark_project_models_records_generation(self):
        project = DeviceProject.load(DIODE)
        with tempfile.TemporaryDirectory() as td:
            result = benchmark_project_models(
                project,
                td,
                models=["diode-basic", "diode-abm-dynamic"],
                dialects=["common", "ltspice"],
            )
            self.assertEqual(result["summary"]["failed_simulations"], 0)
            self.assertEqual(result["summary"]["simulated_decks"], 0)
            self.assertTrue((Path(td) / "benchmark_report.json").exists())
            names = {Path(record["path"]).name for record in result["records"]}
            self.assertIn("DEMO_DIODE_650_diode_abm_ltspice.lib", names)
            self.assertIn("DEMO_DIODE_650_reverse_recovery_diode_abm_ltspice.cir", names)

    def test_public_manifest_has_required_metadata(self):
        manifest = load_manifest(PUBLIC_MANIFEST)
        self.assertEqual(manifest["schema"], "datasheet2spice-validation-v1")
        self.assertGreaterEqual(len(manifest["cases"]), 4)
        for case in manifest["cases"]:
            with self.subTest(case=case["id"]):
                self.assertIn("vendor", case)
                self.assertIn("component_profile", case)
                self.assertIn("datasheet_url", case)
                self.assertIn("layout_tags", case)


if __name__ == "__main__":
    unittest.main()
