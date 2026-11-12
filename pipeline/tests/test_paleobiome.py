import os
import tempfile
import unittest

import numpy as np

from pipeline import compose, paleobiome
from pipeline.raster import Affine
from pipeline.tests.test_pipeline import make_grid


class YearMapping(unittest.TestCase):
    def test_bce_to_nearest_bp_slice(self):
        bp = np.array([13000, 12000, 11000, 10000, 9000, 8000, 7000, 6000, 5000, 4000])
        self.assertEqual(bp[paleobiome.bp_index(-7000, bp)], 9000)    # 8950 BP
        self.assertEqual(bp[paleobiome.bp_index(-10000, bp)], 12000)  # 11950 BP
        self.assertEqual(bp[paleobiome.bp_index(-3000, bp)], 5000)    # 4950 BP


class Sampling(unittest.TestCase):
    def test_to_terrain_leaves_unmapped_blank(self):
        names = paleobiome.to_terrain(np.array([20, 21, 99, -1]),
                                      {"20": "Grassland", "21": "Extreme Desert"})
        self.assertEqual(names.tolist(), ["Grassland", "Extreme Desert", "", ""])

    def test_hex_codes_majority_ignore_and_nearest(self):
        g = make_grid(1, 1)  # one hex at the origin, ~1 x 0.87
        tf = Affine(0.25, -0.25, -0.625, 0.625)
        codes = np.full((6, 6), 20)
        codes[:, 3:] = 21
        codes[:, 2] = 21
        self.assertEqual(paleobiome.hex_codes(g, codes, tf).tolist(), [21])
        # All cells ignored -> no data.
        self.assertEqual(paleobiome.hex_codes(g, codes, tf, ignore=[20, 21]).tolist(), [-1])
        # Coarse raster with no cell centre inside the hex: nearest valid cell.
        coarse = Affine(2.0, -2.0, 0.9, 0.9)
        self.assertEqual(paleobiome.hex_codes(g, np.array([[7, 8], [9, 10]]), coarse).tolist(), [7])

    def test_subset_round_trip(self):
        try:
            import netCDF4
        except ImportError:
            self.skipTest("netCDF4 not installed")
        with tempfile.TemporaryDirectory() as d:
            nc_path, out = os.path.join(d, "t.nc"), os.path.join(d, "t.npz")
            with netCDF4.Dataset(nc_path, "w") as nc:
                nc.createDimension("time", 3)
                nc.createDimension("latitude", 4)
                nc.createDimension("longitude", 5)
                nc.createVariable("time", "f4", ("time",))[:] = [-12000, -8000, -2000]
                nc.createVariable("latitude", "f4", ("latitude",))[:] = [-0.75, -0.25, 0.25, 0.75]
                nc.createVariable("longitude", "f4", ("longitude",))[:] = [-1, -0.5, 0, 0.5, 1]
                b = nc.createVariable("biome", "f4", ("time", "latitude", "longitude"),
                                      fill_value=-9999.0)
                arr = np.arange(60, dtype=float).reshape(3, 4, 5)
                arr[1, 0, 0] = -9999.0
                b[:] = arr
            paleobiome.subset(nc_path, out, (-0.6, -1, 1, 1), 5000, 13000)
            biome, bp, tf = paleobiome.load(out)
            self.assertEqual(bp.tolist(), [12000, 8000])
            self.assertEqual(biome.shape, (2, 4, 4))
            # Row 0 is now north (lat 0.75), col 0 is lon -0.5.
            self.assertAlmostEqual(tf.y0, 0.75)
            self.assertAlmostEqual(tf.x0, -0.5)
            self.assertEqual(biome[0, 0, 0], arr[0, 3, 1])
            self.assertEqual(biome[1, 3, 0], arr[1, 0, 1])
            self.assertEqual((biome == paleobiome.NODATA).sum(), 0)  # masked cell was cut


