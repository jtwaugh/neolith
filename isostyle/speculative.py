"""Speculative layers: the evidence surfaces with their gaps filled from the
gap critic's judgements (data/isostyle/intuitions/*.toml), for the game.

`python -m isostyle speculative` writes data/isostyle/speculative/:

  speculative.csv.gz   per land cell, slice and layer: value, basis
                       (observed | judged | extrapolated), confidence
                       (observed | high | medium | low | none) and the
                       judgement it came from
  maps/<layer>.png     the filled map per slice; judged cells paler by
                       confidence, extrapolated cells palest
  rules.md             the critics' free-text fill rules per layer and region,
                       which this module does not apply (see below)
  summary.json         how much of each layer is observed, judged, extrapolated

Per layer, slice and land cell (ice and sea stay empty):
  1. observed      the evidence surface's value where it has enough evidence
                   (acid-soil masks are ignored: the game wants use, not survival)
  2. judged        else the expected value of the judgement covering the cell's
                   region and slice; several judgements average, weighted by
                   confidence. Haplogroup set files give each clade's share;
                   a clade the judgement leaves out gets 0, and the set's
                   "other" clade takes whatever share is left.
  3. blended       judged cells within `blend_rings` hex steps of observed cells
                   move toward the observed values nearby (weights 0.75, 0.5,
                   0.25 by distance), so region borders are not cliffs
  4. extrapolated  else the mean of the nearest observed values, spread ring by
                   ring across the grid; confidence "none"

Judgements may carry `adjust` entries, the critics' fill rules in machine
form (schema in isostyle/intuitions.py): gradients along latitude or
longitude, values inside a box, near the coast or near a point, and per-slice
values. They are applied in order to the judged cells before blending.
rules.md lists every free-text rule and whether it has been encoded.
"""
import glob
import json
import os
import tomllib
from collections import deque

import numpy as np
import pandas as pd

from . import grid as gridmod, layers as layermod
from .gaps import cell_regions, km, neighbours

HEX_KM = 55.0          # one hex step, for distance to the coast

CONF_WEIGHT = {"high": 3.0, "medium": 2.0, "low": 1.0}
BLEND = [0.75, 0.5, 0.25]


def _resolve(v, lid, members, other):
    """A set value (clade table) for one clade: named clades get their share
    or 0; the "other" clade gets its share or the remainder."""
    if not isinstance(v, dict):
        return v                       # a number or "unknown"
    if other is not None and lid == other["id"] and lid not in v:
        return max(0.0, 1.0 - sum(float(x) for k, x in v.items() if k != lid))
    return float(v.get(lid, 0.0))


def _resolve_adjust(adj, lid, members, other):
    out = []
    for a in adj:
        b = dict(a)
        for k in ("value", "inland"):
            if k in b:
                b[k] = _resolve(b[k], lid, members, other)
        if b.get("kind") == "gradient":
            b["from"] = [b["from"][0], _resolve(b["from"][1], lid, members, other)]
            b["to"] = [b["to"][0], _resolve(b["to"][1], lid, members, other)]
        out.append(b)
    return out


def load_judgements(out_dir, registry):
    """{layer id: [judgement dicts with 'expected' resolved to a number]}."""
    sets = {}
    for L in registry:
        if L["set"]:
            sets.setdefault(L["set"], []).append(L)
    out = {}
    for path in sorted(glob.glob(os.path.join(out_dir, "intuitions", "*.toml"))):
        d = tomllib.load(open(path, "rb"))
        name = d["meta"]["layer"]
        src = os.path.basename(path)
        for k, j in enumerate(d.get("judgement", []), 1):
            ref = f"{src}#{k}"
            e = j.get("expected")
            if name in sets:
                members = sets[name]
                other = next((m for m in members if m.get("other")), None)
                if not isinstance(e, dict):
                    continue
                for m in members:
                    lid = m["id"]
                    out.setdefault(lid, []).append({**j, "expected": float(_resolve(e, lid, members, other)), "ref": ref,
                                                    "adjust": _resolve_adjust(j.get("adjust", []), lid, members, other)})
            elif isinstance(e, (int, float)):
                out.setdefault(name, []).append({**j, "expected": float(e), "ref": ref})
    return out


