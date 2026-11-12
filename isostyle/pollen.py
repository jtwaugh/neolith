"""Off-site pollen cores (Neotoma, which includes the European Pollen Database).

`python -m isostyle pollen` lists every pollen dataset inside the grid's box
and reduces each to one row per counted level: age (cal BP, the dataset's
default chronology), whether cereal-type pollen was counted there, and whether
dung-fungus spores were (only for datasets that count non-pollen
palynomorphs). The rows go to build/isostyle/pollen/levels.csv.gz; raw
downloads are not kept. The run resumes where it stopped.

The build turns levels into core units: one per core and slice that has at
least one counted level. Cereal pollen is present if any level in the slice
has it and absent if none does; the same for dung spores.
"""
import concurrent.futures as cf
import json
import os
import re
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

API = "https://api.neotomadb.org/v2.0/data"
UA = {"User-Agent": "isostyle-pipeline/0.1 (research script)"}
# Cereal-type pollen. "Hordeum-type" and "Avena-type" also hold some wild
# grasses, and SW Asia has wild cereals, so cereal pollen there before
# farming is not a farming signal (see the layer note).
CEREAL = re.compile(r"^(cerealia|cereal|triticum|hordeum|avena|secale)\b|\bcerealia\b", re.I)
DUNG = re.compile(r"sporormiella|sordaria|cercophora|podospora|hdv-?(55|112|113|368)\b", re.I)


def _get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                return json.loads(r.read())
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))


def list_datasets(box):
    poly = {"type": "Polygon", "coordinates": [[[box[0], box[1]], [box[2], box[1]], [box[2], box[3]],
                                                [box[0], box[3]], [box[0], box[1]]]]}
    out, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"datasettype": "pollen", "loc": json.dumps(poly), "limit": 500, "offset": offset})
        page = _get(f"{API}/datasets?{q}")["data"]
        if not page:
            return out
        for row in page:
            site = row["site"]
            for ds in site.get("datasets") or []:
                if ds.get("datasettype") == "pollen":
                    out.append({"datasetid": ds["datasetid"], "siteid": site["siteid"], "sitename": site["sitename"],
                                "database": ds.get("database"), "geography": site.get("geography")})
        offset += 500


def _point(geo):
    g = json.loads(geo) if isinstance(geo, str) else geo
    c = np.asarray(g["coordinates"], float).reshape(-1, 2)
    return float(c[:, 0].mean()), float(c[:, 1].mean())


def summarise(record):
    """One dataset's download -> list of level rows."""
    site = record["site"]
    lon, lat = _point(site["geography"])
    cu = site["collectionunit"]
    ds = cu["dataset"]
    default = cu.get("defaultchronology")
    samples = ds.get("samples") or []
    npp = any(DUNG.search(str(v.get("variablename", ""))) or str(v.get("taxongroup", "")).lower() == "fungi"
              for s in samples for v in s.get("datum") or [])
    rows = []
    for s in samples:
        ages = s.get("ages") or []
        a = next((x for x in ages if x.get("chronologyid") == default), ages[0] if ages else None)
        if not a or a.get("age") is None:
            continue
        unit = str(a.get("agetype") or a.get("units") or "")
        if "Radiocarbon years BP" in unit and "Calibrated" not in unit:
            continue                                    # uncalibrated ages are not comparable
        counted = cer = dung = 0.0
        for v in s.get("datum") or []:
            try:
                val = float(v.get("value") or 0)
            except (TypeError, ValueError):
                continue
            name = str(v.get("variablename", ""))
            if str(v.get("taxongroup", "")).lower().startswith("vascular") and str(v.get("units", "")).upper() == "NISP":
                counted += val
            if val > 0 and CEREAL.search(name):
                cer += val
            if val > 0 and DUNG.search(name):
                dung += val
        if counted <= 0:
            continue
        rows.append({"datasetid": ds["datasetid"], "site": site["sitename"], "lon": lon, "lat": lat,
                     "age_bp": float(a["age"]), "pollen_sum": counted, "cereal": cer,
                     "dung": dung if npp else np.nan, "database": ds.get("database")})
    return rows


