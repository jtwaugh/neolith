import itertools
import unittest

import numpy as np

from pipeline import settlements as st
from pipeline.tests.test_pipeline import make_grid


_ages = itertools.count(1)


def date(site, lon, lat, bp, std=30, periods=()):
    """A date row. bp=0 stands for "some age", distinct on every call."""
    return {"site": site, "lon": lon, "lat": lat, "bp": bp or next(_ages), "std": std, "labnr": "",
            "type": "settlement", "periods": set(periods), "refs": ("RADON",), "dataset": "xronos"}


def point(name, lon, lat, founding, fid=None, **props):
    f = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
         "properties": {"name": name, "founding": founding, "sources": ["xronos"], "references": ["RADON"], **props}}
    if fid is not None:
        f["id"] = fid
    return f


class Rejects(unittest.TestCase):
    def test_drops_only_the_named_date_and_insists_it_exists(self):
        dates = [{"site": "Wustermark 22", "labnr": "Bln-5645"}, {"site": "Wustermark 22", "labnr": "KIA-32463"},
                 {"site": "Elsewhere", "labnr": "Bln-5645"}]
        self.assertEqual(st.apply_rejects(dates, {("Wustermark 22", st.lab_key("BLN 5645"))}), 1)
        self.assertEqual([(d["site"], d["labnr"]) for d in dates],
                         [("Wustermark 22", "KIA-32463"), ("Elsewhere", "Bln-5645")])
        with self.assertRaises(ValueError):
            st.apply_rejects(dates, {("Wustermark 22", "bln5645")})


class Calibrate(unittest.TestCase):
    def test_identity_curve_gives_the_date_back(self):
        cal = np.arange(0, 20001, st.CAL_STEP, dtype=float)
        curve = (cal, cal.copy(), np.full(len(cal), 10.0))
        out = st.calibrate([5000, 9350], [30, 50], curve)
        self.assertEqual(out.tolist(), [5000, 9350])

    def test_off_curve_is_nan(self):
        cal = np.arange(0, 1001, st.CAL_STEP, dtype=float)
        out = st.calibrate([90000], [30], (cal, cal.copy(), np.full(len(cal), 10.0)))
        self.assertTrue(np.isnan(out[0]))

    def test_to_year(self):
        self.assertEqual(st.to_year(9350), -7400)
        self.assertEqual(st.to_year(9354), -7400)


class Derive(unittest.TestCase):
    def test_groups_by_site_and_filters_window(self):
        dates = [date("A", 1, 2, 0, periods=["LBK"]), date("A", 1, 2, 0, periods=["LBK", "x"]),
                 date("B", 3, 4, 0), date("C", 5, 6, 0)]
        feats = st.derive_sites(dates, np.array([-5500, -5000, -2000, np.nan]), (-10000, -3000))
        self.assertEqual(len(feats), 1)
        p = feats[0]["properties"]
        self.assertEqual((p["name"], p["founding"], p["abandoned"], p["n_dates"]), ("A", -5500, -5000, 2))
        self.assertEqual(p["periods"], ["LBK", "x"])
        self.assertEqual(feats[0]["id"], st.site_id(p["key"]))

    def test_trim_ignores_stray_dates_at_well_dated_sites(self):
        ys = [-20000] + [-6000] * 38 + [-100]
        dates = [date("A", 1, 2, 0) for _ in ys]
        p = st.derive_sites(dates, np.array(ys), (-10000, -3000), trim=0.05)[0]["properties"]
        self.assertEqual((p["founding"], p["abandoned"]), (-6000, -6000))
        few = st.derive_sites(dates[:3], np.array([-9000, -6000, -5000]), (-10000, -3000), trim=0.05)
        self.assertEqual(few[0]["properties"]["founding"], -9000)


    def test_spellings_of_one_site_merge(self):
        dates = [date("Cueva de Bricia", 1.0, 2.0, 0), date("Cueva de Bricia", 1.0, 2.0, 0), date("Bricia", 1.001, 2.0, 0),
                 date("Bricia B", 1.0, 2.5, 0), date("Garma A", 1.0, 2.0, 0), date("Garma B", 1.0, 2.0, 0)]
        ys = np.array([-5000, -5100, -5300, -5000, -5000, -5000])
        feats = st.derive_sites(dates, ys, (-10000, -3000), same_km=1.0)
        by = {f["properties"]["name"]: f["properties"] for f in feats}
        self.assertEqual(sorted(by), ["Bricia", "Bricia B", "Garma A", "Garma B"])
        self.assertEqual((by["Bricia"]["n_dates"], by["Bricia"]["founding"]), (3, -5300))
        self.assertEqual(by["Bricia"]["aliases"], ["Cueva de Bricia"])
        self.assertEqual(len(st.derive_sites(dates, ys, (-10000, -3000))), 5)

    def test_same_name_merges_further_apart(self):
        dates = [date("Tell A", 1.0, 2.0, 0), date("tell a.", 1.03, 2.0, 0), date("Tell A East", 1.03, 2.0, 0)]
        ys = np.array([-5000, -5100, -5200])
        feats = st.derive_sites(dates, ys, (-10000, -3000), same_km=1.0, same_name_km=10.0)
        self.assertEqual(sorted(f["properties"]["n_dates"] for f in feats), [3])
        self.assertEqual(len(st.derive_sites(dates, ys, (-10000, -3000), same_km=1.0)), 2)


