import json
import os
import tempfile
import unittest
from unittest import mock

from pipeline import cultures as cu

TABLE = {
    "ignore": [r"\b(transition|or)\b", "^(early|late)$"],
    "stage": [
        {"id": "mesolithic", "name": "Mesolithic", "wikipedia": "Mesolithic", "match": r"\bmesolithi|^lm$",
         "start": -13000, "end": -3000, "quotes": ["15,000 to 5,000 bp"], "traits": {"economy": "foraging"}},
        {"id": "aceramic", "name": "Aceramic Neolithic", "key": "pre pottery", "wikipedia": "Pre-Pottery Neolithic",
         "match": "^acn$", "start": -10000, "end": -6500, "quotes": ["q"], "parent": "neolithic"},
        {"id": "neolithic", "name": "Neolithic", "wikipedia": "Neolithic", "match": r"\bneolith|^en$",
         "start": -10000, "end": -2000, "quotes": ["q"], "traits": {"economy": "farming"}},
    ],
    "culture": [
        {"id": "ppna", "name": "PPNA", "stage": "aceramic", "wikipedia": "Pre-Pottery Neolithic A", "match": r"\bppna\b",
         "start": -10000, "end": -8800, "quotes": ["10,000–8800 bce"]},
        {"id": "ppnb", "name": "PPNB", "stage": "aceramic", "wikipedia": "Pre-Pottery Neolithic B", "match": r"\b[eml]?ppnb\b",
         "start": -8800, "end": -6500, "quotes": ["8800–6500 bc"]},
        {"id": "lbk", "name": "Linear Pottery", "stage": "neolithic", "wikipedia": "Linear Pottery culture",
         "match": r"^(?!.*hinkelstein).*(\blbk\b|bandkeramik)", "traits": {"economy": "farming", "houses": ["longhouse"]}},
        {"id": "rossen", "name": "Rössen", "stage": "neolithic", "wikipedia": "Rössen culture", "match": r"\brossen\b"},
    ],
    "vocab": {"economy": {"farming": "agricultur|farm"}, "houses": {"longhouse": "long ?house"}},
}


def table(**changes):
    data = json.loads(json.dumps(TABLE))
    for k, v in changes.items():
        data[k] = v
    return cu.Table(data)


def row(*periods):
    return {"periods": set(periods)}


class Labels(unittest.TestCase):
    def test_norm_label(self):
        self.assertEqual(cu.norm_label("Starčevo–Körös–Criș"), "starcevo koros cris")
        self.assertEqual(cu.norm_label("Ertebølle-Ellerbek"), "ertebolle ellerbek")
        self.assertEqual(cu.norm_label("Großgartach"), "grossgartach")
        self.assertEqual(cu.norm_label("  ʿAin  Ghazal "), "ain ghazal")

    def test_match(self):
        t = table()
        self.assertEqual(t.match("Linienbandkeramik"), ("culture", "lbk"))
        self.assertEqual(t.match("MPPNB"), ("culture", "ppnb"))
        self.assertEqual(t.match("Neolithic LBK"), ("culture", "lbk"))   # a culture beats a stage
        self.assertEqual(t.match("EN"), ("stage", "neolithic"))
        self.assertIsNone(t.match("LBK/Rössen"))                         # two cultures: ambiguous
        self.assertIsNone(t.match("Mesolithic/Neolithic"))               # two stages: ambiguous
        self.assertIsNone(t.match("LBK-Hinkelstein"))                    # excluded by the pattern
        self.assertIsNone(t.match("transition LBK"))                     # ignore list
        self.assertIsNone(t.match("Early"))
        self.assertIsNone(t.match("Bronze Age"))

    def test_validation(self):
        bad = [
            dict(culture=TABLE["culture"] + [dict(TABLE["culture"][0])]),                      # duplicate id
            dict(culture=[{**TABLE["culture"][0], "stage": "nope"}]),                            # unknown stage
            dict(culture=[{**TABLE["culture"][0], "start": -8000, "end": -9000}]),               # start >= end
            dict(culture=[{**TABLE["culture"][0], "quotes": []}]),                               # range, no quote
            dict(culture=[{**TABLE["culture"][2], "traits": {"colour": "red"}}]),               # unknown trait
            dict(culture=[{**TABLE["culture"][2], "traits": {"houses": "longhouse"}}]),         # list trait
            dict(stage=[{**TABLE["stage"][1], "parent": "nope"}] + TABLE["stage"][2:]),
        ]
        for b in bad:
            with self.subTest(b=list(b)), self.assertRaises(ValueError):
                table(**b)