def fetch(cfg, log=print, workers=3):
    out = os.path.join(cfg["output"]["build_dir"], "pollen")
    os.makedirs(out, exist_ok=True)
    reg = cfg["region"]
    lpath = os.path.join(out, "datasets.json")
    if os.path.exists(lpath):
        dsets = json.load(open(lpath))
    else:
        dsets = list_datasets((reg["lon_min"], reg["lat_min"], reg["lon_max"], reg["lat_max"]))
        json.dump(dsets, open(lpath, "w"))
    log(f"pollen: {len(dsets)} pollen datasets in the box")
    jpath = os.path.join(out, "levels.jsonl")
    done = set()
    if os.path.exists(jpath):
        for line in open(jpath):
            done.add(json.loads(line)["datasetid"])
    todo = [d["datasetid"] for d in dsets if d["datasetid"] not in done]
    log(f"pollen: {len(done)} done, {len(todo)} to fetch")

    def one(did):
        try:
            data = _get(f"{API}/downloads/{did}")["data"]
            rec = data[0] if isinstance(data, list) else data
            return did, summarise(rec), None
        except Exception as e:
            return did, [], repr(e)[:200]

    with open(jpath, "a") as f, cf.ThreadPoolExecutor(workers) as ex:
        for k, (did, rows, err) in enumerate(ex.map(one, todo), 1):
            f.write(json.dumps({"datasetid": did, "rows": rows, "error": err}) + "\n")
            f.flush()
            if k % 100 == 0:
                log(f"pollen: {k}/{len(todo)} fetched")
    rows = [r for line in open(jpath) for r in json.loads(line)["rows"]]
    errs = sum(1 for line in open(jpath) if json.loads(line)["error"])
    pd.DataFrame(rows).to_csv(os.path.join(out, "levels.csv.gz"), index=False)
    log(f"pollen: {len(rows)} counted levels; {errs} datasets failed (rerun to retry)")


def retry_failed(cfg):
    """Drop failed datasets from levels.jsonl so the next fetch retries them."""
    jpath = os.path.join(cfg["output"]["build_dir"], "pollen", "levels.jsonl")
    keep = [line for line in open(jpath) if not json.loads(line)["error"]]
    open(jpath, "w").writelines(keep)


def units(cfg, grid, years, edges, registry, counts, log=print):
    """Core units: one per dataset and slice with a counted level."""
    from . import grid as gridmod
    path = os.path.join(cfg["output"]["build_dir"], "pollen", "levels.csv.gz")
    if not os.path.exists(path):
        log("pollen: no levels yet (run `python -m isostyle pollen`); core layers skipped")
        return None
    lv = pd.read_csv(path)
    lv["year"] = 1950 - lv["age_bp"]
    j = np.full(len(lv), -1)
    for k, (a, b) in enumerate(edges):
        j[(lv["year"] >= a) & (lv["year"] < b)] = k
    lv = lv[j >= 0].assign(slice=j[j >= 0])
    g = lv.groupby(["datasetid", "slice"]).agg(site=("site", "first"), lon=("lon", "first"), lat=("lat", "first"),
                                               levels=("age_bp", "size"), cereal=("cereal", "max"),
                                               dung=("dung", "max"), database=("database", "first")).reset_index()
    g["cell_ix"] = gridmod.locate(grid, g["lon"].values, g["lat"].values)
    g = g[g["cell_ix"] >= 0].reset_index(drop=True)
    W = np.zeros((len(g), len(years)))
    W[np.arange(len(g)), g["slice"].values] = 1.0
    u = g.assign(source="Neotoma: " + g["database"].fillna("").astype(str), dating="core", grave=False,
                 n_dates=0, site_id=-g["datasetid"])
    for L in registry.by_unit("core"):
        col = {"cereal_pollen": "cereal", "dung_spores": "dung"}.get(L["id"])
        if col is None:
            raise ValueError(f"pollen: no rule for core layer {L['id']!r}")
        v = u[col]
        u[f"y_{L['id']}"] = np.where(v.isna(), np.nan, (v > 0).astype(float))
        u[f"basis_{L['id']}"] = np.where(v.isna(), "", "recorded")
    counts["core_units"] = int(len(u))
    counts["cores"] = int(u["datasetid"].nunique())
    for L in registry.by_unit("core"):
        y = u[f"y_{L['id']}"]
        counts[L["id"]] = {"present_recorded": int((y == 1).sum()), "absent_recorded": int((y == 0).sum()),
                           "cores": int(u.loc[y.notna(), "datasetid"].nunique())}
        log(f"{L['id']}: {counts[L['id']]}")
    u.drop(columns=["cell_ix"]).assign(**{f"w_{y}": W[:, k] for k, y in enumerate(years)}).to_csv(
        os.path.join(cfg["output"]["build_dir"], "core_units.csv.gz"), index=False)
    return u, W
