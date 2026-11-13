"""Standalone viewer: one HTML file with the surfaces embedded.

Reads the outputs of `build` (surfaces.csv.gz, contours.geojson,
summary.json, and the unit tables in build/isostyle/) and writes
data/isostyle/viewer.html, which opens in a browser with no server. Each
layer is its own gzipped, base64-encoded blob, unpacked when first shown
(DecompressionStream).

Per layer, slice and cell the page gets seven bytes:
  P  value: share 0-1, or (continuous, grid) the position in vmin..vmax, x200;
     255 = masked or sea
  E  evidence, log scale: E = 10^(q/32)/100 (0 = none)
  B  bootstrap share at or above the middle level, x200 (255 = n/a)
  L  share of evidence from labels, x200 (255 = n/a)
  M  mask: 0 shown, 1 too little evidence, 2 ice, 3 acid soil, 4 sea
  V  speculative value, encoded like P (255 = none)
  C  speculative basis: 0 observed, 1 judged high, 2 medium, 3 low,
     4 extrapolated, 255 none
"""
import base64
import gzip
import json
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from . import grid as gridmod, layers as layermod

MASK = {"": 0, "low evidence": 1, "ice": 2, "acid soil": 3}
TEMPLATE = os.path.join(os.path.dirname(__file__), "viewer_template.html")
UNIT_FILES = {"occupation": "units.csv.gz", "core": "core_units.csv.gz", "sample": "sample_units.csv.gz"}


def _pack(data):
    if isinstance(data, np.ndarray):
        data = data.tobytes()
    elif not isinstance(data, bytes):
        data = json.dumps(data, separators=(",", ":")).encode()
    return base64.b64encode(gzip.compress(data, 9, mtime=0)).decode()


def _layer_bytes(surf, L, n, S, ix, years):
    lay = np.zeros((S, 7, n), dtype=np.uint8)
    lay[:, 0] = 255
    lay[:, 2] = 255
    lay[:, 3] = 255
    lay[:, 4] = 4
    lay[:, 5] = 255
    lay[:, 6] = 255
    s = surf[surf["layer"] == L["id"]]
    if s.empty:
        return lay
    ci = ix.reindex(s["cell"].values).values
    sk = s["slice"].map({y: j for j, y in enumerate(years)}).values
    ok = ~(np.isnan(ci) | np.isnan(sk.astype(float)))
    s, ci, sk = s[ok], ci[ok].astype(int), sk[ok].astype(int)
    lay[sk, 4, ci] = s["mask_reason"].fillna("").map(MASK).fillna(0).astype(int).values
    p = s["presence"].values.astype(float)
    if L["kind"] in ("continuous", "grid"):
        p = (p - L["vmin"]) / (L["vmax"] - L["vmin"])
    lay[sk, 0, ci] = np.where(np.isnan(p), 255, np.round(np.clip(np.nan_to_num(p), 0, 1) * 200)).astype(np.uint8)
    e = s["evidence"].values.astype(float)
    q = np.clip(np.round(32 * np.log10(np.maximum(e, 0.01) * 100)), 1, 254)
    lay[sk, 1, ci] = np.where(e >= 0.01, q, 0).astype(np.uint8)
    bt = s["boot_share_above_50"].values.astype(float)
    lay[sk, 2, ci] = np.where(np.isnan(bt), 255, np.round(np.nan_to_num(bt) * 200)).astype(np.uint8)
    ls = s["label_share"].values.astype(float)
    lay[sk, 3, ci] = np.where(np.isnan(ls) | (e < 0.05), 255, np.round(np.nan_to_num(ls) * 200)).astype(np.uint8)
    return lay


CONF_CODE = {"observed": 0, "high": 1, "medium": 2, "low": 3, "none": 4}


def _spec_bytes(lay, s, L, ix, years):
    if s.empty:
        return
    ci = ix.reindex(s["cell"].values).values
    sk = s["slice"].map({y: j for j, y in enumerate(years)}).values
    ok = ~(np.isnan(ci) | np.isnan(sk.astype(float)))
    s, ci, sk = s[ok], ci[ok].astype(int), sk[ok].astype(int)
    v = s["value"].values.astype(float)
    if L["kind"] in ("continuous", "grid"):
        v = (v - L["vmin"]) / (L["vmax"] - L["vmin"])
    lay[sk, 5, ci] = np.where(np.isnan(v), 255, np.round(np.clip(np.nan_to_num(v), 0, 1) * 200)).astype(np.uint8)
    lay[sk, 6, ci] = s["confidence"].map(CONF_CODE).fillna(255).astype(int).values


