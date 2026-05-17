from pathlib import Path
import tempfile
import unittest

from datasheet2spice.extractors.csv_curves import read_capacitance_csv


class ExtractorTests(unittest.TestCase):
    def test_capacitance_csv(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cap.csv"
            path.write_text("vds_v,ciss_pf,coss_pf,crss_pf\n1,10,5,2\n2,9,4,1\n", encoding="utf-8")
            data = read_capacitance_csv(path)
            self.assertEqual(data["vds_v"], [1.0, 2.0])
            self.assertEqual(data["crss_pf"], [2.0, 1.0])


if __name__ == "__main__":
    unittest.main()
