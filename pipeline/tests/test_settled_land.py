import unittest

import numpy as np

from pipeline import compose
from pipeline.tests.test_pipeline import make_grid

YEARS = [-6000, -5900, -5800, -5700]


def site(hex_id, *occupation):
    return {"properties": {"hex": hex_id, "founding": occupation[0][0], "occupation": [list(p) for p in occupation]}}


class SettledLand(unittest.TestCase):
    def setUp(self):
        self.g = make_grid(5, 5)
        self.i = 12                                       # interior hex, id 13
        self.n = len(self.g)

    def frames(self, *water_at, fill="Grassland"):
        """One frame per YEARS entry; the site's hex is Water in `water_at`."""
        out = {}
        for y in YEARS:
            t = np.full(self.n, fill, dtype=object)
            if y in water_at:
                t[self.i] = "Water"
            out[y] = t
        return out

    def keep(self, terrain, sites, before=None, under=()):
        """Sites are above water except in the years in `under`."""
        return compose.keep_settled_land(terrain, before or terrain, sites, self.g,
                                         depth=lambda n, y: (10.0 if y in under else -10.0, "sea"))

    def test_drawn_water_at_start_stays_land_through_the_phase(self):
        t = self.frames(*YEARS)                          # coast a hex off in every frame
        before = {y: v.copy() for y, v in t.items()}
        before[-6000][self.i] = "Temperate Forest"
        out, feats, stats = self.keep(t, [site(13, (-6000, -5700))], before)
        self.assertEqual(out[-6000][self.i], "Temperate Forest")
        self.assertEqual([out[y][self.i] for y in (-5900, -5800)], ["Grassland", "Grassland"])
        self.assertEqual(out[-5700][self.i], "Water")      # phase over: no site there
        self.assertEqual([stats["kept"][y] for y in YEARS], [1, 1, 1, 0])
        self.assertEqual(t[-6000][self.i], "Water")        # input untouched
        self.assertNotIn("drowned", feats[0]["properties"])

    def test_appears_mid_frame(self):
        out, _, stats = self.keep(self.frames(-5900), [site(13, (-5850, -5700))])
        self.assertEqual(out[-5900][self.i], "Grassland")   # -5850 shows the -5900 frame
        self.assertEqual(stats["kept"][-5900], 1)

    def test_hex_turning_water_over_a_site_above_it_stays_land(self):
        out, feats, stats = self.keep(self.frames(-5800, -5700), [site(13, (-6000, -5000))])
        self.assertEqual([out[y][self.i] for y in (-5800, -5700)], ["Grassland", "Grassland"])
        self.assertNotIn("drowned", feats[0]["properties"])

    def test_site_going_under_ends_the_phase(self):
        out, feats, stats = self.keep(self.frames(-5800, -5700), [site(13, (-6000, -5000))], under={-5700})
        p = feats[0]["properties"]
        self.assertEqual(p["occupation"], [[-6000, -5700]])
        self.assertEqual(p["drowned"], -5700)
        self.assertEqual(stats["drowned"], 1)
        self.assertEqual(out[-5800][self.i], "Grassland")   # still above water
        self.assertEqual(out[-5700][self.i], "Water")       # gone

    def test_below_water_on_dry_hex_is_ignored(self):
        _, feats, _ = self.keep(self.frames(), [site(13, (-6000, -5000))], under=set(YEARS))
        self.assertNotIn("drowned", feats[0]["properties"])

    def test_start_frame_is_land_even_if_below(self):
        out, feats, _ = self.keep(self.frames(-6000), [site(13, (-6000, -5000))], under={-6000})
        self.assertEqual(out[-6000][self.i], "Grassland")    # it is there, so it was dry

    def test_without_elevation_a_water_frame_drowns(self):
        _, feats, _ = compose.keep_settled_land(self.frames(-5800), self.frames(-5800),
                                               [site(13, (-6000, -5000))], self.g)
        self.assertEqual(feats[0]["properties"]["occupation"], [[-6000, -5800]])

    def test_a_later_phase_starts_on_land_again(self):
        _, feats, stats = self.keep(self.frames(-5800), [site(13, (-6000, -5750), (-5700, -5000))],
                                    under={-5800})
        self.assertEqual(feats[0]["properties"]["occupation"], [[-6000, -5800], [-5700, -5000]])

    def test_offshore_start_is_left_alone(self):
        sea = {y: np.full(self.n, "Water", dtype=object) for y in YEARS}
        out, feats, stats = self.keep(sea, [site(13, (-6000, -5000))])
        self.assertEqual(out[-6000][self.i], "Water")
        self.assertEqual(stats["kept"][-6000], 0)
        self.assertEqual(feats[0]["properties"].get("occupation"), [[-6000, -5000]])   # not cut

    def test_islet_site_keeps_its_hex(self):
        sea = {y: np.full(self.n, "Water", dtype=object) for y in YEARS}
        out, feats, stats = compose.keep_settled_land(sea, sea, [site(13, (-6000, -5000))], self.g,
                                                      depth=lambda n, y: (-5.0, "sea"), islets=True)
        self.assertNotEqual(out[-6000][self.i], "Water")
        self.assertEqual(stats["kept"][-5700], 1)
        out, _, _ = compose.keep_settled_land(sea, sea, [site(13, (-6000, -5000))], self.g,
                                              depth=lambda n, y: (5.0, "sea"), islets=True)
        self.assertEqual(out[-6000][self.i], "Water")         # under water: wrong coordinates

    def test_drawn_water_takes_neighbours_biome(self):
        out, _, _ = self.keep(self.frames(-6000, fill="Steppe-Forest"), [site(13, (-6000, -5900))])
        self.assertEqual(out[-6000][self.i], "Steppe-Forest")

    def test_margin_is_over_the_start_depth(self):
        """A shore site the model puts 2 m under at its start: a later 4 m is
        within the 3 m margin, 6 m is not."""
        t = self.frames(*YEARS)
        d = {-6000: 2.0, -5900: 4.0, -5800: 6.0, -5700: 6.0}
        out, feats, stats = compose.keep_settled_land(t, t, [site(13, (-6000, -5000))], self.g,
                                                      depth=lambda n, y: (d[y], "baltic"), margin=3.0)
        p = feats[0]["properties"]
        self.assertEqual(p["occupation"], [[-6000, -5800]])
        self.assertEqual(stats["cuts"], [("?", -5800, "baltic", 2.0, 6.0)])
        self.assertEqual(stats["wet_starts"], [])             # 2 m is within the margin

    def test_wet_start_is_recorded(self):
        t = self.frames()
        _, _, stats = compose.keep_settled_land(t, t, [site(13, (-6000, -5000))], self.g,
                                                depth=lambda n, y: (12.0, "megachad"), margin=3.0)
        self.assertEqual(stats["wet_starts"], [("?", -6000, "megachad", 12.0)])

    def test_phases_fallback_and_frames(self):
        self.assertEqual(compose.phases({"founding": -5950, "abandoned": -5800}, YEARS), [(-5950, -5800)])
        self.assertEqual(compose.frame_of(-5950, YEARS), -6000)
        self.assertEqual(compose.frame_of(-7000, YEARS), -6000)
        self.assertEqual(compose.alive_frames([(-5950, -5800)], YEARS), [-6000, -5900])



