"""Every river and lake in the catalogues must be written up in its
SOURCES.md, so the reasoning and references live in the repo and not only
in a conversation."""
import os
import re
import tomllib
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def documented(name, text):
    """The name, the name before any brackets (`Mayo Kébbi (Megachad
    spillway)` -> `Mayo Kébbi`) or the part in them (`Nile (Canopic branch)`
    -> `Canopic`) appears in the write-up."""
    m = re.match(r"([^(]*?)\s*\(([^)]*)\)", name)
    if not m:
        return name in text
    inner = m.group(2).replace(" branch", "").replace(" course", "")
    return name in text or m.group(1) in text and inner in text


class Sources(unittest.TestCase):
    def check(self, catalogue, key, sources):
        with open(os.path.join(ROOT, catalogue), "rb") as f:
            items = tomllib.load(f)[key]
        with open(os.path.join(ROOT, sources)) as f:
            text = f.read()
        self.assertIn("## References", text, f"{sources} needs a References section")
        missing = [it["name"] for it in items if not documented(it["name"], text)]
        self.assertEqual(missing, [], f"not written up in {sources}")
        # Links cited in the catalogue are listed in the write-up too.
        with open(os.path.join(ROOT, catalogue)) as f:
            urls = set(re.findall(r"https?://[^\s\"]+", f.read()))
        self.assertEqual(sorted(u for u in urls if u not in text), [],
                         f"links in {catalogue} missing from {sources}")

    def test_rivers(self):
        self.check("data/rivers/rivers.toml", "river", "data/rivers/SOURCES.md")

    def test_lakes(self):
        self.check("data/lakes/lakes.toml", "lake", "data/lakes/SOURCES.md")

    def test_coasts(self):
        self.check("data/coasts/coasts.toml", "coast", "data/coasts/SOURCES.md")

    def test_places(self):
        """Every exotic place is written up, and every link in the critic's
        plans is in the places write-up."""
        import glob
        self.check("data/places/places.toml", "place", "data/places/SOURCES.md")
        with open(os.path.join(ROOT, "data/places/SOURCES.md")) as f:
            text = f.read()
        for path in sorted(glob.glob(os.path.join(ROOT, "data/places/plans/*.toml"))):
            with open(path) as f:
                urls = {u.rstrip(".,;") for u in re.findall(r"https?://[^\s\"'<>)\]]+", f.read())}
            self.assertEqual(sorted(u for u in urls if u not in text), [],
                             f"links in {os.path.basename(path)} missing from data/places/SOURCES.md")

    def test_ancestry(self):
        """The ancestry table's write-up exists, names the AADR release it is
        computed from and the tool, and lists every configured reference group."""
        with open(os.path.join(ROOT, "data/ancestry/SOURCES.md")) as f:
            text = f.read()
        self.assertIn("## References", text)
        for needle in ("10.7910/DVN/FFIDCW", "https://github.com/uqrmaie1/admixtools", "10.1093/genetics/iyaa045"):
            self.assertIn(needle, text)
        self.assertNotIn("PLACEHOLDER", text)
        with open(os.path.join(ROOT, "isostyle/config.toml"), "rb") as f:
            acfg = tomllib.load(f)["ancestry"]
        groups = [g for s in acfg["sources"].values() for g in s["groups"]] + [g for r in acfg["right"] for g in r["groups"]]
        self.assertEqual([g for g in groups if g not in text], [], "reference groups missing from data/ancestry/SOURCES.md")

    def test_population(self):
        """Methods and visibility factors are written up, and a factor
        marked as sourced has a reference."""
        for key in ("method", "factor"):
            self.check("data/population/inventory.toml", key, "data/population/SOURCES.md")
        with open(os.path.join(ROOT, "data/population/inventory.toml"), "rb") as f:
            factors = tomllib.load(f)["factor"]
        self.assertEqual([f["name"] for f in factors
                          if (f["status"] == "sourced") != bool(f["refs"])], [])

    def test_anchors(self):
        """Every anchor has a reference, and every dataset the anchors come
        from is in the terrain write-up."""
        import csv
        path = os.path.join(ROOT, "data/terrain/anchors.csv")
        if not os.path.exists(path):
            self.skipTest("no anchors.csv; run `python -m pipeline anchors`")
        with open(os.path.join(ROOT, "data/terrain/SOURCES.md")) as f:
            text = f.read()
        with open(path) as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([r["id"] for r in rows if not r["reference"].strip()], [])
        doi = {"EMBSeCBIO": "10.17864/1947.309", "BIOME 6000": "10.17864/1947.99"}
        for db in {r["database"] for r in rows}:
            self.assertIn(doi.get(db, "10.1017/qua.2017.105"), text, f"{db} not in data/terrain/SOURCES.md")
        self.assertIn("10.1111/jbi.14448", text)        # the biomisation method
        lit = os.path.join(ROOT, "data/terrain/anchors_literature.csv")
        if os.path.exists(lit):
            with open(lit) as f:
                refs = {r["reference"] for r in csv.DictReader(f)}
            self.assertEqual(sorted(u for u in refs if u not in text), [],
                             "literature anchors' references missing from data/terrain/SOURCES.md")

    def test_settlement_corrections(self):
        """Every coordinate correction has a link, listed in CORRECTIONS.md
        (SOURCES.md there is generated by `make settlements`)."""
        path = os.path.join(ROOT, "data/settlements/corrections.toml")
        if not os.path.exists(path):
            self.skipTest("no corrections")
        with open(path, "rb") as f:
            fixes = tomllib.load(f).get("fix", [])
        with open(os.path.join(ROOT, "data/settlements/CORRECTIONS.md")) as f:
            text = f.read()
        self.assertEqual([x["name"] for x in fixes if not str(x.get("source", "")).startswith("http")], [],
                         "corrections without a source link")
        self.assertEqual(sorted(u for u in {x["source"] for x in fixes} if u not in text), [],
                         "correction sources missing from data/settlements/CORRECTIONS.md")

    def test_settlement_records(self):
        """Every record fix (records.toml) has a link, listed in CORRECTIONS.md."""
        path = os.path.join(ROOT, "data/settlements/records.toml")
        if not os.path.exists(path):
            self.skipTest("no record fixes")
        with open(path, "rb") as f:
            doc = tomllib.load(f)
        entries = [e for k in ("locate", "same", "reject", "keep", "refile", "keep_site") for e in doc.get(k, [])]
        with open(os.path.join(ROOT, "data/settlements/CORRECTIONS.md")) as f:
            text = f.read()
        self.assertEqual([e.get("name", e.get("site")) for e in entries
                          if not str(e.get("source", "")).startswith("http")], [], "record fixes without a source link")
        self.assertEqual(sorted(u for u in {e["source"] for e in entries} if u not in text), [],
                         "record fix sources missing from data/settlements/CORRECTIONS.md")

    def test_inferred_settlements(self):
        """Every inferred-settlement rule names its plan and cites links listed
        in data/settlements/INFERRED.md."""
        path = os.path.join(ROOT, "data/settlements/inferred.toml")
        if not os.path.exists(path):
            self.skipTest("no inferred settlements")
        with open(path, "rb") as f:
            rules = tomllib.load(f).get("rule", [])
        with open(os.path.join(ROOT, "data/settlements/INFERRED.md")) as f:
            text = f.read()
        for r in rules:
            self.assertTrue(os.path.exists(os.path.join(ROOT, r["plan"])), r["key"])
            self.assertEqual([u for u in r.get("sources", []) if u not in text], [],
                             f"{r['key']}: sources missing from data/settlements/INFERRED.md")

    def test_renown(self):
        """Every famous site is written up with its link, and has a renown
        of 1-3 and a reference."""
        import json
        with open(os.path.join(ROOT, "neolith-rs/crates/app/assets/renown.json")) as f:
            sites = json.load(f)["site"]
        with open(os.path.join(ROOT, "data/renown/SOURCES.md")) as f:
            text = f.read()
        self.assertIn("## References", text)
        self.assertEqual([s["name"] for s in sites if s["name"] not in text or s["wikipedia"] not in text], [])
        self.assertEqual([s["name"] for s in sites if s["renown"] not in (1, 2, 3)], [])


