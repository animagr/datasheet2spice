import json
from pathlib import Path
import tempfile
import unittest

from datasheet2spice.quality import (
    benchmark_project_models,
    evaluate_switching_measurements,
    instrument_switching_benchmark_deck,
    load_manifest,
    parse_ltspice_measurements,
    render_score_report,
    score_project_against_case,
)
from datasheet2spice.schema import DeviceProject


ROOT = Path(__file__).resolve().parents[1]
DIODE = ROOT / "examples" / "demo_sic_diode" / "device.json"
MOSFET = ROOT / "examples" / "demo_sic_mosfet" / "device.json"
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

    def test_switching_measurement_parser_accepts_ltspice_layouts(self):
        log = """
        d2s_vg_on_avg: AVG(v(gate))=1.65e+001 FROM=5e-006 TO=2e-005
        Measurement: d2s_il_on_avg
          avg(i(lload))=32.5 at 1.2e-005
        d2s_vds_off_min=7.80e+002
        d2s_scaled: value=1.2meg
        """
        measurements = parse_ltspice_measurements(log)
        self.assertAlmostEqual(measurements["d2s_vg_on_avg"], 16.5)
        self.assertAlmostEqual(measurements["d2s_il_on_avg"], 32.5)
        self.assertAlmostEqual(measurements["d2s_vds_off_min"], 780.0)
        self.assertAlmostEqual(measurements["d2s_scaled"], 1.2e6)

    def test_switching_metrics_flag_non_opening_device(self):
        project = DeviceProject.load(MOSFET)
        result = evaluate_switching_measurements(
            {
                "d2s_vg_on_avg": 18.0,
                "d2s_vg_off_avg": -2.0,
                "d2s_il_on_avg": 0.2,
                "d2s_vds_on_avg": 790.0,
                "d2s_vds_reon_max": 5.0,
                "d2s_vds_off_max": 820.0,
                "d2s_vds_off_min": 780.0,
            },
            project,
        )
        self.assertEqual(result["status"], "fail")
        self.assertIn("device_did_not_build_load_current", result["hard_flags"])
        self.assertIn("device_did_not_pull_drain_low", result["hard_flags"])

    def test_switching_metrics_flag_bad_second_turn_on(self):
        project = DeviceProject.load(MOSFET)
        result = evaluate_switching_measurements(
            {
                "d2s_vg_on_avg": 18.0,
                "d2s_vg_off_avg": -2.0,
                "d2s_il_on_avg": 39.0,
                "d2s_vds_on_avg": 0.8,
                "d2s_vds_reon_max": 802.0,
                "d2s_vds_off_max": 820.0,
                "d2s_vds_off_min": 780.0,
            },
            project,
        )
        self.assertEqual(result["status"], "fail")
        self.assertIn("second_turn_on_did_not_pull_drain_low", result["hard_flags"])

    def test_benchmark_can_instrument_mosfet_switching_decks(self):
        project = DeviceProject.load(MOSFET)
        with tempfile.TemporaryDirectory() as td:
            result = benchmark_project_models(
                project,
                td,
                models=["abm-basic"],
                dialects=["ltspice"],
                measure_switching=True,
            )
            deck = next(record for record in result["records"] if record["kind"] == "deck")
            self.assertTrue(deck["switching_instrumented"])
            self.assertEqual(result["summary"]["switching_checks"], 0)
            text = Path(deck["path"]).read_text(encoding="utf-8")
            self.assertIn("d2s_vds_off_max", text)
            self.assertEqual(text.count("datasheet2spice switching benchmark metrics"), 1)
            self.assertEqual(
                instrument_switching_benchmark_deck(text).count("datasheet2spice switching benchmark metrics"),
                1,
            )

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