def _judgements(out_dir, registry):
    """Per layer, the critics' judgements, trimmed for the inspector."""
    import glob
    import tomllib
    sets = {}
    for L in registry:
        if L["set"]:
            sets.setdefault(L["set"], []).append(L["id"])
    out = {}
    for path in sorted(glob.glob(os.path.join(out_dir, "intuitions", "*.toml"))):
        d = tomllib.load(open(path, "rb"))
        name = d["meta"]["layer"]
        ids = sets.get(name, [name])
        for j in d.get("judgement", []):
            e = j.get("expected")
            rec = {"region": j["region"], "slices": j.get("slices", []), "confidence": j.get("confidence"),
                   "why": j.get("why_empty", []), "note": (j.get("why_note") or "")[:300],
                   "rule": (j.get("speculative_rule") or "")[:300], "reasoning": (j.get("reasoning") or "")[:400]}
            for lid in ids:
                r = dict(rec)
                r["expected"] = e.get(lid) if isinstance(e, dict) else e
                out.setdefault(lid, []).append(r)
    return out


def _units(path, years, layer_ids):
    """Coordinates, slice weights, per-layer status and labels of one unit table."""
    u = pd.read_csv(path, low_memory=False)
    nu = len(u)
    xy = np.empty(2 * nu, dtype="<i4")
    xy[0::2] = np.round(u["lon"].values * 1e4)
    xy[1::2] = np.round(u["lat"].values * 1e4)
    w = np.vstack([np.round(np.clip(u[f"w_{y}"].values, 0, 1) * 255) for y in years]).astype(np.uint8)
    st = np.zeros((len(layer_ids), nu), dtype=np.uint8)
    for k, m in enumerate(layer_ids):
        if f"y_{m}" not in u:
            continue
        y, basis = u[f"y_{m}"].values, u[f"basis_{m}"].fillna("").values
        st[k] = np.select([(y == 1) & (basis == "recorded"), (y == 1) & (basis == "label"),
                           (y == 0) & (basis == "label"), (y == 0) & (basis == "recorded")], [1, 2, 3, 4], 0)
    grave = u["grave"].astype(str).str.lower().eq("true").values if "grave" in u else np.zeros(nu, bool)
    rng = u["dating"].astype(str).eq("range").values if "dating" in u else np.zeros(nu, bool)
    flags = (grave * 1 + rng * 2).astype(np.uint8)
    clean = lambda s: str(s).replace("\t", " ").replace("\n", " ")
    extra = []
    for _, r in u.iterrows():
        bits = [clean(r.get("site", "")), clean(r.get("source", "")), str(int(r["n_dates"]) if pd.notna(r.get("n_dates")) else 0),
                clean(r.get("site_type", "") if pd.notna(r.get("site_type", "")) else ""),
                clean(r.get("y", "") if "y" in u and pd.notna(r.get("y")) else ""),
                clean(r.get("mt", "") if "mt" in u and pd.notna(r.get("mt")) else ""),
                clean(r.get("dating", ""))]
        extra.append("\t".join(bits))
    return {"n": nu, "layers": layer_ids, "xy": _pack(xy), "w": _pack(w), "st": _pack(st), "flags": _pack(flags),
            "names": _pack("\n".join(extra).encode())}


