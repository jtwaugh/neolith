"""Gap dossiers: where a layer has no evidence, and what surrounds the hole.

`python -m isostyle gaps --layer pottery [--layer cereals ...]` (no --layer:
every layer) writes, per layer, build/isostyle/gaps/<layer>/:

  dossier.json   one entry per gap: a connected run of masked land cells in
                 one slice (at least `min_cells`), with its size, centre,
                 bounding box, the modern countries under it, the layer's
                 values on the cells bordering it, the distance to the
                 nearest evidence point, and what every other layer shows
                 inside it (cells with evidence, mean value)
  dossier.md     the same, readable
  gap_NN.png     a crop of the layer around each of the largest gaps, with
                 the evidence points of that slice

The gap critic agent (.claude/agents/gap-critic.md) reads these and writes
its intuitions to data/isostyle/intuitions/<layer>.toml.
"""
import json
import os
from collections import deque

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PolyCollection
from matplotlib.patches import Patch

from . import grid as gridmod, layers as layermod
from .maps import ICE, INK, INK2, NO_EVIDENCE, RAMP, SURFACE
from .observe import R_EARTH

DIRS = [(1, 1), (0, 2), (-1, 1), (-1, -1), (0, -2), (1, -1)]
# Macro-regions for splitting gaps, by modern country (Natural Earth NAME).
REGIONS = {
    "British Isles": "United Kingdom|Ireland|Isle of Man",
    "France & Low Countries": "France|Belgium|Netherlands|Luxembourg",
    "Iberia": "Spain|Portugal|Andorra|Gibraltar",
    "Italy & islands": "Italy|Malta|San Marino|Vatican",
    "Central Europe": "Germany|Switzerland|Austria|Czechia|Slovakia|Poland|Hungary|Liechtenstein|Slovenia",
    "Scandinavia": "Denmark|Norway|Sweden|Finland|Iceland|Faeroe Is.|Åland",
    "Baltic": "Estonia|Latvia|Lithuania",
    "Balkans & Greece": "Croatia|Bosnia and Herz.|Serbia|Montenegro|Kosovo|North Macedonia|Albania|Greece|Bulgaria|Romania|Moldova",
    "Ukraine & Belarus": "Ukraine|Belarus",
    "Anatolia & Cyprus": "Turkey|Cyprus|N. Cyprus",
    "Caucasus": "Georgia|Armenia|Azerbaijan",
    "Levant": "Israel|Palestine|Lebanon|Syria|Jordan",
    "Mesopotamia": "Iraq|Kuwait",
    "Iran & Afghanistan": "Iran|Afghanistan",
    "Central Asia": "Kazakhstan|Uzbekistan|Turkmenistan|Kyrgyzstan|Tajikistan",
    "Arabia": "Saudi Arabia|Yemen|Oman|United Arab Emirates|Qatar|Bahrain",
    "Maghreb": "Morocco|Algeria|Tunisia|W. Sahara",
    "Libya & Egypt": "Libya|Egypt",
    "Nile & Sudan": "Sudan|S. Sudan",
    "Sahara–Sahel": "Mauritania|Mali|Niger|Chad",
    "West Africa": "Senegal|Gambia|Guinea-Bissau|Guinea|Sierra Leone|Liberia|Côte d'Ivoire|Burkina Faso|Ghana|Togo|Benin|Nigeria|Cameroon|Central African Rep.",
    "Horn of Africa": "Ethiopia|Eritrea|Djibouti|Somalia|Somaliland",
}
REGION_OF = {c: r for r, cs in REGIONS.items() for c in cs.split("|")}


def region_of(country, lat):
    if country == "Russia":
        return "Russia: forest north of 56°N" if lat >= 56 else "Russia: steppe and forest-steppe"
    if country == "sea or unassigned":
        return "Now-drowned shelves and islands"
    return REGION_OF.get(country, "Other")


def cell_regions(lon, lat, path="build/isostyle/naturalearth/ne_50m_admin_0_countries.shp"):
    """Modern country and macro-region of each cell centre. Cells just outside
    the coarse coastline take the nearest country within 30 km; the rest are
    drowned shelves or small islands."""
    ctry = gpd.read_file(path)[["NAME", "geometry"]]
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(lon, lat), crs=4326)
    j = gpd.sjoin(pts, ctry, how="left", predicate="within")
    country = j[~j.index.duplicated()]["NAME"].values
    miss = pd.isna(country)
    if miss.any():
        near = gpd.sjoin_nearest(pts[miss].to_crs(3035), ctry.to_crs(3035), how="left", max_distance=30000)
        near = near[~near.index.duplicated()]["NAME"]
        country = np.array(country, dtype=object)
        country[np.flatnonzero(miss)] = near.reindex(pts[miss].index).values
    country = pd.Series(country).fillna("sea or unassigned").values
    return country, np.array([region_of(c, la) for c, la in zip(country, lat)])


