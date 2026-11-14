"""Natural-history anchor records for checking the biome maps.

`python -m pipeline anchors` picks long, continuous pollen records, gives
each a biome per time slice, and lists the parts of the map with no record.

1. Candidates: EMBSeCBIO fossil entities (Harrison, Marinova & Cruz-Silva
   2021; the eastern Mediterranean, Black Sea and Caspian corridor, with
   IntCal20 age models), and Neotoma/EPD pollen datasets elsewhere, from the
   level list `python -m isostyle pollen` caches. A Neotoma record within
   `dedupe_degrees` of an EMBSeCBIO one is the same core and is dropped.
2. Quality: share of [time] start..end the levels span, longest gap
   between levels, number of levels, and (EMBSeCBIO only) basin size as a
   stand-in for how much of the region the core sees.
3. Thinning: the best `per_cell` records in each `cell_degrees` cell, so
   the well-studied parts of Europe don't swamp the rest.
4. Labels, published first: the BIOME 6000 classified plotfile (Harrison
   2017) where a site lies within `biome6000_match_degrees` of an anchor.
   It covers only 6 ka BP, so every other slice falls back to biomising the
   anchor's own pollen with Cruz-Silva et al. (2022): each biome is the
   mean and SD of every taxon's percentage over modern samples in that
   biome; a sample's dissimilarity to a biome is
   sqrt(sum_taxa (p - mean)^2 / (sd + eps)^2), its score exp(-d / 100), and
   it takes the best-scoring biome. A score under that biome's ROC
   threshold flags a no-analogue assemblage. EMBSeCBIO anchors use the
   paper's own harmonised percentages; Neotoma anchors are re-fetched with
   full taxa and harmonised to the training taxa here (`harmonise`).
5. Gaps: `cell_degrees` cells with at least `min_land_hexes` land hexes
   and no time-series anchor. The best BIOME 6000 site in a gap cell is
   added as a 6 ka-only anchor. The rest is the research list.

Every anchor has a stable hold-out flag (crc32 of its id mod `holdout`),
so a scorer can tune on some anchors and test on the others.

Outputs (in `out_dir`): anchors.csv, anchor_biomes.csv, anchors_report.md.
"""
import csv
import gzip
import io
import json
import math
import os
import re
import time
import urllib.request
import zipfile
import zlib
from collections import Counter, defaultdict

import numpy as np

UA = {"User-Agent": "neolith-pipeline/0.1 (research script)"}
NEOTOMA = "https://api.neotomadb.org/v2.0/data/downloads/"
# Cruz-Silva et al. 2022's biome codes, in their column order.
BIOMES = ("TUND", "DESE", "GRAM", "XSHB", "ENWD", "WTSFS", "CENF", "CMIX", "TEDE")
EMB_BOX = (20.0, 28.0, 62.0, 49.0)  # lon0, lat0, lon1, lat1 of the EMBSeCBIO database


def year_of(bp):
    """Signed year (negative = BCE) of an age in years BP."""
    return 1950.0 - bp


# --------------------------------------------------------------- downloads

def _download(url, path):
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        data = r.read()
    with open(path + ".part", "wb") as f:
        f.write(data)
    os.replace(path + ".part", path)
    return path


def _get_json(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                return json.loads(r.read())
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))


def fetch_neotoma(ids, cache, log=print, workers=3):
    """Download each Neotoma dataset once into cache/<id>.json; return the ids that failed."""
    import concurrent.futures as cf
    os.makedirs(cache, exist_ok=True)
    todo = [d for d in ids if not os.path.exists(os.path.join(cache, f"{d}.json"))]

    def one(d):
        try:
            data = _get_json(NEOTOMA + d)["data"]
        except Exception as e:
            return d, repr(e)[:120]
        p = os.path.join(cache, f"{d}.json")
        with open(p + ".part", "w") as f:
            json.dump(data[0] if isinstance(data, list) else data, f)
        os.replace(p + ".part", p)
        return d, None

    failed = set()
    with cf.ThreadPoolExecutor(workers) as ex:
        for k, (d, err) in enumerate(ex.map(one, todo), 1):
            if err:
                failed.add(d)
            if k % 25 == 0 or k == len(todo):
                log(f"anchors: Neotoma {k}/{len(todo)} fetched")
    return failed


def fetch_inputs(acfg):
    """Download the published inputs once into the cache; return their paths."""
    c = acfg["cache"]
    base = acfg["cruzsilva_url"].rstrip("/") + "/"
    p = {"biome6000": _download(acfg["biome6000_url"], os.path.join(c, "biome6000.csv")),
         "embsecbio": _download(acfg["embsecbio_url"], os.path.join(c, "embsecbio.zip"))}
    for key, rel in (("train", "Outputs/Train_dataset/Train_dataset.csv"),
                     ("cutpoints", "Outputs/Cutpoints/Cutpoints_optimal_umbrales.csv"),
                     ("downcore", "Inputs/Modern_and_fossil_pollen_percentages/SampleData_DOWNCORE.csv"),
                     ("modern", "Inputs/Modern_and_fossil_pollen_percentages/Modern_pollen_perc_emb_smpds.csv")):
        p[key] = _download(base + rel, os.path.join(c, "cruzsilva", os.path.basename(rel)))
    return p


