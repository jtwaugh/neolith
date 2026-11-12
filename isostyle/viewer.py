"""Standalone viewer: one HTML file with the surfaces embedded.

Reads the outputs of `build` (surfaces.csv.gz, contours.geojson,
summary.json, build/isostyle/units.csv.gz) and writes
data/isostyle/viewer.html, which opens in a browser with no server. Arrays
are gzipped and base64-encoded inside the page and unpacked with the
browser's DecompressionStream.
"""
import base64
import gzip
import json
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from . import grid as gridmod
from .observe import MATERIALS

NAMES = {"pottery": "Pottery", "flaked_stone": "Flaked stone", "ground_stone": "Ground stone",
         "bone_antler": "Bone and antler", "ornaments": "Ornaments"}
MASK = {"": 0, "low evidence": 1, "ice": 2, "acid soil": 3}   # 4 = sea (no row)
TEMPLATE = os.path.join(os.path.dirname(__file__), "viewer_template.html")


def _pack(data):
    if isinstance(data, np.ndarray):
        data = data.tobytes()
    elif not isinstance(data, bytes):
        data = json.dumps(data, separators=(",", ":")).encode()
    return base64.b64encode(gzip.compress(data, 9, mtime=0)).decode()


def run(cfg, log=print):
    out, bdir = cfg["output"]["out_dir"], cfg["output"]["build_dir"]
    years = [int(y) for y in cfg["time"]["slices"]]
    S, M = len(years), len(MATERIALS)
    grid, _ = gridmod.load_game(cfg["grid"]["file"], years)
    n = len(grid)
    b = grid.geometry.iloc[0].bounds
    hex_w, hex_h = b[2] - b[0], b[3] - b[1]
    summary = json.load(open(os.path.join(out, "summary.json")))

    # ---- per material, slice and field: one byte per cell
    lay = np.zeros((M, S, 5, n), dtype=np.uint8)
    lay[:, :, 0] = 255
    lay[:, :, 2] = 255
    lay[:, :, 3] = 255
    lay[:, :, 4] = 4
    surf = pd.read_csv(os.path.join(out, "surfaces.csv.gz"), keep_default_na=True)
    ix = pd.Series(np.arange(n), index=grid["cell"].values)
    ci = ix.reindex(surf["cell"].values).values
    mk = surf["material"].map({m: k for k, m in enumerate(MATERIALS)}).values
    sk = surf["slice"].map({y: j for j, y in enumerate(years)}).values
    ok = ~(np.isnan(ci) | np.isnan(mk.astype(float)) | np.isnan(sk.astype(float)))
    surf, ci, mk, sk = surf[ok], ci[ok].astype(int), mk[ok].astype(int), sk[ok].astype(int)
    lay[mk, sk, 4, ci] = surf["mask_reason"].fillna("").map(MASK).values
    p = surf["presence"].values
    lay[mk, sk, 0, ci] = np.where(np.isnan(p), 255, np.round(np.nan_to_num(p) * 200)).astype(np.uint8)
    e = surf["evidence"].values
    q = np.clip(np.round(32 * np.log10(np.maximum(e, 0.01) * 100)), 1, 254)
    lay[mk, sk, 1, ci] = np.where(e >= 0.01, q, 0).astype(np.uint8)
    bt = surf["boot_share_above_50"].values
    lay[mk, sk, 2, ci] = np.where(np.isnan(bt), 255, np.round(np.nan_to_num(bt) * 200)).astype(np.uint8)
    ls = surf["label_share"].values
    lay[mk, sk, 3, ci] = np.where(np.isnan(ls) | (e < 0.05), 255, np.round(np.nan_to_num(ls) * 200)).astype(np.uint8)

    cells = np.empty(2 * n, dtype="<i4")
    cells[0::2] = np.round(grid["lon"].values * 1e4)
    cells[1::2] = np.round(grid["lat"].values * 1e4)

    # ---- occupation units
    u = pd.read_csv(os.path.join(bdir, "units.csv.gz"), low_memory=False)
    nu = len(u)
    uxy = np.empty(2 * nu, dtype="<i4")
    uxy[0::2] = np.round(u["lon"].values * 1e4)
    uxy[1::2] = np.round(u["lat"].values * 1e4)
    uw = np.vstack([np.round(np.clip(u[f"w_{y}"].values, 0, 1) * 255) for y in years]).astype(np.uint8)
    st = np.zeros((M, nu), dtype=np.uint8)
    for k, m in enumerate(MATERIALS):
        y, basis = u[f"y_{m}"].values, u[f"basis_{m}"].fillna("").values
        st[k] = np.select([(y == 1) & (basis == "recorded"), (y == 1) & (basis == "label"),
                           (y == 0) & (basis == "label"), (y == 0) & (basis == "recorded")], [1, 2, 3, 4], 0)
    flags = (u["grave"].astype(str).str.lower().eq("true").values * 1
             + u["dating"].astype(str).eq("range").values * 2).astype(np.uint8)
    clean = lambda s: str(s).replace("\t", " ").replace("\n", " ")
    names = "\n".join(f"{clean(a)}\t{clean(b)}\t{int(c)}" for a, b, c in
                      zip(u["site"], u["source"], u["n_dates"].fillna(0))).encode()

    # ---- country borders and isolines
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
        key = f"{pr['material']}|{pr['slice']}|{pr['level']:g}"
        contours.setdefault(key, []).extend(
            np.round(np.asarray(s) * 1000).astype(int).ravel().tolist() for s in f["geometry"]["coordinates"])

    mats = []
    for m in MATERIALS:
        info = summary["materials"][m]
        absrec = summary["counts"].get(m, {}).get("absent_recorded", 0)
        mats.append({"absentRecorded": absrec, "id": m, "slug": m.replace("_", "-"), "name": NAMES[m], "hasAbsences": info["has_absences"],
                     "sigma": info["sigma_km"], "sigmaCv": "cv" in info, "f0": info["f0"], "bySlice": info["by_slice"],
                     "acid": m == "bone_antler"})
    meta = {"years": years, "half": summary["half_width"], "n": n, "nUnits": nu, "hexW": hex_w, "hexH": hex_h,
            "lon0": float(grid["lon"].min()), "lat0": float(grid["lat"].min()),
            "bounds": [float(v) for v in gb], "eMin": summary["e_min"], "bootstrap": summary["bootstrap"],
            "phMin": summary["bone_ph_min"], "materials": mats,
            "ids": None if np.array_equal(grid["cell"].values, np.arange(1, n + 1)) else grid["cell"].tolist(),
            "counts": {k: summary["counts"].get(k) for k in ("episodes", "sites_with_episode_in_window", "units_in_window",
                                                              "grave_units", "external_records")},
            "caveats": {"pottery|-7000": "Highs outside the Near East in this slice come from labels stamped on every date "
                                         "at a site, and are artefacts."}}
    blob = {"meta": meta, "cells": _pack(cells), "layers": _pack(lay), "uxy": _pack(uxy), "uw": _pack(uw),
            "ust": _pack(st), "uflag": _pack(flags), "unames": _pack(names), "borders": _pack(borders),
            "contours": _pack(contours)}
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
