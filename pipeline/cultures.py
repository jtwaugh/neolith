"""Archaeological cultures: data/cultures/cultures.toml -> per-site timelines.

Each dated sample carries the period labels its source gave it ("LBK",
"Trichterbecher-Nordgruppe", "EN"...). `Table.match` maps a label to one
culture or one stage, or to nothing when it is unknown or ambiguous.
`assign` then gives every site two step-function timelines keyed by year,
the same shape as the map's year keys:

    culture = {"-5300": "lbk", "-4700": "rossen"}
    stage   = {"-9000": "mesolithic", "-5300": "neolithic"}

`check` fetches the Wikipedia article each entry cites and records which
traits the article text supports (python -m pipeline cultures-check).
"""
import hashlib
import json
import os
import re
import tomllib
import unicodedata
import urllib.parse
from collections import Counter, defaultdict

import numpy as np

TRAITS = ("economy", "pottery", "houses", "burial", "monuments", "metal", "domesticates", "other")
LIST_TRAITS = {"houses", "burial", "monuments", "metal", "domesticates", "other"}
_FOLD = str.maketrans({"ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "ß": "ss", "ł": "l", "Ł": "l", "đ": "d", "ı": "i"})


def norm_label(s):
    """Lower case, accents folded, anything but letters and digits as one space."""
    s = unicodedata.normalize("NFKD", (s or "").translate(_FOLD))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()  # dashes, apostrophes, other scripts: separators


class Table:
    def __init__(self, data, path="cultures.toml"):
        self.path = path
        # Copies: compiled patterns and observed ranges are added to entries.
        self.stages = [dict(e) for e in data.get("stage", [])]
        self.cultures = [dict(e) for e in data.get("culture", [])]
        self.vocab = data.get("vocab", {})
        self.ignore = [re.compile(p) for p in data.get("ignore", [])]
        self.entries = {}
        for kind, items in (("stage", self.stages), ("culture", self.cultures)):
            for e in items:
                for k in ("id", "name", "wikipedia", "match"):
                    if not e.get(k):
                        raise ValueError(f"{path}: {kind} {e.get('id', '?')!r} has no {k}")
                if e["id"] in self.entries:
                    raise ValueError(f"{path}: duplicate id {e['id']!r}")
                bad = set(e.get("traits", {})) - set(TRAITS)
                if bad:
                    raise ValueError(f"{path}: {e['id']}: unknown traits {sorted(bad)}")
                for t in LIST_TRAITS & set(e.get("traits", {})):
                    if not isinstance(e["traits"][t], list):
                        raise ValueError(f"{path}: {e['id']}: trait {t} must be a list")
                lo, hi = e.get("start"), e.get("end")
                if any(v is not None and not isinstance(v, int) for v in (lo, hi)) or (lo is not None and hi is not None and lo >= hi):
                    raise ValueError(f"{path}: {e['id']}: start/end must be whole years with start < end")
                if (lo is not None or hi is not None) and not e.get("quotes"):
                    raise ValueError(f"{path}: {e['id']}: a date range needs `quotes` from the cited article")
                e["kind"], e["re"] = kind, re.compile(e["match"])
                self.entries[e["id"]] = e
        stage_ids = {s["id"] for s in self.stages}
        for st_ in self.stages:
            if st_.get("parent") is not None and st_["parent"] not in stage_ids:
                raise ValueError(f"{path}: stage {st_['id']!r} has unknown parent {st_['parent']!r}")
        for c in self.cultures:
            if c.get("stage") not in stage_ids:
                raise ValueError(f"{path}: culture {c['id']!r} has unknown stage {c.get('stage')!r}")
        self._cache = {}

    @classmethod
    def load(cls, path):
        with open(path, "rb") as f:
            return cls(tomllib.load(f), path)

    def stage_of(self, eid):
        e = self.entries[eid]
        return eid if e["kind"] == "stage" else e["stage"]

    def match(self, label):
        """Label -> ("culture", id), ("stage", id) or None."""
        n = norm_label(label)
        if n in self._cache:
            return self._cache[n]
        hit = None
        if n and not any(r.search(n) for r in self.ignore):
            cs = [c["id"] for c in self.cultures if c["re"].search(n)]
            if len(cs) == 1:
                hit = ("culture", cs[0])
            elif not cs:
                ss = [s["id"] for s in self.stages if s["re"].search(n)]
                if len(ss) == 1:
                    hit = ("stage", ss[0])
        self._cache[n] = hit
        return hit


# ----------------------------------------------------------------- assign
def _timeline(years, trim):
    """{id: [years]} -> {"year": id}: each id starts at the trim quantile of
    its dates; on a tie the id with more dates keeps the year."""
    starts = sorted((int(np.quantile(ys, trim, method="lower")), -len(ys), i) for i, ys in years.items())
    out = {}
    for y, _, i in starts:
        out.setdefault(str(y), i)
    return out


def in_range(e, year, margin):
    lo, hi = e.get("start", e.get("obs_start")), e.get("end", e.get("obs_end"))
    return (lo is None or year >= lo - margin) and (hi is None or year <= hi + margin)


def date_hits(table, periods, year, margin):
    """The culture and stage one dated sample attests, from its labels.

    The labels may describe the whole site, so a culture or stage counts
    only if the date falls in its range (+- margin). If more than one
    labelled culture fits, the sample attests none of them, and its stage is
    the one they share, if any. Without a culture, the stage is the one stage
    label that fits; a stage and its parent together count as the parent.
    Returns (culture, stage, labelled cultures that didn't fit)."""
    hits = {h for p in periods if (h := table.match(p))}
    labelled = {i for k, i in hits if k == "culture"}
    fits = {i for i in labelled if in_range(table.entries[i], year, margin)}
    culture = next(iter(fits)) if len(fits) == 1 else None
    stages = {table.stage_of(i) for i in fits}
    if not stages:
        stages = {i for k, i in hits if k == "stage" and in_range(table.entries[i], year, margin)}
        stages -= {i for i in stages if table.entries[i].get("parent") in stages}
    stage = next(iter(stages)) if len(stages) == 1 else None
    return culture, stage, labelled - fits


def observe_ranges(table, site_rows, lo_q=10, hi_q=90):
    """For cultures without a cited start or end, set obs_start / obs_end
    from the central dates carrying their label (all sites)."""
    need = [c for c in table.cultures if c.get("start") is None or c.get("end") is None]
    years = defaultdict(list)
    for rows in site_rows:
        for y, d in rows:
            for k, i in {h for p in d["periods"] if (h := table.match(p))}:
                if k == "culture":
                    years[i].append(y)
    for c in need:
        ys = years.get(c["id"])
        if ys:
            c["obs_start"], c["obs_end"] = int(np.percentile(ys, lo_q)), int(np.percentile(ys, hi_q))


def assign(feats, dated, table, trim=0.0, margin=0):
    """Set properties culture, stage and culture_dates from the labels on
    each site's dated samples. dated: site key -> [(year, date row)].
    Returns (sites with a culture, Counter of dates per culture that fit
    its range, Counter of labelled dates that didn't)."""
    observe_ranges(table, dated.values())
    n, used, outside = 0, Counter(), Counter()
    for f in feats:
        rows = dated.get(f["properties"].get("key"), ())
        cy, sy = defaultdict(list), defaultdict(list)
        for y, d in rows:
            c, s, out = date_hits(table, d["periods"], y, margin)
            outside.update(out)
            if c:
                cy[c].append(y)
                used[c] += 1
            if s:
                sy[s].append(y)
        p = f["properties"]
        for k in ("culture", "stage", "culture_dates", "_evidence"):
            p.pop(k, None)
        if cy or sy:
            p["_evidence"] = {"culture": dict(cy), "stage": dict(sy)}  # for infer; removed by build
        if cy:
            p["culture"] = _timeline(cy, trim)
            p["culture_dates"] = dict(sorted(((c, len(v)) for c, v in cy.items()), key=lambda kv: (-kv[1], kv[0])))
            n += 1
        if sy:
            p["stage"] = _timeline(sy, trim)
    return n, used, outside


# ------------------------------------------------------------------ infer
def haversine_km(lon, lat, lons, lats):
    lon, lat, lons, lats = map(np.radians, (lon, lat, lons, lats))
    a = np.sin((lats - lat) / 2) ** 2 + np.cos(lat) * np.cos(lats) * np.sin((lons - lon) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


class Neighbours:
    """Labelled evidence: for each site, the span of years over which its own
    labels attest each culture and stage (from `assign`)."""

    def __init__(self, feats, field):
        self.keys, self.lon, self.lat, self.spans = [], [], [], []
        for f in feats:
            ev = f["properties"].get("_evidence", {}).get(field)
            if ev:
                self.keys.append(f["properties"]["key"])
                self.lon.append(f["geometry"]["coordinates"][0])
                self.lat.append(f["geometry"]["coordinates"][1])
                self.spans.append({i: (min(ys), max(ys)) for i, ys in ev.items()})
        self.lon, self.lat = np.array(self.lon), np.array(self.lat)

    def near(self, lon, lat, radius_km, exclude=None):
        """[(km, spans)] of labelled sites within radius_km, nearest first."""
        if not self.keys:
            return []
        d = haversine_km(lon, lat, self.lon, self.lat)
        idx = np.flatnonzero(d <= radius_km)
        return [(float(d[j]), self.spans[j]) for j in idx[np.argsort(d[idx])] if self.keys[j] != exclude]


def vote(near, year, window, ok, min_sites, min_share):
    """The id most nearby sites attest within `window` years of `year`, if
    at least min_sites attest it and it has min_share of all the votes.
    ok(id) filters ids (e.g. the date must fit the culture's range).
    Returns (id, sites for it, sites voting, nearest km) or None."""
    sites, nearest = Counter(), {}
    for km, spans in near:
        for i, (lo, hi) in spans.items():
            if lo - window <= year <= hi + window and ok(i):
                sites[i] += 1
                nearest.setdefault(i, km)
    if not sites:
        return None
    (best, n), total = sites.most_common(1)[0], sum(sites.values())
    if n < min_sites or n / total < min_share or list(sites.values()).count(n) > 1:
        return None
    return best, n, total, nearest[best]


def infer(feats, dated, table, cfg, trim=0.0, margin=0):
    """Fill dates whose own labels give no culture (or no stage) from the
    labelled sites around them. Writes culture_inferred / stage_inferred
    timelines and *_inferred_support {id: [max sites agreeing, nearest km]},
    separate from the observed culture / stage. Returns (sites given an
    inferred culture, sites given an inferred stage)."""
    nb = {fld: Neighbours(feats, fld) for fld in ("culture", "stage")}
    r, w, ms, sh = cfg["radius_km"], cfg["window_years"], cfg["min_sites"], cfg["min_share"]
    counts = Counter()
    for f in feats:
        p = f["properties"]
        for fld in ("culture", "stage"):
            p.pop(f"{fld}_inferred", None)
            p.pop(f"{fld}_inferred_support", None)
        rows = dated.get(p.get("key"), ())
        if not rows:
            continue
        lon, lat = f["geometry"]["coordinates"][:2]
        near = {fld: nb[fld].near(lon, lat, r, exclude=p["key"]) for fld in nb}
        got = {"culture": defaultdict(list), "stage": defaultdict(list)}
        support = {"culture": {}, "stage": {}}
        for y, d in rows:
            c, s, _ = date_hits(table, d["periods"], y, margin)
            for fld, own in (("culture", c), ("stage", s)):
                if own or not near[fld]:
                    continue
                v = vote(near[fld], y, w, lambda i: in_range(table.entries[i], y, margin), ms, sh)
                if v:
                    i, n, _, km = v
                    got[fld][i].append(y)
                    old = support[fld].get(i, [0, km])
                    support[fld][i] = [max(old[0], n), round(min(old[1], km), 1)]
        for fld in ("culture", "stage"):
            if got[fld]:
                p[f"{fld}_inferred"] = _timeline(got[fld], trim)
                p[f"{fld}_inferred_support"] = support[fld]
                counts[fld] += 1
    return counts["culture"], counts["stage"]


def holdout(feats, dated, table, cfg, margin=0):
    """How well `infer` recovers known labels: for each date whose own labels
    give a culture (stage), vote from the other sites as if it had none.
    Returns {field: (dates tested, dates given an answer, answers right)}."""
    nb = {fld: Neighbours(feats, fld) for fld in ("culture", "stage")}
    r, w, ms, sh = cfg["radius_km"], cfg["window_years"], cfg["min_sites"], cfg["min_share"]
    out = {fld: [0, 0, 0] for fld in nb}
    for f in feats:
        p = f["properties"]
        rows = dated.get(p.get("key"), ())
        if not rows or "_evidence" not in p:
            continue
        lon, lat = f["geometry"]["coordinates"][:2]
        near = {fld: nb[fld].near(lon, lat, r, exclude=p["key"]) for fld in nb}
        for y, d in rows:
            c, s, _ = date_hits(table, d["periods"], y, margin)
            for fld, own in (("culture", c), ("stage", s)):
                if not own:
                    continue
                t = out[fld]
                t[0] += 1
                v = vote(near[fld], y, w, lambda i: in_range(table.entries[i], y, margin), ms, sh) if near[fld] else None
                if v:
                    t[1] += 1
                    t[2] += v[0] == own
    return {k: tuple(v) for k, v in out.items()}


def unmapped(dated, keys, table):
    """Labels no entry matched, as (label, n sites, n dates), most sites first."""
    sites, dates = defaultdict(set), Counter()
    for k in keys:
        for _, d in dated.get(k, ()):
            for p in d["periods"]:
                if table.match(p) is None and norm_label(p):
                    n = norm_label(p)
                    sites[n].add(k)
                    dates[n] += 1
    return sorted(((l, len(s), dates[l]) for l, s in sites.items()), key=lambda t: (-t[1], -t[2], t[0]))


# ---------------------------------------------------------------- compile
def range_record(e):
    """start/end with where each came from: the cited article or the dates."""
    r = {}
    for side in ("start", "end"):
        if e.get(side) is not None:
            r[side], r[f"{side}_source"] = e[side], "cited"
        elif e.get(f"obs_{side}") is not None:
            r[side], r[f"{side}_source"] = e[f"obs_{side}"], "observed"
    if e.get("quotes"):
        r["quotes"] = e["quotes"]
    return r


def compile_table(table, feats, wiki, used=None, outside=None):
    """cultures.json: each entry with its traits, citation and what the
    dated sites say about where and when it is found."""
    starts, where = defaultdict(list), defaultdict(list)
    for f in feats:
        p = f["properties"]
        for field in ("culture", "stage"):
            for y, i in p.get(field, {}).items():
                starts[i].append(int(y))
                where[i].append(f["geometry"]["coordinates"])
    out = []
    for e in table.stages + table.cultures:
        i = e["id"]
        w = wiki.get(i, {})
        rec = {"id": i, "kind": e["kind"], "name": e["name"],
               **({"stage": e["stage"]} if e["kind"] == "culture" else {}),
               "traits": e.get("traits", {}),
               **({"range": range_record(e)} if any(k in e for k in ("start", "end", "obs_start")) else {}),
               "wikipedia": {k: w[k] for k in ("title", "revid", "url", "wikidata") if k in w} or {"title": e["wikipedia"]},
               "unverified": w.get("unsupported", None)}
        ys = starts.get(i)
        if ys:
            pts = np.array(where[i])
            rec["sites"] = len(ys)
            rec["observed"] = {
                "start_p10": int(np.percentile(ys, 10)), "start_median": int(np.median(ys)),
                "start_p90": int(np.percentile(ys, 90)),
                "centre": [round(float(np.median(pts[:, 0])), 2), round(float(np.median(pts[:, 1])), 2)],
                "bbox_p5_p95": [round(float(v), 2) for v in (*np.percentile(pts, 5, axis=0), *np.percentile(pts, 95, axis=0))],
            }
        else:
            rec["sites"] = 0
        if e["kind"] == "culture" and used is not None:
            rec["dates_used"], rec["dates_outside_range"] = used.get(i, 0), outside.get(i, 0)
        out.append(rec)
    return out


def write_sources(path, compiled, checked, inference=None):
    L = ["# Sources for `data/cultures/`", "",
         "`cultures.toml` is written by hand. Its traits are short summaries",
         "made for this project; each entry cites the English Wikipedia",
         "article revision below. `make cultures-check` fetches those",
         "revisions and lists any trait the article text does not mention;",
         "those are marked `unverified` in `cultures.json` and listed here.",
         "",
         "Which culture a site belongs to comes from the period labels on its",
         "dated samples, so it is cited to the same records as the dates",
         "(see `data/settlements/SOURCES.md`). Wikipedia text is CC BY-SA 4.0;",
         "no text is copied into this repository.", ""]
    if not checked:
        L += ["**Not yet checked:** run `make cultures-check`.", ""]
    if inference:
        st = inference["settings"]
        L += ["## Inferred cultures", "",
              "`culture_inferred` and `stage_inferred` are not cited: they are guesses",
              "for dates whose own labels give no culture (stage). A date gets the",
              f"culture that at least {st['min_sites']} labelled sites within {st['radius_km']} km attest",
              f"within {st['window_years']} years of it, if it has {st['min_share']:.0%} of the votes, no tie,",
              "and the date fits that culture's range. `*_inferred_support` gives, per",
              "culture, the most sites that agreed and the nearest one's distance (km).", "",
              "Holdout test (each labelled date voted on by the other sites, as if unlabelled):", "",
              "| Field | Known dates | Answered | Right |", "|---|---|---|---|"]
        for fld, (t, a, ok) in inference["holdout"].items():
            L.append(f"| {fld} | {t} | {a} ({a / t:.0%}) | {ok} ({ok / a:.0%}) |" if a and t else f"| {fld} | {t} | 0 | — |")
        L += ["", "Rates count dates, so well-dated sites weigh most. A neighbour can be",
              "the same place under another name; ignoring neighbours closer than",
              "10 km lowered culture accuracy from 96% to 94% (2026-11-12 build).", ""]
    L += ["| Entry | Sites | Wikipedia revision | Unverified traits |", "|---|---|---|---|"]
    for r in compiled:
        w = r["wikipedia"]
        cite = (f"[{w['title']}]({w['url']}) ({w['revid']})" if "revid" in w else f"{w['title']} (unchecked)")
        unv = ", ".join(r["unverified"]) if r["unverified"] else ("—" if r["unverified"] is not None else "unchecked")
        L.append(f"| {r['name']} (`{r['id']}`) | {r['sites']} | {cite} | {unv} |")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")


def build(table_path, out_dir, feats, dated, report_path, trim, margin, log=print, infer_cfg=None):
    table = Table.load(table_path)
    n, used, outside = assign(feats, dated, table, trim, margin)
    keys = [f["properties"]["key"] for f in feats if f["properties"].get("key") in dated]
    labelled = sum(1 for f in feats if "stage" in f["properties"])
    log(f"cultures: {n} sites with a named culture, {labelled} with a stage, of {len(keys)} dated; "
        f"{sum(outside.values())} culture-labelled dates fell outside that culture's range")
    inference = None
    if infer_cfg:
        test = holdout(feats, dated, table, infer_cfg, margin)
        ic, is_ = infer(feats, dated, table, infer_cfg, trim, margin)
        only = {fld: sum(1 for f in feats if f"{fld}_inferred" in f["properties"] and fld not in f["properties"])
                for fld in ("culture", "stage")}
        inference = {"settings": dict(infer_cfg), "holdout": test,
                     "sites": {"culture": ic, "stage": is_}, "sites_with_only_inferred": only}
        for fld, (t, a, ok) in test.items():
            log(f"  infer {fld}: {ic if fld == 'culture' else is_} sites filled "
                f"({only[fld]} had none of their own); holdout: answered {a}/{t} known dates, "
                f"{ok / a:.0%} right" if a else f"  infer {fld}: holdout gave no answers")
    for f in feats:
        f["properties"].pop("_evidence", None)
    miss = unmapped(dated, keys, table)
    with open(report_path, "w") as f:
        f.write("label\tsites\tdates\n" + "".join(f"{l}\t{s}\t{d}\n" for l, s, d in miss))
    wiki_path = os.path.join(out_dir, "wikipedia.json")
    wiki = json.load(open(wiki_path)) if os.path.exists(wiki_path) else {}
    compiled = compile_table(table, feats, wiki, used, outside)
    with open(os.path.join(out_dir, "cultures.json"), "w") as f:
        json.dump(compiled, f, ensure_ascii=False, indent=1)
    write_sources(os.path.join(out_dir, "SOURCES.md"), compiled, bool(wiki), inference)
    return table


# ------------------------------------------------------------------ check
API = "https://en.wikipedia.org/w/api.php"


def supported(value, field, text, vocab):
    """Does the article text mention this trait value?"""
    pat = vocab.get(field, {}).get(value)
    if pat:
        return re.search(pat, text) is not None
    words = [w for w in re.findall(r"[a-z]+", value.lower()) if len(w) >= 5]
    return bool(words) and all(w[:6] in text for w in words)


def trait_values(traits):
    for field in TRAITS:
        v = traits.get(field)
        for x in (v if isinstance(v, list) else [v] if v is not None else []):
            yield field, x


def entry_key(e):
    """Words an article must contain to count as being about entry e."""
    return norm_label(e.get("key") or re.sub(r"\(.*?\)", "", e["name"]))


def scoped_text(text, title, key):
    """The part of an article that can support an entry's traits: all of it
    when the title names the entry ("article"), else only the paragraphs
    that do ("section"), else nothing ("none")."""
    if key in norm_label(title):
        return text, "article"
    paras = [p for p in text.split("\n") if key in norm_label(p)]
    return ("\n".join(paras), "section") if paras else ("", "none")


def parse_article(raw):
    """API JSON for one title -> {title, revid, url, wikidata, text, redirected_from} or None."""
    q = raw.get("query", {})
    pages = q.get("pages", [])
    if not pages or pages[0].get("missing") or pages[0].get("invalid"):
        return None
    p = pages[0]
    redirects = q.get("redirects", []) + q.get("normalized", [])
    return {"title": p["title"], "revid": p["revisions"][0]["revid"],
            "url": f"https://en.wikipedia.org/w/index.php?title={urllib.parse.quote(p['title'].replace(' ', '_'))}&oldid={p['revisions'][0]['revid']}",
            "wikidata": p.get("pageprops", {}).get("wikibase_item"),
            "text": p.get("extract", ""),
            "redirected_from": [r["from"] for r in redirects]}


def check(table_path, cache_dir, out_path, log=print):
    """Fetch each cited article (cached) and record supported traits."""
    from .settlements import fetch
    table = Table.load(table_path)
    os.makedirs(cache_dir, exist_ok=True)
    out, problems = {}, []
    for e in table.stages + table.cultures:
        title = e["wikipedia"]
        q = {"action": "query", "format": "json", "formatversion": "2", "redirects": "1",
             "prop": "extracts|revisions|pageprops", "explaintext": "1", "rvprop": "ids",
             "ppprop": "wikibase_item", "titles": title}
        url = API + "?" + urllib.parse.urlencode(q)
        safe = re.sub(r"[^a-z0-9]+", "_", norm_label(title))[:60]
        path = os.path.join(cache_dir, f"{safe}_{hashlib.sha1(url.encode()).hexdigest()[:8]}.json")
        fetch(url, path, "wikipedia", tries=5)
        art = parse_article(json.load(open(path)))
        if art is None:
            out[e["id"]] = {"title": title, "missing": True, "unsupported": [f"{f}={v}" for f, v in trait_values(e.get("traits", {}))]}
            problems.append(f"{e['id']}: no article {title!r}")
            continue
        text = art.pop("text").lower()
        body, scope = scoped_text(text, art["title"], entry_key(e))
        if scope == "none":
            problems.append(f"{e['id']}: article {art['title']!r} never mentions {entry_key(e)!r}")
        uns = [f"{f}={v}" for f, v in trait_values(e.get("traits", {})) if not supported(v, f, body, table.vocab)]
        flat = " ".join(body.split())
        uns += [f"range quote={q!r}" for q in e.get("quotes", []) if " ".join(q.lower().split()) not in flat]
        out[e["id"]] = {**art, "requested": title, "scope": scope, "unsupported": uns}
        if uns:
            problems.append(f"{e['id']}: unsupported {', '.join(uns)}")
    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for p in problems:
        log("  " + p)
    log(f"checked {len(out)} entries: {sum(1 for v in out.values() if not v.get('missing'))} articles found, "
        f"{sum(len(v['unsupported']) for v in out.values())} unsupported traits")
    return out
