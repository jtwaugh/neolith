"""The master attribution list.

data/ATTRIBUTIONS.toml is the one registry of upstream sources. This module
renders it into ATTRIBUTIONS.md (repo root, for people) and
neolith-rs/crates/app/assets/credits.json (shipped sources only, for the
app's Credits window). `python -m pipeline attributions` writes both;
pipeline/tests/test_sources.py checks they are up to date."""
import json
import os
import re
import tomllib

REGISTRY = "data/ATTRIBUTIONS.toml"
MARKDOWN = "ATTRIBUTIONS.md"
CREDITS = "neolith-rs/crates/app/assets/credits.json"

# Licences whose terms forbid commercial use or derivatives. Nothing with
# one of these may be shipped in the app or committed as rows.
RESTRICTED = ("NC", "ND")

LICENCE_URLS = {
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC-BY-SA-4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC-BY-NC-4.0": "https://creativecommons.org/licenses/by-nc/4.0/",
    "CC-BY-NC-ND-4.0": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
    "OFL-1.1": "https://openfontlicense.org",
    "MIT": "https://opensource.org/license/mit",
}

GROUPS = [
    ("Shipped in the app", lambda s: s["shipped"]),
    ("Committed to the repository but not shipped", lambda s: not s["shipped"] and s["committed"]),
    ("Used to build or fit, not redistributed", lambda s: not s["shipped"] and not s["committed"]),
]


def load(root="."):
    with open(os.path.join(root, REGISTRY), "rb") as f:
        return tomllib.load(f)["source"]


def restricted(licence):
    parts = licence.upper().replace("(", " ").replace(")", " ").split("-")
    return any(p in RESTRICTED for p in parts)


def _licence_md(licence):
    url = LICENCE_URLS.get(licence)
    return f"[{licence}]({url})" if url else licence


def render_md(sources):
    out = [
        "# Attributions",
        "",
        "Every upstream dataset, image and font that enters this repository or the",
        "published app, with its licence and the citation its authors ask for.",
        "Generated from `data/ATTRIBUTIONS.toml` by `python -m pipeline attributions`;",
        "edit that file, not this one.",
        "",
        "- **Code** is MIT (`LICENSE`). **Derived data** (`data/`, `neolith-rs/assets/world.bin`,",
        "  the evidence layers) is CC BY-SA 4.0 (`LICENSE-DATA`), because some inputs are share-alike.",
        "- *facts*: numbers read from a paper (a sea-level curve, a date, a coordinate). Facts carry",
        "  no licence, but we cite them.",
        "- *unknown*: the licence has not yet been confirmed on the upstream page.",
        "- Each dataset's own write-up is in `data/<dataset>/SOURCES.md`; the original sources of",
        "  individual radiocarbon dates are kept per date in `data/settlements/dates.csv.gz`.",
        "",
    ]
    unverified = [s for s in sources if not s.get("verified")]
    if unverified:
        out += ["**Licences still to confirm:** " + "; ".join(re.sub(r"\s*\(.*?\)", "", s["name"]) for s in unverified) + ".", ""]
    for title, pred in GROUPS:
        group = [s for s in sources if pred(s)]
        if not group:
            continue
        out += [f"## {title}", ""]
        for s in group:
            out += [f"### {s['name']}", ""]
            out.append(f"- Licence: {_licence_md(s['licence'])}"
                       + ("" if s.get("verified") else " (not yet confirmed)"))
            out.append(f"- Source: <{s['url']}>")
            out.append(f"- Cite: {s['citation']}")
            out.append(f"- Used in: {s['used_in']}")
            if s.get("notes"):
                out.append(f"- Note: {s['notes']}")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def credits(sources):
    """What the app shows: shipped sources only, in registry order."""
    return [{"name": s["name"], "licence": s["licence"], "url": s["url"], "citation": s["citation"],
             "used_in": s["used_in"]} for s in sources if s["shipped"]]


def credits_json(sources):
    return json.dumps(credits(sources), indent=1, ensure_ascii=False) + "\n"


