import unittest

from datasheet2spice.units import parse_number


class UnitTests(unittest.TestCase):
    def test_parse_engineering_suffixes(self):
        self.assertAlmostEqual(parse_number("11mΩ"), 0.011)
        self.assertAlmostEqual(parse_number("7868p"), 7868e-12)
        self.assertAlmostEqual(parse_number("1.2k"), 1200)


if __name__ == "__main__":
    unittest.main()