def judged_values(j, cells, lon, lat, year, coast_km, elev=None, lo_hi=(0.0, 1.0), hydro=None):
    """The judgement's value at each of `cells`, after its `adjust` entries,
    clipped to the layer's range lo_hi."""
    v = np.full(len(cells), float(j["expected"]))
    lo, la = lon[cells], lat[cells]
    for a in j.get("adjust", []):
        kind = a["kind"]
        if kind == "slice_value":
            if year in a["slices"]:
                v = np.full(len(cells), float(a["value"]))
            continue
        if "slices" in a and year not in a["slices"]:
            continue
        add = a.get("mode") == "add"
        if kind == "gradient":
            x = la if a["axis"] == "lat" else lo
            (c0, v0), (c1, v1) = a["from"], a["to"]
            t = np.clip((x - c0) / (c1 - c0), 0, 1) if c1 != c0 else np.zeros(len(x))
            g = v0 + t * (v1 - v0)
            v = v + g if add else g
            continue
        if kind == "area":
            b = a["bbox"]
            hit = (lo >= b[0]) & (lo <= b[2]) & (la >= b[1]) & (la <= b[3])
        elif kind == "coast":
            hit = coast_km[cells] <= a["within_km"]
            if "inland" in a:
                v = np.where(hit, v, v + a["inland"] if add else a["inland"])
        elif kind == "near":
            hit = km(a["point"][0], a["point"][1], lo, la) <= a["radius_km"]
        elif kind == "polygon":
            from .hydro import in_polygon
            hit = in_polygon(a["points"], lo, la)
        elif kind == "river":
            if hydro is None:
                from .hydro import Hydro
                hydro = Hydro()
            d = hydro.distance_km(lo, la, year, a.get("names", ()), a.get("lakes", ()), a.get("min_upland_km2"),
                                  a.get("bbox"))
            hit = d <= a["within_km"]
            if "outside" in a:
                v = np.where(hit, v, v + a["outside"] if add else a["outside"])
        elif kind == "elevation":
            z = elev[cells] if elev is not None else np.full(len(cells), np.nan)
            hit = (z >= a["above_m"]) if "above_m" in a else (z <= a["below_m"])
            hit &= ~np.isnan(z)
        else:
            continue
        if a["value"] == "unknown":
            v = np.where(hit, np.nan, v)
        else:
            v = np.where(hit, v + a["value"] if add else a["value"], v)
    return np.clip(v, *lo_hi)


def cell_elevation(grid, path="build/etopo.asc"):
    """ETOPO1 elevation (m) at each cell centre, or None if the raster is missing."""
    if not os.path.exists(path):
        return None
    from pipeline.elevation import load_asc
    arr, tf = load_asc(path)
    r = np.clip(np.rint(tf.row(grid["lat"].values)).astype(int), 0, arr.shape[0] - 1)
    c = np.clip(np.rint(tf.col(grid["lon"].values)).astype(int), 0, arr.shape[1] - 1)
    return arr[r, c].astype(float)


def coast_distance(sea, nb):
    """km from the nearest sea cell, in hex steps (sea: bool per cell)."""
    dist, _ = ring_distance({i: 0.0 for i in np.flatnonzero(sea)}, nb, len(sea))
    return np.where(dist < 0, 1e9, dist * HEX_KM)


def ring_distance(sources, nb, n):
    """Hex steps from the nearest source cell, and the propagated mean of the
    source values (each ring takes the mean of its already-reached neighbours).
    sources: dict cell -> value."""
    dist = np.full(n, -1)
    val = np.full(n, np.nan)
    q = deque()
    for i, v in sources.items():
        dist[i], val[i] = 0, v
        q.append(i)
    while q:
        i = q.popleft()
        for j in nb[i]:
            if dist[j] < 0:
                dist[j] = dist[i] + 1
                vals = [val[k] for k in nb[j] if dist[k] == dist[j] - 1 and not np.isnan(val[k])]
                val[j] = float(np.mean(vals)) if vals else val[i]
                q.append(j)
    return dist, val


def fill(observed, land, judged, judged_conf, judged_ref, nb, blend_rings=3):
    """One layer and slice. observed: values (NaN where masked); land: bool;
    judged: expected value per cell (NaN where no judgement). Returns
    value, basis, confidence, ref arrays."""
    n = len(observed)
    have = land & ~np.isnan(observed)
    value = np.where(have, observed, np.nan)
    basis = np.where(have, "observed", "").astype(object)
    conf = np.where(have, "observed", "").astype(object)
    ref = np.full(n, "", dtype=object)
    dist, near = ring_distance({i: observed[i] for i in np.flatnonzero(have)}, nb, n)
    jd = land & ~have & ~np.isnan(judged)
    w = np.zeros(n)
    for k, b in enumerate(BLEND[:blend_rings], 1):
        w[dist == k] = b
    value[jd] = np.where(np.isnan(near[jd]), judged[jd], w[jd] * near[jd] + (1 - w[jd]) * judged[jd])
    basis[jd], conf[jd], ref[jd] = "judged", judged_conf[jd], judged_ref[jd]
    ex = land & ~have & ~jd & ~np.isnan(near)
    value[ex], basis[ex], conf[ex] = near[ex], "extrapolated", "none"
    return value, basis, conf, ref


