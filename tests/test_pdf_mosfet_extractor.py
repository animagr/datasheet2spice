from pathlib import Path
import tempfile
import unittest

from datasheet2spice.extractors.pdf_evidence import render_pdf_evidence_images
from datasheet2spice.extractors.pdf_mosfet import extract_mosfet_project_from_pdf, extract_mosfet_project_from_text
from datasheet2spice.validate import validate_project


ROOT = Path(__file__).resolve().parents[1]
LOCAL_S4661 = ROOT / "TK-S4661_Rev.T17.2.pdf"


class PdfMosfetExtractorTests(unittest.TestCase):
    def test_extracts_common_table_values_from_text(self):
        text = """
        ROHM S4661 Datasheet
        Unit VDSS 1200V RDS(on) (Typ.) 11mohm ID *1 130A
        Recommended turn-on gate - source drive voltage
        VGS_on
        *5,6,7
        +18
        V
        VDS = 800V
        VGS = +18V / -2V
        Tvj = 25°C
        2.8
        3.8
        4.8
        Gate threshold voltage
        VGS (th)
        Tvj = 25°C
        -
        11.0
        13.8
        Static Drain - Source
        on - state resistance
        RDS(on)
        Gate input resistance
        RG
        -
        1
        -
        Transconductance
        gfs
        -
        47
        Input capacitance
        Ciss
        -
        7868
        -
        pF
        VGS = +18V / -2V
        209
        -
        pF
        Output capacitance
        Reverse transfer capacitance
        Crss
        -
        10
        -
        Total Gate charge
        Qg
        -
        307
        -
        101
        -
        Gate - Drain charge
        Qgd
        -
        45
        -
        Reverse recovery time
        trr
        -
        19
        -
        Reverse recovery charge
        Qrr
        -
        876
        -
        nC
        Peak reverse recovery current
        Irrm
        -
        74
        -
        """
        result = extract_mosfet_project_from_text(text, source="synthetic.pdf", fallback_part="S4661")
        project = result["project"]
        self.assertEqual(project.part_number, "S4661")
        self.assertEqual(project.data["ratings"]["vdss_v"], 1200.0)
        self.assertEqual(project.data["ratings"]["vgs_on_v"], 18.0)
        self.assertEqual(project.data["static"]["rds_on_mohm"]["25"], 11.0)
        self.assertEqual(project.data["dynamic"]["gate_charge"]["qgd_nc"], 45.0)
        self.assertEqual(validate_project(project), [])

    @unittest.skipUnless(LOCAL_S4661.exists(), "local confidential S4661 PDF is not in the repository")
    def test_local_s4661_pdf_smoke(self):
        result = extract_mosfet_project_from_pdf(LOCAL_S4661)
        project = result["project"]
        self.assertEqual(project.part_number, "S4661")
        self.assertEqual(project.data["ratings"]["vdss_v"], 1200.0)
        self.assertEqual(project.data["static"]["rds_on_mohm"]["25"], 11.0)
        caps = project.data["dynamic"]["capacitance"]
        idx = caps["vds_v"].index(800.0)
        self.assertAlmostEqual(caps["ciss_pf"][idx], 7869.87, places=1)
        self.assertGreaterEqual(len(result["tables"]), 3)
        self.assertEqual(result["curve_digitization"]["page"], 11)
        with tempfile.TemporaryDirectory() as td:
            evidence = render_pdf_evidence_images(
                LOCAL_S4661,
                Path(td),
                "/assets/test",
                findings=result["findings"],
                tables=result["tables"],
                curve_digitization=result["curve_digitization"],
            )
        field_evidence = [item for item in evidence if item.get("kind") == "field_finding"]
        self.assertGreaterEqual(len(field_evidence), 12)
        self.assertTrue(any(item.get("field") == "dynamic.capacitance.ciss_pf" for item in field_evidence))
        self.assertEqual(validate_project(project), [])


if __name__ == "__main__":
    unittest.main()
