from pathlib import Path
import tempfile
import unittest

from datasheet2spice.extractors.csv_curves import read_capacitance_csv, read_wpd_capacitance_csv_with_warnings


class ExtractorTests(unittest.TestCase):
    def test_capacitance_csv(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cap.csv"
            path.write_text("vds_v,ciss_pf,coss_pf,crss_pf\n1,10,5,2\n2,9,4,1\n", encoding="utf-8")
            data = read_capacitance_csv(path)
            self.assertEqual(data["vds_v"], [1.0, 2.0])
            self.assertEqual(data["crss_pf"], [2.0, 1.0])

    def test_webplotdigitizer_capacitance_csv(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "wpd.csv"
            path.write_text(
                "ciss,,coss,,crss,\n"
                "X,Y,X,Y,X,Y\n"
                "0.1,656.6,0.097,616.0,0.098,305.1\n"
                "0.2,650.6,0.195,587.0,0.196,295.8\n",
                encoding="utf-8",
            )
            imported = read_wpd_capacitance_csv_with_warnings(path)
            self.assertEqual(imported.data["vds_v"], [0.1, 0.2])
            self.assertEqual(imported.data["ciss_pf"], [656.6, 650.6])
            self.assertEqual(imported.data["coss_pf"], [616.0, 587.0])
            self.assertEqual(imported.data["crss_pf"], [305.1, 295.8])
            self.assertEqual(imported.warnings, [])

    def test_webplotdigitizer_capacitance_csv_warns_on_x_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "wpd.csv"
            path.write_text(
                "ciss,,coss,,crss,\n"
                "X,Y,X,Y,X,Y\n"
                "1,100,1.2,80,1,20\n"
                "2,90,2,70,2,10\n",
                encoding="utf-8",
            )
            imported = read_wpd_capacitance_csv_with_warnings(path)
            self.assertIn("coss X differs", imported.warnings[0])


if __name__ == "__main__":
    unittest.main()