def run(cfg, log=print):
    out_dir, bdir = cfg["output"]["out_dir"], cfg["output"]["build_dir"]
    sdir = os.path.join(out_dir, "speculative")
    os.makedirs(os.path.join(sdir, "maps"), exist_ok=True)
    registry = layermod.Registry.load(cfg["presence"]["layers"])
    years = [int(y) for y in cfg["time"]["slices"]]
    grid, terrain = gridmod.load_game(cfg["grid"]["file"], np.array(years))
    n = len(grid)
    nb = neighbours(grid)
    _, region = cell_regions(grid["lon"].values, grid["lat"].values)
    surf = pd.read_csv(os.path.join(out_dir, "surfaces.csv.gz"))
    ix = pd.Series(np.arange(n), index=grid["cell"].values)
    summary = json.load(open(os.path.join(out_dir, "summary.json")))
    judgements = load_judgements(out_dir, registry)
    elev = cell_elevation(grid)
    from .hydro import Hydro
    hydro = Hydro()
    rows, stats, rules = [], {}, {}
    for L in registry:
        m = L["id"]
        if m not in summary["layers"]:
            continue
        js = judgements.get(m, [])
        s = surf[surf["layer"] == m]
        stats[m] = []
        for j, y in enumerate(years):
            t = s[s["slice"] == y]
            ci = ix.reindex(t["cell"].values).values.astype(int)
            obs = np.full(n, np.nan)
            land = np.zeros(n, bool)
            reason = np.full(n, "sea", dtype=object)
            reason[ci] = t["mask_reason"].fillna("").values
            land[ci] = True
            land &= terrain[:, j] != "Ice"
            v = t["presence"].values.astype(float)
            obs[ci] = v
            # Acid soil masks survival, not use: treat its cells as gaps.
            obs[(reason == "acid soil")] = np.nan
            judged = np.full(n, np.nan)
            jconf = np.full(n, "", dtype=object)
            jref = np.full(n, "", dtype=object)
            acc = {}
            coast = None
            for jj in js:
                if y not in jj.get("slices", []):
                    continue
                cells = np.flatnonzero(region == jj["region"])
                if not len(cells):
                    continue
                if coast is None and any(a["kind"] == "coast" for a in jj.get("adjust", [])):
                    coast = coast_distance(terrain[:, j] == "Water", nb)
                rng = (L["vmin"], L["vmax"]) if L["kind"] in ("continuous", "grid") else (0.0, 1.0)
                vals = judged_values(jj, cells, grid["lon"].values, grid["lat"].values, y, coast, elev, rng, hydro)
                wgt = CONF_WEIGHT.get(jj.get("confidence"), 1.0)
                for c, e in zip(cells, vals):
                    if not np.isnan(e):
                        acc.setdefault(c, []).append((float(e), wgt, jj["confidence"], jj["ref"]))
            for c, lst in acc.items():
                tot = sum(w for _, w, _, _ in lst)
                judged[c] = sum(e * w for e, w, _, _ in lst) / tot
                best = max(lst, key=lambda t: t[1])
                jconf[c] = best[2]
                jref[c] = ";".join(sorted({r for *_, r in lst}))
            val, basis, conf, ref = fill(obs, land, judged, jconf, jref, nb)
            keep = land
            rows.append(pd.DataFrame({"cell": grid["cell"].values[keep], "slice": y, "layer": m,
                                      "value": np.round(val[keep], 3), "basis": basis[keep],
                                      "confidence": conf[keep], "judgement": ref[keep]}))
            b = pd.Series(basis[keep]).value_counts()
            stats[m].append({"slice": y, "land_cells": int(keep.sum()),
                             **{k: int(b.get(k, 0)) for k in ("observed", "judged", "extrapolated")}})
        for jj in js:
            rules.setdefault(m, []).append((jj["region"], jj["slices"], jj.get("confidence"), jj.get("speculative_rule", ""),
                                            jj["ref"], len(jj.get("adjust", []))))
        tot = {k: sum(x[k] for x in stats[m]) for k in ("observed", "judged", "extrapolated")}
        log(f"speculative: {m}: observed {tot['observed']}, judged {tot['judged']}, extrapolated {tot['extrapolated']}")
    out = pd.concat(rows, ignore_index=True)
    out.to_csv(os.path.join(sdir, "speculative.csv.gz"), index=False)
    json.dump({"slices": years, "layers": stats}, open(os.path.join(sdir, "summary.json"), "w"), indent=1)
    write_rules(os.path.join(sdir, "rules.md"), rules, registry)
    draw(sdir, grid, registry, out, years, terrain, summary, log)
    log(f"speculative: wrote {sdir}/")