class Xronos(unittest.TestCase):
    def test_parse_dedupes_filters_and_types(self):
        import json, os, tempfile
        def m(i, **kw):
            return {"measurement": {"id": i, "labnr": "X-1", "bp": 6000, "std": 40, "site": " Tell  A ",
                                    "lat": "30.5", "lng": "31.5", "site_type": "Plein  Air",
                                    "periods": [{"periode": "PN"}, {"periode": "PN"}], **kw}}
        with tempfile.TemporaryDirectory() as d:
            a, b, c = (os.path.join(d, n) for n in "abc")
            json.dump([m(1), m(2, lat=None), m(3, site_type=None)], open(a, "w"))
            json.dump([m(1), m(4, std=0)], open(b, "w"))
            json.dump(None, open(c, "w"))
            seen = set()
            rows = st.parse_xronos(a, seen, {"plein air": "open air"})
            self.assertEqual([(r["site"], r["type"], r["lat"]) for r in rows],
                             [("Tell A", "open air", 30.5), ("Tell A", "site", 30.5)])
            self.assertEqual(rows[0]["periods"], {"PN"})
            self.assertEqual(st.parse_xronos(b, seen), [])
            self.assertEqual(st.parse_xronos(c, seen), [])


    def test_fix_mojibake(self):
        self.assertEqual(st.fix_mojibake("Sundfj√¶ra"), "Sundfjæra")            # Mac Roman
        self.assertEqual(st.fix_mojibake("GraviÃ¨re II"), "Gravière II")         # Windows-1252, not Mac Roman
        self.assertEqual(st.fix_mojibake("CaÅ‚owanie"), "Całowanie")
        self.assertEqual(st.fix_mojibake("OkrouhlÃ\xadk I."), "Okrouhlík I.")     # soft hyphen byte
        self.assertEqual(st.fix_mojibake("Ã…Â¡andalija II"), "šandalija II")      # two layers
        self.assertEqual(st.fix_mojibake("GÔøΩbekli Tepe"), "G\ufffdbekli Tepe")  # lost in the source
        self.assertEqual(st.fix_mojibake("Skj√¶rvika øvre"), "Skjærvika øvre")    # good and bad letters mixed
        self.assertEqual(st.fix_mojibake("Å\uf181ojewo 1"), "Łojewo 1")            # undefined byte as U+F1xx
        self.assertEqual(st.fix_mojibake("Vela peÃÂÂ"), "Vela pe\ufffd")            # cut off: lost
        self.assertEqual(st.fix_mojibake("Can Sadurn√ɬâ‰ÂÂ"), "Can Sadurn\ufffd")
        self.assertEqual(st.fix_mojibake("SÃO JOÃO"), "SÃO JOÃO")
        self.assertEqual(st.fix_mojibake("PàÔøΩÔøΩovice"), "Pà\ufffd\ufffdovice")       # bad start, good rest
        self.assertEqual(st.fix_mojibake("JezevÄ\uf18dÃ\xad převis"), "Jezevčí převis")
        self.assertEqual(st.fix_mojibake("Goulet Â«Â\xa0Le MontÂ\xa0Â»"), "Goulet «\xa0Le Mont\xa0»")
        self.assertEqual(st.fix_mojibake("Balmes Ã\xa0Sollières"), "Balmes àSollières")
        for ok in ("Çatalhöyük", "Tell es-Sultan", "ʿAin Ghazal", "Ærø", "Sesklo Â", "Gravière",
                   "Pas de l’Échelle", "Tsé Haal’á"):                                # valid UTF-8 as Mac Roman, but not Latin
            self.assertEqual(st.fix_mojibake(ok), ok)

    def test_repair_lost(self):
        L = "\ufffd"
        dates = [date("Göbekli Tepe", 38.92, 37.22, 9000, 50), date(f"G{L}bekli Tepe", 38.921, 37.22, 9100, 50),
                 date(f"Clot de l{L}Hospital", 2.0, 42.0, 7000, 50), date("Clot de l’Hospital", 2.0, 42.0, 7010, 50),
                 date(f"K{L}nigsaue", 11.0, 51.0, 6000, 50),                       # no clean spelling
                 date(f"G{L}bekli Tepe", 10.0, 10.0, 6000, 50),                    # too far from the clean one
                 date(f"B{L}rg", 5.0, 50.0, 6000, 50), date("Barg", 5.0, 50.0, 1, 1), date("Borg", 5.0, 50.0, 1, 1)]
        self.assertEqual(st.repair_lost(dates, km=10), (2, 3))
        self.assertEqual([d["site"] for d in dates[:4]], ["Göbekli Tepe"] * 2 + ["Clot de l’Hospital"] * 2)
        self.assertEqual(dates[6]["site"], f"B{L}rg")                               # two candidates: ambiguous