THIRD_PARTY = "THIRD_PARTY.md"
THIRD_PARTY_HEAD = """# Third-party software

The Rust app (`neolith-rs/`) is MIT (`LICENSE`). It is built from the crates below, all under
permissive licences (MIT, Apache-2.0, BSD, ISC, Zlib, Unicode-3.0, BSL-1.0, CDLA-Permissive-2.0).
Where a crate offers a choice that includes a copyleft licence (`self_cell`: Apache-2.0 OR GPL-2.0;
`r-efi`: MIT OR Apache-2.0 OR LGPL-2.1), we use it under Apache-2.0 or MIT. Not every crate is
compiled into the web build; this is the whole lock file.

Fonts and data sources are in `ATTRIBUTIONS.md`: EB Garamond (SIL OFL 1.1, text in
`neolith-rs/crates/app/assets/fonts/OFL.txt`) and the egui default fonts bundled by
`epaint_default_fonts` (Ubuntu Font Licence 1.0, OFL 1.1, MIT/Apache-2.0).

The Python pipeline (`pipeline/`, `isostyle/`) is not distributed; its dependencies are listed
in the `requirements.txt` files there.

Generated from `neolith-rs/Cargo.lock` by `python -m pipeline attributions`.

| Crate | Version | Licence | Repository |
|---|---|---|---|
"""


def third_party(root="."):
    """The crate table from `cargo metadata`, or None if cargo isn't installed."""
    import shutil
    import subprocess
    if not shutil.which("cargo"):
        return None
    m = json.loads(subprocess.run(["cargo", "metadata", "--format-version", "1", "--locked"],
                                  cwd=os.path.join(root, "neolith-rs"), capture_output=True,
                                  check=True, text=True).stdout)
    ws = set(m["workspace_members"])
    rows = sorted({(p["name"], p["version"], p.get("license") or "unstated", p.get("repository") or "")
                   for p in m["packages"] if p["id"] not in ws})
    return THIRD_PARTY_HEAD + "".join(f"| {n} | {v} | {l} | {r} |\n" for n, v, l, r in rows)


ISOSTYLE = "data/isostyle/SOURCES.md"
ISOSTYLE_HEAD = """# Sources for `data/isostyle/`

Generated from `data/ATTRIBUTIONS.toml` by `python -m pipeline attributions`; edit that file.

The evidence atlas is built from the datasets below, downloaded by `python -m isostyle fetch`
(`isostyle/config.toml` `[[sources]]`, checksums in `build/isostyle/sources/provenance.json`),
plus the settlement dates (`data/settlements/SOURCES.md`) and two tables transcribed by hand
(`data/isostyle/inputs/`). How each one becomes a layer is in `METHODS.md`. The master list of
licences and citations is `ATTRIBUTIONS.md` at the repository root; the key of each entry there
is given in brackets.

The speculative fill (`speculative/`) rests on the gap critic's judgements in `intuitions/*.toml`.
Each judgement carries its own literature list, with `checked = false` where a citation was not
read in full. They are judgements, not data, and are marked as such wherever they appear.

Removed: Paulsson 2019 megalith dates (CC BY-NC-ND), joined by lab number until 2026-11-13.

## Datasets

| Dataset | Used in | Licence | Link |
|---|---|---|---|
"""


def isostyle_md(sources):
    iso = [s for s in sources if s["shipped"] or s["committed"]
           if any(p.startswith("isostyle:") for p in s["provides"]) or "isostyle" in s["used_in"]]
    rows = [f"| {s['name']} [`{s['key']}`] | {s['used_in']} | {s['licence']}"
            f"{'' if s.get('verified') else ' (to confirm)'} | {s['url']} |" for s in iso]
    refs = [f"- {s['citation']} {s['url']}" for s in iso]
    return ISOSTYLE_HEAD + "\n".join(rows) + "\n\n## References\n\n" + "\n".join(refs) + "\n"


def write(root="."):
    sources = load(root)
    with open(os.path.join(root, MARKDOWN), "w") as f:
        f.write(render_md(sources))
    with open(os.path.join(root, CREDITS), "w") as f:
        f.write(credits_json(sources))
    with open(os.path.join(root, ISOSTYLE), "w") as f:
        f.write(isostyle_md(sources))
    msg = f"wrote {MARKDOWN}, {ISOSTYLE} and {CREDITS} ({len(sources)} sources)"
    tp = third_party(root)
    if tp is not None:
        with open(os.path.join(root, THIRD_PARTY), "w") as f:
            f.write(tp)
        msg += f" and {THIRD_PARTY}"
    return msg