class Attributions(unittest.TestCase):
    """data/ATTRIBUTIONS.toml covers every download, every entry says where
    it comes from and under what licence, nothing non-commercial or
    no-derivatives is shipped or committed, and the generated list and app
    credits are up to date."""

    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, ROOT)
        from pipeline import attributions
        cls.mod = attributions
        cls.sources = attributions.load(ROOT)
        cls.provides = {p for s in cls.sources for p in s["provides"]}

    def covered(self, key):
        if key in self.provides:
            return True
        if key.startswith("url:"):
            return any(p.startswith("url:") and key.startswith(p) for p in self.provides)
        return False

    def test_fields(self):
        need = ("key", "name", "url", "licence", "citation", "used_in", "role", "shipped", "committed",
                "verified", "provides")
        for s in self.sources:
            self.assertEqual([k for k in need if k not in s], [], s.get("key"))
            self.assertTrue(s["url"].startswith("http"), s["key"])
            self.assertIn(s["role"], ("data", "fit", "asset", "reference"), s["key"])
        keys = [s["key"] for s in self.sources]
        self.assertEqual(len(keys), len(set(keys)), "duplicate keys")

    def test_no_restricted_licence_shipped(self):
        self.assertEqual([s["key"] for s in self.sources
                          if (s["shipped"] or s["committed"]) and self.mod.restricted(s["licence"])], [])

    def test_isostyle_sources_covered(self):
        with open(os.path.join(ROOT, "isostyle/config.toml"), "rb") as f:
            files = [s["file"] for s in tomllib.load(f).get("sources", [])]
        self.assertEqual([x for x in files if not self.covered("isostyle:" + x)], [],
                         "isostyle [[sources]] missing from data/ATTRIBUTIONS.toml")

    def test_settlement_tables_covered(self):
        with open(os.path.join(ROOT, "pipeline/config.toml"), "rb") as f:
            st = tomllib.load(f).get("settlements", {})
        names = [t["name"] for t in st.get("tables", [])]
        self.assertEqual([n for n in names if not self.covered("settlements:" + n)], [],
                         "[[settlements.tables]] missing from data/ATTRIBUTIONS.toml")

    def test_downloads_covered(self):
        """Every URL the Makefile downloads, and every *url / source URL in
        pipeline/config.toml outside comments and the settlements literature
        list, is covered."""
        urls = set()
        with open(os.path.join(ROOT, "Makefile")) as f:
            urls |= set(re.findall(r"https?://[^\s\"']+", f.read()))
        with open(os.path.join(ROOT, "pipeline/config.toml")) as f:
            for line in f:
                m = re.match(r"\s*\w*url\w*\s*=\s*\"(https?://[^\"]+)\"", line)
                if m:
                    urls.add(m.group(1))
        for path in ("isostyle/pollen.py", "pipeline/anchors.py"):
            with open(os.path.join(ROOT, path)) as f:
                urls |= {u for u in re.findall(r"https?://[^\s\"'{]+", f.read()) if "api." in u}
        self.assertEqual(sorted(u for u in urls if not self.covered("url:" + u)), [],
                         "downloads missing from data/ATTRIBUTIONS.toml")

    def test_generated_up_to_date(self):
        with open(os.path.join(ROOT, self.mod.MARKDOWN)) as f:
            self.assertEqual(f.read(), self.mod.render_md(self.sources),
                             "ATTRIBUTIONS.md is stale: run `python -m pipeline attributions`")
        with open(os.path.join(ROOT, self.mod.CREDITS)) as f:
            self.assertEqual(f.read(), self.mod.credits_json(self.sources),
                             "credits.json is stale: run `python -m pipeline attributions`")
        with open(os.path.join(ROOT, self.mod.ISOSTYLE)) as f:
            self.assertEqual(f.read(), self.mod.isostyle_md(self.sources),
                             "data/isostyle/SOURCES.md is stale: run `python -m pipeline attributions`")


if __name__ == "__main__":
    unittest.main()
