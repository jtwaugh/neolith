import json
import os
import tempfile
import unittest

import numpy as np

from pipeline import compose, elevation, emit
from pipeline.grid import Grid, adjacency
from pipeline.raster import Affine, classify_image, hex_majority, point_in_poly


def hex_ring(cx, cy, w=1.0, h=np.sqrt(3) / 2):
    """Flat-topped hex centred at (cx, cy), width w, height h."""
    return [[cx - w / 2, cy], [cx - w / 4, cy + h / 2], [cx + w / 4, cy + h / 2],
            [cx + w / 2, cy], [cx + w / 4, cy - h / 2], [cx - w / 4, cy - h / 2],
            [cx - w / 2, cy]]


def make_grid(cols, rows, w=1.0, h=np.sqrt(3) / 2):
    """QGIS-style flat-topped grid: odd columns sit half a hex lower."""
    rings, bbox = [], []
    for c in range(cols):
        for r in range(rows):
            cx, cy = c * 0.75 * w, -r * h - (h / 2 if c % 2 else 0)
            rings.append(hex_ring(cx, cy, w, h))
            bbox.append([cx - w / 2, cy + h / 2, cx + w / 2, cy - h / 2])
    bbox = np.array(bbox)
    return Grid(np.arange(1, len(rings) + 1), rings, bbox, adjacency(bbox))


class Raster(unittest.TestCase):
    def test_point_in_poly(self):
        ring = hex_ring(0, 0)
        x = np.array([0.0, 0.45, 0.6, 0.0])
        y = np.array([0.0, 0.0, 0.0, 0.5])
        self.assertEqual(point_in_poly(x, y, ring).tolist(), [True, True, False, False])

    def test_classify_exact_tolerance_transparent(self):
        palette = [((0, 0, 0), "A"), ((255, 255, 255), "B")]
        px = np.array([[[0, 0, 0, 255], [250, 250, 250, 255],
                        [128, 128, 128, 255], [0, 0, 0, 0]]], np.uint8)
        classes, unmatched = classify_image(px, palette, tolerance=20)
        self.assertEqual(classes.tolist(), [[0, 1, -1, -1]])
        self.assertEqual(dict(unmatched), {(128, 128, 128): 1})

    def test_hex_majority(self):
        g = make_grid(1, 1)
        # 0.05-degree raster over the hex: left 60% class 0, rest class 1.
        tf = Affine(0.05, -0.05, -0.6, 0.5)
        classes = np.zeros((21, 25), int)
        classes[:, 15:] = 1
        self.assertEqual(hex_majority(g, classes, tf, 2).tolist(), [0])
        classes[:] = -1
        self.assertEqual(hex_majority(g, classes, tf, 2).tolist(), [-1])


class Grids(unittest.TestCase):
    def test_neighbours_are_the_touching_hexes(self):
        g = make_grid(4, 4)
        c, h = g.centres, np.sqrt(3) / 2
        for i, ns in enumerate(g.neighbours):
            d = np.hypot(*(c - c[i]).T)
            want = np.flatnonzero((d > 0) & (d < 1.01 * h)).tolist()
            self.assertEqual(sorted(ns), want)
        self.assertEqual(len(g.neighbours[5]), 6)  # an interior hex


class Sea(unittest.TestCase):
    def test_sea_level_interp(self):
        curve = [[-10000, -60.0], [-5000, -10.0], [0, 0.0]]
        self.assertAlmostEqual(elevation.sea_level(-7500, curve), -35.0)
        self.assertAlmostEqual(elevation.sea_level(-20000, curve), -60.0)

    def test_closed_basin_does_not_flood(self):
        # A line: [edge ocean][shelf][land][basin][land]
        elev = np.array([-100.0, -20.0, 50.0, -30.0, 50.0])
        nb = [[1], [0, 2], [1, 3], [2, 4], [3]]
        edge = np.array([True, False, False, False, False])
        m = elevation.ocean_mask(elev, -10.0, nb, edge, seed_depth=-1500)
        self.assertEqual(m.tolist(), [True, True, False, False, False])
        m = elevation.ocean_mask(elev, -25.0, nb, edge, seed_depth=-1500)
        self.assertEqual(m.tolist(), [True, False, False, False, False])

    def test_exposed_shelf_takes_neighbour_land(self):
        g = make_grid(3, 1)  # three hexes in a row-ish chain
        t = {-9000: np.array(["Water", "Water", "Grassland"], dtype=object)}
        elev = np.array([-100.0, -20.0, 30.0])
        sea = {"curve": [[-9000, -50.0], [0, 0.0]], "seed_depth": -1500.0}
        out, stats = compose.apply_sea(t, elev, g, sea)
        self.assertEqual(out[-9000].tolist(), ["Water", "Grassland", "Grassland"])
        self.assertEqual(stats[-9000]["exposed"], 1)