# ------------------------------------------------------------ biomisation

def load_training(train_path, cutpoints_path):
    """({taxon: (mean (9,), sd (9,))}, {biome: threshold}) in BIOMES order."""
    taxa = {}
    with open(train_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            taxa[r["taxon_name"]] = (np.array([float(r[f"Mean_{b}"]) for b in BIOMES]),
                                     np.array([float(r[f"Stdev_{b}"]) for b in BIOMES]))
    thr = {}
    with open(cutpoints_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            thr[r["biome"]] = max(thr.get(r["biome"], 0.0), float(r["threshold"]))
    return taxa, thr


def biomise(percents, training, thresholds, eps=0.5):
    """One sample {taxon: percent} -> (biome, score, analog), as Cruz-Silva
    et al. 2022: only taxa in both the sample and the training set count."""
    d2 = np.zeros(len(BIOMES))
    used = 0
    for taxon, p in percents.items():
        if taxon in training and p > 0:
            mean, sd = training[taxon]
            d2 += (p - mean) ** 2 / (sd + eps) ** 2
            used += 1
    if not used:
        return None
    scores = np.exp(-np.sqrt(d2) / 100.0)
    k = int(scores.argmax())
    b = BIOMES[k]
    return b, float(scores[k]), bool(scores[k] >= thresholds.get(b, 0.0))


def training_sites(modern_path):
    """(n, 2) lon/lat of the modern samples the biomes were trained on."""
    pts = set()
    with open(modern_path, encoding="latin-1") as f:
        for r in csv.DictReader(f):
            try:
                pts.add((round(float(r["longitude"]), 2), round(float(r["latitude"]), 2)))
            except (KeyError, ValueError):
                continue
    return np.array(sorted(pts), dtype=float)


def nearest_km(lon, lat, pts):
    """Great-circle distance (km) from a point to the nearest of pts (n, 2)."""
    p = np.radians(pts)
    lo, la = math.radians(lon), math.radians(lat)
    h = (np.sin((p[:, 1] - la) / 2) ** 2 + math.cos(la) * np.cos(p[:, 1]) * np.sin((p[:, 0] - lo) / 2) ** 2)
    return float(6371.0 * 2 * np.arcsin(np.sqrt(np.clip(h, 0, 1))).min())


def local_share(percents, local_taxa):
    """Percent of a sample in taxa that mostly grow on the core site itself."""
    return sum(percents.get(t, 0.0) for t in local_taxa)


def load_literature(path):
    """Hand-entered anchors from the literature (anchors_literature.csv):
    one row per anchor and slice, with id, name, lon, lat, year,
    game_classes (";"-separated), description and reference."""
    if not os.path.exists(path):
        return {}, []
    with open(path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("id") and not r["id"].startswith("#")]
    anchors = {}
    for r in rows:
        anchors.setdefault(r["id"], {"id": r["id"], "name": r["name"], "database": "literature", "record": r["id"],
                                     "lon": float(r["lon"]), "lat": float(r["lat"]), "basin": "",
                                     "reference": r["reference"], "coverage": "", "max_gap": "", "levels": "",
                                     "score": ""})
    return anchors, rows


def slice_labels(samples, slices, half):
    """samples: [(year, biome, score, analog)] -> {slice: dict} with the
    commonest biome among samples within `half` years of the slice (ties go
    to the higher mean score), its share, mean score and analogue share."""
    out = {}
    for s in slices:
        win = [x for x in samples if abs(x[0] - s) <= half]
        if not win:
            continue
        n = Counter(x[1] for x in win)
        top = max(n, key=lambda b: (n[b], np.mean([x[2] for x in win if x[1] == b])))
        mine = [x for x in win if x[1] == top]
        out[s] = {"pollen_biome": top, "samples": len(win), "share": n[top] / len(win),
                  "score": float(np.mean([x[2] for x in mine])),
                  "analog": float(np.mean([x[3] for x in mine]))}
    return out


# ------------------------------------------------ Neotoma taxon harmonising

_ALIAS = {
    "gramineae": "Poaceae", "compositae": "Asteraceae", "umbelliferae": "Apiaceae",
    "cruciferae": "Brassicaceae", "leguminosae": "Fabaceae", "papilionaceae": "Fabaceae",
    "labiatae": "Lamiaceae", "guttiferae": "Clusiaceae",
    "chenopodiaceae": "Amaranthaceae", "chenopodiaceae/amaranthaceae": "Amaranthaceae",
    "amaranthaceae/chenopodiaceae": "Amaranthaceae", "chenopodiaceae-amaranthaceae": "Amaranthaceae",
    "tubuliflorae": "Asteroideae", "asteraceae subf. asteroideae": "Asteroideae",
    "liguliflorae": "Cichorioideae", "cichoriaceae": "Cichorioideae",
    "asteraceae subf. cichorioideae": "Cichorioideae", "lactuceae": "Cichorioideae",
    "betula nana": "Betula (Chamaebetula)", "alnus viridis": "Alnus alnobetula",
    "carpinus": "Carpinus betulus", "ostrya": "Carpinus orientalis/Ostrya",
    "carpinus orientalis": "Carpinus orientalis/Ostrya", "ostrya/carpinus orientalis": "Carpinus orientalis/Ostrya",
    "rumex": "Oxyria/Rumex", "oxyria": "Oxyria/Rumex", "rumex/oxyria": "Oxyria/Rumex",
    "zelkova": "Ulmus/Zelkova", "ulmus/zelkova": "Ulmus/Zelkova",
}
_Q_EVERGREEN = re.compile(r"\b(ilex|coccifera|suber|calliprinos|evergreen|rotundifolia)\b")
_P_HAPLO = re.compile(r"haploxylon|cembra|peuce|strobus")
_STRIP = re.compile(r"\b(cf\.|aff\.|undiff\.?|t\.|type|sp\.|spp\.)|-type|-t\b|\?|\(.*?\)")


def harmonise(name, train_lower):
    """A Neotoma variable name -> a training taxon, or None.
    `train_lower` maps lower-case training names to themselves. Unqualified
    Quercus counts as deciduous, and unqualified Pinus as diploxylon (the
    training set's plain "Pinus" is the EMBSeCBIO region's, near absent from
    its boreal and mixed forests): both right north of the Mediterranean,
    where the Neotoma anchors are (the EMBSeCBIO ones come pre-harmonised)."""
    n = name.strip().lower()
    if n.startswith("quercus"):
        return "Quercus evergreen" if _Q_EVERGREEN.search(n) else "Quercus deciduous"
    if n.startswith("pinus"):
        if _P_HAPLO.search(n):
            return "Pinus (haploxylon)"
        return "Pinus (diploxylon)"
    for cand in (n, _STRIP.sub(" ", n)):
        cand = re.sub(r"\s+", " ", cand).strip(" -")
        if cand in _ALIAS:
            return _ALIAS[cand]
        if cand in train_lower:
            return train_lower[cand]
    first = re.split(r"[\s/\-]", _STRIP.sub(" ", n).strip())[0]
    if first in _ALIAS:
        return _ALIAS[first]
    return train_lower.get(first)


def _point(geo):
    g = json.loads(geo) if isinstance(geo, str) else geo
    c = np.asarray(g["coordinates"], float).reshape(-1, 2)
    return float(c[:, 0].mean()), float(c[:, 1].mean())


def neotoma_samples(record, training, min_mapped):
    """A Neotoma download -> ([(year, {taxon: percent})], doi). Percentages
    are of the harmonised pollen and spores, as in the training set; levels
    with under `min_mapped` of their pollen and spores harmonised are dropped."""
    train_lower = {t.lower(): t for t in training}
    cu = record["site"]["collectionunit"]
    ds = cu["dataset"]
    default = cu.get("defaultchronology")
    out = []
    for s in ds.get("samples") or []:
        ages = s.get("ages") or []
        a = next((x for x in ages if x.get("chronologyid") == default), ages[0] if ages else None)
        if not a or a.get("age") is None:
            continue
        if "Radiocarbon years BP" in str(a.get("agetype") or "") and "Calibrated" not in str(a.get("agetype")):
            continue
        mapped, total = defaultdict(float), 0.0
        for v in s.get("datum") or []:
            if str(v.get("element", "")).lower() not in ("pollen", "spore") or str(v.get("units", "")).upper() != "NISP":
                continue
            try:
                val = float(v.get("value") or 0)
            except (TypeError, ValueError):
                continue
            if val <= 0:
                continue
            total += val
            t = harmonise(str(v.get("variablename", "")), train_lower)
            if t:
                mapped[t] += val
        m = sum(mapped.values())
        if total <= 0 or m / total < min_mapped:
            continue
        out.append((year_of(float(a["age"])), {t: 100.0 * v / m for t, v in mapped.items()}))
    doi = ds.get("doi") or []
    return out, (f"https://doi.org/{doi[0]}" if doi else NEOTOMA + str(ds["datasetid"]))


# ------------------------------------------------------------- candidates

def quality(years, start, end):
    """(coverage share, longest gap in years, levels inside) of level years
    over start..end."""
    y = np.sort(np.asarray([v for v in years if start <= v <= end], float))
    if not len(y):
        return 0.0, float(end - start), 0
    cov = (y.max() - y.min()) / (end - start)
    gap = float(np.diff(np.concatenate([[start], y, [end]])).max())
    return float(cov), gap, len(y)


def rank_score(cov, gap, n, basin, acfg):
    w = acfg["basin_weight"].get(basin or "", acfg["basin_weight"]["unknown"])
    return cov * min(1.0, n / acfg["full_levels"]) * min(1.0, acfg["good_gap"] / max(gap, 1.0)) * w


def embsecbio_candidates(paths, overrides=()):
    """{id: candidate} for EMBSeCBIO fossil entities in Cruz-Silva's
    downcore file, with their samples as (year, {taxon: percent}).
    `overrides` ([[anchors.override]]: id, lon, lat, source) replace a
    position the database has wrong; the database's own is kept as `filed_at`."""
    z = zipfile.ZipFile(paths["embsecbio"])

    def table(name):
        return list(csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8")))

    entity = {r["ID_ENTITY"]: r for r in table("entity.csv")}
    site = {r["ID_SITE"]: r for r in table("site.csv")}
    s2e = {r["ID_SAMPLE"]: r["ID_ENTITY"] for r in table("sample.csv")}
    pubs = {r["ID_PUB"]: r["citation"] for r in table("pub.csv")}
    e2pub = {}
    for r in table("entity_pub.csv"):
        e2pub.setdefault(r["ID_ENTITY"], pubs.get(r["ID_PUB"], ""))
    samples = defaultdict(dict)                       # entity -> sample -> (year, {taxon: %})
    with open(paths["downcore"], encoding="latin-1") as f:
        for r in csv.DictReader(f):
            e = s2e.get(r["ID_SAMPLE"])
            if r["age"] == "NA" or e is None:
                continue
            yr, taxa = samples[e].setdefault(r["ID_SAMPLE"], (year_of(float(r["age"])), {}))
            taxa[r["taxon_name"]] = taxa.get(r["taxon_name"], 0.0) + float(r["taxon_percent"])
    out = {}
    for e, smp in samples.items():
        en = entity[e]
        st = site.get(en["ID_SITE"], {})
        out[f"emb:{e}"] = {"id": f"emb:{e}", "name": en["entity_name"], "database": "EMBSeCBIO",
                           "record": e, "lon": float(en["longitude"]), "lat": float(en["latitude"]),
                           "basin": st.get("ID_BASIN_SIZE", ""),
                           "reference": e2pub.get(e) or "https://doi.org/10.17864/1947.309",
                           "years": [y for y, _ in smp.values()], "samples": list(smp.values())}
    for o in overrides:
        c = out.get(o["id"])
        if c is None:
            raise SystemExit(f"anchors: [[anchors.override]] {o['id']} matches no EMBSeCBIO entity")
        c["filed_at"] = (c["lon"], c["lat"])
        c["lon"], c["lat"] = float(o["lon"]), float(o["lat"])
    return out


def neotoma_candidates(levels_path):
    """{id: candidate} from the isostyle level list (ages only; taxa are
    fetched later, for the chosen ones)."""
    rows = defaultdict(list)
    meta = {}
    with gzip.open(levels_path, "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["datasetid"]].append(year_of(float(r["age_bp"])))
            meta[r["datasetid"]] = r
    return {f"neotoma:{d}": {"id": f"neotoma:{d}", "name": meta[d]["site"], "database": meta[d]["database"] or "Neotoma",
                             "record": d, "lon": float(meta[d]["lon"]), "lat": float(meta[d]["lat"]),
                             "basin": "", "reference": "", "years": ys}
            for d, ys in rows.items()}


def cell_of(lon, lat, size):
    return (int(math.floor(lon / size)), int(math.floor(lat / size)))


def select(cands, acfg, start, end):
    """Score, filter and thin candidates -> chosen list, best first per cell."""
    near = acfg["dedupe_degrees"]
    emb = [c for c in cands if c["database"] == "EMBSeCBIO"]
    ok = []
    for c in cands:
        if c["database"] != "EMBSeCBIO" and any(abs(c["lon"] - e["lon"]) < near and abs(c["lat"] - e["lat"]) < near
                                                for e in emb):
            continue
        cov, gap, n = quality(c["years"], start, end)
        if cov < acfg["min_coverage"] or gap > acfg["max_gap"] or n < acfg["min_levels"]:
            continue
        c.update(coverage=cov, max_gap=gap, levels=n, score=rank_score(cov, gap, n, c["basin"], acfg),
                 cell=cell_of(c["lon"], c["lat"], acfg["cell_degrees"]))
        ok.append(c)
    ok.sort(key=lambda c: (-c["score"], c["id"]))
    chosen, per = [], Counter()
    for c in ok:
        core = EMB_BOX[0] <= c["lon"] <= EMB_BOX[2] and EMB_BOX[1] <= c["lat"] <= EMB_BOX[3]
        if per[c["cell"]] >= (acfg.get("per_cell_core", acfg["per_cell"]) if core else acfg["per_cell"]):
            continue
        if any((abs(c["lon"] - o["lon"]) < near and abs(c["lat"] - o["lat"]) < near)
               or same_site(c, o, acfg.get("same_site_km", 0.0)) for o in chosen):
            continue                                  # another dataset from the same site
        chosen.append(c)
        per[c["cell"]] += 1
    return chosen, len(ok)


_GENERIC = {"lake", "lac", "lago", "lagoa", "laguna", "core", "section", "mire", "bog", "moss", "peat", "fen",
            "golu", "gol", "see", "sjon", "jarvi", "ozero", "lough", "loch", "the", "de", "la", "le", "di", "du",
            "des", "of", "and", "noaa", "site", "profile", "bottema", "wick"}


def _name_words(name):
    import unicodedata
    n = unicodedata.normalize("NFKD", name.lower()).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z]{3,}", n) if w not in _GENERIC}


def same_site(a, b, km):
    """Two records of one lake or bog: within km and sharing a name word
    ("Van - Wick Core" and "Lake Van")."""
    d = 111.0 * math.hypot((a["lon"] - b["lon"]) * math.cos(math.radians(a["lat"])), a["lat"] - b["lat"])
    return d <= km and bool(_name_words(a["name"]) & _name_words(b["name"]))


def holdout(anchor_id, k):
    return zlib.crc32(anchor_id.encode()) % k == 0


# ---------------------------------------------------------- BIOME 6000

def load_biome6000(path, box):
    """6 ka BP rows in the box: [(name, lon, lat, consolidated name, BIOME4 codes)]."""
    with open(path, encoding="mac_roman", newline="") as f:     # a classic-Mac file: CR line ends
        text = f.read().replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for r in list(csv.reader(io.StringIO(text)))[1:]:
        if len(r) < 10 or r[0].strip() != "6":
            continue
        lat, lon = float(r[2]), float(r[3])
        if box[0] <= lon <= box[2] and box[1] <= lat <= box[3]:
            out.append((r[1].strip(), lon, lat, r[4].strip(), [c for c in r[9].split("+") if c.strip()]))
    return out


def biome4_classes(codes, classes):
    """BIOME4 codes ("4", "16") -> game classes in order, without repeats."""
    out = []
    for c in codes:
        g = classes.get(c.strip())
        if g and g not in out:
            out.append(g)
    return out


# ------------------------------------------------------------------ build

class MapTerrain:
    """The build's combined map: each hex's centre and its terrain over time
    (sparse year keys, each value holding until the next)."""

    def __init__(self, combined_path):
        with open(combined_path) as f:
            feats = json.load(f)["features"]
        self.centre = np.array([((ft["properties"]["left"] + ft["properties"]["right"]) / 2,
                                 (ft["properties"]["top"] + ft["properties"]["bottom"]) / 2) for ft in feats])
        self.terrain = [sorted((int(y), v) for y, v in ft["properties"]["terrain"].items()) for ft in feats]
        self.land = np.array([any(v != "Water" for _, v in t) for t in self.terrain])

    def at(self, i, year):
        v = self.terrain[i][0][1]
        for y, t in self.terrain[i]:
            if y > year:
                break
            v = t
        return v

    def nearest(self, lon, lat, year=None):
        """Index of the hex nearest a point; with `year`, of the nearest hex
        that isn't Water that year."""
        d = (self.centre[:, 0] - lon) ** 2 * math.cos(math.radians(lat)) ** 2 + (self.centre[:, 1] - lat) ** 2
        if year is not None:
            d = np.where(self.water(year), np.inf, d)
        return int(d.argmin())

    def water(self, year):
        if not hasattr(self, "_water"):
            self._water = {}
        if year not in self._water:
            self._water[year] = np.array([self.at(i, year) == "Water" for i in range(len(self.terrain))])
        return self._water[year]

    def land_cells(self, size):
        """{cell: land hex count}; a hex is land if any year it isn't Water."""
        return Counter(cell_of(lon, lat, size) for (lon, lat), l in zip(self.centre, self.land) if l)


def build(cfg, log=print):
    acfg = cfg["anchors"]
    start, end = cfg["time"]["start"], cfg["time"]["end"]
    slices = list(range(start, end + 1, acfg["slice_step"]))
    half = acfg["slice_half_window"]
    paths = fetch_inputs(acfg)
    training, thr = load_training(paths["train"], paths["cutpoints"])
    log(f"anchors: {len(training)} training taxa, thresholds for {len(thr)} biomes")

    emb = embsecbio_candidates(paths, acfg.get("override", []))
    neo = neotoma_candidates(acfg["neotoma_levels"])
    log(f"anchors: {len(emb)} EMBSeCBIO and {len(neo)} Neotoma candidate records")
    chosen, qualified = select(list(emb.values()) + list(neo.values()), acfg, start, end)
    log(f"anchors: {qualified} pass the quality filter, {len(chosen)} kept after thinning")

    # Labels: biomise every chosen record's samples.
    ncache = os.path.join(acfg["cache"], "neotoma")
    failed = fetch_neotoma([c["record"] for c in chosen if c["database"] != "EMBSeCBIO"], ncache, log)
    if failed:
        log(f"anchors: {len(failed)} Neotoma downloads failed and are left out this run: {sorted(failed)}")
        chosen = [c for c in chosen if c["database"] == "EMBSeCBIO" or c["record"] not in failed]
    # Anchors the map can't judge or the method can't read.
    mt = MapTerrain(cfg["output"]["combined"])
    land_centres = mt.centre[mt.land]
    tsites = training_sites(paths["modern"])
    excl = {(e["name"], e["what"]): e["reason"] for e in acfg.get("exclude", [])}
    dropped = []
    keep = []
    for c in chosen:
        if excl.get((c["name"], "all")):
            dropped.append((c["name"], excl[(c["name"], "all")]))
            continue
        d = np.hypot((land_centres[:, 0] - c["lon"]) * math.cos(math.radians(c["lat"])), land_centres[:, 1] - c["lat"])
        if not len(d) or d.min() > acfg["off_grid_degrees"]:
            dropped.append((c["name"], "no land hex nearby: off the grid"))
            continue
        c["out_of_domain"] = nearest_km(c["lon"], c["lat"], tsites) > acfg["domain_km"]
        c["distrust"] = excl.get((c["name"], "biomised"), "")
        keep.append(c)
    chosen = keep
    local_taxa, max_local = acfg.get("local_taxa", []), acfg.get("max_local_share", 100.0)
    labels, local_dropped = {}, 0
    for c in chosen:
        if c["database"] != "EMBSeCBIO":
            with open(os.path.join(ncache, f"{c['record']}.json")) as f:
                c["samples"], c["reference"] = neotoma_samples(json.load(f), training, acfg["min_mapped"])
        out = []
        for yr, pct in c["samples"]:
            if local_share(pct, local_taxa) > max_local:
                local_dropped += 1                      # the core's own mire, not the region
                continue
            r = biomise(pct, training, thr, acfg["epsilon"])
            if r:
                out.append((yr, *r))
        labels[c["id"]] = slice_labels(out, slices, half)

    # Published 6 ka labels.
    box = cfg["paleobiome"]["box"]
    b6 = load_biome6000(paths["biome6000"], box)
    six = min(slices, key=lambda s: abs(s - year_of(6000)))
    pclasses = cfg["paleobiome"]["classes"]
    m = acfg["biome6000_match_degrees"]
    published = {}
    for c in chosen:
        hit = min(b6, key=lambda r: abs(r[1] - c["lon"]) + abs(r[2] - c["lat"]), default=None)
        if hit and abs(hit[1] - c["lon"]) <= m and abs(hit[2] - c["lat"]) <= m:
            published[c["id"]] = hit

    for aid in [a for a, r in published.items() if excl.get((r[0], "published"))]:
        del published[aid]
    for c in chosen:
        if excl.get((c["name"], "published")):
            published.pop(c["id"], None)

    # Hand-entered anchors from the literature.
    lit, lit_rows = load_literature(acfg.get("literature", ""))

    # Gaps, and 6 ka-only anchors from BIOME 6000 to fill what they can.
    land = mt.land_cells(acfg["cell_degrees"])
    covered = {c["cell"] for c in chosen} | {cell_of(a["lon"], a["lat"], acfg["cell_degrees"]) for a in lit.values()}
    gaps = sorted(((cell, n) for cell, n in land.items()
                   if n >= acfg["min_land_hexes"] and cell not in covered),
                  key=lambda x: (-x[1], -x[0][1], x[0][0]))
    six_only = []
    for cell, _ in gaps:
        inside = [r for r in b6 if cell_of(r[1], r[2], acfg["cell_degrees"]) == cell]
        if inside:
            r = sorted(inside)[0]
            aid = f"biome6000:{r[0]}"
            six_only.append({"id": aid, "name": r[0], "database": "BIOME 6000", "record": r[0], "lon": r[1],
                             "lat": r[2], "basin": "", "reference": "https://doi.org/10.17864/1947.99",
                             "coverage": "", "max_gap": "", "levels": "", "score": "", "cell": cell})
            published[aid] = r

    # Write.
    os.makedirs(acfg["out_dir"], exist_ok=True)
    k = acfg["holdout"]
    with open(os.path.join(acfg["out_dir"], "anchors.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "kind", "database", "record", "lon", "lat", "basin", "levels", "coverage",
                    "max_gap", "rank_score", "holdout", "out_of_domain", "distrust_biomised", "reference"])
        for c in chosen + six_only + list(lit.values()):
            kind = "timeseries" if c in chosen else "literature" if c["id"] in lit else "6ka"
            w.writerow([c["id"], c["name"], kind, c["database"], c["record"], f"{c['lon']:.4f}", f"{c['lat']:.4f}",
                        c["basin"], c["levels"], _fmt(c["coverage"], 2), _fmt(c["max_gap"], 0),
                        _fmt(c["score"], 3), int(holdout(c["id"], k)), int(bool(c.get("out_of_domain"))),
                        c.get("distrust", ""), c["reference"]])
    cross, wet, lit_vs_map = [], [], []
    with open(os.path.join(acfg["out_dir"], "anchor_biomes.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "year", "method", "pollen_biome", "game_classes", "samples", "share", "score",
                    "analog", "used", "map_terrain", "on_water", "nearest_land_terrain"])
        for c in chosen + six_only:
            pub = published.get(c["id"])
            mine = labels.get(c["id"], {})
            hexi = mt.nearest(c["lon"], c["lat"])
            for s in slices:
                use_pub = pub is not None and s == six
                here = mt.at(hexi, s)
                # A lake core sits in water by nature; the land around it is
                # what its pollen describes, so that is what a scorer compares.
                land_t = mt.at(mt.nearest(c["lon"], c["lat"], s), s) if here == "Water" else here
                tail = [here, int(here == "Water"), land_t]
                if here == "Water" and (use_pub or s in mine):
                    wet.append((c["id"], c["name"], s))
                if use_pub:
                    w.writerow([c["id"], s, "published", pub[3], ";".join(biome4_classes(pub[4], pclasses)),
                                "", "", "", "", 1, *tail])
                if s in mine:
                    L = mine[s]
                    trusted = not c.get("out_of_domain") and not c.get("distrust")
                    w.writerow([c["id"], s, "biomised", L["pollen_biome"],
                                ";".join(acfg["classes"][L["pollen_biome"]]), L["samples"], f"{L['share']:.2f}",
                                f"{L['score']:.3f}", f"{L['analog']:.2f}", int(trusted and not use_pub), *tail])
                if use_pub and s in mine:
                    cross.append((c["id"], biome4_classes(pub[4], pclasses), acfg["classes"][mine[s]["pollen_biome"]]))
        for r in lit_rows:
            a = lit[r["id"]]
            hexi = mt.nearest(a["lon"], a["lat"])
            y = int(r["year"])
            here = mt.at(hexi, y)
            land_t = mt.at(mt.nearest(a["lon"], a["lat"], y), y) if here == "Water" else here
            w.writerow([a["id"], y, "literature", r["description"], r["game_classes"], "", "", "", "", 1,
                        here, int(here == "Water"), land_t])
            lit_vs_map.append((a["name"], y, r["game_classes"].split(";"), land_t, holdout(a["id"], k)))
    flags = {"dropped": dropped, "local_dropped": local_dropped,
             "out_of_domain": [c["name"] for c in chosen if c.get("out_of_domain")],
             "distrust": [(c["name"], c["distrust"]) for c in chosen if c.get("distrust")],
             "excluded_published": sorted(n for n, w_ in excl if w_ == "published"),
             "literature": len(lit), "lit_vs_map": lit_vs_map,
             "low_analog": sorted({c["name"] for c in chosen
                                   for L in labels.get(c["id"], {}).values() if L["analog"] < 0.5})}
    write_report(os.path.join(acfg["out_dir"], "anchors_report.md"), chosen, six_only, qualified, gaps,
                 cross, labels, slices, k, acfg, wet, flags)
    log(f"anchors: wrote {len(chosen)} time-series and {len(six_only)} 6 ka anchors, "
        f"{len(gaps)} gap cells, to {acfg['out_dir']}")


def _fmt(v, nd):
    return "" if v == "" else f"{v:.{nd}f}"


def write_report(path, chosen, six_only, qualified, gaps, cross, labels, slices, k, acfg, wet=(), flags=None):
    size = acfg["cell_degrees"]
    by_db = Counter(c["database"] for c in chosen)
    L = ["# Biome anchors", "",
         "Generated by `python -m pipeline anchors`; method and sources in `data/terrain/SOURCES.md`.", "",
         f"- {qualified} records pass the quality filter; {len(chosen)} are kept, at most {acfg['per_cell']} "
         f"per {size:g}° cell ({acfg.get('per_cell_core', acfg['per_cell'])} inside the EMBSeCBIO box): "
         + ", ".join(f"{n} {db}" for db, n in by_db.most_common()) + ".",
         f"- {len(six_only)} more are BIOME 6000 sites with a 6 ka label only, one per gap cell that has one.",
         f"- Held out: {sum(holdout(c['id'], k) for c in chosen + six_only)} of {len(chosen) + len(six_only)}.", ""]
    n_lab = sum(len(v) for v in labels.values())
    if n_lab:
        an = [x["analog"] for v in labels.values() for x in v.values()]
        L += [f"Biomised slice labels: {n_lab}; mean share of samples flagged no-analogue: "
              f"{1 - float(np.mean(an)):.0%}.", ""]
    if cross:
        prim = sum(a[0] == b[0] for _, a, b in cross if a and b)
        comp = sum(bool(set(a) & set(b)) for _, a, b in cross)
        L += ["## Published vs biomised at 6 ka", "",
              f"{len(cross)} anchors have both. Same main game class: {prim} ({prim / len(cross):.0%}); "
              f"compatible (the class lists overlap): {comp} ({comp / len(cross):.0%}).", ""]
    if flags:
        L += ["## Left out or distrusted", ""]
        for name, why in flags["dropped"]:
            L.append(f"- Dropped {name}: {why}.")
        for name, why in flags["distrust"]:
            L.append(f"- Biomised labels not used for {name}: {why}.")
        for name in flags["excluded_published"]:
            L.append(f"- Published label not used for {name} (see `[[anchors.exclude]]`).")
        if flags["out_of_domain"]:
            L.append(f"- Biomised labels not used, over {acfg['domain_km']:g} km from every training sample "
                     f"(the method has no biomes for them): " + ", ".join(flags["out_of_domain"]) + ".")
        L.append(f"- Samples left out as mostly the core's own mire ({', '.join(acfg.get('local_taxa', []))} over "
                 f"{acfg.get('max_local_share', 100):g}%): {flags['local_dropped']}.")
        if flags["low_analog"]:
            L.append(f"- Anchors with a slice whose samples are mostly no-analogue (weight these low): "
                     + ", ".join(flags["low_analog"]) + ".")
        if flags["literature"]:
            L.append(f"- Literature anchors (data/terrain/anchors_literature.csv): {flags['literature']}.")
        L.append("")
    lvm = (flags or {}).get("lit_vs_map") or []
    if lvm:
        def agree(rows):
            if not rows:
                return "none"
            first = sum(m == cl[0] for _, _, cl, m, _ in rows)
            comp = sum(m in cl for _, _, cl, m, _ in rows)
            return (f"{len(rows)} slices from {len({r[0] for r in rows})} records: the map's class is the "
                    f"first class in {first} ({first / len(rows):.0%}) and one of the classes in {comp} "
                    f"({comp / len(rows):.0%})")
        held = [r for r in lvm if r[4]]
        L += ["## Literature anchors against the map", "",
              "Records in data/terrain/anchors_literature.csv against the map's class on the nearest land hex. "
              "The ones not held out also train the gap filling ([paleobiome.calibrate] use_literature), so "
              "only the held-out ones are a fair test.", "",
              f"- All: {agree(lvm)}.",
              f"- Held out: {agree(held)}.",
              f"- Used in training: {agree([r for r in lvm if not r[4]])}.", "",
              "Where they disagree, by record and the map's class:", "",
              "| record | held out | map has | record says | slices |", "|---|---|---|---|---|"]
        miss = defaultdict(list)
        for n, y, cl, m, h in lvm:
            if m not in cl:
                miss[(n, h, m, cl[0])].append(y)
        for (n, h, m, want), ys in sorted(miss.items(), key=lambda x: -len(x[1])):
            L.append(f"| {n} | {'yes' if h else ''} | {m} | {want} | {len(ys)}: {min(ys)}…{max(ys)} |")
        by_map = Counter(m for _, _, cl, m, _ in lvm if m not in cl)
        L += ["", "Map classes most often contradicted: "
              + ", ".join(f"{k} {v}" for k, v in by_map.most_common(6)) + ".", ""]
    L += ["## Slices labelled per anchor", "", "| slice | anchors |", "|---|---|"]
    for s in slices:
        L.append(f"| {s} | {sum(s in v for v in labels.values())} |")
    if wet:
        per = defaultdict(list)
        for aid, name, s in wet:
            per[(aid, name)].append(s)
        L += ["## Anchors on Water hexes", "",
              f"{len(per)} anchors sit on a hex the map has as Water in at least one labelled slice. "
              "Lake and marine cores do by nature (`nearest_land_terrain` in anchor_biomes.csv is what "
              "to compare); a land site here means the coast or lake is drawn wrong for that slice.", "",
              "| anchor | slices on Water |", "|---|---|"]
        for (aid, name), ss in sorted(per.items(), key=lambda x: -len(x[1])):
            L.append(f"| {name} (`{aid}`) | {len(ss)}: {min(ss)}…{max(ss)} |")
        L.append("")
    L += ["", "## Gaps", "",
          f"{size:g}° cells with at least {acfg['min_land_hexes']} land hexes and no time-series anchor, "
          "most land first. These are the research list.", "",
          "| cell (lon, lat) | land hexes | 6 ka site |", "|---|---|---|"]
    for cell, n in gaps:
        lo, la = cell[0] * size, cell[1] * size
        six = next((a["name"] for a in six_only if a["cell"] == cell), "")
        L.append(f"| {lo:g}…{lo + size:g}°E, {la:g}…{la + size:g}°N | {n} | {six} |")
    L.append("")
    with open(path, "w") as f:
        f.write("\n".join(L))
