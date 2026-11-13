"""Date tables tracked in the repository (`[[settlements.tables]]` with a
`path`): every row says where it comes from and how good its position is,
positions read off a map or a locality are flagged approximate, and the
pipeline reads every row."""
import csv
import os
import tomllib
import unittest

from pipeline.settlements import lab_key, parse_table

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def local_tables():
    with open(os.path.join(ROOT, "pipeline/config.toml"), "rb") as f:
        sc = tomllib.load(f)["settlements"]
    return [t for t in sc.get("tables", []) if t.get("path")], sc.get("citations", {})


class LocalTables(unittest.TestCase):
    def test_rows_are_sourced_and_parse(self):
        tables, cites = local_tables()
        for spec in tables:
            path = os.path.join(ROOT, spec["path"])
            with self.subTest(table=spec["name"]):
                self.assertIn(spec["name"], cites, "needs a [settlements.citations] entry")
                with open(path, encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                self.assertTrue(rows)
                for i, r in enumerate(rows, 2):
                    for k in ("labnr", "site", "source", "page", "precision", "refs"):
                        self.assertTrue(r[k].strip(), f"{spec['path']}:{i} has no {k}")
                    self.assertIn(r["approximate"], ("true", "false"), f"{spec['path']}:{i}")
                    if r["approximate"] == "true":
                        self.assertTrue(r["precision"].lower().startswith("approximate"),
                                        f"{spec['path']}:{i}: say how the position was found")
                    self.assertTrue(-180 <= float(r["lon"]) <= 180 and -90 <= float(r["lat"]) <= 90)
                    self.assertGreater(float(r["std"]), 0)
                labs = {lab_key(r["labnr"]) for r in rows}
                self.assertEqual(len(labs), len(rows), f"{spec['path']}: repeated lab numbers")
                got = parse_table(path, spec, set())
                self.assertEqual(len(got), len(rows), f"{spec['path']}: rows the pipeline drops")
                self.assertTrue(all(d["dataset"] == spec["name"] for d in got))


if __name__ == "__main__":
    unittest.main()
