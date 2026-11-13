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
import tomllib
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


_POSSESSIVE = re.compile(r"\b([A-Z][a-z]+) s (?=[A-Z])")
_ELISION = re.compile(r"(?<![\w'´])([dlDL]) (?=[AEIOUHÀ-ÖØ-Ý])")


def restore_apostrophes(name):
    """Put back apostrophes XRONOS turned into spaces: "Gough s Cave" ->
    "Gough's Cave", "Pont d Ambon" -> "Pont d'Ambon". Elision only before a
    vowel or h, so "L1 (L Basin)" and Danish "Hyllested s., ..." are left alone."""
    return _ELISION.sub(r"\1'", _POSSESSIVE.sub(r"\1's ", name or ""))


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


def load_records(path):
    """data/settlements/records.toml -> (locate, same).

    locate: filed site name -> (lon, lat) for records filed with no position.
    same: filed site name -> (site name, lon, lat), for `apply_same`.
    Every `[[same]]` member is also in `locate`, at the site's position."""
    if not path or not os.path.exists(path):
        return {}, {}
    with open(path, "rb") as f:
        doc = tomllib.load(f)
    locate, same = {}, {}
    for e in doc.get("locate", []):
        locate[e["site"]] = tuple(e["at"])
    for e in doc.get("same", []):
        for m in e["members"]:
            if m in same:
                raise ValueError(f"{path}: {m!r} is in two [[same]] entries")
            same[m] = (e["name"], *e["at"])
            locate[m] = tuple(e["at"])
    return locate, same


def load_rejects(path):
    """data/settlements/records.toml `[[reject]]` entries -> {(filed site
    name, lab_key(lab))}: single dates filed under the wrong site, dropped
    before the records are grouped into sites."""
    if not path or not os.path.exists(path):
        return set()
    with open(path, "rb") as f:
        doc = tomllib.load(f)
    return {(e["site"], lab_key(e["lab"])) for e in doc.get("reject", [])}


def load_keeps(path):
    """data/settlements/records.toml `[[keep]]` entries -> {(filed site name,
    lab_key(lab))}: single dates admitted although their 1-sigma error is
    above `max_std` (old, wide dates that are a site's only record)."""
    if not path or not os.path.exists(path):
        return set()
    with open(path, "rb") as f:
        doc = tomllib.load(f)
    return {(e["site"], lab_key(e["lab"])) for e in doc.get("keep", [])}


def kept(d, keeps):
    """Whether date row d is named by a `[[keep]]` (by its filed name)."""
    return (d.get("filed", d["site"]), lab_key(d["labnr"])) in keeps


def apply_rejects(dates, rejects):
    """Drop the date rows named by `load_rejects`, in place. Raises when a
    reject matches no row (the record changed under it). Returns how many
    rows were dropped."""
    hit = set()
    keep = []
    for d in dates:
        k = (d["site"], lab_key(d["labnr"]))
        if k in rejects:
            hit.add(k)
        else:
            keep.append(d)
    missing = sorted(rejects - hit)
    if missing:
        raise ValueError(f"records.toml [[reject]] matches no date: {missing}")
    n = len(dates) - len(keep)
    dates[:] = keep
    return n


def apply_same(dates, same):
    """Refile the date rows of each `[[same]]` member under the site's name
    and position; the filed name is kept as `filed` (it becomes an alias).
    Returns how many rows were refiled."""
    n = 0
    for d in dates:
        hit = same.get(d["site"])
        if hit:
            d["filed"], (d["site"], d["lon"], d["lat"]) = d["site"], hit
            n += 1
    return n


def load_refiles(path):
    """data/settlements/records.toml `[[refile]]` entries -> {(filed site
    name, lab_key(lab)): (site name, lon, lat)}: single dates filed under
    another site's name (and position), moved to their own."""
    if not path or not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        doc = tomllib.load(f)
    return {(e["site"], lab_key(e["lab"])): (e["name"], *e["at"]) for e in doc.get("refile", [])}


def apply_refiles(dates, refiles):
    """Move the date rows named by `load_refiles`, in place. The filed name is
    kept as `filed`, but as a wrong name, not an alias (`misfiled`). Raises
    when an entry matches no row. Returns how many rows were moved."""
    hit = set()
    for d in dates:
        k = (d["site"], lab_key(d["labnr"]))
        if k in refiles:
            hit.add(k)
            d["filed"], d["misfiled"] = d["site"], True
            d["site"], d["lon"], d["lat"] = refiles[k]
    missing = sorted(set(refiles) - hit)
    if missing:
        raise ValueError(f"records.toml [[refile]] matches no date: {missing}")
    return len(hit)


