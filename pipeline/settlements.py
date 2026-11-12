"""Dated archaeological sites -> data/settlements/ (python -m pipeline settlements).

Radiocarbon dates from XRONOS and the tables in `[[settlements.tables]]` are
calibrated and grouped into one point feature per site, then matched to
Wikidata. `founding` is the earliest calibrated date at the site, so it is a
"no later than" bound.

Every output is traceable: each site lists its `sources` and `references`,
dates.csv.gz lists every date used with its own references, provenance.json
lists every download, and SOURCES.md says how to cite it all.
"""
import csv
import gzip
import hashlib
import io
import json
import math
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zlib
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .raster import point_in_poly

CAL_STEP = 10  # years; resolution of calibrated dates
USER_AGENT = "hexmap-data-pipeline/1.0 (python-urllib)"


# ------------------------------------------------------------------ fetch
MAX_WAIT = 120  # seconds; a longer Retry-After is treated as a refusal


def fetch(url, path, dataset, accept=None, tries=1, contact=""):
    """Download url to path unless it's already there. Returns provenance.

    tries: attempts allowed when the server answers 429 (too many requests);
    it waits as long as the server's Retry-After says (65 s if it doesn't),
    and gives up if that is over MAX_WAIT.
    contact: appended to the User-Agent, for services that ask for one.
    """
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".part"
        # XRONOS refuses urllib's default User-Agent; say what this client is.
        agent = f"{USER_AGENT} {contact}".strip()
        headers = {"User-Agent": agent, **({"Accept": accept} if accept else {})}
        req = urllib.request.Request(url, headers=headers)
        for attempt in range(tries):
            try:
                with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as f:
                    while chunk := r.read(1 << 20):
                        f.write(chunk)
                break
            except urllib.error.HTTPError as e:
                wait = e.headers.get("Retry-After", "")
                wait = int(wait) + 1 if wait.isdigit() else 65
                if e.code != 429 or attempt == tries - 1 or wait > MAX_WAIT:
                    raise
                time.sleep(wait)
        os.replace(tmp, path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return {"dataset": dataset, "url": url, "path": path, "sha256": h.hexdigest(),
            "bytes": os.path.getsize(path),
            "fetched": time.strftime("%Y-%m-%d", time.gmtime(os.path.getmtime(path)))}


# ------------------------------------------------------------ calibration
def load_curve(path):
    """IntCal .14c file -> (cal_bp, c14_age, sigma) on an even CAL_STEP grid."""
    rows = np.array([[float(v) for v in line.split(",")[:3]]
                     for line in open(path) if line.strip() and not line.startswith("#")])
    rows = rows[np.argsort(rows[:, 0])]
    cal = np.arange(rows[0, 0], rows[-1, 0] + 1, CAL_STEP)
    return cal, np.interp(cal, rows[:, 0], rows[:, 1]), np.interp(cal, rows[:, 0], rows[:, 2])


def calibrate(bp, std, curve, chunk=512):
    """Median calibrated age (cal BP) per date. NaN if off the curve."""
    cal, mu, sig = curve
    bp, std = np.asarray(bp, float), np.asarray(std, float)
    out = np.full(len(bp), np.nan)
    for i in range(0, len(bp), chunk):
        b, s = bp[i:i + chunk, None], std[i:i + chunk, None]
        var = s ** 2 + sig[None, :] ** 2
        p = np.exp(-(b - mu[None, :]) ** 2 / (2 * var)) / np.sqrt(var)
        tot = p.sum(axis=1)
        cdf = np.cumsum(p, axis=1)
        ok = tot > 0
        idx = (cdf >= tot[:, None] / 2).argmax(axis=1)
        out[i:i + chunk] = np.where(ok, cal[idx], np.nan)
    return out


def to_year(cal_bp):
    """cal BP -> signed year (negative = BCE), as the map's year keys."""
    return int(round((1950 - cal_bp) / CAL_STEP) * CAL_STEP)


# ----------------------------------------------------------------- parse
# A date row: {site, lon, lat, bp, std, labnr, type, periods, refs, dataset}.
# refs are the original publications or databases the record itself cites.
def site_type(raw, aliases):
    """Normalised site type: lower case, config aliases applied, "site" if unknown."""
    t = " ".join((raw or "").lower().split())
    return aliases.get(t, t) or "site"


LOST = "\ufffd"  # U+FFFD: a character the source lost


def _cp1252_bytes(s):
    """s as Windows-1252 bytes. The five bytes it leaves undefined come
    through as Latin-1 controls or as private-use U+F1xx ("Å\uf181" for
    the bytes of "Ł"), the two ways converters pass them on."""
    out = bytearray()
    for c in s:
        try:
            out += c.encode("cp1252")
        except UnicodeEncodeError:
            o = ord(c)
            if 0xF180 <= o <= 0xF1FF:
                o -= 0xF100
            elif o > 0xFF:
                raise
            out.append(o)
    return bytes(out)


def fix_mojibake(name, layers=3):
    """Undo UTF-8 read as Windows-1252 ("GraviÃ¨re" -> "Gravière") or Mac
    Roman ("Sundfj√¶ra" -> "Sundfjæra"), faults in some XRONOS site names.
    Each run of non-ASCII characters is repaired on its own, so names that
    mix good and bad letters ("Skj√¶rvika øvre") are fixed too."""
    name = re.sub(r"[^\x00-\x7f]+", lambda m: _fix_run(m.group(), layers), name or "")
    # What is left of a run that would not decode ("peÃÂÂ", cut off in the
    # source) is a lost letter, for repair_lost to match.
    name = re.sub(r"[^\x00-\x7f]*[ÃÂ√][^\x00-\x7f]+", LOST, name)
    return unicodedata.normalize("NFC", re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", name))


def _latin(c):
    """Latin letters, general punctuation, €, or a lost character: what a
    real repair of these (European, African, Near Eastern) site names gives.
    "l’Église" read as Mac Roman bytes is valid UTF-8 too, but Armenian."""
    o = ord(c)
    return o < 0x250 or 0x1E00 <= o <= 0x1EFF or 0x2000 <= o <= 0x206F or c in "€\ufffd"


def _fix_run(run, layers):
    """One run of non-ASCII characters: the whole run if it decodes, else,
    from each position, the longest piece that does ("à" + "ÔøΩÔøΩ")."""
    whole = _decode(run, layers)
    if whole != run or len(run) < 2:
        return whole
    out, i = [], 0
    while i < len(run):
        for j in range(len(run), i, -1):
            piece = _decode(run[i:j], layers)
            if piece != run[i:j] or j == i + 1:
                out.append(piece)
                i = j
                break
    return "".join(out)


def _decode(name, layers):
    """Re-read as UTF-8 up to `layers` times over ("Ã…Â¡" -> "Å¡" -> "š").
    A reading is kept only if it is valid UTF-8 with fewer non-ASCII
    characters, as a real repair always has."""
    def wide(t):
        return sum(ord(c) > 0x7F for c in t)

    for _ in range(layers):
        for enc in (_cp1252_bytes, lambda t: t.encode("mac_roman")):
            try:
                fixed = enc(name).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            if fixed != name and wide(fixed) < wide(name) and all(map(_latin, fixed)):
                name = fixed
                break
        else:
            break
    return name


def repair_lost(dates, km=10.0):
    """Names with U+FFFD (a letter the source lost, "G\ufffdbekli Tepe")
    take the one clean name within km that matches them with 1-3
    characters in place of each lost run. Rows are changed in place.
    Returns (repaired, still damaged) counts of distinct names."""
    clean = defaultdict(set)
    cell = _cell_size(km)
    for d in dates:
        if LOST not in d["site"]:
            clean[(math.floor(d["lon"] / cell), math.floor(d["lat"] / cell))].add((d["site"], d["lon"], d["lat"]))
    fixes, bad = {}, set()
    for d in dates:
        n = d["site"]
        if LOST not in n:
            continue
        k = (n, d["lon"], d["lat"])
        if k not in fixes:
            pat = re.compile("".join(".{1,3}" if not p.strip(LOST) else re.escape(p)
                                     for p in re.split(f"({LOST}+)", n) if p), re.IGNORECASE)
            cx, cy = math.floor(d["lon"] / cell), math.floor(d["lat"] / cell)
            hits = {c for dx in (-1, 0, 1) for dy in (-1, 0, 1) for c, lo, la in clean.get((cx + dx, cy + dy), ())
                    if pat.fullmatch(c) and _km((lo, la), (d["lon"], d["lat"])) <= km}
            fixes[k] = hits.pop() if len(hits) == 1 else None
        if fixes[k]:
            d["site"] = fixes[k]
        else:
            bad.add(n)
    return len({k[0] for k, v in fixes.items() if v}), len(bad)


def lab_key(labnr):
    """Lab number reduced to letters and digits, to spot one date in two sources."""
    return re.sub(r"[^a-z0-9]", "", (labnr or "").lower())


def _clean(s):
    return " ".join((s or "").split())


def parse_xronos(path, seen=None, type_aliases=None):
    """XRONOS API dump -> date rows.

    seen: set of measurement ids already taken from other dumps; updated.
    """
    out, seen = [], set() if seen is None else seen
    for row in json.load(open(path)) or []:  # an empty result is `null`
        m = row["measurement"]
        if m["id"] in seen:
            continue
        seen.add(m["id"])
        try:
            lat, lon, bp, std = float(m["lat"]), float(m["lng"]), float(m["bp"]), float(m["std"])
        except (TypeError, ValueError):
            continue
        name = _clean(fix_mojibake(m.get("site")))  # before _clean: it eats NBSP bytes
        if not name or std <= 0:
            continue
        refs = tuple(sorted({r for x in m.get("reference") or [] if (r := _clean(x.get("reference")))}))
        out.append({"site": name, "lon": lon, "lat": lat, "bp": bp, "std": std,
                    "labnr": m.get("labnr") or "", "type": site_type(m.get("site_type"), type_aliases or {}),
                    "periods": {p.get("periode") for p in m.get("periods") or [] if p.get("periode")},
                    "refs": refs, "dataset": "xronos"})
    return out


def parse_table(path, spec, seen_labs, type_aliases=None):
    """A CSV/TSV of dates -> date rows, skipping lab numbers in seen_labs.

    spec: a `[[settlements.tables]]` entry; `columns` maps labnr, bp, std,
    lon, lat, site and optionally type, period, refs (a list) to its headers.
    seen_labs: lab_key()s already used by earlier sources; updated.
    """
    col = spec["columns"]
    csv.field_size_limit(1 << 30)
    out = []
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        for r in csv.DictReader(f, delimiter=spec.get("delimiter", ",")):
            lab = lab_key(r.get(col["labnr"]))
            if not lab or lab in seen_labs:
                continue
            try:
                lon, lat = float(r[col["lon"]]), float(r[col["lat"]])
                bp, std = float(r[col["bp"]]), float(r[col["std"]])
            except (TypeError, ValueError):
                continue
            name = _clean(fix_mojibake(r.get(col["site"])))
            if not name or std <= 0:
                continue
            seen_labs.add(lab)
            period = _clean(r.get(col.get("period", ""), ""))
            refs = tuple(sorted({v for c in col.get("refs", []) if (v := _clean(r.get(c)))}))
            out.append({"site": name, "lon": lon, "lat": lat, "bp": bp, "std": std,
                        "labnr": _clean(r[col["labnr"]]),
                        "type": site_type(r.get(col.get("type", ""), ""), type_aliases or {}),
                        "periods": {period} if period else set(),
                        "refs": refs, "dataset": spec["name"]})
    return out


# ---------------------------------------------------------------- derive
def site_id(key):
    return zlib.crc32(key.encode())


def name_tokens(name):
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return frozenset(re.findall(r"[a-z0-9]+", plain))


def _km(a, b):
    (lo1, la1), (lo2, la2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2)
    return 12742 * math.asin(math.sqrt(h))


def _cell_size(km):
    return km / 111.0 / 0.3  # degrees; cos(lat) >= 0.3 up to ~72°N


def merge_spellings(groups, same_km, same_name_km=0.0):
    """Fold together entries for one site filed under several spellings:
    within same_km of each other, and one name's words all appear in the
    other's ("Bricia" / "Cueva de Bricia"); or within same_name_km with the
    same words, for one site filed at differing coordinates. The shortest
    name wins (then not all capitals, then most dates); the entry with the
    most dates gives the point. Returns [(name, lon, lat, rows, aliases)]."""
    keys = sorted(groups)
    parent = list(range(len(keys)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    reach = max(same_km, same_name_km)
    if reach > 0:
        toks = [name_tokens(k[0]) for k in keys]
        cell = _cell_size(reach)
        cells = defaultdict(list)
        for i, (_, lon, lat) in enumerate(keys):
            cells[(math.floor(lon / cell), math.floor(lat / cell))].append(i)
        for i, (_, lon, lat) in enumerate(keys):
            cx, cy = math.floor(lon / cell), math.floor(lat / cell)
            for j in (j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in cells.get((cx + dx, cy + dy), ())):
                if j <= i or not toks[i] or not toks[j]:
                    continue
                if toks[i] == toks[j]:
                    limit = reach
                elif toks[i] <= toks[j] or toks[j] <= toks[i]:
                    limit = same_km
                else:
                    continue
                if _km(keys[i][1:], keys[j][1:]) <= limit:
                    parent[find(j)] = find(i)
    members = defaultdict(list)
    for i in range(len(keys)):
        members[find(i)].append(keys[i])
    out = []
    for ks in members.values():
        _, lon, lat = max(ks, key=lambda k: (len(groups[k]), k))
        name = min(ks, key=lambda k: (LOST in k[0], len(name_tokens(k[0])), k[0].isupper(), -len(groups[k]), k))[0]
        rows = [r for k in ks for r in groups[k]]
        out.append((name, lon, lat, rows, sorted({k[0] for k in ks} - {name})))
    return sorted(out, key=lambda t: t[:3])


def collapse_duplicates(rows):
    """One row per measurement at a site. Sources that compile other
    databases hold a date once per database, so rows with the same lab number,
    or the same age and error, are one date; its references are pooled.
    rows: [(year, date row)], in source order (the first row is kept)."""
    out, by_lab, by_age = [], {}, {}
    for y, d in rows:
        lab, age = lab_key(d["labnr"]), (d["bp"], d["std"])
        i = by_lab.get(lab) if lab else None
        if i is None:
            i = by_age.get(age)
        if i is None:
            i = len(out)
            out.append((y, dict(d)))
        else:
            kept = out[i][1]
            kept["refs"] = tuple(sorted({*kept["refs"], *d["refs"]}))
            kept["periods"] = kept["periods"] | d["periods"]
        if lab:
            by_lab.setdefault(lab, i)
        by_age.setdefault(age, i)
    return out


def _by_count(counter):
    return [k for k, _ in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]


def derive_sites(dates, years, window, trim=0.0, same_km=0.0, same_name_km=0.0,
                 max_periods=5, dated=None):
    """Group dated measurements into site features.

    dates: date rows. years: calibrated signed year per row (NaN to skip).
    window: (start, end) signed years; a site needs a date inside it.
    trim: founding/abandoned are the trim and 1-trim quantiles of the site's
    dates, so stray old or young dates at well-dated sites don't set them.
    With fewer than 1/trim dates this is the plain earliest and latest.
    dated: if a dict, filled with site key -> [(year, date row)].
    """
    groups = defaultdict(list)
    for d, y in zip(dates, years):
        if not np.isnan(y):
            groups[(d["site"], round(d["lon"], 4), round(d["lat"], 4))].append((int(y), d))
    feats, seen = [], {}
    for name, lon, lat, rows, aliases in merge_spellings(groups, same_km, same_name_km):
        rows = collapse_duplicates(rows)
        ys = [y for y, _ in rows]
        if not any(window[0] <= y <= window[1] for y in ys):
            continue
        founding = int(np.quantile(ys, trim, method="lower"))
        if founding > window[1]:  # its only in-window dates were trimmed as strays
            continue
        key = f"c14:{name}@{lon},{lat}"
        fid = site_id(key)
        if fid in seen:
            raise ValueError(f"settlement id clash: {key!r} vs {seen[fid]!r}")
        seen[fid] = key
        if dated is not None:
            dated[key] = rows
        feats.append({
            "type": "Feature", "id": fid,
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "name": name,
                "founding": founding,
                "abandoned": int(np.quantile(ys, 1 - trim, method="higher")),
                "type": Counter(d["type"] for _, d in rows).most_common(1)[0][0], "population": {},
                "n_dates": len(ys),
                "periods": _by_count(Counter(p for _, d in rows for p in d["periods"]))[:max_periods],
                "sources": sorted({d["dataset"] for _, d in rows}),
                "references": _by_count(Counter(r for _, d in rows for r in d["refs"])),
                "key": key, **({"aliases": aliases} if aliases else {}),
            },
        })
    return feats


# -------------------------------------------------------------- wikidata
WIKIDATA_QUERY = """SELECT ?item (SAMPLE(?label) AS ?name) (SAMPLE(?coord) AS ?point) (MIN(?inc) AS ?inception)
       (GROUP_CONCAT(DISTINCT ?cultureLabel; separator="|") AS ?cultures)
       (GROUP_CONCAT(DISTINCT ?alt; separator="|") AS ?alts) (SAMPLE(?title) AS ?enwiki) WHERE {
  SERVICE wikibase:box { ?item wdt:P625 ?coord .
    bd:serviceParam wikibase:cornerSouthWest "Point(%s %s)"^^geo:wktLiteral ;
                    wikibase:cornerNorthEast "Point(%s %s)"^^geo:wktLiteral . }
  ?item wdt:P31/wdt:P279* wd:Q839954 .
  ?art schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?title .
  OPTIONAL { ?item rdfs:label ?label FILTER(LANG(?label) = "en") }
  OPTIONAL { ?item wdt:P571 ?inc }
  OPTIONAL { ?item wdt:P2596 ?culture . ?culture rdfs:label ?cultureLabel FILTER(LANG(?cultureLabel) = "en") }
  OPTIONAL { ?item skos:altLabel ?alt FILTER(LANG(?alt) = "en") }
} GROUP BY ?item"""

# Words that don't tell two sites apart when matching names to Wikidata.
GENERIC = frozenset("""a abri archaeological cave cueva de del di el grotta grotte hoyuk la le les of
    rock shelter site tall tel tell tepe the""".split())


def wikidata_tiles(bounds, size):
    """(lon0, lat0, lon1, lat1) tiles of `size` degrees covering bounds."""
    lon0, lat0, lon1, lat1 = bounds
    return [(x, y, min(x + size, lon1), min(y + size, lat1))
            for x in np.arange(lon0, lon1, size).tolist() for y in np.arange(lat0, lat1, size).tolist()]


def parse_wikidata(path):
    """Query result CSV -> [{qid, name, names, lon, lat, inception, cultures, wikipedia}]."""
    out = []
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            m = re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", r["point"])
            if not m:
                continue
            y = re.match(r"(-?\d+)-", r["inception"])
            title = r["enwiki"]
            names = [n for n in [r["name"], re.sub(r"\s*\(.*\)$", "", title), *r["alts"].split("|")] if n]
            out.append({"qid": r["item"].rsplit("/", 1)[-1], "name": r["name"] or title, "names": names,
                        "lon": float(m[1]), "lat": float(m[2]), "inception": int(y[1]) if y else None,
                        "cultures": sorted(c for c in r["cultures"].split("|") if c), "wikipedia": title})
    return out


def _distinct(name):
    return name_tokens(name) - GENERIC


def enrich_wikidata(feats, items, match_km, window):
    """Attach Wikidata ids to sites and add Wikidata sites founded in window.

    An item matches the nearest site within match_km that shares its name:
    ignoring GENERIC words, one name's words all appear in the other's. A
    site takes its nearest matching item. Items that match nothing and have
    an inception date inside window become sites of their own.
    """
    cell = _cell_size(match_km)
    cells = defaultdict(list)
    names = []
    for i, f in enumerate(feats):
        lon, lat = f["geometry"]["coordinates"]
        cells[(math.floor(lon / cell), math.floor(lat / cell))].append(i)
        p = f["properties"]
        names.append([t for n in [p["name"], *p.get("aliases", [])] if (t := _distinct(n))])
    best, seen_q = {}, set()   # feature index -> (km, item)
    unmatched = []
    for it in items:
        if it["qid"] in seen_q:  # tiles share their edges
            continue
        seen_q.add(it["qid"])
        toks = [t for n in it["names"] if (t := _distinct(n))]
        cx, cy = math.floor(it["lon"] / cell), math.floor(it["lat"] / cell)
        hit = None
        for i in (i for dx in (-1, 0, 1) for dy in (-1, 0, 1) for i in cells.get((cx + dx, cy + dy), ())):
            if not any(a <= b or b <= a for a in toks for b in names[i]):
                continue
            d = _km((it["lon"], it["lat"]), feats[i]["geometry"]["coordinates"])
            if d <= match_km and (hit is None or d < hit[0]):
                hit = (d, i)
        if hit is None:
            unmatched.append(it)
        elif hit[1] not in best or hit[0] < best[hit[1]][0]:
            best[hit[1]] = (hit[0], it)
    for i, (_, it) in best.items():
        p = feats[i]["properties"]
        p.update(wikidata=it["qid"], wikipedia=it["wikipedia"], sources=p["sources"] + ["wikidata"])
        if it["cultures"]:
            p["culture"] = it["cultures"]
    added = []
    for it in unmatched:
        if it["inception"] is None or not window[0] <= it["inception"] <= window[1]:
            continue
        key = f"wikidata:{it['qid']}"
        added.append({
            "type": "Feature", "id": site_id(key),
            "geometry": {"type": "Point", "coordinates": [round(it["lon"], 4), round(it["lat"], 4)]},
            "properties": {
                "name": it["name"], "founding": int(round(it["inception"] / CAL_STEP) * CAL_STEP),
                "type": "site", "population": {}, "n_dates": 0, "periods": [],
                "sources": ["wikidata"], "references": [f"Wikidata {it['qid']}"], "key": key,
                "wikidata": it["qid"], "wikipedia": it["wikipedia"],
                **({"culture": it["cultures"]} if it["cultures"] else {}),
            },
        })
    return feats + added, len(best), len(added)


# ------------------------------------------------------------------- hex
def assign_hex(grid, feats):
    """Set properties.hex to the containing hex id; drop features off the grid."""
    left, top, right, bottom = grid.bbox.T
    out = []
    for f in feats:
        lon, lat = f["geometry"]["coordinates"]
        for i in np.flatnonzero((left <= lon) & (lon <= right) & (bottom <= lat) & (lat <= top)):
            if point_in_poly(np.array([lon]), np.array([lat]), grid.rings[i])[0]:
                f["properties"]["hex"] = int(grid.ids[i])
                out.append(f)
                break
    return out


# --------------------------------------------------------------- curated
def merge_curated(feats, curated, merge_km):
    """Hand entries win key by key over a derived site; the derived site's
    other properties are kept. The site is the one whose name or alias equals
    the entry's `match` property (the best dated, if several), else the
    nearest within merge_km. Unmatched entries are added as they are. A null
    geometry takes the matched site's."""
    feats = list(feats)
    for c in curated:
        own = {k: v for k, v in c["properties"].items() if k != "match"}
        want, geom = c["properties"].get("match"), c.get("geometry")
        if want:
            near = [(-f["properties"].get("n_dates", 0), i) for i, f in enumerate(feats)
                    if want in [f["properties"]["name"], *f["properties"].get("aliases", [])]]
            if not near:
                raise ValueError(f"curated {own['name']!r}: no dated site named {want!r}")
        else:
            near = [(d, i) for i, f in enumerate(feats)
                    if (d := _km(geom["coordinates"], f["geometry"]["coordinates"])) <= merge_km]
        props = {"type": "settlement", "population": {}, "sources": ["curated"], "references": [], **own}
        if near:
            _, i = min(near)
            base = feats.pop(i)
            geom = geom or base["geometry"]
            props = {**base["properties"], **own,
                     "sources": base["properties"]["sources"] + ["curated"],
                     "aliases": [base["properties"]["name"]] + base["properties"].get("aliases", [])}
        feats.append({"type": "Feature", "id": c.get("id", site_id("curated:" + props["name"])),
                      "geometry": geom, "properties": props})
    return feats


# ------------------------------------------------------------- citations
def write_dates(path, feats, dated):
    """Every date behind every site, with the references its record gives."""
    ids = {f["properties"]["key"]: f["id"] for f in feats if "key" in f["properties"]}
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["site_id", "site", "lab_number", "c14_age", "c14_error", "cal_year", "dataset",
                "site_as_filed", "references"])
    n = 0
    for key in sorted(k for k in dated if k in ids):
        name = key[len("c14:"):].rsplit("@", 1)[0]
        for y, d in sorted(dated[key], key=lambda r: (r[0], r[1]["labnr"])):
            w.writerow([ids[key], name, d["labnr"], f"{d['bp']:g}", f"{d['std']:g}", y, d["dataset"],
                        d["site"], " | ".join(d["refs"])])
            n += 1
    with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as gz:
        gz.write(buf.getvalue().encode())
    return n


def write_sources(path, cites, feats, dated, prov, min_refs):
    """SOURCES.md: what to cite for the generated files, and how much of the
    output rests on each source."""
    kept = {f["properties"]["key"] for f in feats if "key" in f["properties"]}
    n_dates = Counter(d["dataset"] for k in kept if k in dated for _, d in dated[k])
    n_sites = Counter(s for f in feats for s in f["properties"]["sources"])
    refs = Counter(r for k in kept if k in dated for _, d in dated[k] for r in d["refs"])
    uncited = sum(1 for k in kept if k in dated for _, d in dated[k] if not d["refs"])
    got = defaultdict(list)
    for p in prov:
        got[p["dataset"]].append(p["fetched"])
    L = ["# Sources for `data/settlements/`", "",
         "Generated by `make settlements`; edit `[settlements.citations]` in",
         "`pipeline/config.toml`, not this file.", "",
         "## Datasets", "",
         "Cite each dataset below that the sites you use list in their `sources`",
         "property, plus the calibration curve.", ""]
    for name, c in cites.items():
        if name not in got and not n_sites[name]:
            continue  # configured but not used in this build
        when = sorted(set(got.get(name, [])))
        L += [f"### {c['title']} (`{name}`)", "",
              f"- **Cite:** {c['citation']}",
              f"- **Licence:** {c['licence']}",
              *([f"- **URL:** {c['url']}"] if c.get("url") else []),
              *([f"- **Retrieved:** {when[0]}" + (f" to {when[-1]}" if len(when) > 1 else "")
                 + f" ({len(got[name])} file{'s' if len(got[name]) > 1 else ''}, hashes in `provenance.json`)"]
                if when else []),
              *([f"- **In the output:** {n_sites[name]} sites" + (f", {n_dates[name]} dates" if n_dates[name] else "")]
                if n_sites[name] else []),
              *([f"- **Note:** {c['note']}"] if c.get("note") else []), ""]
    L += ["## Original sources of the dates", "",
          "XRONOS asks that the original sources listed on each record are cited",
          "as well as XRONOS itself. Each site's `references` property lists them,",
          "and `dates.csv.gz` gives them date by date with lab numbers.",
          f"There are {len(refs)} distinct references; those behind at least {min_refs}",
          "dates in the output are:", "",
          "| Reference | Dates |", "|---|---|"]
    L += [f"| {r.replace('|', '/')} | {n} |" for r, n in sorted(refs.items(), key=lambda kv: (-kv[1], kv[0]))
          if n >= min_refs]
    L += ["", f"{uncited} dates carry no reference in their source record; they are cited to their",
          "dataset alone.", ""]
    with open(path, "w") as f:
        f.write("\n".join(L))


# ------------------------------------------------------------------- run
def build(cfg, grid, log=print):
    sc, tc = cfg["settlements"], cfg["time"]
    raw, out_dir = sc["raw_dir"], os.path.dirname(sc["out"])
    window = (tc["start"], tc["end"])
    prov = [fetch(sc["curve_url"], os.path.join(raw, "intcal20.14c"), "intcal20")]
    curve = load_curve(prov[0]["path"])

    xc = sc["xronos"]
    queries = ([("type", t) for t in xc.get("site_types", [])]
               + [("country", c) for c in xc.get("countries", [])])

    def get(q):
        kind, v = q
        url = xc["url"] + "?" + urllib.parse.urlencode({f"query_{'site_type' if kind == 'type' else kind}": v})
        name = f"xronos_{kind}_{''.join(c if c.isalnum() else '_' for c in v)}.json"
        return fetch(url, os.path.join(raw, name), "xronos")

    with ThreadPoolExecutor(8) as ex:
        dumps = list(ex.map(get, queries))
    prov += dumps
    aliases = xc.get("type_aliases")
    dates, seen = [], set()
    for p in dumps:
        dates += parse_xronos(p["path"], seen, aliases)
    log(f"xronos: {len(dates)} usable dates from {len(dumps)} queries")

    labs = {lab_key(d["labnr"]) for d in dates}
    for spec in sc.get("tables", []):
        p = fetch(spec["url"], os.path.join(raw, spec["file"]), spec["name"])
        prov.append(p)
        rows = parse_table(p["path"], spec, labs, aliases)
        log(f"{spec['name']}: {len(rows)} usable dates not already in hand")
        dates += rows

    fixed, lost = repair_lost(dates, sc["same_name_km"])
    log(f"names: {fixed} with lost letters matched to a clean spelling nearby, {lost} left as they are")

    left, top, right, bottom = grid.bbox.T
    bounds = (float(left.min()), float(bottom.min()), float(right.max()), float(top.max()))
    skip = xc.get("exclude_types", [])
    dates = [d for d in dates
             if d["std"] <= sc["max_std"] and not any(x in d["type"] for x in skip)
             and bounds[0] <= d["lon"] <= bounds[2] and bounds[1] <= d["lat"] <= bounds[3]]

    cal = calibrate([d["bp"] for d in dates], [d["std"] for d in dates], curve)
    years = np.array([to_year(c) if not np.isnan(c) else np.nan for c in cal])
    dated = {}
    feats = derive_sites(dates, years, window, sc["trim"], sc["same_km"], sc["same_name_km"], dated=dated)
    feats = [f for f in feats if f["properties"]["n_dates"] >= sc["min_dates"]]
    log(f"{len(feats)} dated sites in {window[0]}..{window[1]}")

    wc = sc.get("wikidata", {})
    if wc.get("enabled"):
        def tile(t):
            url = wc["url"] + "?" + urllib.parse.urlencode({"query": WIKIDATA_QUERY % t})
            name = "wikidata_%g_%g.csv" % t[:2]
            return fetch(url, os.path.join(raw, name), "wikidata", accept="text/csv", tries=10,
                         contact=wc.get("contact", ""))

        # One at a time: the query service limits request rates.
        tiles = [tile(t) for t in wikidata_tiles(bounds, wc["tile_degrees"])]
        prov += tiles
        items = [it for p in tiles for it in parse_wikidata(p["path"])]
        feats, matched, added = enrich_wikidata(feats, items, wc["match_km"], window)
        log(f"wikidata: {matched} sites matched, {added} added from {len(tiles)} tiles")

    if os.path.exists(sc["curated"]):
        curated = json.load(open(sc["curated"]))["features"]
        feats = merge_curated(feats, curated, sc["merge_km"])
        log(f"merged {len(curated)} curated entries")

    n = len(feats)
    feats = assign_hex(grid, feats)
    log(f"{n - len(feats)} sites off the grid dropped")

    cc = sc.get("cultures")
    if cc:
        from . import cultures
        os.makedirs(cc["out_dir"], exist_ok=True)
        os.makedirs(os.path.dirname(cc["unmapped"]), exist_ok=True)
        cultures.build(cc["table"], cc["out_dir"], feats, dated, cc["unmapped"], sc["trim"],
                       cc["range_margin"], log, cc.get("infer"))
    feats.sort(key=lambda f: (f["properties"]["founding"], f["properties"]["name"]))

    os.makedirs(out_dir, exist_ok=True)
    with open(sc["out"], "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, ensure_ascii=False, indent=1)
    nd = write_dates(os.path.join(out_dir, "dates.csv.gz"), feats, dated)
    write_sources(os.path.join(out_dir, "SOURCES.md"), sc["citations"], feats, dated, prov, sc["min_refs_listed"])
    with open(os.path.join(out_dir, "provenance.json"), "w") as f:
        json.dump(sorted(prov, key=lambda p: p["path"]), f, indent=1)
    log(f"wrote {sc['out']}: {len(feats)} settlements, {nd} dates cited")
    return feats
