import unittest

import numpy as np

from pipeline import anchors as an


def training(**means):
    """A training set where each taxon has one mean per biome (all others 0)
    and SD 1 everywhere."""
    out = {}
    for taxon, per in means.items():
        m = np.array([per.get(b, 0.0) for b in an.BIOMES])
        out[taxon] = (m, np.ones(len(an.BIOMES)))
    return out


class Biomise(unittest.TestCase):
    def test_takes_the_biome_whose_means_match(self):
        tr = training(Betula={"CENF": 40, "TEDE": 2}, Quercus={"CENF": 0, "TEDE": 30})
        b, score, analog = an.biomise({"Betula": 40, "Quercus": 1}, tr, {"CENF": 0.5})
        self.assertEqual(b, "CENF")
        self.assertTrue(analog)
        b, _, _ = an.biomise({"Betula": 2, "Quercus": 30}, tr, {})
        self.assertEqual(b, "TEDE")

    def test_score_is_cruz_silva_formula(self):
        tr = training(A={"TEDE": 10})
        _, score, _ = an.biomise({"A": 10}, tr, {})
        self.assertAlmostEqual(score, 1.0)            # zero distance
        # Distance to TUND: (10 - 0) / (1 + 0.5) = 6.67; but TEDE wins at 0.
        tr = training(A={"TEDE": 4})
        _, score, _ = an.biomise({"A": 10}, tr, {}, eps=0.5)
        self.assertAlmostEqual(score, np.exp(-(6 / 1.5) / 100))

    def test_ignores_taxa_outside_training_and_absent_ones(self):
        tr = training(A={"GRAM": 20})
        self.assertIsNone(an.biomise({"Unknownia": 50}, tr, {}))
        self.assertIsNone(an.biomise({"A": 0}, tr, {}))

    def test_low_score_is_no_analogue(self):
        tr = training(A={"GRAM": 0})
        _, _, analog = an.biomise({"A": 90}, tr, {b: 0.9 for b in an.BIOMES})
        self.assertFalse(analog)


class Slices(unittest.TestCase):
    def test_commonest_biome_in_the_window(self):
        s = [(-6010, "TEDE", 0.9, True), (-5990, "TEDE", 0.8, True), (-6100, "GRAM", 0.95, False),
             (-5000, "DESE", 0.9, True)]
        out = an.slice_labels(s, [-6000, -5500, -5000], 250)
        self.assertEqual(out[-6000]["pollen_biome"], "TEDE")
        self.assertAlmostEqual(out[-6000]["share"], 2 / 3)
        self.assertNotIn(-5500, out)
        self.assertEqual(out[-5000]["samples"], 1)

    def test_tie_goes_to_higher_score(self):
        s = [(0, "TEDE", 0.8, True), (0, "CMIX", 0.9, True)]
        self.assertEqual(an.slice_labels(s, [0], 10)[0]["pollen_biome"], "CMIX")


class Harmonise(unittest.TestCase):
    TRAIN = {t.lower(): t for t in ("Poaceae", "Amaranthaceae", "Betula", "Betula (Chamaebetula)", "Corylus",
                                     "Asteroideae", "Cichorioideae", "Oxyria/Rumex", "Carpinus betulus")}

    def h(self, name):
        return an.harmonise(name, self.TRAIN)

    def test_synonyms_and_qualifiers(self):
        self.assertEqual(self.h("Gramineae"), "Poaceae")
        self.assertEqual(self.h("Chenopodiaceae"), "Amaranthaceae")
        self.assertEqual(self.h("Corylus-type"), "Corylus")
        self.assertEqual(self.h("Betula undiff."), "Betula")
        self.assertEqual(self.h("Betula pubescens"), "Betula")
        self.assertEqual(self.h("Betula nana"), "Betula (Chamaebetula)")
        self.assertEqual(self.h("Rumex acetosa-type"), "Oxyria/Rumex")
        self.assertEqual(self.h("Carpinus"), "Carpinus betulus")
        self.assertIsNone(self.h("Nymphaea"))

    def test_oak_and_pine(self):
        self.assertEqual(self.h("Quercus"), "Quercus deciduous")
        self.assertEqual(self.h("Quercus robur-type"), "Quercus deciduous")
        self.assertEqual(self.h("Quercus ilex-type"), "Quercus evergreen")
        self.assertEqual(self.h("Pinus"), "Pinus (diploxylon)")
        self.assertEqual(self.h("Pinus sylvestris-type"), "Pinus (diploxylon)")
        self.assertEqual(self.h("Pinus cembra"), "Pinus (haploxylon)")
        self.assertEqual(self.h("Pinus subg. Strobus"), "Pinus (haploxylon)")


