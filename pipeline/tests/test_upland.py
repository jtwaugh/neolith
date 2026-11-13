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



D = {"box": [-10.0, 36.0, 60.0, 56.0], "max_elevation": 300.0, "min_warm": 20.0,
     "steppe_forest_precip": 600.0, "woodland_precip": 700.0,
     "apply_to": ["Temperate Forest", "Boreal Forest", "Woodlands"]}


class DryLowland(unittest.TestCase):
    def test_classes(self):
        f = paleobiome.dry_lowland_class
        self.assertEqual(f("Temperate Forest", 500.0, 22.0, D), "Steppe-Forest")
        self.assertEqual(f("Temperate Forest", 650.0, 22.0, D), "Woodlands")
        self.assertEqual(f("Woodlands", 650.0, 22.0, D), "")           # already open woodland
        self.assertEqual(f("Temperate Forest", 800.0, 22.0, D), "")    # wet enough
        self.assertEqual(f("Temperate Forest", 500.0, 18.0, D), "")    # summers too cool
        self.assertEqual(f("Grassland", 500.0, 22.0, D), "")           # only forest changes

    def test_box_and_elevation(self):
        c = np.array([[20.0, 47.0], [20.0, 47.0], [70.0, 47.0]])
        t = np.array(["Temperate Forest"] * 3, dtype=object)
        clim = np.array([[500.0, 22.0]] * 3)
        out, n = paleobiome.apply_dry_lowland(t, np.array([100.0, 900.0, 100.0]), c, clim, D)
        self.assertEqual(out.tolist(), ["Steppe-Forest", "Temperate Forest", "Temperate Forest"])
        self.assertEqual(n, 1)
        self.assertEqual(t[0], "Temperate Forest")



class ColdTemperateAndOverrides(unittest.TestCase):
    def test_cold_temperate(self):
        c = np.array([[40.0, 55.0]] * 4)
        t = np.array(["Temperate Forest", "Temperate Forest", "Temperate Forest", "Grassland"], dtype=object)
        clim = np.array([[500.0, -20.0], [800.0, -20.0], [500.0, -10.0], [500.0, -20.0]])
        cfg = {"box": [-10, 36, 66, 64], "max_coldest": -16.0, "steppe_forest_precip": 600.0, "max_elevation": 600.0}
        out, n = paleobiome.apply_cold_temperate(t, c, clim, cfg, np.array([100.0, 100.0, 100.0, 100.0]))
        self.assertEqual(out.tolist(), ["Steppe-Forest", "Boreal Forest", "Temperate Forest", "Grassland"])
        self.assertEqual(n, 2)
        high, _ = paleobiome.apply_cold_temperate(t, c, clim, cfg, np.array([900.0] * 4))
        self.assertEqual(high.tolist(), t.tolist())

    def test_overrides_years_box_elevation(self):
        c = np.array([[-2.0, 37.0], [-2.0, 37.0], [10.0, 50.0]])
        t = np.array(["Temperate Forest", "Water", "Temperate Forest"], dtype=object)
        rules = [{"boxes": [[-3.1, 36.6, -1.6, 37.5]], "years": [-10000, -6000], "to": "Semi-Desert",
                  "max_elevation": 800.0}]
        elev = np.array([100.0, 0.0, 100.0])
        out, n = paleobiome.apply_overrides(t, c, elev, rules, -7000)
        self.assertEqual(out.tolist(), ["Semi-Desert", "Water", "Temperate Forest"])
        same, n2 = paleobiome.apply_overrides(t, c, elev, rules, -5000)
        self.assertEqual((same.tolist(), n2), (t.tolist(), 0))
        hi, _ = paleobiome.apply_overrides(t, c, np.array([1000.0, 0.0, 100.0]), rules, -7000)
        self.assertEqual(hi[0], "Temperate Forest")



class ForestType(unittest.TestCase):
    F = {"box": [-10, 42, 66, 70], "boreal_coldest": -16.0, "boreal_warm": 10.5,
         "temperate_coldest": -8.0, "mixed_from": -6500, "mixed_warm": 16.5}

    def test_classes(self):
        f = lambda c, w, y: paleobiome.forest_type(np.array([c]), np.array([w]), y, self.F)[0]
        self.assertEqual(f(-20.0, 18.0, -5000), "Boreal Forest")      # too cold
        self.assertEqual(f(-5.0, 9.0, -5000), "Boreal Forest")        # summers too cool
        self.assertEqual(f(-5.0, 18.0, -9000), "Temperate Forest")    # mild winters
        self.assertEqual(f(-12.0, 18.0, -5000), "Temperate Forest")   # mixed band, broadleaf there
        self.assertEqual(f(-12.0, 18.0, -8000), "Boreal Forest")      # mixed band, before broadleaf
        self.assertEqual(f(-12.0, 15.0, -5000), "Boreal Forest")      # mixed band, cool summers

    def test_latitude_cap(self):
        F = {**self.F, "temperate_max_lat": 60.5}
        out = paleobiome.forest_type(np.array([-5.0, -5.0]), np.array([18.0, 18.0]), -5000, F, np.array([55.0, 62.0]))
        self.assertEqual(out.tolist(), ["Temperate Forest", "Boreal Forest"])

    def test_only_forest_in_box(self):
        t = np.array(["Boreal Forest", "Grassland", "Boreal Forest"], dtype=object)
        c = np.array([[20.0, 50.0], [20.0, 50.0], [100.0, 50.0]])
        out, n = paleobiome.apply_forest_type(t, c, np.array([[-5.0, 18.0]] * 3), self.F, -5000)
        self.assertEqual(out.tolist(), ["Temperate Forest", "Grassland", "Boreal Forest"])
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
