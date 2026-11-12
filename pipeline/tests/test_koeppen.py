import os
import re
import unittest

import numpy as np

from pipeline import koeppen
from pipeline.tests.test_pipeline import make_grid

# Rough monthly climatologies (Jan..Dec): temperature °C, precipitation mm.
STATIONS = {
    "Cfb": ([5, 5, 7, 9, 13, 16, 18, 18, 15, 11, 8, 5],
            [55, 40, 42, 44, 49, 45, 45, 50, 49, 69, 59, 55], 51.5),        # London
    "BWh": ([14, 15, 18, 21, 25, 27, 28, 28, 26, 24, 19, 15],
            [5, 4, 4, 1, 0, 0, 0, 0, 0, 1, 3, 6], 30.0),                    # Cairo
    "Csa": ([8, 9, 11, 14, 18, 22, 25, 25, 21, 17, 12, 9],
            [70, 75, 60, 65, 40, 20, 15, 25, 70, 110, 110, 85], 41.9),      # Rome
    "Dfb": ([-7, -6, -1, 6, 13, 17, 19, 17, 11, 5, -1, -5],
            [50, 40, 35, 37, 50, 80, 85, 80, 65, 60, 55, 50], 55.75),       # Moscow
    "Af": ([27, 27, 28, 28, 28, 28, 28, 28, 28, 28, 27, 27],
           [240, 160, 180, 170, 170, 130, 150, 150, 170, 190, 250, 290], 1.3),  # Singapore
    "Dwd": ([-39, -35, -22, -7, 6, 15, 19, 15, 6, -8, -28, -38],
            [3, 3, 3, 8, 15, 30, 40, 40, 25, 15, 6, 4], 62.0),              # Yakutsk-like
    "ET": ([-20, -20, -18, -12, -3, 2, 5, 4, 0, -7, -14, -18],
           [20, 20, 20, 15, 15, 20, 30, 35, 30, 25, 20, 20], 70.0),
    "EF": ([-30] * 6 + [-5] * 6, [10] * 12, 80.0),
}


def classify_one(t, p, lat):
    T = np.array(t, float).reshape(12, 1)
    P = np.array(p, float).reshape(12, 1)
    k, h = koeppen.classify(T, P, np.array([lat]))
    return koeppen.CODES[k[0]], koeppen.CODES[h[0]]


class Classify(unittest.TestCase):
    def test_stations(self):
        for code, (t, p, lat) in STATIONS.items():
            with self.subTest(code):
                self.assertEqual(classify_one(t, p, lat)[0], code)

    def test_humid_class_ignores_aridity(self):
        k, h = classify_one(*STATIONS["BWh"])
        self.assertEqual(k, "BWh")
        self.assertEqual(h[0], "C")  # warm, frost-free, but no B test

    def test_southern_hemisphere_flips_seasons(self):
        # Rome's seasons shifted by six months, at 41.9 S: still Csa.
        t, p, lat = STATIONS["Csa"]
        self.assertEqual(classify_one(t[6:] + t[:6], p[6:] + p[:6], -lat)[0], "Csa")
        # Unshifted at 41.9 S, the dry season is winter: Cw, not Cs.
        self.assertTrue(classify_one(t, p, -lat)[0].startswith("C"))
        self.assertNotEqual(classify_one(t, p, -lat)[0], "Csa")

    def test_missing_data(self):
        T = np.full((12, 2), 10.0)
        P = np.full((12, 2), 50.0)
        T[3, 1] = np.nan
        k, h = koeppen.classify(T, P, np.array([45.0, 45.0]))
        self.assertEqual(k[1], koeppen.NODATA)
        self.assertEqual(h[1], koeppen.NODATA)
        self.assertGreater(k[0], 0)


