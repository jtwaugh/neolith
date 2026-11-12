import unittest

import numpy as np

from pipeline import paleobiome

U = {"box": [26.0, 30.0, 62.0, 43.5], "min_elevation": 700.0, "max_coldest": -2.0, "min_precip": 200.0,
     "woodland_from": -7000, "woodland_precip": 350.0, "forest_steppe_precip": 225.0}


class UplandClass(unittest.TestCase):
    def test_classes(self):
        self.assertEqual(paleobiome.upland_class(-5000, 400, -6, U), "Woodlands")
        self.assertEqual(paleobiome.upland_class(-8000, 400, -6, U), "Steppe-Forest")   # before the woodland
        self.assertEqual(paleobiome.upland_class(-5000, 300, -6, U), "Steppe-Forest")
        self.assertEqual(paleobiome.upland_class(-5000, 210, -6, U), "Grassland")
        self.assertEqual(paleobiome.upland_class(-5000, 150, -6, U), "")                 # desert: left alone
        self.assertEqual(paleobiome.upland_class(-5000, 700, 1, U), "")                  # mild winter: Mediterranean
        self.assertEqual(paleobiome.upland_class(-5000, np.nan, -6, U), "")


class ApplyUpland(unittest.TestCase):
    def test_only_upland_gaps_in_the_box(self):
        t = np.array(["Chaparral", "Chaparral", "Chaparral", "Alpine", "Chaparral"], dtype=object)
        gap = np.array([True, False, True, True, True])
        elev = np.array([1500, 1500, 300, 3000, 1500.0])
        centres = np.array([[45, 35], [45, 35], [45, 35], [45, 35], [10, 35.0]])
        clim = np.full((5, 2), [400.0, -6.0])
        out, n = paleobiome.apply_upland(t, gap, elev, centres, clim, -5000, U)
        self.assertEqual(list(out), ["Woodlands", "Chaparral", "Chaparral", "Alpine", "Chaparral"])
        self.assertEqual(n, 1)
        self.assertEqual(t[0], "Chaparral")                   # input untouched


if __name__ == "__main__":
    unittest.main()
