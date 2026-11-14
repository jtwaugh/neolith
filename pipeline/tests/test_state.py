import json
import os
import tempfile
import unittest
from unittest import mock

from pipeline import state


class Parsers(unittest.TestCase):
    def test_unittest(self):
        self.assertEqual(state.parse_unittest("....\nRan 12 tests in 0.1s\n\nOK\n"), (12, 0))
        self.assertEqual(state.parse_unittest("Ran 5 tests in 1s\n\nFAILED (failures=2, errors=1)"), (5, 3))

    def test_cargo(self):
        out = ("test result: ok. 9 passed; 0 failed; 0 ignored\n"
               "test result: FAILED. 4 passed; 2 failed; 1 ignored\n")
        self.assertEqual(state.parse_cargo(out), (13, 2, True))
        self.assertFalse(state.parse_cargo("error[E0425]: cannot find value\nerror: could not compile `x`")[2])

    def test_anchors(self):
        t = "23 anchors have both. Same main game class: 15 (65%); compatible (the class lists overlap): 20 (87%)."
        self.assertEqual(state.parse_anchors(t), (65, 87))
        self.assertEqual(state.parse_anchors("nothing"), (None, None))

    def test_suspects(self):
        line = ("wrote a.md and a.json: 66 straight edges and thin bands, 100 surges and flickers, "
                "0 floodplains lost, 24 speckle")
        self.assertEqual(state.parse_suspects(line), {"straight edges and thin bands": 66, "surges and flickers": 100,
                                                      "floodplains lost": 0, "speckle": 24})

    def test_report(self):
        t = ("Grid: 26410 hexes. Neighbour\n\n## Settlements on Water\n\n15 of 8108 settlements have their own hex as Water"
             "\n\n| settlement | lon, lat | years | first…last | offshore |\n|---|---|---|---|---|\n"
             "| A | 1, 2 | 1 / 1 | -1…-1 | 0 |\n| B | 1, 2 | 1 / 1 | -1…-1 | 800 |\n\n## Islands\n")
        r = state.parse_report(t)
        self.assertEqual((r["hexes"], r["on_water"], r["settlements"], r["offshore"]), (26410, 15, 8108, 1))


class Fold(unittest.TestCase):
    def test_matches_renown_rs(self):
        # The examples in renown.rs `fold`'s doc comment.
        self.assertEqual(state.fold("Qala’at Jarmo"), "qalaat jarmo")
        self.assertEqual(state.fold("Çatalhöyük"), "catalhoyuk")
        self.assertEqual(state.fold("Ġgantija"), "ggantija")
        self.assertEqual(state.fold("Tell es-Sultan"), "tell es sultan")


class FamousSites(unittest.TestCase):
    E = [{"name": "Jericho", "aliases": ["Tell es-Sultan"], "renown": 3, "lon": 35.444, "lat": 31.871},
         {"name": "Mehrgarh", "aliases": [], "renown": 3, "lon": 67.6, "lat": 29.4}]

    def site(self, name, lon, lat, f=-9000, a=-6000):
        return {"name": name, "pos": (lon, lat), "founding": f, "abandoned": a, "occupation": [[f, a]]}

    def test_match_and_problems(self):
        sites = [self.site("Jericho", 35.444, 31.871), self.site("Tell es-Sultan area B", 35.50, 31.80),
                 self.site("Jericho", 36.5, 31.871)]  # over 15 km away: not Jericho
        r = {x["name"]: x for x in state.famous_sites(self.E, sites)}
        self.assertEqual(r["Jericho"]["records"], 2)
        self.assertEqual(r["Jericho"]["problems"], ["1 more records over 2 km away"])
        self.assertEqual(r["Mehrgarh"]["problems"], ["not on the map"])

    def test_whole_words_and_span(self):
        sites = [self.site("Jerichoville", 35.444, 31.871), self.site("Jericho", 35.444, 31.871, -2000, -1000)]
        r = state.famous_sites(self.E[:1], sites)[0]
        self.assertEqual(r["records"], 1)
        self.assertEqual(r["problems"], ["dated outside 10,000-3,000 BCE"])

    def test_parts_are_not_stray(self):
        e = {"name": "Fayum", "aliases": ["Faiyum"], "renown": 2, "lon": 30.6, "lat": 29.45, "radius_km": 40}
        sites = [self.site("Fayum", 30.5, 29.5), self.site("Fayum A80", 30.5, 29.33),  # 19 km apart
                 self.site("Fayum B", 30.9, 29.45)]
        r = state.famous_sites([e], sites)[0]
        self.assertEqual((r["records"], r["problems"]), (3, ["2 more records over 2 km away"]))
        r = state.famous_sites([{**e, "parts": ["Fayum A80"]}], sites)[0]
        self.assertEqual((r["records"], r["problems"]), (3, ["1 more records over 2 km away"]))
        # A part is the primary only when nothing else matches: the nearer
        # part does not make the site's own record a stray.
        near = {**e, "lon": 30.5, "lat": 29.33, "parts": ["Fayum A80"]}
        self.assertEqual(state.famous_sites([near], sites[:2])[0]["problems"], [])
        self.assertEqual(state.famous_sites([near], sites[1:2])[0]["problems"], [])
        # Whole words, like aliases: "A80" is not "A801".
        self.assertEqual(state.famous_sites([{**e, "parts": ["Fayum A80"]}],
                                            [sites[0], self.site("Fayum A801", 30.5, 29.33)])[0]["problems"],
                         ["1 more records over 2 km away"])


