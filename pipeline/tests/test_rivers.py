import os
import tempfile
import unittest

import numpy as np

from pipeline import rivers
from pipeline.raster import Affine
from pipeline.tests.test_pipeline import make_grid


class States(unittest.TestCase):
    def test_step_function_absent_before_first_key(self):
        at = rivers._state_fn({"-8500": "seasonal", "-5300": "absent"})
        self.assertEqual([at(-9000), at(-8500), at(-6000), at(-5000)],
                         ["absent", "seasonal", "seasonal", "absent"])

    def test_unknown_state_rejected(self):
        with self.assertRaises(ValueError):
            rivers._state_fn({"-9000": "dry"})


class Geometry(unittest.TestCase):
    def test_simplify_keeps_corners_drops_collinear(self):
        pts = np.array([[0, 0], [1, 0], [2, 0], [2, 1], [2, 2]], float)
        self.assertEqual(rivers.simplify(pts, 0.01).tolist(), [[0, 0], [2, 0], [2, 2]])

    def test_resample_spacing(self):
        out = rivers.resample(np.array([[0, 0], [1, 0]], float), 0.1)
        self.assertEqual(len(out), 11)
        self.assertTrue(np.allclose(np.diff(out[:, 0]), 0.1))

    def test_hex_locator_matches_point_in_hex(self):
        g = make_grid(5, 4)
        loc = rivers.HexLocator(g)
        self.assertEqual(loc.locate(g.centres).tolist(), list(range(len(g))))
        self.assertEqual(loc.locate(np.array([[50.0, 50.0]])).tolist(), [-1])

    def test_shelf_path_runs_downhill_to_the_sea(self):
        # A ramp from +5 m at the west edge to -100 m at the east edge.
        z = np.tile(np.linspace(5, -100, 40), (20, 1)).astype(np.float32)
        tf = Affine(0.1, -0.1, 0.0, 2.0)
        path = rivers.shelf_path((0.0, 1.0), z, tf, level=-50.0, window=5.0)
        self.assertGreater(len(path), 5)
        self.assertAlmostEqual(path[0][0], 0.0)
        cols = np.rint(tf.col(path[:, 0])).astype(int)
        self.assertTrue(np.all(np.diff(cols) >= 0))
        self.assertLess(z[0, cols[-1]], -50.0)
        self.assertGreaterEqual(z[0, cols[-2]], -50.0)


class Trace(unittest.TestCase):
    def reaches(self):
        # 1 -> 2 -> 3 -> outlet (sea); 4 -> 2 is a tributary.
        line = lambda *p: np.array(p, float)
        return {"id": np.array([1, 2, 3, 4]), "next": np.array([2, 3, 0, 2]),
                "upland": np.array([10.0, 30.0, 40.0, 5.0]),
                "endorheic": np.array([0, 0, 0, 0]),
                "coords": [line([0, 0], [1, 0]), line([1, 0], [2, 0]),
                           line([2, 0], [3, 0]), line([1, 1], [1, 0])]}

    def test_traces_to_the_sea(self):
        r = self.reaches()
        pts, sea, used = rivers.trace(r, 0)
        self.assertTrue(sea)
        self.assertEqual(pts.tolist(), [[0, 0], [1, 0], [2, 0], [3, 0]])
        self.assertEqual(used, [0, 1, 2])

    def test_tributary_stops_at_drawn_river(self):
        r = self.reaches()
        pts, sea, used = rivers.trace(r, 3, stop={0, 1, 2})
        self.assertFalse(sea)
        self.assertEqual(pts.tolist(), [[1, 1], [1, 0], [1, 0]])

    def test_nearest_reach_respects_min_upland(self):
        r = self.reaches()
        self.assertEqual(rivers.nearest_reach(r, (1.0, 0.9))[0], 3)
        self.assertEqual(rivers.nearest_reach(r, (1.0, 0.9), min_upland=20)[0], 1)


class Build(unittest.TestCase):
    def test_lower_course_drowns_with_the_sea(self):
        g = make_grid(8, 1)
        n = len(g)
        years = [-10000, -9000, -8000]
        # The sea creeps west: the last 1, 3 and 5 hexes are Water.
        terrain = {}
        for k, y in enumerate(years):
            t = np.array(["Plains"] * n, dtype=object)
            t[n - (1 + 2 * k):] = "Water"
            terrain[y] = t
        xs = g.centres[:, 0]
        cat = ('[[river]]\nkey = "r"\nname = "R"\nsize = 2\n'
               f'points = [[{xs[0]}, {g.centres[0, 1]}], [{xs[-1]}, {g.centres[0, 1]}]]\n'
               'shelf = false\nstate = { "-10000" = "perennial" }\n')
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "rivers.toml")
            with open(path, "w") as f:
                f.write(cat)
            cfg = {"rivers": {"catalogue": path, "geoglows": {}, "sample": 0.05,
                              "simplify": 0.01, "hex_min_length": 0.2, "snap_max": 1,
                              "shelf_window": 1},
                   "sea": {"curve": [[-12000, -60.0], [0, 0.0]]}}
            segs, hex_river = rivers.build(cfg, g, terrain, None, None, years, log=lambda m: None)
        # Upstream to downstream: one stretch that always flows, then the
        # stretch drowned at -8000, then the one at the mouth drowned first.
        self.assertEqual([s["state"] for s in segs],
                         [{"-10000": "perennial"},
                          {"-10000": "perennial", "-8000": "absent"},
                          {"-10000": "perennial", "-9000": "absent"}])
        self.assertTrue(np.allclose(segs[0]["points"][0], g.centres[0]))
        # Hexes: river class 2 on dry hexes it crosses; none at sea.
        self.assertEqual(hex_river[-10000][0], 2)
        self.assertEqual(hex_river[-8000][n - 1], 0)
        self.assertEqual(hex_river[-8000][n - 6], 2)
        self.assertEqual(hex_river[-8000][n - 4], 0)


if __name__ == "__main__":
    unittest.main()