def drop_shifted(dates, path, spec, km, block=("Source", "Vermeersch2019")):
    """Drop XRONOS dates taken from a p3k14c block whose names are out of step.

    XRONOS takes in p3k14c's records and files each under the XRONOS site of
    its name. In p3k14c's Vermeersch2019 rows, names (and some positions) are
    an alphabetical neighbour's (GIN-4858 from Lake Lacha is 'Peschio Ranaro',
    LE-1469 'Vergara'), so XRONOS filed those dates at namesakes in Italy and
    Spain. A XRONOS date that cites p3k14c, whose twin in the block (same lab
    number and age) is more than `km` from where XRONOS has it, contradicts
    itself and is dropped: neither its name nor its position can be trusted.
    Rows already moved by hand (`filed`) are left alone. spec: the p3k14c
    `[[settlements.tables]]` entry. Returns (dates dropped, sites hit)."""
    col = spec["columns"]
    twins = defaultdict(list)
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        for r in csv.DictReader(f, delimiter=spec.get("delimiter", ",")):
            if block[1] not in (r.get(block[0]) or ""):
                continue
            try:
                twins[lab_key(r[col["labnr"]])].append((float(r[col["bp"]]), float(r[col["lon"]]), float(r[col["lat"]])))
            except (TypeError, ValueError):
                continue
    keep, sites = [], set()
    for d in dates:
        twin = [(lo, la) for bp, lo, la in twins.get(lab_key(d["labnr"]), ()) if abs(bp - d["bp"]) < 1]
        if (twin and d["dataset"] == "xronos" and "p3k14c" in d["refs"] and not d.get("filed")
                and all(_km(p, (d["lon"], d["lat"])) > km for p in twin)):
            sites.add((d["site"], d["lon"], d["lat"]))
            continue
        keep.append(d)
    n = len(dates) - len(keep)
    dates[:] = keep
    return n, len(sites)


def parse_xronos(path, seen=None, type_aliases=None, locate=None):
    """XRONOS API dump -> date rows.

    seen: set of measurement ids already taken from other dumps; updated.
    locate: filed site name -> (lon, lat) for records filed with no position
    (`load_records`); without one such a record is dropped.
    """
    out, seen = [], set() if seen is None else seen
    for row in json.load(open(path)) or []:  # an empty result is `null`
        m = row["measurement"]
        if m["id"] in seen:
            continue
        seen.add(m["id"])
        name = restore_apostrophes(_clean(fix_mojibake(m.get("site"))))  # fix_mojibake before _clean: it eats NBSP bytes
        try:
            bp, std = float(m["bp"]), float(m["std"])
        except (TypeError, ValueError):
            continue
        try:
            lat, lon = float(m["lat"]), float(m["lng"])
        except (TypeError, ValueError):
            if not (locate and name in locate):
                continue
            lon, lat = locate[name]
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
            name = restore_apostrophes(_clean(fix_mojibake(r.get(col["site"]))))
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


# Letters NFKD leaves whole, so the ASCII step dropped them ("Nevalı" ->
# "neval", "Sølager" -> "slager").
_FOLD = str.maketrans({"ı": "i", "İ": "I", "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "œ": "oe",
                       "Œ": "OE", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ð": "d", "Ð": "D",
                       "þ": "th", "Þ": "Th", "ß": "ss", "ħ": "h"})
# An apostrophe inside a word joins it ("Qala’at", "Dja'de", "Ra's"), whichever
# of the quote marks and modifier letters the source used.
_APOS = re.compile(r"(?<=\w)['’‘ʼʻʿʾ`´](?=\w)")


def name_tokens(name):
    plain = _APOS.sub("", name.translate(_FOLD))
    plain = unicodedata.normalize("NFKD", plain).encode("ascii", "ignore").decode().lower()
    return frozenset(re.findall(r"[a-z0-9]+", plain))


# Words that make a name a different site or locus: numbers, Roman numerals,
# single letters and compass/level words ("Sabi Abyad II", "Gobero G3",
# "Çatalhöyük West"); also glued on ("HierakonpolisII").
_QUAL = re.compile(r"^(?:[ivx]+|\d+[a-z]?|[a-z]\d*|north|south|east|west|upper|lower|nord|sud|est|ouest)$")