class SiteBelowWater(unittest.TestCase):
    def test_ground_against_sea_and_lake(self):
        import tempfile, os
        from pipeline.raster import Affine
        arr = np.array([[5.0, -50.0], [-50.0, -50.0]])     # one dry cell, NW
        tf = Affine(1.0, -1.0, 0.0, 1.0)                    # cell centres lon 0,1; lat 1,0
        with tempfile.TemporaryDirectory() as d:
            cfg = {"sea": {"curve": [[-8000, -60.0], [-3000, 0.0]]}}
            g = make_grid(1, 1)
            sites = [{"geometry": {"coordinates": [1.0, 0.0]}, "properties": {"hex": 1}}]
            ring = [[0.5, -0.5], [1.5, -0.5], [1.5, 0.5], [0.5, 0.5], [0.5, -0.5]]
            lakes = [{"key": "pond", "shapes": [{"level": -40.0, "rings": [ring], "from": -8000, "to": -3000}]}]
            ocean = {-3000: np.array([True]), -8000: np.array([False]), -5000: np.array([False])}
            depth = compose.site_water_depth(sites, arr, tf, cfg, lakes, g, ocean, radius=0)
            self.assertEqual(depth(0, -8000), (10.0, "pond"))     # -50 m ground, pond at -40 m
            self.assertEqual(depth(0, -3000), (50.0, "sea"))      # pond gone; the hex is open sea
            self.assertEqual(depth(0, -5000)[1], "pond")
            ocean[-6000] = np.array([False])
            lakes[0]["shapes"][0]["to"] = -7000
            depth = compose.site_water_depth(sites, arr, tf, cfg, lakes, g, ocean, radius=0)
            self.assertEqual(depth(0, -6000), (-np.inf, "none"))  # no lake, no sea: an inland basin
            g2 = make_grid(2, 1)
            beside = [{"geometry": {"coordinates": [1.0, 0.0]}, "properties": {"hex": 1}}]
            oc2 = {-3000: np.array([False, True])}                # only the neighbour is sea
            near = compose.site_water_depth(beside, arr, tf, cfg, [], g2, oc2, radius=0, coast_cap=20.0)
            self.assertEqual(near(0, -3000)[1], "none")         # -50 m: a basin behind the coast
            near = compose.site_water_depth(beside, arr, tf, cfg, [], g2, oc2, radius=0, coast_cap=60.0)
            self.assertEqual(near(0, -3000), (50.0, "sea"))
            wide = compose.site_water_depth(sites, arr, tf, cfg, lakes, g, ocean, radius=1)
            self.assertEqual(wide(0, -3000), (-5.0, "sea"))       # the dry cell next door: +5 m

if __name__ == "__main__":
    unittest.main()
