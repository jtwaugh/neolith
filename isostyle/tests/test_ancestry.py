"""Tests for the ancestry table and its layers: python -m unittest discover -s isostyle/tests -t ."""
import os
import tempfile
import tomllib
import unittest

import numpy as np
import pandas as pd

from isostyle import ancestry, layers, people, speculative, surface

CFG = tomllib.load(open("isostyle/config.toml", "rb"))
ACFG = CFG["ancestry"]
ORDER = ACFG["order"]
ANNO = os.path.join(CFG["output"]["build_dir"], "sources", ACFG["anno"])
REGISTRY = layers.Registry.load("data/isostyle/layers.toml")


def table(rows):
    base = {c: "" for c in ancestry.out_columns(ORDER)}
    return pd.DataFrame([{**base, **{f"w_{k}": np.nan for k in ORDER}, **{f"se_{k}": np.nan for k in ORDER}, **r}
                         for r in rows], columns=ancestry.out_columns(ORDER))


class Genotypes(unittest.TestCase):
    def test_tgeno_round_trip(self):
        rng = np.random.default_rng(1)
        nind, nsnp = 7, 1003
        g = rng.integers(0, 4, (nind, nsnp)).astype(np.uint8)
        pad = np.concatenate([g, np.full((nind, (-nsnp) % 4), 3, np.uint8)], axis=1).reshape(nind, -1, 4)
        packed = (pad[:, :, 0] << 6 | pad[:, :, 1] << 4 | pad[:, :, 2] << 2 | pad[:, :, 3]).astype(np.uint8)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.geno")
            with open(path, "wb") as f:
                f.write(f"TGENO {nind} {nsnp} 0 0".encode().ljust(ancestry.HEADER, b"\0") + packed.tobytes())
            rows, n = ancestry.read_rows(path, np.array([5, 0, 3]))
            self.assertEqual(n, nsnp)
            np.testing.assert_array_equal(ancestry.unpack(rows, n), g[[5, 0, 3]])
            keep = rng.random(nsnp) < 0.6
            ancestry.write_geno(os.path.join(d, "y.geno"), rows, n, keep)
            raw = open(os.path.join(d, "y.geno"), "rb").read()
            self.assertTrue(raw.startswith(b"GENO"))
            rec = np.frombuffer(raw, np.uint8).reshape(-1, ancestry.HEADER)[1:]        # SNP-major, 48-byte records
            self.assertEqual(len(rec), keep.sum())
            back = (rec[:, :, None] >> np.array([6, 4, 2, 0], np.uint8) & 3).reshape(len(rec), -1)
            np.testing.assert_array_equal(back[:, :3].T, g[[5, 0, 3]][:, keep])
            self.assertTrue((back[:, 3:] == 3).all())

    def test_incomplete_file_needs_url(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.geno")
            open(path, "wb").write(b"TGENO 4 8 0 0".ljust(ancestry.HEADER, b"\0") + b"\0\0")
            with self.assertRaises(FileNotFoundError):
                ancestry.read_rows(path, np.array([0]))


class Model(unittest.TestCase):
    def test_config(self):
        self.assertEqual(sorted(ACFG["sources"]), sorted(ORDER))
        self.assertEqual(len(ORDER), 6)
        for v in ACFG["validate"]:
            self.assertLessEqual(set(v["expect"]), set(ORDER), v["name"])

    @unittest.skipUnless(os.path.exists(ANNO), "AADR annotation not fetched")
    def test_labels_exist_in_anno(self):
        """AADR group labels drift between releases: every configured label
        and genetic id must be in the annotation, with a usable individual."""
        refs = ancestry.reference_sets(ACFG, people.load_anno(ANNO))
        self.assertEqual(sorted(refs), sorted(ORDER + [r["pop"] for r in ACFG["right"]]))
        ids = [g for v in refs.values() for g in v]
        self.assertEqual(len(ids), len(set(ids)), "an individual sits in two reference populations")

    def test_unknown_label_is_an_error(self):
        anno = pd.DataFrame({"gid": ["a.AG"], "individual": ["a"], "group": ["Somewhere_N"], "snps": [1e5], "assessment": ["Pass"]})
        bad = {"order": ["x"], "sources": {"x": {"groups": ["Nowhere_N"]}}, "right": []}
        with self.assertRaises(LookupError):
            ancestry.reference_sets(bad, anno)


class Table(unittest.TestCase):
    def test_check_table(self):
        good = table([{"individual": "a", "status": "fit", "model": "whg+ana", **{f"w_{k}": 0.0 for k in ORDER}, "w_whg": 0.3, "w_ana": 0.7},
                      {"individual": "b", "status": "no_fit"}, {"individual": "c", "status": "low_coverage"}])
        self.assertEqual(ancestry.check_table(good, ORDER), [])
        off = good.copy()
        off.loc[0, "w_ana"] = 0.6
        self.assertTrue(any("sum" in b for b in ancestry.check_table(off, ORDER)))
        odd = good.copy()
        odd.loc[1, "status"] = "maybe"
        self.assertTrue(any("status" in b for b in ancestry.check_table(odd, ORDER)))
        leak = good.copy()
        leak.loc[2, "w_whg"] = 1.0
        self.assertTrue(any("not fits" in b for b in ancestry.check_table(leak, ORDER)))

    def test_assemble(self):
        t = pd.DataFrame({"gid": ["a.AG", "b.SG", "c.AG", "r.SG"], "individual": ["a", "b", "c", "r"], "group": ["G", "G", "G", "Turkey_N"],
                          "locality": "x", "lat": 1.0, "lon": 2.0, "bp": 7000.0, "sd": 50.0, "snps": [5e5, 1e3, 5e5, 9e5], "publication": "P"})
        refs = {k: [] for k in ORDER}
        refs["ana"] = ["r.SG"]
        res = pd.DataFrame([{"gid": "a.AG", "status": "fit", "model": "whg+ana", "p": 0.4, "w_whg": 0.25, "w_ana": 0.75, "se_whg": 0.02, "se_ana": 0.02},
                            {"gid": "c.AG", "status": "no_fit", "model": "", "p": np.nan}])
        out = ancestry.assemble(ACFG, t, refs, res).set_index("individual")
        self.assertEqual(list(out["status"]), ["fit", "low_coverage", "no_fit", "reference"])
        self.assertEqual(out.loc["a", "w_irn"], 0.0)
        self.assertTrue(np.isnan(out.loc["a", "se_irn"]))
        self.assertEqual(out.loc["r", "w_ana"], 1.0)
        self.assertEqual(ancestry.check_table(out.reset_index(), ORDER), [])

    @unittest.skipUnless(os.path.exists(ACFG["out"]), "ancestry table not built")
    def test_committed_table(self):
        d = pd.read_csv(ACFG["out"])
        self.assertEqual(ancestry.check_table(d, ORDER), [])
        self.assertLessEqual(set(d["status"]), set(ancestry.STATUSES))
        fit = d[d["status"] == "fit"]
        s = fit[[f"w_{k}" for k in ORDER]].sum(axis=1)
        self.assertTrue(((s - 1).abs() <= 0.01).all())
        self.assertTrue(d["publication"].notna().mean() > 0.95, "each genome cites its paper")
        self.assertEqual([v for v in ancestry.validation(ACFG, d) if not v[-1]], [], "validation individuals moved")


class Layers(unittest.TestCase):
    def test_registry(self):
        ids = [L["id"] for L in REGISTRY if L["set"] == "Ancestry"]
        self.assertEqual(ids, [f"anc_{k}" for k in ORDER])
        for m in ids:
            L = REGISTRY[m]
            self.assertFalse(L["fill"], m)
            self.assertEqual((L["kind"], L["unit"], L["value_field"], L["evidence_word"]), ("share", "sample", "w_" + m[4:], "genomes"))
        self.assertTrue(all(L["fill"] for L in REGISTRY if L["set"] != "Ancestry"))
        self.assertEqual({REGISTRY[m]["sigma"] for m in ids}, {"cv", "anc_ana"}, "the six layers share one kernel width")
        self.assertEqual(REGISTRY["anc_ana"]["sigma"], "cv")

    def test_colours_match_the_game(self):
        """The pipeline's maps and the app use one colour per component."""
        import re
        src = open("neolith-rs/crates/app/src/palette.rs").read()
        row = re.search(r"pub const ANCESTRY: \[Rgb; [^\]]+\] =\s*\[(.*?)\];", src, re.S).group(1)
        game = ["#" + h.lower() for h in re.findall(r"hex\(0x([0-9a-fA-F]{6})\)", row)]
        self.assertEqual([REGISTRY[f"anc_{k}"]["colour"] for k in ORDER], game)

    def test_values_join(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.csv.gz")
            table([{"individual": "a", "status": "fit", **{f"w_{k}": 0.0 for k in ORDER}, "w_whg": 0.3, "w_ana": 0.7},
                   {"individual": "b", "status": "no_fit"},
                   {"individual": "r", "status": "reference", **{f"w_{k}": 0.0 for k in ORDER}, "w_ana": 1.0}]).to_csv(path, index=False)
            v = people.ancestry_values(path, ["b", "a", "zz", "r"])
            self.assertTrue(np.isnan(v["w_ana"].values[[0, 2, 3]]).all(), "only fits carry a value")
            self.assertEqual((v["w_ana"][1], v["w_irn"][1]), (0.7, 0.0))
        self.assertIsNone(people.ancestry_values(os.path.join(d, "missing.csv.gz"), ["a"]))

    def test_surface_takes_fractional_shares(self):
        """Kernel mean and leave-one-out loss with soft labels: the surface of
        fractional values is the weighted mean, and components sum to 1."""
        rng = np.random.default_rng(3)
        n = 60
        lon, lat = rng.uniform(10, 14, n), rng.uniform(45, 48, n)
        W = rng.uniform(0.2, 1, (n, 2))
        parts = rng.dirichlet([1, 1, 1], n)
        glon, glat = np.meshgrid(np.linspace(10, 14, 5), np.linspace(45, 48, 4))
        f = []
        for k in range(3):
            y = parts[:, k]
            r = surface.surfaces(glon.ravel(), glat.ravel(), lon, lat, W, y, np.zeros(n, bool), W, lon, lat,
                                 100, 2.5, 1.0, 1.2, 5, 7)
            f.append(r["f"])
            self.assertTrue(((r["f"] >= y.min() - 1e-9) & (r["f"] <= y.max() + 1e-9)).all())
        np.testing.assert_allclose(sum(f), 1.0, atol=1e-5)
        # One far-off place whose neighbours all hold 0.8: a narrow kernel predicts it, loss is the soft cross-entropy.
        y = np.full(n, 0.8)
        cv = surface.cross_validate(lon, lat, W, y, [100], 2.5, 1.0)[100]
        h = -(0.8 * np.log(0.8) + 0.2 * np.log(0.2))
        self.assertAlmostEqual(cv["log_loss"], h, places=5)
        skew = surface.cross_validate(lon, lat, W, np.where(lon > 12, 0.9, 0.1), [50, 300], 2.5, 1.0)
        self.assertLess(skew[50]["log_loss"], skew[300]["log_loss"])


class NoFill(unittest.TestCase):
    def test_written_cells(self):
        land = np.array([True, True, True, False])
        basis = np.array(["observed", "judged", "extrapolated", ""], dtype=object)
        np.testing.assert_array_equal(speculative.written(land, basis, True), land)
        np.testing.assert_array_equal(speculative.written(land, basis, False), [True, False, False, False])

    @unittest.skipUnless(os.path.exists("data/isostyle/speculative/speculative.csv.gz"), "speculative layers not built")
    def test_no_ancestry_cell_is_filled(self):
        s = pd.read_csv("data/isostyle/speculative/speculative.csv.gz", usecols=["layer", "basis"])
        a = s[s["layer"].str.startswith("anc_")]
        self.assertEqual(sorted(set(a["basis"]) - {"observed"}), [])


if __name__ == "__main__":
    unittest.main()