class Dates(unittest.TestCase):
    def test_site_level_labels_resolve_by_range(self):
        t = table()
        site = ("ACN", "PPNA", "PPNB", "Neolithic")       # every date at the site carries all of these
        self.assertEqual(cu.date_hits(t, site, -9500, 200), ("ppna", "aceramic", {"ppnb"}))
        self.assertEqual(cu.date_hits(t, site, -7500, 200), ("ppnb", "aceramic", {"ppna"}))
        c, s, out = cu.date_hits(t, site, -8850, 200)      # both fit within the margin
        self.assertEqual((c, s, out), (None, "aceramic", set()))
        c, s, out = cu.date_hits(t, site, -6000, 200)      # neither culture: the stage that fits
        self.assertEqual((c, s), (None, "neolithic"))
        self.assertEqual(cu.date_hits(t, site, -22000, 200)[:2], (None, None))

    def test_stage_parent_and_out_of_range(self):
        t = table()
        self.assertEqual(cu.date_hits(t, ("ACN", "Neolithic"), -8000, 0)[1], "neolithic")
        self.assertEqual(cu.date_hits(t, ("Mesolithic", "Neolithic"), -11000, 0)[1], "mesolithic")
        self.assertIsNone(cu.date_hits(t, ("Mesolithic", "Neolithic"), -5000, 0)[1])
        self.assertIsNone(cu.date_hits(t, ("EN",), -20000, 200)[1])

    def test_rangeless_culture_uses_observed_range(self):
        t = table()
        sites = [[(y, row("LBK")) for y in (-5400, -5300, -5200, -5100, -5000)], [(-9000, row("LBK", "Mesolithic"))]]
        cu.observe_ranges(t, sites, lo_q=10, hi_q=90)
        lbk = t.entries["lbk"]
        self.assertTrue(-9000 < lbk["obs_start"] <= -5300 and -5100 <= lbk["obs_end"] <= -5000)
        self.assertEqual(cu.date_hits(t, ("LBK",), -5250, 0)[0], "lbk")
        self.assertEqual(cu.date_hits(t, ("LBK", "Mesolithic"), -9000, 200)[:2], (None, "mesolithic"))
        self.assertEqual(cu.range_record(lbk)["start_source"], "observed")
        self.assertEqual(cu.range_record(t.entries["ppna"]),
                         {"start": -10000, "start_source": "cited", "end": -8800, "end_source": "cited",
                          "quotes": ["10,000–8800 bce"]})

    def test_assign_builds_timelines(self):
        t = table()
        feats = [{"geometry": {"coordinates": [35.4, 31.8]}, "properties": {"key": "k"}},
                 {"geometry": {"coordinates": [0, 0]}, "properties": {"key": "none"}}]
        site = ("ACN", "PPNA", "PPNB")
        dated = {"k": [(y, row(*site)) for y in (-9600, -9400, -8000, -7600, -7000)]}
        n, used, outside = cu.assign(feats, dated, t, trim=0.0, margin=200)
        p = feats[0]["properties"]
        self.assertEqual(n, 1)
        self.assertEqual(p["culture"], {"-9600": "ppna", "-8000": "ppnb"})
        self.assertEqual(p["culture_dates"], {"ppnb": 3, "ppna": 2})
        self.assertEqual(p["stage"], {"-9600": "aceramic"})
        self.assertEqual((used["ppna"], outside["ppna"], outside["ppnb"]), (2, 3, 2))
        self.assertNotIn("culture", feats[1]["properties"])
        compiled = {r["id"]: r for r in cu.compile_table(t, feats, {}, used, outside)}
        self.assertEqual((compiled["ppna"]["sites"], compiled["ppna"]["dates_used"]), (1, 2))
        self.assertEqual(compiled["ppnb"]["observed"]["start_median"], -8000)

    def test_timeline_tie_goes_to_more_dates(self):
        self.assertEqual(cu._timeline({"a": [-100], "b": [-100, -50], "c": [-10]}, 0.0), {"-100": "b", "-10": "c"})