class Sources(unittest.TestCase):
    def test_duplicate_records_of_one_date_collapse(self):
        a = {**date("A", 1, 2, 5690, 45), "labnr": "Ly-2447", "refs": ("RADON",)}
        b = {**a, "refs": ("EUROEVOL", "p3k14c"), "dataset": "p3k14c"}
        c = {**a, "labnr": "Lyon-2447", "refs": ("CalPal",)}       # same age and error
        d = {**a, "labnr": "Ly-2447", "bp": 5700.0, "refs": ()}     # same lab number
        e = {**date("A", 1, 2, 5000, 40), "labnr": "Ly-1"}
        dated = {}
        f = st.derive_sites([a, b, c, d, e], np.array([-4520, -4520, -4520, -4530, -3800]),
                            (-10000, -3000), dated=dated)[0]["properties"]
        self.assertEqual((f["n_dates"], f["sources"]), (2, ["xronos"]))
        self.assertEqual(f["references"], ["RADON", "CalPal", "EUROEVOL", "p3k14c"])
        rows = dated[f["key"]]
        self.assertEqual([r["labnr"] for _, r in rows], ["Ly-2447", "Ly-1"])
        self.assertEqual(a["refs"], ("RADON",))  # inputs untouched

    def test_parse_table_skips_dates_in_hand(self):
        import os, tempfile
        spec = {"name": "t", "delimiter": "\t",
                "columns": {"labnr": "Lab", "bp": "Age", "std": "SD", "lon": "X", "lat": "Y",
                            "site": "Site", "period": "Per", "refs": ["bib", "url"]}}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.tsv")
            with open(path, "w", encoding="utf-8") as f:
                f.write("Site\tLab\tAge\tSD\tX\tY\tPer\tbib\turl\r\n"
                        "Cova A\tBeta-1\t6500\t40\t1.5\t41.0\tEN\tSmith 2001\thttps://x\r\n"
                        "Cova A\tBETA 1\t6500\t40\t1.5\t41.0\tEN\tdup\t\r\n"
                        "Cova B\tOxA-9\t6400\t35\t1.6\t41.1\t\tJones 1999\t\r\n"
                        "Cova C\t\t6400\t35\t1.6\t41.1\t\t\t\r\n"
                        "Cova D\tKN-3\tn/a\t35\t1.6\t41.1\t\t\t\r\n")
            labs = {"oxa9"}
            rows = st.parse_table(path, spec, labs)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["site"], r["labnr"], r["bp"], r["lon"], r["dataset"], r["type"]),
                         ("Cova A", "Beta-1", 6500.0, 1.5, "t", "site"))
        self.assertEqual((r["refs"], r["periods"]), (("Smith 2001", "https://x"), {"EN"}))
        self.assertEqual(labs, {"oxa9", "beta1"})

    def test_citation_files(self):
        import gzip, os, tempfile
        dated = {}
        dates = [{**date("A", 1, 2, 6000), "labnr": "X-1", "refs": ("RADON", "Smith 2001")},
                 {**date("A", 1, 2, 5900), "labnr": "X-2", "refs": (), "dataset": "t"},
                 {**date("Gone", 9, 9, 5900), "labnr": "X-3"}]
        feats = st.derive_sites(dates, np.array([-4900, -4800, -4800]), (-10000, -3000), dated=dated)
        feats = [f for f in feats if f["properties"]["name"] == "A"]
        feats[0]["id"] = 7  # as a curated merge would
        cites = {"xronos": {"title": "XRONOS", "citation": "Roe 2025", "licence": "CC BY 4.0", "url": "u"},
                 "t": {"title": "T", "citation": "T 2020", "licence": "L", "note": "n"}}
        prov = [{"dataset": "xronos", "fetched": "2026-11-11", "path": "a"},
                {"dataset": "xronos", "fetched": "2026-11-12", "path": "b"}]
        with tempfile.TemporaryDirectory() as d:
            n = st.write_dates(os.path.join(d, "dates.csv.gz"), feats, dated)
            text = gzip.open(os.path.join(d, "dates.csv.gz"), "rt").read().splitlines()
            st.write_sources(os.path.join(d, "S.md"), cites, feats, dated, prov, min_refs=1)
            md = open(os.path.join(d, "S.md")).read()
        self.assertEqual(n, 2)
        self.assertEqual(text[1], "7,A,X-1,6000,30,-4900,xronos,A,RADON | Smith 2001")
        self.assertEqual(text[2], "7,A,X-2,5900,30,-4800,t,A,")
        self.assertIn("**Cite:** Roe 2025", md)
        self.assertIn("2026-11-11 to 2026-11-12 (2 files", md)
        self.assertIn("**In the output:** 1 sites, 1 dates", md)
        self.assertIn("| RADON | 1 |", md)
        self.assertIn("1 dates carry no reference", md)
        self.assertNotIn("Gone", "".join(text))