UNIT_FILES = {"occupation": "units.csv.gz", "core": "core_units.csv.gz", "sample": "sample_units.csv.gz"}


def neighbours(grid):
    lon, lat = grid["lon"].values, grid["lat"].values
    b = grid.geometry.iloc[0].bounds
    w, h = b[2] - b[0], b[3] - b[1]
    col = np.rint((lon - lon.min()) / (0.75 * w)).astype(int)
    row = np.rint(2 * (lat - lat.min()) / h).astype(int)
    key = {(c, r): i for i, (c, r) in enumerate(zip(col, row))}
    return [[key[(c + dc, r + dr)] for dc, dr in DIRS if (c + dc, r + dr) in key] for c, r in zip(col, row)]


def components(mask, nb):
    """Connected runs of True cells; list of index arrays, largest first."""
    seen = np.zeros(len(mask), bool)
    out = []
    for s in np.flatnonzero(mask):
        if seen[s]:
            continue
        q, comp = deque([s]), []
        seen[s] = True
        while q:
            i = q.popleft()
            comp.append(i)
            for j in nb[i]:
                if mask[j] and not seen[j]:
                    seen[j] = True
                    q.append(j)
        out.append(np.array(comp))
    return sorted(out, key=len, reverse=True)


def km(lon1, lat1, lon2, lat2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * R_EARTH * np.arcsin(np.sqrt(a))


def _value(L, v):
    if v is None or np.isnan(v):
        return None
    return round(float(v), 1) if L["kind"] in ("continuous", "grid") else round(float(v), 3)


def run(cfg, layer_ids=None, min_cells=25, max_gaps=12, log=print):
    out_root = os.path.join(cfg["output"]["build_dir"], "gaps")
    registry = layermod.Registry.load(cfg["presence"]["layers"])
    years = [int(y) for y in cfg["time"]["slices"]]
    grid, terrain = gridmod.load_game(cfg["grid"]["file"], np.array(years))
    nb = neighbours(grid)
    lon, lat = grid["lon"].values, grid["lat"].values
    country, region = cell_regions(lon, lat)
    surf = pd.read_csv(os.path.join(cfg["output"]["out_dir"], "surfaces.csv.gz"))
    ix = pd.Series(np.arange(len(grid)), index=grid["cell"].values)
    summary = json.load(open(os.path.join(cfg["output"]["out_dir"], "summary.json")))
    built = [L for L in registry if L["id"] in summary["layers"]]

    # value[layer][slice] and masked[layer][slice] as full-grid arrays
    val, msk, reason = {}, {}, {}
    for L in built:
        s = surf[surf["layer"] == L["id"]]
        for y in years:
            t = s[s["slice"] == y]
            ci = ix.reindex(t["cell"].values).values.astype(int)
            v = np.full(len(grid), np.nan)
            m = np.ones(len(grid), bool)
            r = np.full(len(grid), "sea", dtype=object)
            v[ci], m[ci], r[ci] = t["presence"].values, t["masked"].values.astype(bool), t["mask_reason"].fillna("").values
            val[(L["id"], y)], msk[(L["id"], y)], reason[(L["id"], y)] = v, m, r
    unit_tables = {}
    for unit, f in UNIT_FILES.items():
        p = os.path.join(cfg["output"]["build_dir"], f)
        if os.path.exists(p):
            unit_tables[unit] = pd.read_csv(p, low_memory=False)

    targets = [L for L in built if not layer_ids or L["id"] in layer_ids]
    for L in targets:
        m = L["id"]
        odir = os.path.join(out_root, m)
        os.makedirs(odir, exist_ok=True)
        u = unit_tables.get(L["unit"])
        gaps = []
        for y in years:
            r = reason[(m, y)]
            hole = np.isin(r, ["low evidence"])
            comps = []
            for reg in np.unique(region[hole]):
                comps += [c for c in components(hole & (region == reg), nb) if len(c) >= min_cells]
            for comp in sorted(comps, key=len, reverse=True):
                cset = set(comp.tolist())
                edge = sorted({k for i in comp for k in nb[i] if k not in cset and not msk[(m, y)][k]})
                edge_vals = val[(m, y)][edge] if edge else np.array([])
                cx, cy = float(lon[comp].mean()), float(lat[comp].mean())
                near = None
                if u is not None and f"y_{m}" in u:
                    w = u[f"w_{y}"].values
                    sel = (w > 0.2) & u[f"y_{m}"].notna().values
                    if sel.any():
                        d = km(cx, cy, u.loc[sel, "lon"].values, u.loc[sel, "lat"].values)
                        near = round(float(d.min()))
                others = {}
                for O in built:
                    if O["id"] == m:
                        continue
                    ok = ~msk[(O["id"], y)][comp]
                    if ok.any():
                        others[O["id"]] = {"cells_with_evidence": int(ok.sum()),
                                           "mean_value": _value(O, np.nanmean(val[(O["id"], y)][comp][ok]))}
                cn = pd.Series(country[comp]).value_counts()
                gaps.append({
                    "id": f"{m}-{abs(y)}-{len(gaps) + 1:02d}", "layer": m, "slice": y, "cells": int(len(comp)),
                    "centre": [round(cx, 2), round(cy, 2)],
                    "bbox": [round(float(lon[comp].min()), 1), round(float(lat[comp].min()), 1),
                             round(float(lon[comp].max()), 1), round(float(lat[comp].max()), 1)],
                    "region": str(region[comp[0]]),
                    "countries": {k: int(v) for k, v in cn.head(6).items()},
                    "edge_cells_with_evidence": len(edge),
                    "edge_mean_value": _value(L, np.nanmean(edge_vals)) if len(edge_vals) else None,
                    "edge_range": [_value(L, np.nanmin(edge_vals)), _value(L, np.nanmax(edge_vals))] if len(edge_vals) else None,
                    "nearest_evidence_km": near,
                    "other_layers_inside": others,
                    "_cells": comp.tolist()})
        gaps.sort(key=lambda g: -g["cells"])
        top = gaps
        picks, seen_reg = [], set()
        for g in sorted(top, key=lambda g: -g["cells"]):
            if g["region"] not in seen_reg:
                picks.append(g)
                seen_reg.add(g["region"])
        for k, g in enumerate(picks[:max_gaps]):
            g["image"] = f"gap_{k + 1:02d}.png"
            crop(os.path.join(odir, g["image"]), grid, L, g, val[(m, g["slice"])], reason[(m, g["slice"])],
                 u, terrain, years.index(g["slice"]))
        land = np.array([[reason[(m, y)][i] != "sea" for y in years] for i in range(len(grid))])
        shown = np.array([~msk[(m, y)] for y in years]).T
        cover = {}
        for reg in sorted(set(region)):
            sel = region == reg
            n = land[sel].sum(axis=0)
            if n.max() < 10:
                continue
            cover[reg] = [None if n[k] == 0 else round(float(shown[sel, k].sum() / n[k]), 3) for k in range(len(years))]
        info = summary["layers"][m]
        head = {"layer": m, "name": L["name"], "group": L["group"], "kind": L["kind"], "unit": L["unit"],
                "note": L["note"], "licence": L["licence"], "sigma_km": info.get("sigma_km"),
                "has_absences": info.get("has_absences"), "n_absent": info.get("n_absent"),
                "by_slice": info.get("by_slice"), "f0": info.get("f0"), "min_cells": min_cells,
                "slices": years, "coverage_by_region": cover}
        json.dump({"layer": head, "gaps": [{k: v for k, v in g.items() if k != "_cells"} for g in top]},
                  open(os.path.join(odir, "dossier.json"), "w"), indent=1, ensure_ascii=False)
        write_md(os.path.join(odir, "dossier.md"), head, top, registry)
        log(f"gaps: {m}: {len(gaps)} gaps of {min_cells}+ cells; {len(top)} written, "
            f"{sum(1 for g in top if 'image' in g)} with images")


def write_md(path, head, gaps, registry):
    lines = [f"# Gap dossier: {head['name']}", "",
             f"{head['group']} · {head['kind']} · unit: {head['unit']} · σ = {head['sigma_km']} km · "
             f"absences recorded: {head['n_absent']}", "", head["note"] or "", "",
             "| Slice | Units with known status | Cells shown / land cells | Mean |", "|---|---|---|---|"]
    for k, b in enumerate(head["by_slice"] or []):
        f0 = (head["f0"] or [None] * 8)[k]
        lines.append(f"| {-b['slice']:,} BCE | {b.get('occupations', '')} | {b.get('cells_unmasked')} / {b.get('land_cells')} | {f0} |")
    lines += ["", "## Share of land cells with enough evidence, by region", "",
              "| Region | " + " | ".join(f"{-y // 1000}k" for y in head["slices"]) + " |",
              "|---|" + "---|" * len(head["slices"])]
    for reg, row in sorted(head["coverage_by_region"].items(), key=lambda kv: sum(v or 0 for v in kv[1])):
        lines.append(f"| {reg} | " + " | ".join("—" if v is None else f"{round(100 * v)}%" for v in row) + " |")
    lines += ["", "## Gaps (largest first)", ""]
    for g in gaps:
        others = ", ".join(f"{registry[k]['name']}: {v['cells_with_evidence']} cells"
                           + (f" (mean {v['mean_value']})" if v["mean_value"] is not None else "")
                           for k, v in sorted(g["other_layers_inside"].items(), key=lambda kv: -kv[1]["cells_with_evidence"])[:8])
        lines += [f"### {g['id']}: {g['region']}, {-g['slice']:,} BCE, {g['cells']} cells around {g['centre'][1]}°N {g['centre'][0]}°E"
                  + (f"  (image: {g['image']})" if g.get("image") else ""),
                  f"- Countries: {', '.join(f'{k} ({v})' for k, v in g['countries'].items())}",
                  f"- Bounding box (lon, lat): {g['bbox']}",
                  f"- Edge: {g['edge_cells_with_evidence']} bordering cells with evidence; mean {g['edge_mean_value']}, range {g['edge_range']}",
                  f"- Nearest evidence point: {g['nearest_evidence_km']} km from the centre",
                  f"- Other layers inside: {others or 'none'}", ""]
    open(path, "w").write("\n".join(lines))


def crop(path, grid, L, g, v, r, units, terrain, j, pad=4.0):
    b = g["bbox"]
    x0, y0, x1, y1 = b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad
    lon, lat = grid["lon"].values, grid["lat"].values
    sel = (lon >= x0) & (lon <= x1) & (lat >= y0) & (lat <= y1)
    verts = [np.asarray(grid.geometry.iloc[i].exterior.coords) for i in np.flatnonzero(sel)]
    cols = []
    hole = set(g["_cells"])
    for i in np.flatnonzero(sel):
        if r[i] == "sea":
            cols.append(SURFACE)
        elif terrain[i, j] == "Ice":
            cols.append(ICE)
        elif np.isnan(v[i]):
            cols.append("#c9a7a7" if i in hole else NO_EVIDENCE)
        else:
            x = v[i] if L["kind"] not in ("continuous", "grid") else (v[i] - L["vmin"]) / (L["vmax"] - L["vmin"])
            cols.append(RAMP[min(4, int(np.clip(x, 0, 0.999) * 5))])
    fig, ax = plt.subplots(figsize=(7.5, 6.2))
    ax.set_facecolor(SURFACE)
    ax.add_collection(PolyCollection(verts, facecolors=cols, edgecolors="none"))
    try:
        gpd.read_file("build/isostyle/naturalearth/ne_50m_admin_0_countries.shp", bbox=(x0, y0, x1, y1)).boundary.plot(
            ax=ax, color=INK2, linewidth=0.4)
    except Exception:
        pass
    if units is not None and f"y_{L['id']}" in units:
        w = units[f"w_{g['slice']}"].values
        y = units[f"y_{L['id']}"].values
        inbox = (units["lon"].between(x0, x1) & units["lat"].between(y0, y1)).values & (w > 0.2)
        for val, mk, c, lab in ((1, "o", "#d9531f", "present"), (0, "o", "#2f3638", "absent")):
            s = inbox & (y == val)
            ax.scatter(units.loc[s, "lon"], units.loc[s, "lat"], s=14, c=c, marker=mk, edgecolors="white", linewidths=0.4, label=lab)
        s = inbox & np.isnan(y)
        ax.scatter(units.loc[s, "lon"], units.loc[s, "lat"], s=4, c="#898781", label="status unknown")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect(1 / np.cos(np.radians((y0 + y1) / 2)))
    ax.set_title(f"{L['name']}, {-g['slice']:,} BCE: gap {g['id']} ({g['cells']} cells, pink)", fontsize=10, loc="left", color=INK)
    hand = [Patch(fc="#c9a7a7", label="this gap"), Patch(fc=NO_EVIDENCE, label="other masked land")] + \
           [Patch(fc=c, label=l) for c, l in zip(RAMP, ["0–20%", "20–40%", "40–60%", "60–80%", "80–100%"])]
    leg1 = ax.legend(handles=hand, loc="lower left", fontsize=7, frameon=True)
    ax.add_artist(leg1)
    if units is not None:
        ax.legend(loc="lower right", fontsize=7, frameon=True)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