class Infer(unittest.TestCase):
    CFG = {"radius_km": 50, "window_years": 250, "min_sites": 2, "min_share": 0.67}

    def sites(self):
        # Three LBK sites within ~20 km, one unlabelled site among them, one far away.
        pts = {"a": (10.0, 50.0), "b": (10.1, 50.05), "c": (10.2, 50.0), "u": (10.1, 50.0), "far": (20.0, 50.0)}
        feats = [{"geometry": {"coordinates": list(xy)}, "properties": {"key": k}} for k, xy in pts.items()]
        dated = {k: [(y, row("LBK")) for y in (-5300, -5200, -5100)] for k in "abc"}
        dated["u"] = [(-5250, row()), (-5150, row("Bronze Age")), (-3000, row())]
        dated["far"] = [(-5200, row())]
        return feats, dated

    def test_vote(self):
        ok = lambda i: True
        near = [(1.0, {"lbk": (-5300, -5100)}), (5.0, {"lbk": (-5400, -5000), "rossen": (-4800, -4600)}),
                (9.0, {"rossen": (-5000, -4600)})]
        self.assertEqual(cu.vote(near, -5200, 0, ok, 2, 0.67), ("lbk", 2, 2, 1.0))
        self.assertIsNone(cu.vote(near, -4900, 150, ok, 2, 0.67))        # rossen 2 of 3 votes: under min_share
        self.assertEqual(cu.vote(near, -4700, 0, ok, 2, 0.67)[0], "rossen")
        self.assertIsNone(cu.vote(near, -5200, 0, ok, 3, 0.67))          # min_sites
        self.assertIsNone(cu.vote(near, -5200, 0, lambda i: i != "lbk", 2, 0.67))

    def test_infer_fills_only_unlabelled_dates_nearby(self):
        t = table()
        feats, dated = self.sites()
        cu.assign(feats, dated, t, trim=0.0, margin=200)
        ic, _ = cu.infer(feats, dated, t, self.CFG, trim=0.0, margin=200)
        p = {f["properties"]["key"]: f["properties"] for f in feats}
        self.assertEqual(ic, 1)
        self.assertEqual(p["u"]["culture_inferred"], {"-5250": "lbk"})   # -3000 is outside LBK's observed range
        self.assertEqual(p["u"]["culture_inferred_support"]["lbk"][0], 3)
        self.assertNotIn("culture", p["u"])
        self.assertNotIn("culture_inferred", p["far"])
        self.assertNotIn("culture_inferred", p["a"])                       # its own labels already say

    def test_holdout(self):
        t = table()
        feats, dated = self.sites()
        cu.assign(feats, dated, t, trim=0.0, margin=200)
        self.assertEqual(cu.holdout(feats, dated, t, self.CFG, margin=200)["culture"], (9, 9, 9))


class Check(unittest.TestCase):
    def test_scoped_text_and_support(self):
        text = "intro about egypt.\nthe faiyum a people farmed emmer.\nunrelated: cattle herding in the delta."
        self.assertEqual(cu.scoped_text(text, "Faiyum A culture", "faiyum")[1], "article")
        body, scope = cu.scoped_text(text, "Prehistoric Egypt", "faiyum")
        self.assertEqual((scope, body), ("section", "the faiyum a people farmed emmer."))
        self.assertEqual(cu.scoped_text(text, "Prehistoric Egypt", "badari")[1], "none")
        vocab = {"economy": {"farming": "farm"}}
        self.assertTrue(cu.supported("farming", "economy", body, vocab))
        self.assertFalse(cu.supported("herding", "economy", body, vocab))      # only outside the section
        self.assertTrue(cu.supported("emmer", "domesticates", body, vocab))    # words, no vocab entry
        self.assertFalse(cu.supported("long houses", "houses", body, vocab))

    def test_check_records_revision_and_flags(self):
        t = table()

        def article(title, text):
            return {"query": {"pages": [{"title": title, "revisions": [{"revid": 42}],
                                         "pageprops": {"wikibase_item": "Q1"}, "extract": text}]}}
        texts = {"Linear Pottery culture": "The LBK were early farmers; agriculture spread.",
                 "Pre-Pottery Neolithic A": "PPNA, 10,000–8800 BCE.",
                 "Pre-Pottery Neolithic B": "PPNB dates differ."}

        def fake_fetch(url, path, dataset, **kw):
            title = next(v for k, v in __import__("urllib.parse").parse.parse_qsl(url.split("?", 1)[1]) if k == "titles")
            body = article(title, texts.get(title, title)) if title != "Rössen culture" else {"query": {"pages": [{"missing": True}]}}
            json.dump(body, open(path, "w"))
            return {"dataset": dataset, "url": url, "path": path}

        with tempfile.TemporaryDirectory() as d, mock.patch("pipeline.settlements.fetch", fake_fetch):
            path = os.path.join(d, "t.toml")
            with open(path, "w") as f:
                f.write("")
            with mock.patch.object(cu.Table, "load", classmethod(lambda cls, p: t)):
                out = cu.check(path, os.path.join(d, "cache"), os.path.join(d, "w.json"), log=lambda *_: None)
        self.assertEqual((out["lbk"]["revid"], out["lbk"]["wikidata"], out["lbk"]["scope"]), (42, "Q1", "article"))
        self.assertIn("oldid=42", out["lbk"]["url"])
        self.assertEqual(out["lbk"]["unsupported"], ["houses=longhouse"])
        self.assertEqual(out["ppna"]["unsupported"], [])
        self.assertEqual(out["ppnb"]["unsupported"], ["range quote='8800–6500 bc'"])
        self.assertTrue(out["rossen"]["missing"])


if __name__ == "__main__":
    unittest.main()