class Wikidata(unittest.TestCase):
    ITEMS = [
        {"qid": "Q1", "name": "Franchthi Cave", "names": ["Franchthi Cave", "Franchthi"], "lon": 23.13,
         "lat": 37.42, "inception": -38000, "cultures": ["X culture"], "wikipedia": "Franchthi Cave"},
        {"qid": "Q2", "name": "Other", "names": ["Other"], "lon": 23.13, "lat": 37.42,
         "inception": -5005, "cultures": [], "wikipedia": "Other (site)"},
        {"qid": "Q3", "name": "Late", "names": ["Late"], "lon": 23.0, "lat": 37.0,
         "inception": 300, "cultures": [], "wikipedia": "Late"},
        {"qid": "Q4", "name": "The Cave", "names": ["The Cave"], "lon": 23.131, "lat": 37.42,
         "inception": None, "cultures": [], "wikipedia": "The Cave"},
        {"qid": "Q2", "name": "Other", "names": ["Other"], "lon": 23.13, "lat": 37.42,
         "inception": -5005, "cultures": [], "wikipedia": "Other (site)"},
    ]

    def test_match_add_and_skip(self):
        feats = [point("Franchthi", 23.131, 37.422, -9000), point("Far Franchthi", 25.0, 37.4, -9000)]
        out, matched, added = st.enrich_wikidata(feats, self.ITEMS, 5.0, (-10000, -3000))
        self.assertEqual((matched, added, len(out)), (1, 1, 3))
        p = out[0]["properties"]
        self.assertEqual((p["wikidata"], p["wikipedia"], p["wikidata_culture"]), ("Q1", "Franchthi Cave", ["X culture"]))
        self.assertEqual(p["sources"], ["xronos", "wikidata"])
        self.assertNotIn("wikidata", out[1]["properties"])
        new = out[2]["properties"]
        self.assertEqual((new["name"], new["founding"], new["sources"], new["references"], new["n_dates"]),
                         ("Other", -5000, ["wikidata"], ["Wikidata Q2"], 0))

    def test_parse(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "w.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write("item,name,point,inception,cultures,alts,enwiki\r\n"
                        "http://www.wikidata.org/entity/Q173527,Knossos,Point(25.163 35.298),"
                        "-6999-01-01T00:00:00Z,Minoan civilization,Cnossus|Knossus,Knossos (Crete)\r\n"
                        "http://www.wikidata.org/entity/Q9,,Point(1 2),,,,Some Site\r\n")
            a, b = st.parse_wikidata(path)
        self.assertEqual((a["qid"], a["lon"], a["lat"], a["inception"]), ("Q173527", 25.163, 35.298, -6999))
        self.assertEqual(a["names"], ["Knossos", "Knossos", "Cnossus", "Knossus"])
        self.assertEqual((a["cultures"], a["wikipedia"]), (["Minoan civilization"], "Knossos (Crete)"))
        self.assertEqual((b["name"], b["inception"], b["cultures"]), ("Some Site", None, []))

    def test_tiles_cover_bounds(self):
        t = st.wikidata_tiles((-16.5, 6.0, 66.0, 76.0), 10.0)
        self.assertEqual(len(t), 9 * 7)
        self.assertEqual((t[0], t[-1]), ((-16.5, 6.0, -6.5, 16.0), (63.5, 66.0, 66.0, 76.0)))


