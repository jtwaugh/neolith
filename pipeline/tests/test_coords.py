import unittest

import numpy as np

from pipeline import coords
from pipeline.raster import Affine
from pipeline.tests.test_pipeline import make_grid


def site(name, lon, lat, hex_id, start=-6000, end=-5000):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"name": name, "hex": hex_id, "founding": start, "occupation": [[start, end]]}}


class Apply(unittest.TestCase):
    def setUp(self):
        self.g = make_grid(4, 4)
        c = self.g.centres
        self.c = c

    def test_move_drop_submerged(self):
        a = site("A", 0.0, 0.0, 1)
        b = site("B", 5.0, 5.0, 2)
        dup = site("A", 9.0, 9.0, 3)
        tx, ty = self.c[5]
        fixes = [{"name": "A", "was": [0.0, 0.0], "to": [float(tx), float(ty)], "source": "x", "note": ""},
                 {"name": "A", "was": [9.0, 9.0], "drop": True, "source": "x", "note": ""},
                 {"name": "B", "was": [5.0, 5.0], "submerged": True, "source": "x", "note": ""}]
        out, applied, unmatched = coords.apply([a, b, dup], fixes, self.g)
        self.assertEqual([f["properties"]["name"] for f in out], ["A", "B"])
        self.assertEqual(out[0]["properties"]["hex"], int(self.g.ids[5]))
        self.assertEqual(out[0]["properties"]["moved_from"], [0.0, 0.0])
        self.assertTrue(out[1]["properties"]["submerged"])
        self.assertEqual(unmatched, [])
        self.assertEqual(a["geometry"]["coordinates"], [0.0, 0.0])      # input untouched

    def test_unmatched_reported(self):
        _, _, unmatched = coords.apply([site("A", 0, 0, 1)], [{"name": "A", "was": [3, 3], "drop": True}], self.g)
        self.assertEqual(unmatched, ["A"])


class Audit(unittest.TestCase):
    def test_reasons(self):
        g = make_grid(5, 5)
        n = len(g)
        sea = np.full(n, "Water", dtype=object)
        land = np.full(n, "Grassland", dtype=object)
        terrain = {-6000: sea, -5900: sea}
        # A raster that is -500 m everywhere except a dry column at lon 2.
        arr = np.full((20, 20), -500.0)
        arr[:, 2] = 20.0
        tf = Affine(1.0, -1.0, 0.0, 10.0)
        feats = [site("Deep cave", 8.0, 5.0, 13), site("Twin site", 8.0, 5.0, 13), site("Twin site", 15.0, 5.0, 13)]
        rows = {r["name"] + str(r["lon"]): r for r in coords.audit(feats, terrain, g, arr, tf)}
        r = rows["Deep cave8.0"]
        self.assertIn("at_sea", r["reasons"])
        self.assertIn("offshore", r["reasons"])
        self.assertIn("same_name_far", rows["Twin site8.0"]["reasons"])
        dry = {-6000: land, -5900: land}
        basin = np.full((20, 20), -200.0)                     # below sea level, on dry land
        self.assertEqual(coords.audit([site("Dead Sea shore", 8.0, 5.0, 13)], dry, g, basin, tf), [])
        abyss = coords.audit([site("Abyss", 8.0, 5.0, 13)], dry, g, arr, tf)   # -500 m: no dry land that low
        self.assertIn("at_sea", abyss[0]["reasons"])


if __name__ == "__main__":
    unittest.main()