class Nudge(unittest.TestCase):
    I = koeppen.INDEX

    def test_steps_up_never_down(self):
        I = self.I
        k = np.array([I["BWh"], I["BWk"], I["BWh"], I["BSh"], I["Cfb"], I["BWh"]])
        humid = np.array([I["Aw/As"], I["Cfb"], I["Aw/As"], I["Aw/As"], I["Cfb"], I["Aw/As"]])
        terrain = np.array(["Savannah", "Grassland", "Tropical Forest", "Extreme Desert",
                            "Extreme Desert", "Land"])
        wanted = {"Savannah": "BS", "Grassland": "BS", "Tropical Forest": "humid"}
        out, nudged = koeppen.nudge(k, humid, terrain, wanted)
        self.assertEqual([koeppen.CODES[v] for v in out],
                         ["BSh", "BSk", "Aw/As", "BSh", "Cfb", "BWh"])
        self.assertEqual(nudged.tolist(), [True, True, True, False, False, False])


class Align(unittest.TestCase):
    def test_water_ocean_and_exposed_land(self):
        g = make_grid(3, 1)
        I = koeppen.INDEX
        k = np.array([I["Cfb"], koeppen.OCEAN, I["Cfb"]])
        terrain = np.array(["Temperate Forest", "Grassland", "Water"])
        out = koeppen.align(k, terrain, g.neighbours)
        self.assertEqual([koeppen.CODES[v] for v in out], ["Cfb", "Cfb", "Ocean"])
        self.assertEqual(out[2], koeppen.OCEAN)

    def test_force_and_missing(self):
        g = make_grid(2, 1)
        k = np.array([koeppen.NODATA, koeppen.NODATA])
        out = koeppen.align(k, np.array(["Ice", "Grassland"]), g.neighbours, {"Ice": "EF"})
        # EF counts as a land neighbour, so the gap takes it.
        self.assertEqual([koeppen.CODES[v] for v in out], ["EF", "EF"])
        out = koeppen.align(k, np.array(["Water", "Grassland"]), g.neighbours)
        self.assertEqual(out.tolist(), [koeppen.OCEAN, koeppen.MISSING])

    def test_isolated_land_takes_nearest(self):
        g = make_grid(4, 1)
        I = koeppen.INDEX
        k = np.array([I["Dfc"], koeppen.OCEAN, koeppen.OCEAN, koeppen.NODATA])
        terrain = np.array(["Boreal Forest", "Water", "Water", "Plains"])
        out = koeppen.align(k, terrain, g.neighbours, centres=g.centres)
        self.assertEqual([koeppen.CODES[v] for v in out], ["Dfc", "Ocean", "Ocean", "Dfc"])

    def test_codes(self):
        self.assertEqual(koeppen.codes([0, 3, 31]).tolist(), ["Ocean", "Aw/As", "missingno"])


class CodeTable(unittest.TestCase):
    def test_matches_rust(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "neolith-rs", "crates",
                            "core", "src", "values.rs")
        if not os.path.exists(path):
            self.skipTest("neolith-rs not present")
        with open(path) as f:
            src = f.read()
        body = re.search(r"KOEPPEN_CODES: \[&str; \d+\] = \[(.*?)\];", src, re.S).group(1)
        self.assertEqual(re.findall(r'"([^"]+)"', body), koeppen.CODES)


if __name__ == "__main__":
    unittest.main()


class Lapse(unittest.TestCase):
    def test_at_hexes_shifts_temperature_only(self):
        from pipeline.raster import Affine
        g = make_grid(2, 1)
        tf = Affine(0.25, -0.25, -0.625, 0.625)
        t, p, _ = STATIONS["Cfb"]
        T = np.broadcast_to(np.array(t, float)[:, None, None], (12, 6, 9)).copy()
        P = np.broadcast_to(np.array(p, float)[:, None, None], (12, 6, 9)).copy()
        g.centres[:, 1] = 51.5  # summer is Apr-Sep in the north
        k, _ = koeppen.at_hexes(g, T, P, tf, np.array([0.0, -0.0065 * 2500]))
        self.assertEqual([koeppen.CODES[v] for v in k], ["Cfb", "ET"])