class Hex(unittest.TestCase):
    def test_assign_and_drop(self):
        g = make_grid(3, 3)
        feats = st.assign_hex(g, [point("in", 0.75, -0.9, -5000), point("out", 50, 50, -5000)])
        self.assertEqual([f["properties"]["name"] for f in feats], ["in"])
        i = int(np.flatnonzero(g.ids == feats[0]["properties"]["hex"])[0])
        self.assertTrue(np.allclose(g.centres[i], [0.75, -np.sqrt(3) / 2 - np.sqrt(3) / 4], atol=0.5))


class Occupation(unittest.TestCase):
    def test_phases_split_at_gaps_and_end_after_gap(self):
        self.assertEqual(st.occupation([-9000, -8500, -7900, -5000, -4800], 1000),
                         [[-9000, -6900], [-5000, -3800]])
        self.assertEqual(st.occupation([-6000], 1000), [[-6000, -5000]])
        self.assertEqual(st.occupation([-6000, -5000], 1000), [[-6000, -4000]])  # exactly gap: one phase
        self.assertEqual(st.occupation([-6000], 0), [])
        self.assertEqual(st.occupation([], 1000), [])

    def test_derive_sites_uses_trimmed_dates(self):
        dates = [{"site": "S", "lon": 1.0, "lat": 2.0, "type": "site", "periods": [], "dataset": "x",
                  "refs": [], "labnr": f"L-{i}", "bp": i, "std": 0} for i in range(3)]
        p = st.derive_sites(dates, np.array([-7000, -6800, -3000]), (-10000, -3000), gap=1000)[0]["properties"]
        self.assertEqual(p["occupation"], [[-7000, -5800], [-3000, -2000]])


class Curated(unittest.TestCase):
    def test_merge_by_distance_by_name_and_unmatched(self):
        feats = [point("Tell es-Sultan", 35.47, 31.86, -9000, n_dates=5),
                 point("Far I", 39.0, 36.5, -7000, n_dates=9)]
        cur = [point("Jericho", 35.44, 31.85, -9600, fid=4),
               {"type": "Feature", "id": 11, "geometry": None,
                "properties": {"name": "Far", "founding": -6100, "match": "Far I"}},
               point("Lone", 0.0, 0.0, -4000, fid=13)]
        for c in cur:
            c["properties"].pop("sources", None)
            c["properties"].pop("references", None)
        out = {f["properties"]["name"]: f for f in st.merge_curated(feats, cur, 5.0)}
        self.assertEqual(sorted(out), ["Far", "Jericho", "Lone"])
        j = out["Jericho"]
        self.assertEqual((j["id"], j["properties"]["founding"], j["properties"]["n_dates"]), (4, -9600, 5))
        self.assertEqual(j["properties"]["aliases"], ["Tell es-Sultan"])
        self.assertEqual(j["geometry"]["coordinates"], [35.44, 31.85])
        self.assertEqual(out["Far"]["geometry"]["coordinates"], [39.0, 36.5])
        self.assertNotIn("match", out["Far"]["properties"])
        self.assertEqual(out["Lone"]["properties"]["sources"], ["curated"])
        self.assertEqual(j["properties"]["sources"], ["xronos", "curated"])
        self.assertEqual(j["properties"]["references"], ["RADON"])

    def test_features_and_wikipedia_pass_through(self):
        feats = [point("Valcamonica", 10.35, 46.03, -8000, n_dates=3)]
        cur = [{"type": "Feature", "geometry": None,
                "properties": {"name": "Val Camonica", "founding": -8000, "match": "Valcamonica",
                               "features": ["rock art"], "wikipedia": "Rock Drawings in Valcamonica"}}]
        (out,) = st.merge_curated(feats, cur, 5.0)
        self.assertEqual(out["properties"]["features"], ["rock art"])
        self.assertEqual(out["properties"]["wikipedia"], "Rock Drawings in Valcamonica")

    def test_unknown_match_raises(self):
        cur = [{"type": "Feature", "geometry": None, "properties": {"name": "X", "founding": 0, "match": "nope"}}]
        with self.assertRaises(ValueError):
            st.merge_curated([], cur, 5.0)


