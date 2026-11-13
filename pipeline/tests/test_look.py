import os
import tempfile
import unittest

import numpy as np

from pipeline import look
from pipeline.tests.test_pipeline import make_grid

S = {**look.DEFAULTS, "edge_min": 8, "stripe_min": 8, "tile_degrees": 5.0, "tile_min_hexes": 5, "cluster_min": 4}


def grid_codes(g, t):
    """(codes, ok) on the 2-D layout for a per-hex class array."""
    idx = look.cells(g)
    names = sorted(set(t.tolist()))
    col = np.array([names.index(v) for v in t])
    return (np.where(idx >= 0, col[idx], -1), np.where(idx >= 0, ~np.isin(t, look.NOT_BIOME)[idx], False),
            names, idx)


class Series(unittest.TestCase):
    def test_step_function(self):
        feats = [{"properties": {"terrain": {"-9000": "A", "-7000": "B"}}},
                 {"properties": {"terrain": {"-10000": "C"}}}, {"properties": {}}]
        out = look.series(feats, "terrain", [-10000, -9000, -8000, -7000, -6000])
        # Before its first key a hex takes that first value.
        self.assertEqual(out[0].tolist(), ["A", "A", "A", "B", "B"])
        self.assertEqual(out[1].tolist(), ["C"] * 5)
        self.assertEqual(out[2].tolist(), [""] * 5)


class Bands(unittest.TestCase):
    def setUp(self):
        self.g = make_grid(24, 16)
        self.idx = look.cells(self.g)
        self.row = np.zeros(len(self.g), dtype=int)
        self.col = np.zeros(len(self.g), dtype=int)
        ys, xs = np.nonzero(self.idx >= 0)
        self.row[self.idx[ys, xs]], self.col[self.idx[ys, xs]] = ys, xs

    def test_rows_run_north_to_south(self):
        lat = self.g.centres[:, 1]
        self.assertGreater(lat[self.row == 0].mean(), lat[self.row == 5].mean())

    def test_straight_edge_found_and_wavy_edge_not(self):
        t = np.where(self.row < 8, "Boreal Forest", "Grassland").astype(object)
        codes, ok, names, _ = grid_codes(self.g, t)
        found = look.straight_edges(codes, ok, 8)
        self.assertEqual(len(found), 1)
        r, i, j, a, b = found[0]
        self.assertEqual((r, i, j, names[a], names[b]), (7, 0, 23, "Boreal Forest", "Grassland"))
        # An edge that climbs a row every two columns never keeps to one row for 8.
        t = np.where(self.row < 2 + self.col // 2, "Boreal Forest", "Grassland").astype(object)
        codes, ok, _, _ = grid_codes(self.g, t)
        self.assertEqual(look.straight_edges(codes, ok, 8), [])

    def test_water_edges_do_not_count(self):
        t = np.where(self.row < 8, "Water", "Grassland").astype(object)
        codes, ok, _, _ = grid_codes(self.g, t)
        self.assertEqual(look.straight_edges(codes, ok, 8), [])

    def test_thin_band(self):
        t = np.full(len(self.g), "Grassland", dtype=object)
        t[(self.row == 6) & (self.col >= 3) & (self.col <= 18)] = "Chaparral"
        codes, ok, names, _ = grid_codes(self.g, t)
        found = look.stripes(codes, ok, 2, 8)
        self.assertEqual([(r[1], r[2], names[r[3]]) for r in found], [(3, 18, "Chaparral")])
        # A band five hexes thick is not thin.
        t[(self.row >= 6) & (self.row <= 10) & (self.col >= 3) & (self.col <= 18)] = "Chaparral"
        codes, ok, _, _ = grid_codes(self.g, t)
        self.assertEqual(look.stripes(codes, ok, 2, 8), [])

    def test_suspects_merge_years_and_give_a_box(self):
        t = np.where(self.row < 8, "Boreal Forest", "Grassland").astype(object)
        out = look.band_suspects(self.g, self.idx, np.column_stack([t, t]), [-6000, -5000], S)
        edges = [r for r in out if r["kind"] == "straight edge" and "east-west" in r["what"]]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["years"], [-6000, -5000])
        self.assertIn("Boreal Forest above Grassland", edges[0]["what"])
        lat = self.g.centres[self.row == 8, 1].mean()
        self.assertLess(edges[0]["box"][1], lat + 1)
        self.assertGreater(edges[0]["box"][3], lat - 1)