def write_rules(path, rules, registry):
    lines = ["# Speculative fill rules from the gap critics", "",
             "Free-text rules the critics proposed for each gap, with how many machine-readable `adjust`",
             "entries encode each (applied by `speculative.py`). A rule with none is filled with the judgement's",
             "flat expected value. Each line names its judgement (file#index).", ""]
    for m, lst in rules.items():
        lines += [f"## {registry[m]['name']}", ""]
        seen = set()
        for reg, slices, conf, rule, ref, nadj in sorted(lst, key=lambda t: (t[0], min(t[1]) if t[1] else 0)):
            key = (reg, rule)
            if key in seen or not rule:
                continue
            seen.add(key)
            span = f"{-max(slices):,}–{-min(slices):,} BCE" if slices else ""
            enc = f"encoded ({nadj} adjust)" if nadj else "flat value"
            lines.append(f"- **{reg}**, {span} ({conf}, {enc}): {rule} `{ref}`")
        lines.append("")
    open(path, "w").write("\n".join(lines))


def draw(sdir, grid, registry, out, years, terrain, summary, log):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from matplotlib.colors import to_rgb
    from matplotlib.patches import Patch

    from .maps import ICE, INK, INK2, RAMP, SURFACE
    verts = [np.asarray(g.exterior.coords) for g in grid.geometry]
    ix = pd.Series(np.arange(len(grid)), index=grid["cell"].values)
    alpha = {"observed": 1.0, "high": 0.8, "medium": 0.62, "low": 0.45, "none": 0.25}
    plain = np.array(to_rgb("#e7e7e2"))
    for L in registry:
        m = L["id"]
        sub = out[out["layer"] == m]
        if sub.empty:
            continue
        fig, axes = plt.subplots(2, 4, figsize=(17.2, 11.4))
        for j, (ax, y) in enumerate(zip(axes.ravel(), years)):
            t = sub[sub["slice"] == y]
            col = np.tile(np.array(to_rgb(SURFACE)), (len(grid), 1))
            col[terrain[:, j] == "Ice"] = to_rgb(ICE)
            ci = ix.reindex(t["cell"].values).values.astype(int)
            v = t["value"].values.astype(float)
            if L["kind"] in ("continuous", "grid"):
                v = (v - L["vmin"]) / (L["vmax"] - L["vmin"])
            k = np.clip(np.nan_to_num(v, nan=-1) * 5, 0, 4.999).astype(int)
            base = np.array([to_rgb(c) for c in RAMP])[k]
            a = np.array([alpha.get(c, 0.25) for c in t["confidence"].values])[:, None]
            rgb = base * a + plain * (1 - a)
            rgb[np.isnan(v)] = plain
            col[ci] = rgb
            ax.add_collection(PolyCollection(verts, facecolors=col, edgecolors="none", rasterized=True))
            b = grid.total_bounds
            ax.set_xlim(b[0], b[2])
            ax.set_ylim(b[1], b[3])
            ax.set_aspect(1.41)
            ax.set_axis_off()
            ax.set_title(f"{-y:,} BCE", fontsize=10, loc="left", color=INK)
        fig.suptitle(f"{L['name']}: speculative", x=0.012, ha="left", fontsize=15, fontweight="bold")
        fig.text(0.012, 0.955, "Full colour: observed. Paler: judged by the gap critic (high, medium, low confidence). "
                 "Palest: extrapolated from the nearest observed values. Not evidence.", fontsize=9.5, color=INK2)
        hand = [Patch(fc=tuple(np.array(to_rgb(RAMP[3])) * a + plain * (1 - a)), label=lab)
                for lab, a in (("observed", 1.0), ("judged, high", 0.8), ("judged, medium", 0.62), ("judged, low", 0.45),
                               ("extrapolated", 0.25))]
        fig.legend(handles=hand, loc="lower left", ncol=5, frameon=False, fontsize=9)
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        fig.savefig(os.path.join(sdir, "maps", f"{m}.png"), dpi=100)
        plt.close(fig)