class Mountains(unittest.TestCase):
    CFG = {"relief": 300.0, "relief_radius": 7000.0,
           "bands": [{"above": 2500.0}, {"above": 1500.0, "slope": 2.0},
                     {"above": 300.0, "rugged": True}]}

    def test_cells_need_height_and_relief(self):
        tf = Affine(0.05, -0.05, 0.0, 45.0)  # cells about 4 x 5.5 km
        z = np.zeros((40, 80), np.float32)
        z[:, 20:40] = 2000.0                             # flat plateau
        z[:, 40:60] = 3000.0                             # above the top band
        z[:, 60:] = 400.0 + 500.0 * (np.arange(20) % 2)  # ridges and valleys
        z[:, :20] = 250.0 * (np.arange(20) % 2)          # rugged but low
        m = elevation.mountain_cells(z, tf, self.CFG)
        self.assertFalse(m[:, :16].any())      # too low, however rugged
        self.assertFalse(m[:, 25:35].any())    # high but flat
        self.assertTrue(m[:, 40:60].all())
        self.assertTrue(m[:, 62:78].all())

    def test_hex_fraction(self):
        g = make_grid(1, 1)
        tf = Affine(0.05, -0.05, -0.6, 0.5)
        mask = np.zeros((21, 25), bool)
        mask[:, 12:] = True                    # the hex's right half
        self.assertAlmostEqual(elevation.hex_fraction(g, mask, tf)[0], 0.5, delta=0.06)

    def test_landform_classes(self):
        cfg = {"hills_fraction": 0.15, "min_fraction": 0.4, "high_elevation": 2000.0}
        frac = np.array([0.0, 0.2, 0.5, 0.9, 0.9])
        elev = np.array([100.0, 600.0, 1200.0, 2400.0, np.nan])
        self.assertEqual(elevation.landform(frac, elev, cfg).tolist(),
                         [elevation.FLAT, elevation.HILLS, elevation.MOUNTAINS,
                          elevation.HIGH_MOUNTAINS, elevation.MOUNTAINS])

    def test_alpine_needs_mountains_and_cold(self):
        nb = [[1], [0, 2], [1, 3], [2, 4], [3]]
        t = np.array(["Grassland", "Mountains", "Boreal Forest", "Grassland", "Ice"], dtype=object)
        mountain = np.array([False, True, True, False, True])
        cold = np.array([True, False, True, True, True])
        out, stats = compose.apply_alpine(t, mountain, cold, nb)
        # 1: drawn Mountains left unfilled take a neighbour; 2: alpine;
        # 3: cold but not mountain; 4: stays under ice.
        self.assertEqual(out.tolist(),
                         ["Grassland", "Boreal Forest", "Alpine", "Grassland", "Ice"])
        self.assertEqual(stats, {"mountain": 3, "alpine": 1, "covered": 1, "neighbours": 1})
        self.assertEqual(t[1], "Mountains")    # input untouched

    def test_drawn_mountains_are_gaps(self):
        nb = [[1], [0, 2], [1]]
        t = np.array(["Grassland", "Mountains", "Land"], dtype=object)
        biome = np.array(["", "Semi-Desert", ""], dtype=object)
        out, stats = compose.resolve_land(t, biome, nb, gaps=("Land", "Mountains"))
        self.assertEqual(out.tolist(), ["Grassland", "Semi-Desert", "Semi-Desert"])
        self.assertEqual(stats, {"gap": 2, "model": 1, "neighbours": 1})

    def test_exposed_shelf_does_not_become_alpine(self):
        g = make_grid(3, 1)
        t = {-9000: np.array(["Water", "Water", "Alpine"], dtype=object)}
        elev = np.array([-100.0, -20.0, 900.0])
        sea = {"curve": [[-9000, -50.0], [0, 0.0]], "seed_depth": -1500.0}
        out, _ = compose.apply_sea(t, elev, g, sea)
        self.assertEqual(out[-9000].tolist(), ["Water", "Plains", "Alpine"])


