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
            urls = set(re.findall(r"https?://\S+", f.read()))
        self.assertEqual(sorted(u for u in urls if u not in text), [],
                         f"links in {catalogue} missing from {sources}")

    def test_rivers(self):
        self.check("data/rivers/rivers.toml", "river", "data/rivers/SOURCES.md")

    def test_lakes(self):
        self.check("data/lakes/lakes.toml", "lake", "data/lakes/SOURCES.md")

    def test_coasts(self):
        self.check("data/coasts/coasts.toml", "coast", "data/coasts/SOURCES.md")


if __name__ == "__main__":
    unittest.main()