class Select(unittest.TestCase):
    CFG = {"dedupe_degrees": 0.05, "min_coverage": 0.8, "max_gap": 1000, "min_levels": 5, "full_levels": 10,
           "good_gap": 500, "cell_degrees": 5.0, "per_cell": 1,
           "basin_weight": {"LARG": 1.0, "SMAL": 0.5, "unknown": 0.7}}

    def cand(self, cid, lon, lat, years, db="European Pollen Database", basin=""):
        return {"id": cid, "name": cid, "database": db, "record": cid, "lon": lon, "lat": lat,
                "basin": basin, "reference": "", "years": years}

    def test_quality(self):
        cov, gap, n = an.quality([-9000, -8000, -7000], -10000, -6000)
        self.assertAlmostEqual(cov, 0.5)
        self.assertEqual(gap, 1000)
        self.assertEqual(n, 3)

    def test_filters_thins_and_dedupes(self):
        dense = list(range(-10000, -2999, 250))
        cands = [self.cand("a", 1, 46, dense), self.cand("b", 2, 46, dense[::2]),        # same cell, worse
                 self.cand("c", 11, 46, dense[:10]),                                      # too short
                 self.cand("e", 21, 30, dense, db="EMBSeCBIO", basin="LARG"),
                 self.cand("dup", 21.01, 30.01, dense)]                                   # EMBSeCBIO's twin
        chosen, n = an.select(cands, self.CFG, -10000, -3000)
        self.assertEqual(sorted(c["id"] for c in chosen), ["a", "e"])
        self.assertEqual(n, 3)

    def test_same_lake_under_two_names(self):
        a = {"name": "Van - Wick Core", "lon": 42.47, "lat": 38.53}
        b = {"name": "Lake Van", "lon": 42.84, "lat": 38.59}
        c = {"name": "Lake Zeribar", "lon": 42.80, "lat": 38.60}
        self.assertTrue(an.same_site(a, b, 50))
        self.assertFalse(an.same_site(b, c, 50))          # near, but another lake
        self.assertFalse(an.same_site(a, {**b, "lon": 45.0}, 50))

    def test_holdout_is_stable(self):
        ids = [f"neotoma:{i}" for i in range(300)]
        held = [i for i in ids if an.holdout(i, 3)]
        self.assertEqual(held, [i for i in ids if an.holdout(i, 3)])
        self.assertTrue(70 < len(held) < 130)


class Classes(unittest.TestCase):
    def test_biome4_codes_to_game_classes(self):
        classes = {"4": "Temperate Forest", "16": "Woodlands", "7": "Temperate Forest"}
        self.assertEqual(an.biome4_classes(["4", "16"], classes), ["Temperate Forest", "Woodlands"])
        self.assertEqual(an.biome4_classes(["4", "7"], classes), ["Temperate Forest"])

    def test_every_cruz_silva_biome_is_mapped(self):
        import tomllib
        with open("pipeline/config.toml", "rb") as f:
            cfg = tomllib.load(f)
        game = set(cfg["paleobiome"]["classes"].values()) | {"Alpine"}
        for b in an.BIOMES:
            got = cfg["anchors"]["classes"][b]
            self.assertTrue(got and set(got) <= game, (b, got))

    def test_year_of(self):
        self.assertEqual(an.year_of(6000), -4050)


if __name__ == "__main__":
    unittest.main()