def run(cfg, log=print):
    out, bdir = cfg["output"]["out_dir"], cfg["output"]["build_dir"]
    registry = layermod.Registry.load(cfg["presence"]["layers"])
    years = [int(y) for y in cfg["time"]["slices"]]
    S = len(years)
    grid, _ = gridmod.load_game(cfg["grid"]["file"], years)
    n = len(grid)
    b = grid.geometry.iloc[0].bounds
    summary = json.load(open(os.path.join(out, "summary.json")))
    built = summary["layers"]
    surf = pd.read_csv(os.path.join(out, "surfaces.csv.gz"), keep_default_na=True)
    ix = pd.Series(np.arange(n), index=grid["cell"].values)

    spath = os.path.join(out, "speculative", "speculative.csv.gz")
    spec = pd.read_csv(spath) if os.path.exists(spath) else None
    if spec is not None and "land" in spec:
        spec = spec[spec["land"] == 1]  # cells that are land only between slices are for the game
    judg = _judgements(out, registry) if spec is not None else {}
    from .gaps import cell_regions
    _, region = cell_regions(grid["lon"].values, grid["lat"].values)
    region_names = sorted(set(region))
    region_ix = np.array([region_names.index(r) for r in region], dtype=np.uint8)

    cells = np.empty(2 * n, dtype="<i4")
    cells[0::2] = np.round(grid["lon"].values * 1e4)
    cells[1::2] = np.round(grid["lat"].values * 1e4)

    layers, blobs = [], {}
    for L in registry:
        if L["id"] not in built:
            continue
        info = built[L["id"]]
        lay = _layer_bytes(surf, L, n, S, ix, years)
        if spec is not None:
            _spec_bytes(lay, spec[spec["layer"] == L["id"]], L, ix, years)
        blobs[L["id"]] = _pack(lay)
        layers.append({k: L.get(k) for k in ("id", "slug", "name", "group", "set", "kind", "unit", "colour", "colour_dark",
                                              "levels", "units_label", "vmin", "vmax", "note", "licence", "evidence_word")}
                      | {"acid": "acid" in L["mask"], "hasAbsences": info.get("has_absences", False),
                         "sigma": info.get("sigma_km"), "sigmaFrom": info.get("sigma_from", ""),
                         "nAbsent": info.get("n_absent"), "f0": info.get("f0"), "bySlice": info.get("by_slice", []),
                         "unitsKnown": info.get("units_known"), "judgements": judg.get(L["id"], [])})
    units = {}
    for unit, fname in UNIT_FILES.items():
        path = os.path.join(bdir, fname)
        ids = [L["id"] for L in layers if L["unit"] == unit]
        if ids and os.path.exists(path):
            units[unit] = _units(path, years, ids)
            log(f"viewer: {unit} units {units[unit]['n']}")

    gb = grid.total_bounds
    ctry = gpd.read_file("build/isostyle/naturalearth/ne_50m_admin_0_countries.shp")
    lines = ctry.clip(box(gb[0] - 1, gb[1] - 1, gb[2] + 1, gb[3] + 1)).boundary.simplify(0.02)
    borders = []
    for g in lines.explode(index_parts=False):
        if g is None or g.is_empty:
            continue
        c = np.round(np.asarray(g.coords) * 100).astype(int).ravel().tolist()
        if len(c) >= 4:
            borders.append(c)
    contours = {}
    for f in json.load(open(os.path.join(out, "contours.geojson")))["features"]:
        pr = f["properties"]
        key = f"{pr['layer']}|{pr['slice']}|{pr['level']:g}"
        contours.setdefault(key, []).extend(
            np.round(np.asarray(s) * 1000).astype(int).ravel().tolist() for s in f["geometry"]["coordinates"])

    groups = [g for g in registry.groups if any(L["group"] == g for L in layers)]
    meta = {"years": years, "half": summary["half_width"], "n": n, "hexW": b[2] - b[0], "hexH": b[3] - b[1],
            "lon0": float(grid["lon"].min()), "lat0": float(grid["lat"].min()), "bounds": [float(v) for v in gb],
            "eMin": summary["e_min"], "bootstrap": summary["bootstrap"], "phMin": summary["bone_ph_min"],
            "groups": groups, "layers": layers, "regions": region_names, "speculative": spec is not None,
            "ids": None if np.array_equal(grid["cell"].values, np.arange(1, n + 1)) else grid["cell"].tolist(),
            "units": {k: {"n": v["n"], "layers": v["layers"]} for k, v in units.items()},
            "caveats": {"pottery|-7000": "Highs outside the Near East in this slice come from labels stamped on every date "
                                         "at a site, and are artefacts.",
                        "cereal_pollen|-10000": "Wild cereals grow in SW Asia, so cereal-type pollen there is not a farming signal.",
                        "cereal_pollen|-9000": "Wild cereals grow in SW Asia, so cereal-type pollen there is not a farming signal."}}
    blob = {"meta": meta, "cells": _pack(cells), "region": _pack(region_ix), "borders": _pack(borders), "contours": _pack(contours),
            "layers": blobs, "units": {k: {kk: vv for kk, vv in v.items() if kk not in ("n", "layers")} for k, v in units.items()}}
    data = json.dumps(blob, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    page = open(TEMPLATE).read().replace("__ISO_DATA__", data)
    art = os.path.join(bdir, "viewer_artifact.html")
    with open(art, "w") as f:
        f.write(page)
    local = os.path.join(out, "viewer.html")
    with open(local, "w") as f:
        f.write('<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n' + page)
    log(f"viewer: {local} ({os.path.getsize(local) / 1e6:.1f} MB); artifact copy {art}")
    return local, art