if __name__ == "__main__":
    unittest.main()


CLASSES = {"default": 1, "3": ["tell", "enclosure"], "2": ["settlement"], "1": ["cave"], "0": ["pit", "hearth"]}
IMPORTANCE = {"min_span": 1000, "persist_top": 0.75, "local_km": 150, "local_top": 0.9, "local_min_dates": 5, "class": CLASSES}


class Importance(unittest.TestCase):
    def test_site_class_highest_keyword_wins(self):
        self.assertEqual(st.site_class("causewayed enclosure", CLASSES), 3)
        self.assertEqual(st.site_class("settlement (pit)", CLASSES), 2)
        self.assertEqual(st.site_class("isolated pit", CLASSES), 0)
        self.assertEqual(st.site_class("something new", CLASSES), 1)

    def test_local_rank_compares_with_neighbours_only(self):
        # A cluster of ten 8-date sites, and one 8-date site 1,000 km away
        # among 1-date sites.
        pts = [[0.0 + 0.01 * i, 50.0] for i in range(10)] + [[14.0, 50.0]] + [[14.0 + 0.01 * i, 50.1] for i in range(1, 10)]
        n = [8] * 10 + [8] + [1] * 9
        r = st.local_rank(pts, n, 150)
        self.assertEqual(r[0], 0.0)
        self.assertEqual(r[10], 1.0)

    def test_isolated_site_is_rank_one(self):
        self.assertEqual(st.local_rank([[0, 0], [90, 0]], [1, 1], 150).tolist(), [1.0, 1.0])

    def test_score_uses_class_bonuses_and_clamps(self):
        feats = [
            point("tell", 0, 40, -7000, type="tell", n_dates=30, occupation=[[-7000, -5000], [-4000, -2000]]),
            point("pit", 0.01, 40, -5000, type="pit", n_dates=1, occupation=[[-5000, -4000]]),
            point("camp", 0.02, 40, -5000, type="camp", n_dates=1, occupation=[[-5000, -4000]]),
            point("wd", 20, 40, -5000, type="settlement", n_dates=0, sources=["wikidata"]),
        ]
        st.score_sites(feats, IMPORTANCE)
        got = {f["properties"]["name"]: (f["properties"]["importance"], f["properties"]["evidence"]) for f in feats}
        self.assertEqual(got, {"tell": (3, 2), "pit": (0, 0), "camp": (1, 0), "wd": (2, 1)})

    def test_well_dated_site_in_dug_region_gets_no_local_bonus(self):
        dug = [point(f"s{i}", 0.01 * i, 50, -5000, type="settlement", n_dates=8) for i in range(20)]
        lone = point("lone", 30, 50, -5000, type="settlement", n_dates=8)
        st.score_sites(dug + [lone], IMPORTANCE)
        self.assertEqual(dug[0]["properties"]["importance"], 2)
        self.assertEqual(lone["properties"]["importance"], 3)


class Survey(unittest.TestCase):
    def test_density_follows_records_and_levels_cut(self):
        g = make_grid(6, 6, w=1.0)
        left, top, right, bottom = g.bbox.T
        cx, cy = (left[0] + right[0]) / 2, (top[0] + bottom[0]) / 2
        dates = [date("a", cx, cy, 0) for _ in range(500)]
        dens, level = st.survey_intensity(g, dates, {"sigma_km": 100, "thin": 5, "well": 25})
        self.assertEqual(int(np.argmax(dens)), 0)
        self.assertEqual(level[0], 2)
        self.assertEqual(level[-1], 0)  # ~5 hexes (~400 km) away

    def test_round_trip(self):
        import os, tempfile
        g = make_grid(2, 2)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.csv.gz")
            st.write_survey(p, g, np.array([0.0, 6.0, 30.0, 1.0]), np.array([0, 1, 2, 0]))
            self.assertEqual(st.read_survey(p), {1: 0, 2: 1, 3: 2, 4: 0})