class Rows(unittest.TestCase):
    def test_targets_gate_and_delta(self):
        rows = [state.row("H", "a", 2), state.row("H", "b", 0.5), state.row("H", "c", 7)]
        state.apply_targets(rows, {"a": {"max": 0, "gate": True}, "b": {"min": 0.4}})
        self.assertEqual([r["ok"] for r in rows], [False, True, None])
        self.assertEqual([r["gate"] for r in rows], [True, False, False])
        state.add_deltas(rows, {"rows": [{"name": "a", "value": 3}, {"name": "c", "value": 7}]})
        self.assertEqual([r["delta"] for r in rows], [-1, None, None])

    def test_render(self):
        rows = state.apply_targets([state.row("Health", "a", 0)], {"a": {"max": 0, "gate": True}})
        card = {"commit": "abc", "dirty": False, "date": "2026-11-13", "pass": True, "rows": rows,
                "famous": [], "critics": [], "stale": []}
        md = state.render(card)
        self.assertIn("| ok | a | 0 |", md)
        self.assertIn("≤ 0 (gate)", md)


class Critics(unittest.TestCase):
    def test_latest_per_critic(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "critics"))
            for date, overall in (("2026-11-01", 1.0), ("2026-11-10", 2.0)):
                json.dump({"critic": "gsg-critic", "date": date, "overall": overall,
                           "findings": [{"id": "x", "status": "open"}, {"id": "y", "status": "fixed"}]},
                          open(os.path.join(d, "critics", f"{date}-gsg-critic.json"), "w"))
            with mock.patch.object(state, "STATE_DIR", d):
                out = state.critics(today="2026-11-13")
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]["overall"], out[0]["age_days"], out[0]["open"], out[0]["findings"]), (2.0, 3, 1, 2))


class Interact(unittest.TestCase):
    def test_widget_shifts(self):
        from pipeline import interact
        w = lambda role, label, x, y: {"role": role, "label": label, "centre_px": [x, y]}
        before = [w("Button", "Play", 10, 10), w("Label", "Savannah", 50, 200), w("TextRun", "x", 0, 0)]
        after = [w("Button", "Play", 12, 10), w("Label", "Savannah", 50, 430), w("Label", "New", 9, 9)]
        self.assertEqual(interact.widget_shifts(before, after, 4), [{"widget": "Label 'Savannah'", "px": 230}])

    def test_crowded(self):
        from pipeline import interact
        self.assertEqual(interact.crowded([(0, 0), (10, 0), (100, 100)], 24), 2)


class RepoCritics(unittest.TestCase):
    def test_critic_files_parse(self):
        import glob
        for p in glob.glob("data/state/critics/*.json"):
            d = json.load(open(p))
            self.assertTrue(os.path.basename(p).startswith(d["date"]), p)
            self.assertTrue(os.path.basename(p).endswith(f"-{d['critic']}.json"), p)
            for f in d.get("findings", []):
                self.assertIn(f.get("status", "open"), ("open", "fixed", "wontfix"), p)


if __name__ == "__main__":
    unittest.main()