def qualifiers(name):
    q = {t for t in name_tokens(name) if _QUAL.match(t)} - set("adelnosy")
    q |= {m.lower() for m in re.findall(r"(?<=[A-Za-z])([IVX]+)\b", name) if len(m) < len(name) - 3}
    return q | ({"i"} if re.search(r"\bI\b", name) else set())


_VOWELS = frozenset("aeiouy")


def _vowel_drop(x, y):
    """x is y with only vowels left out ("catalhyk" / "catalhoyuk", the
    source lost the accented letters)."""
    if len(x) < 4 or len(x) >= len(y):
        return False
    i = 0
    for c in y:
        if i < len(x) and c == x[i]:
            i += 1
        elif c not in _VOWELS:
            return False
    return i == len(x)


def garbled_same(a, b):
    """Two names that are one spelling with letters lost: a U+FFFD standing for
    1-3 letters ("G\ufffdytepe" / "Göytepe"), or words that differ only by left-out
    vowels ("Demircihyk" / "Demircihöyük"). Qualifiers must agree."""
    if qualifiers(a) != qualifiers(b):
        return False
    for n, m in ((a, b), (b, a)):
        if LOST in n and re.fullmatch("".join(".{1,3}" if c == LOST else re.escape(c) for c in n), m, re.I):
            return True
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or len(ta) != len(tb) or ta == tb:
        return False
    xa, xb = ta - tb, tb - ta
    return len(xa) == len(xb) and all(any(_vowel_drop(x, y) or _vowel_drop(y, x) for y in xb) for x in xa)


def _km(a, b):
    (lo1, la1), (lo2, la2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2)
    return 12742 * math.asin(math.sqrt(h))


def _cell_size(km):
    return km / 111.0 / 0.3  # degrees; cos(lat) >= 0.3 up to ~72°N


