import os
import tomllib
import unittest

from pipeline import isostasy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Isostasy(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "pipeline", "config.toml"), "rb") as f:
            self.cfg = tomllib.load(f)["isostasy"]

    def test_fits_the_dated_shorelines(self):
        for name, lon, lat, age, observed in self.cfg["calibration"]:
            year = 1950 - age * 1000
            model = float(isostasy.uplift(lon, lat, year, self.cfg))
            self.assertLessEqual(abs(model - observed), self.cfg["tolerance"],
                                 f"{name}: model {model:.0f} m, observed {observed:.0f} m")

    def test_no_uplift_today_or_outside_the_dome(self):
        self.assertAlmostEqual(float(isostasy.uplift(18.4, 63.1, 1950, self.cfg)), 0.0)
        self.assertEqual(float(isostasy.uplift(2.0, 48.0, -9000, self.cfg)), 0.0)
        # Present rates in the right range: Gulf of Bothnia vs Stockholm.
        self.assertGreater(float(isostasy.rate(19.5, 63.5, self.cfg)), 8.0)
        self.assertTrue(3.5 < float(isostasy.rate(18.07, 59.33, self.cfg)) < 6.5)


if __name__ == "__main__":
    unittest.main()