class Fill(unittest.TestCase):
    def test_island_amid_water_takes_nearest_coast_not_a_placeholder(self):
        # A chain: Forest, Water, Water, island (to fill), Water, Steppe, Steppe.
        nb = [[1], [0, 2], [1, 3], [2, 4], [3, 5], [4, 6], [5]]
        v = np.array(["Forest", "Water", "Water", "Water", "Water", "Steppe", "Steppe"], dtype=object)
        todo = np.zeros(7, dtype=bool)
        todo[3] = True
        out = compose.fill_from_neighbours(v, todo, nb, exclude=("Water",))
        self.assertEqual(out[3], "Steppe")               # two steps; Forest is three
        todo[3], todo[1] = False, True                   # one step from Forest
        self.assertEqual(compose.fill_from_neighbours(v, todo, nb, exclude=("Water",))[1], "Forest")
        # Nothing usable anywhere: the old placeholder; an explicit default still wins.
        w = np.array(["Water", "Water"], dtype=object)
        self.assertEqual(compose.fill_from_neighbours(w, np.array([True, False]), [[1], [0]])[0], "Plains")
        self.assertEqual(compose.fill_from_neighbours(w, np.array([True, False]), [[1], [0]], default="X")[0], "X")

    def test_hold(self):
        kf = {-9000: np.array(["a"]), -7000: np.array(["b"])}
        out, prov = compose.fill(kf, range(-10000, -5999, 1000))
        self.assertEqual({y: v[0] for y, v in out.items()},
                         {-10000: "a", -9000: "a", -8000: "a", -7000: "b", -6000: "b"})
        self.assertEqual(prov[-10000], "hold -9000")
        self.assertEqual(prov[-7000], "keyframe")

    def test_fronts_advance_from_existing_value(self):
        # A chain: hex 0 is already B; hexes 1-4 turn A -> B.
        nb = [[1], [0, 2], [1, 3], [2, 4], [3]]
        a = np.array(list("BAAAA"), dtype=object)
        b = np.array(list("BBBBB"), dtype=object)
        np.testing.assert_allclose(compose.switch_fraction(a, b, nb), [0, .25, .5, .75, 1])
        out, prov = compose.fill({-9000: a, -8000: b}, range(-9000, -7999, 100), "fronts", nb)
        self.assertEqual("".join(out[-8800]), "BAAAA")
        self.assertEqual("".join(out[-8500]), "BBBAA")
        self.assertEqual("".join(out[-8000]), "BBBBB")
        self.assertEqual(prov[-8500], "fronts -9000..-8000")

    def test_new_patch_grows_from_its_middle(self):
        g = make_grid(5, 5)
        centre = 12
        patch = [centre] + g.neighbours[centre]
        a = np.full(len(g), "A", dtype=object)
        b = a.copy()
        b[patch] = "B"
        f = compose.switch_fraction(a, b, g.neighbours)
        self.assertEqual(f[centre], 0.5)
        self.assertTrue(all(f[j] == 1.0 for j in g.neighbours[centre]))
        self.assertEqual(f[0], 0)

    def test_distance_fronts_are_round_not_hexagonal(self):
        # One source hex in the middle of a big patch. By hops, the hexes
        # switching together form a hexagon with straight vertical sides; by
        # straight-line distance they form a circle.
        g = make_grid(31, 31)
        xy = g.centres
        mid = int(np.argmin(np.hypot(*(xy - xy.mean(axis=0)).T)))
        a = np.full(len(g), "A", dtype=object)
        a[mid] = "B"
        b = np.full(len(g), "B", dtype=object)
        r = np.hypot(*(xy - xy[mid]).T)
        hops = compose.switch_fraction(a, b, g.neighbours)
        dist = compose.switch_fraction(a, b, g.neighbours, xy)
        # Within a disc, how far the switch time strays from a line in the
        # radius: small for round fronts, large for hexagonal ones.
        disc = r < 12

        def stray(f):
            fit = np.polyval(np.polyfit(r[disc], f[disc], 1), r[disc])
            return np.std(f[disc] - fit) / np.ptp(f[disc])
        self.assertLess(stray(dist), 0.3 * stray(hops))
        self.assertEqual(dist[mid], 0)
        self.assertTrue(np.all(np.diff(dist[np.argsort(r)][1:]) > -0.05))

    def test_distance_fronts_stay_inside_their_patch(self):
        # A U-shaped patch: the far arm is reached round the bend, so it
        # switches after the near arm even though it is close in a line.
        g = make_grid(12, 12)
        col = np.rint(g.centres[:, 0] / 0.75).astype(int)
        row = np.rint(-g.centres[:, 1] / (np.sqrt(3) / 2)).astype(int)
        a = np.full(len(g), "X", dtype=object)
        u = ((col == 2) | (col == 6) | (row == 10)) & (col >= 2) & (col <= 6) & (row >= 1)
        a[u] = "A"
        a[(col == 2) & (row == 0)] = "B"
        b = a.copy()
        b[u] = "B"
        f = compose.switch_fraction(a, b, g.neighbours, g.centres)
        near, far = u & (col == 2) & (row == 3), u & (col == 6) & (row == 3)
        self.assertLess(f[near].max(), f[far].min())

    def test_front_geometry(self):
        g = make_grid(10, 10)
        self.assertEqual(compose.front_geometry(g, {"metric": "hops"}), (None, None))
        xy, slow = compose.front_geometry(g, {"metric": "distance", "noise": 0.25})
        self.assertEqual(xy.shape, (len(g), 2))
        self.assertTrue(np.all((slow >= 0.75) & (slow <= 1.25)))
        self.assertGreater(np.ptp(slow), 0)
        _, none = compose.front_geometry(g, {"metric": "distance"})
        self.assertIsNone(none)

    def test_fronts_hold_outside_keyframes(self):
        nb = [[]]
        out, prov = compose.fill({-9000: np.array(["x"]), -8000: np.array(["y"])},
                                 [-9500, -7500], "fronts", nb)
        self.assertEqual((out[-9500][0], out[-7500][0]), ("x", "y"))
        self.assertEqual(prov[-9500], "hold -9000")