class Surges(unittest.TestCase):
    def test_flicker_and_surge(self):
        g = make_grid(6, 6)
        a = np.full(len(g), "Temperate Forest", dtype=object)
        b = np.full(len(g), "Chaparral", dtype=object)
        years = [-9000, -8000, -7000, -6000]
        out = look.surge_suspects(g, np.column_stack([a, b, a, a]), years, S)
        kinds = {(r["kind"], r["what"].split(" share")[0]) for r in out}
        self.assertIn(("flicker: appears for one step", "Chaparral"), kinds)
        self.assertIn(("flicker: vanishes for one step", "Temperate Forest"), kinds)
        out = look.surge_suspects(g, np.column_stack([a, a, b, b]), years, S)
        self.assertEqual({r["kind"] for r in out}, {"surge", "collapse"})
        self.assertEqual(look.surge_suspects(g, np.column_stack([a, a, a, a]), years, S), [])


class Climate(unittest.TestCase):
    def test_patch_in_the_wrong_climate(self):
        g = make_grid(8, 8)
        ter = np.full((len(g), 1), "Chaparral", dtype=object)
        cli = np.full((len(g), 1), "Csa", dtype=object)
        cold = look.in_box(g, [0, -3, 3, 0])
        cli[cold, 0] = "Dfb"
        out = look.climate_suspects(g, ter, cli, [-8000], {"Chaparral": ["Cs", "BS"]}, S)
        self.assertEqual(len(out), 1)
        self.assertIn("Chaparral under Köppen Dfb", out[0]["what"])
        self.assertIn(f"{int(cold.sum())} hexes", out[0]["what"])


class Floodplains(unittest.TestCase):
    def test_lost_while_the_river_runs(self):
        g = make_grid(10, 4)
        years = [-9000, -8900, -8800]
        ter = np.full((len(g), 3), "Grassland", dtype=object)
        riv = np.zeros((len(g), 3))
        on = np.flatnonzero(np.abs(g.centres[:, 1] + 1.3) < 0.5)[:6]
        riv[on] = 2
        ter[on, 0] = "Floodplain"
        ter[on, 1] = "Boreal Forest"       # the biome changed under the river
        ter[on, 2] = "Water"               # drowned: not a loss
        out, on_river = look.floodplain_suspects(g, ter, riv, years, 2, S)
        self.assertEqual(len(out), 1)
        self.assertIn("Boreal Forest", out[0]["what"])
        self.assertEqual(out[0]["years"], [-8900])
        self.assertEqual(on_river[-9000]["Floodplain"], len(on))

    def test_never_a_floodplain_is_not_a_loss(self):
        g = make_grid(10, 4)
        ter = np.full((len(g), 2), "Boreal Forest", dtype=object)
        out, _ = look.floodplain_suspects(g, ter, np.full((len(g), 2), 2.0), [-9000, -8900], 2, S)
        self.assertEqual(out, [])


class Stages(unittest.TestCase):
    def test_round_trip_and_attribution(self):
        g = make_grid(3, 2)
        arr = lambda *v: np.array(v, dtype=object)
        frames = {
            "drawn": {-8000: arr("Chaparral", "Land", "Land", "Mountains", "Grassland", "Land")},
            "biome4": {-8000: arr("Grassland", "Tundra", "Semi-Desert", "Grassland", "Grassland", "")},
            "calibrated": {-8000: arr("Grassland", "Tundra", "Savannah", "Grassland", "Grassland", "")},
            "filled": {-8000: arr("Chaparral", "Tundra", "Savannah", "Grassland", "Grassland", "Grassland")},
            "keyframe": {-8000: arr("Chaparral", "Tundra", "Savannah", "Alpine", "Grassland", "Grassland")},
        }
        final = arr("Chaparral", "Tundra", "Savannah", "Alpine", "Floodplain", "Grassland")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "stages.npz")
            look.write_stages(p, g, frames)
            back = look.read_stages(p, g)
            self.assertEqual(look.read_stages(p, make_grid(2, 2)), {})
        self.assertEqual(back["drawn"][-8000].tolist(), frames["drawn"][-8000].tolist())
        self.assertEqual(back["biome4"][-8000][5], "")
        att = look.attribute(final, back, -8000, ["Land", "Mountains"])
        self.assertEqual(att.tolist(), ["drawn", "BIOME4 (calibration agrees)", "calibration", "cleanup",
                                        "after keyframes", "neighbour fill"])


if __name__ == "__main__":
    unittest.main()