class Calibrate(unittest.TestCase):
    def test_learns_drawn_labels_and_rejects_unfamiliar_climate(self):
        rng = np.random.default_rng(0)
        # Drawn maps: "dry" climate (rain ~1) is Grassland, wet (~3) is Forest.
        x = np.vstack([rng.normal([20, 1], 0.2, (50, 2)), rng.normal([20, 3], 0.2, (50, 2))])
        y = np.array(["Grassland"] * 50 + ["Forest"] * 50, dtype=object)
        cal = paleobiome.Calibration(x, y, k=5, max_distance_quantile=0.99, factor=2.5)
        q = np.array([[20, 1.1], [20, 2.9], [-30, 1.0], [np.nan, 1.0]])
        self.assertEqual(cal.predict(q).tolist(), ["Grassland", "Forest", "", ""])

    def test_block_cv_holds_tiles_out(self):
        # Labels follow climate, not place: held-out tiles are still recovered.
        x = np.array([[0.0], [0.1], [5.0], [5.1]] * 3)
        y = np.array(["A", "A", "B", "B"] * 3, dtype=object)
        centres = np.array([[i * 20.0, 0.0] for i in range(3) for _ in range(4)])
        self.assertEqual(paleobiome.block_cv(x, y, centres, k=1, block_deg=10.0), 1.0)


class ResolveLand(unittest.TestCase):
    def test_gaps_take_model_then_neighbours(self):
        g = make_grid(3, 3)
        terrain = np.array(["Grassland"] * 9, dtype=object)
        terrain[[3, 4, 5]] = "Land"
        model = np.array([""] * 9, dtype=object)
        model[[0, 3, 4]] = ["Boreal Forest", "Tundra", "Tundra"]  # 0 isn't a gap
        out, stats = compose.resolve_land(terrain, model, g.neighbours)
        self.assertNotIn("Land", out.tolist())
        self.assertEqual(out[0], "Grassland")  # non-gap untouched
        self.assertEqual(out[[3, 4]].tolist(), ["Tundra", "Tundra"])
        self.assertIn(out[5], ("Tundra", "Grassland"))
        self.assertEqual(stats, {"gap": 3, "model": 2, "neighbours": 1})


class CalibrationDistance(unittest.TestCase):
    def test_far_training_rows_dont_vote(self):
        """Same climate, 4000 km apart: with max_km the far label can't win."""
        rng = np.random.default_rng(0)
        x = np.array([[0.0, 0.0]] * 6 + [[5.0, 5.0]] * 6) + rng.normal(0, 0.3, (12, 2))
        y = np.array(["Chaparral"] * 6 + ["Grassland"] * 6, dtype=object)
        ll = np.array([[-5.0, 35.0]] * 6 + [[47.0, 33.0]] * 6)       # Morocco; the Zagros
        near = paleobiome.Calibration(x, y, k=3, max_distance_quantile=0.99, factor=50.0, ll=ll, max_km=1500)
        anywhere = paleobiome.Calibration(x, y, k=3, max_distance_quantile=0.99, factor=50.0)
        q = np.array([[0.2, 0.2]])                                     # Morocco's climate
        self.assertEqual(anywhere.predict(q)[0], "Chaparral")
        self.assertEqual(near.predict(q, np.array([[47.5, 33.5]]))[0], "Grassland")
        self.assertEqual(near.predict(q, np.array([[100.0, 10.0]]))[0], "")    # nothing in range

    def test_literature_labels_skip_held_out(self):
        import csv
        import os
        import tempfile
        from pipeline.anchors import holdout
        from pipeline.tests.test_pipeline import make_grid
        g = make_grid(3, 3)
        ids = [f"lit:site-{k}" for k in range(12)]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "lit.csv")
            with open(p, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["id", "name", "lon", "lat", "year", "game_classes", "description", "reference"])
                for a in ids:
                    w.writerow([a, a, 0.0, 0.0, -5000, "Woodlands;Grassland", "", "x"])
            got = paleobiome.literature_labels(p, 3, g)
        kept = [a for a in ids if not holdout(a, 3)]
        self.assertEqual(len(got[-5000]), len(kept))
        self.assertTrue(all(cls == "Woodlands" for _, cls in got[-5000]))


if __name__ == "__main__":
    unittest.main()