class Emit(unittest.TestCase):
    def test_sparse_keeps_only_changes(self):
        g = make_grid(1, 1)
        props = {"terrain": {y: np.array([v], dtype=object) for y, v in
                             [(-9000, "A"), (-8900, "A"), (-8800, "B"), (-8700, "B"), (-8600, "A")]}}
        p = emit.features(g, props, sparse=True)[0]["properties"]
        self.assertEqual(p["terrain"], {"-9000": "A", "-8800": "B", "-8600": "A"})

    def test_static_props_are_scalars(self):
        g = make_grid(1, 2)
        props = {"terrain": {-9000: np.array(["A", "B"], dtype=object)}}
        feats = emit.features(g, props, static={"elevation": np.array([312.0, np.nan])})
        self.assertEqual(feats[0]["properties"]["elevation"], 312.0)
        self.assertNotIn("elevation", feats[1]["properties"])

    def test_spec_shape(self):
        g = make_grid(1, 2)
        props = {"terrain": {-9000: np.array(["Water", "Ice"], dtype=object),
                             -10000: np.array(["Ice", "Ice"], dtype=object)},
                 "koeppen": {-9000: np.array([0.0, 30.0]), -10000: np.array([0.0, 29.0])}}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.geojson")
            emit.write_combined(path, g, props)
            fc = json.load(open(path))
        f = fc["features"][1]
        self.assertEqual(fc["type"], "FeatureCollection")
        self.assertEqual(list(f["properties"])[:5], ["id", "left", "top", "bottom", "right"])
        self.assertEqual(f["properties"]["terrain"], {"-10000": "Ice", "-9000": "Ice"})
        self.assertEqual(f["properties"]["koeppen"], {"-10000": 29.0, "-9000": 30.0})
        self.assertEqual(f["geometry"]["type"], "Polygon")


if __name__ == "__main__":
    unittest.main()