def merge_spellings(groups, same_km, same_name_km=0.0, share_km=0.0, measure=None):
    """Fold together entries for one site filed under several spellings:
    within same_km of each other, and one name's words all appear in the
    other's ("Bricia" / "Cueva de Bricia"); or within same_name_km with the
    same words, for one site filed at differing coordinates, or a name with
    lost letters ("Catalhyk East" / "Çatalhöyük East"); or within share_km
    whatever the names, when they hold the same measurements ("Aswad" / "Tell
    Aswad", 27 of 31 dates): at least two, and half of the smaller entry's, or
    the one date of a one-date entry by its lab number. measure(row) gives
    (lab_key, (bp, std)) for a row of `groups`; without it there is no
    share_km rule. Names whose qualifiers differ ("Sabi Abyad II" / "Tell
    Sabi Abyad III") are only folded by the share rule when the shared dates
    are half of the larger entry too. The shortest name wins (then not all
    capitals, then most dates); the entry with the most dates gives the
    point. Returns [(name, lon, lat, rows, aliases)]."""
    keys = sorted(groups)
    parent = list(range(len(keys)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    if measure is None:
        share_km = 0.0
    reach = max(same_km, same_name_km, share_km)
    if reach > 0:
        toks = [name_tokens(k[0]) for k in keys]
        quals = [qualifiers(k[0]) for k in keys]
        if share_km > 0:
            meas = [[measure(r) for r in groups[k]] for k in keys]
            labs = [{l for l, _ in m if l} for m in meas]
            ages = [{a for _, a in m} for m in meas]
        cell = _cell_size(reach)
        cells = defaultdict(list)
        for i, (_, lon, lat) in enumerate(keys):
            cells[(math.floor(lon / cell), math.floor(lat / cell))].append(i)

        def shares(i, j):
            # Lab numbers are written differently between sources ("GrA-20801/Lyon-1787",
            # "Ly-1787"), so the same age and error counts as the same date too.
            n = max(len(labs[i] & labs[j]), len(ages[i] & ages[j]))
            small, big = sorted((len(groups[keys[i]]), len(groups[keys[j]])))
            if quals[i] != quals[j] and n < big / 2:
                return False
            return (n >= 2 and n >= small / 2) or (small == 1 and bool(labs[i] & labs[j]))

        for i, (_, lon, lat) in enumerate(keys):
            cx, cy = math.floor(lon / cell), math.floor(lat / cell)
            for j in (j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in cells.get((cx + dx, cy + dy), ())):
                if j <= i or not toks[i] or not toks[j]:
                    continue
                d = _km(keys[i][1:], keys[j][1:])
                if toks[i] == toks[j] or garbled_same(keys[i][0], keys[j][0]):
                    limit = same_name_km
                elif toks[i] <= toks[j] or toks[j] <= toks[i]:
                    limit = same_km
                else:
                    limit = -1.0  # names alone never fold these
                if d <= limit or (0 < share_km and d <= share_km and shares(i, j)):
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


def occupation(ys, gap):
    """Occupation phases [[start, abandoned_by], ...] from calibrated years.

    Dates more than `gap` years apart start a new phase. A phase is taken to
    end `gap` years after its last date: with no evidence for that long, the
    site is assumed abandoned by then. (So "abandoned_by" is an upper bound;
    the last date is the lower one.) gap <= 0 gives no phases.
    """
    ys = sorted(ys)
    if gap <= 0 or not ys:
        return []
    phases = [[ys[0], ys[0]]]
    for y in ys[1:]:
        if y - phases[-1][1] > gap:
            phases.append([y, y])
        else:
            phases[-1][1] = y
    return [[a, b + gap] for a, b in phases]


def derive_sites(dates, years, window, trim=0.0, same_km=0.0, same_name_km=0.0,
                 max_periods=5, dated=None, gap=0, share_km=0.0):
    """Group dated measurements into site features.

    dates: date rows. years: calibrated signed year per row (NaN to skip).
    window: (start, end) signed years; a site needs a date inside it.
    trim: founding/abandoned are the trim and 1-trim quantiles of the site's
    dates, so stray old or young dates at well-dated sites don't set them.
    With fewer than 1/trim dates this is the plain earliest and latest.
    dated: if a dict, filled with site key -> [(year, date row)].
    gap: see `occupation`; phases use the dates left after trimming.
    """
    groups = defaultdict(list)
    for d, y in zip(dates, years):
        if not np.isnan(y):
            groups[(d["site"], round(d["lon"], 4), round(d["lat"], 4))].append((int(y), d))
    feats, seen = [], {}
    measure = lambda r: (lab_key(r[1]["labnr"]), (r[1]["bp"], r[1]["std"]))
    for name, lon, lat, rows, aliases in merge_spellings(groups, same_km, same_name_km, share_km, measure):
        # Names refiled by `apply_same` are aliases too (not `apply_refiles`' wrong names).
        aliases = sorted(set(aliases) | {f for _, d in rows
                                         if (f := d.get("filed")) and f != name and not d.get("misfiled")})
        rows = collapse_duplicates(rows)
        ys = [y for y, _ in rows]
        if not any(window[0] <= y <= window[1] for y in ys):
            continue
        founding = int(np.quantile(ys, trim, method="lower"))
        if founding > window[1]:  # its only in-window dates were trimmed as strays
            continue
        last = int(np.quantile(ys, 1 - trim, method="higher"))
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
                "abandoned": last,
                **({"occupation": phases} if (phases := occupation(
                    [y for y in ys if founding <= y <= last], gap)) else {}),
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
            p["wikidata_culture"] = it["cultures"]
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
                **({"wikidata_culture": it["cultures"]} if it["cultures"] else {}),
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
    nearest dated site within merge_km (never an earlier hand entry). Unmatched entries are added as they are. A null
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
            # Never another hand entry: two of them close together are two sites.
            near = [(d, i) for i, f in enumerate(feats) if f["properties"].get("sources") != ["curated"]
                    and (d := _km(geom["coordinates"], f["geometry"]["coordinates"])) <= merge_km]
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


# ------------------------------------------------------------ importance
# How a piece is sized when a site has no population figure. Only what the
# record says about the past counts: what kind of place it was, how long and
# how often it was lived in, and whether it stands out among its neighbours.
# `references` and `sources` are never used: they measure research effort.

def site_class(kind, classes):
    """Class 0-3 of a normalised site type: the highest class with a keyword
    in the type, else classes["default"]."""
    for c in sorted((int(k) for k in classes if k != "default"), reverse=True):
        if any(w in kind for w in classes[str(c)]):
            return c
    return int(classes.get("default", 1))


def _unit(lonlat):
    lon, lat = np.radians(np.asarray(lonlat, dtype=float)).T
    return np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=1)


def _within(a, b, km, chunk=1024):
    """For each point of a, the indices of points of b within km
    (great-circle), as a list of arrays. a, b: (n, 2) lon/lat."""
    ua, ub = _unit(a), _unit(b)
    cos_max = math.cos(km / 6371.0)
    out = []
    for i in range(0, len(ua), chunk):
        near = ua[i:i + chunk] @ ub.T >= cos_max
        out += [np.flatnonzero(r) for r in near]
    return out


def local_rank(lonlat, n_dates, km):
    """Per site, the share of the *other* sites within km that have fewer
    dates; 1.0 for a site with no neighbours."""
    n = np.asarray(n_dates)
    out = np.ones(len(n))
    for i, idx in enumerate(_within(lonlat, lonlat, km)):
        others = idx[idx != i]
        if len(others):
            out[i] = float(np.mean(n[others] < n[i]))
    return out


def score_sites(feats, cfg):
    """Set properties.importance (0-3) and properties.evidence (0-2).

    importance = the site-type class, plus one for persistence (total
    occupied years over `min_span`, i.e. more than one date's worth, and a
    `local_rank` of `persist_top` or more within `local_km`), plus one for standing out locally (at
    least `local_min_dates` dates and a `local_rank` of `local_top` or more
    within `local_km`), clamped to 0-3. Both bonuses compare a site with its
    own region, since span and date counts grow with research effort: a
    heavily dug region doesn't get bigger pieces just for being dug.
    evidence: 0 for one date or none (unless the site is known from
    Wikidata or a hand entry), 1 for 2-4, 2 for 5 or more.
    """
    if not feats:
        return feats
    P = [f["properties"] for f in feats]
    xy = [f["geometry"]["coordinates"] for f in feats]
    span = np.array([sum(b - a for a, b in p.get("occupation", [])) for p in P], dtype=float)
    span_rank = local_rank(xy, span, cfg["local_km"])
    n = np.array([p.get("n_dates", 0) for p in P])
    rank = local_rank(xy, n, cfg["local_km"])
    for i, p in enumerate(P):
        persistent = span[i] > cfg["min_span"] and span_rank[i] >= cfg["persist_top"]
        stands_out = n[i] >= cfg["local_min_dates"] and rank[i] >= cfg["local_top"]
        score = site_class(p.get("type") or "site", cfg["class"]) + persistent + stands_out
        p["importance"] = int(min(3, max(0, score)))
        known = bool({"wikidata", "curated"} & set(p.get("sources", [])))
        p["evidence"] = 2 if n[i] >= 5 else 1 if n[i] >= 2 or known else 0
    return feats


# ---------------------------------------------------------------- survey
def survey_intensity(grid, dates, cfg):
    """Research effort per hex: every dated record of any period and site
    type (graves, medieval kilns and all), Gaussian-smoothed over
    `sigma_km` and given as records per 10,000 km². Dense dating of any age
    marks a region where people dig, so few early sites there mean
    something; few records of any age mean an absence says little.

    This is a detection model only. It must never feed expected density.
    Returns (density array per hex, level array 0/1/2 per hex).
    """
    left, top, right, bottom = grid.bbox.T
    centres = np.stack([(left + right) / 2, (top + bottom) / 2], axis=1)
    pts = np.array([[d["lon"], d["lat"]] for d in dates]) if dates else np.zeros((0, 2))
    # Records per hex (nearest centre is close enough for a 100 km kernel).
    counts = np.zeros(len(centres))
    if len(pts):
        uc, up = _unit(centres), _unit(pts)
        for i in range(0, len(up), 4096):
            counts += np.bincount(np.argmax(up[i:i + 4096] @ uc.T, axis=1), minlength=len(centres))
    sigma = cfg["sigma_km"]
    uc = _unit(centres)
    dens = np.zeros(len(centres))
    has = np.flatnonzero(counts)
    for i in range(0, len(uc), 1024):
        d = np.arccos(np.clip(uc[i:i + 1024] @ uc[has].T, -1, 1)) * 6371.0
        dens[i:i + 1024] = (np.exp(-0.5 * (d / sigma) ** 2) * counts[has]).sum(axis=1)
    dens *= 1e4 / (2 * math.pi * sigma ** 2)
    level = np.where(dens >= cfg["well"], 2, np.where(dens >= cfg["thin"], 1, 0))
    return dens, level


def write_survey(path, grid, dens, level):
    with gzip.open(path, "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(["hex", "records_per_10k_km2", "level"])
        for hid, d, l in zip(grid.ids, dens, level):
            w.writerow([int(hid), round(float(d), 2), int(l)])


def read_survey(path):
    """{hex id: level} from write_survey's file."""
    with gzip.open(path, "rt", newline="") as f:
        return {int(r["hex"]): int(r["level"]) for r in csv.DictReader(f)}


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
    locate, same = load_records(sc.get("records"))
    dates, seen = [], set()
    for p in dumps:
        dates += parse_xronos(p["path"], seen, aliases, locate)
    log(f"xronos: {len(dates)} usable dates from {len(dumps)} queries")

    labs = {lab_key(d["labnr"]) for d in dates}
    for spec in sc.get("tables", []):
        # `path`: a table tracked in the repository, read in place.
        p = fetch(spec["url"], spec.get("path") or os.path.join(raw, spec["file"]), spec["name"])
        prov.append(p)
        rows = parse_table(p["path"], spec, labs, aliases)
        for d in rows:  # `keep_types`: its site types (burials) pass exclude_types
            d["keep_type"] = bool(spec.get("keep_types"))
        log(f"{spec['name']}: {len(rows)} usable dates not already in hand")
        dates += rows

    log(f"records: {apply_rejects(dates, load_rejects(sc.get('records')))} dates rejected")
    log(f"records: {apply_refiles(dates, load_refiles(sc.get('records')))} dates moved to their own site")
    p3k = next((t for t in sc.get("tables", []) if t["name"] == "p3k14c"), None)
    if p3k and sc.get("p3k14c_km"):
        n, hit = drop_shifted(dates, p3k.get("path") or os.path.join(raw, p3k["file"]), p3k, sc["p3k14c_km"])
        log(f"p3k14c: {n} XRONOS dates at {hit} sites dropped, filed by a shifted Vermeersch2019 name")
    log(f"records: {apply_same(dates, same)} dates refiled under {len(set(v[0] for v in same.values()))} sites "
        f"({sc.get('records')})")
    fixed, lost = repair_lost(dates, sc["same_name_km"])
    log(f"names: {fixed} with lost letters matched to a clean spelling nearby, {lost} left as they are")

    left, top, right, bottom = grid.bbox.T
    bounds = (float(left.min()), float(bottom.min()), float(right.max()), float(top.max()))
    if sc.get("survey"):
        everything = [d for d in dates if d["std"] <= sc["max_std"]
                      and bounds[0] <= d["lon"] <= bounds[2] and bounds[1] <= d["lat"] <= bounds[3]]
        dens, level = survey_intensity(grid, everything, sc["survey"])
        os.makedirs(out_dir, exist_ok=True)
        write_survey(sc["survey"]["out"], grid, dens, level)
        log(f"survey: {len(everything)} records of any period; hexes by level "
            f"{np.bincount(level, minlength=3).tolist()} -> {sc['survey']['out']}")
    skip = xc.get("exclude_types", [])
    keeps = load_keeps(sc.get("records"))
    hit = {(d.get("filed", d["site"]), lab_key(d["labnr"])) for d in dates if kept(d, keeps)}
    if keeps - hit:
        raise ValueError(f"records.toml [[keep]] matches no date: {sorted(keeps - hit)}")
    dates = [d for d in dates
             if (d["std"] <= sc["max_std"] or kept(d, keeps)) and (d.get("keep_type") or not any(x in d["type"] for x in skip))
             and bounds[0] <= d["lon"] <= bounds[2] and bounds[1] <= d["lat"] <= bounds[3]]

    cal = calibrate([d["bp"] for d in dates], [d["std"] for d in dates], curve)
    years = np.array([to_year(c) if not np.isnan(c) else np.nan for c in cal])
    dated = {}
    feats = derive_sites(dates, years, window, sc["trim"], sc["same_km"], sc["same_name_km"], dated=dated,
                         gap=sc.get("abandon_after", 0), share_km=sc.get("share_km", 0.0))
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
    if sc.get("importance"):
        score_sites(feats, sc["importance"])
        log("importance tiers: " + str(np.bincount([f["properties"]["importance"] for f in feats], minlength=4).tolist())
            + ", evidence levels: " + str(np.bincount([f["properties"]["evidence"] for f in feats], minlength=3).tolist()))

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
