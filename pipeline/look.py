"""Looking at the terrain map, for the terrain critic (.claude/agents/terrain-critic.md).

- `suspects`: screens over the whole built map for things that look like
  artefacts: straight biome edges and thin bands, biomes that surge or
  flicker in a region between keyframes, biomes in the wrong climate,
  floodplains that vanish while their river still runs, and speckle. Each
  suspect is a box and years to look at, not a verdict.
- `look`: one region over time as a sheet of maps in a diagnostic palette
  (every class distinct, with rivers and pollen anchors), the same region
  stage by stage for each keyframe (drawn map, BIOME4, calibrated, gaps
  filled, after cleanup, final), and tables: class shares, transitions,
  which stage each class came from, climate, river hexes, anchors.

Both read build/combined_map.geojson and build/stages.npz (written by
`python -m pipeline build`) and write under [critic] out. Neither changes
the map.
"""
import ast
import csv
import json
import os
from collections import Counter, defaultdict

import numpy as np

from . import grid as gridmod

# Diagnostic colours: every class distinct at a glance. The game's own
# palette has three near-identical forest greens.
PALETTE = {
    "Water": "#cfe3f5", "Ice": "#ffffff", "Tundra": "#b9a8dc", "Alpine": "#6f4fa3",
    "Boreal Forest": "#16506e", "Temperate Forest": "#2f9140", "Tropical Forest": "#0a3b16",
    "Woodlands": "#93d15c", "Steppe-Forest": "#c7d444", "Grassland": "#f4dc4a",
    "Savannah": "#f39a30", "Chaparral": "#d93b2b", "Semi-Desert": "#cfa77c",
    "Extreme Desert": "#f5ead6", "Floodplain": "#12c4c4", "Plains": "#9e9e9e",
    "Land": "#e86bd0", "Mountains": "#7a7a7a", "": "#eeeeee",
}
OTHER = "#ff00ff"
# Never part of a band, a surge or a speckle.
NOT_BIOME = ("Water", "Ice", "Floodplain", "Alpine", "")
STAGES = [
    ("drawn", "drawn map (after reinterpret rules)"),
    ("biome4", "BIOME4 model"),
    ("calibrated", "calibrated model (kNN)"),
    ("filled", "gaps filled"),
    ("keyframe", "after alpine, upland, warp, adjacency"),
]
DEFAULTS = {
    "out": "build/critic/terrain", "years_step": 500, "edge_min": 14, "stripe_max_thick": 2,
    "stripe_min": 10, "tile_degrees": 5.0, "tile_min_hexes": 20, "flicker": 0.25, "surge": 0.5,
    "cluster_min": 6, "pad_degrees": 3.0, "top": 40,
}


def settings(cfg):
    return {**DEFAULTS, **cfg.get("critic", {})}


# ------------------------------------------------------------------ loading
def series(feats, prop, years, default=""):
    """(N, len(years)) object array of a year-keyed step-function property:
    each year takes the value of the latest key at or before it."""
    out = np.full((len(feats), len(years)), default, dtype=object)
    for i, f in enumerate(feats):
        d = f["properties"].get(prop)
        if not isinstance(d, dict) or not d:
            continue
        keys = sorted((int(k), v) for k, v in d.items())
        j, cur = 0, keys[0][1]
        for t, y in enumerate(years):
            while j < len(keys) and keys[j][0] <= y:
                cur = keys[j][1]
                j += 1
            out[i, t] = cur
    return out


def load_map(cfg):
    feats = gridmod.load_geojson(cfg["output"]["combined"])["features"]
    return gridmod.from_features(feats), feats


def all_years(cfg, step=None):
    tc = cfg["time"]
    return list(range(tc["start"], tc["end"] + 1, step or tc["step"]))


def write_stages(path, grid, frames):
    """Save {stage: {year: class per hex}} compactly for `look`."""
    names = sorted({str(v) for d in frames.values() for a in d.values() for v in np.unique(a.astype(str))})
    code = {n: i for i, n in enumerate(names)}
    out = {"ids": np.asarray(grid.ids), "classes": np.array(names)}
    for stage, d in frames.items():
        for y, a in d.items():
            out[f"{stage}|{y}"] = np.array([code[str(v)] for v in a], dtype=np.int16)
    np.savez_compressed(path, **out)


def read_stages(path, grid):
    """{stage: {year: object array}} from `write_stages`, or {} when the file
    is missing or was written for another grid."""
    if not os.path.exists(path):
        return {}
    z = np.load(path)
    if len(z["ids"]) != len(grid) or (z["ids"] != np.asarray(grid.ids)).any():
        return {}
    names = z["classes"].astype(object)
    out = defaultdict(dict)
    for k in z.files:
        if "|" in k:
            stage, y = k.split("|")
            out[stage][int(y)] = names[z[k]]
    return dict(out)


def cells(grid):
    """The grid as a 2-D array of hex indices (-1: no hex): idx[row, column],
    rows running north to south. Odd columns sit half a hex lower."""
    left, top, right, bottom = grid.bbox.T
    w = abs(left[0] - right[0]) * 3 / 4
    h = abs(top[0] - bottom[0])
    gx = np.rint((left - left.min()) / w).astype(int)
    off = np.where(gx % 2 == 0, -h / 2, 0.0)
    gy = np.rint((top - top.min() + off) / h).astype(int)
    if h > 0 and top[0] > bottom[0] and np.corrcoef(gy, top)[0, 1] > 0:
        gy = gy.max() - gy                      # make row 0 the northernmost
    idx = np.full((gy.max() + 1, gx.max() + 1), -1)
    idx[gy, gx] = np.arange(len(grid))
    return idx


def in_box(grid, box):
    c = grid.centres
    return (c[:, 0] >= box[0]) & (c[:, 0] <= box[2]) & (c[:, 1] >= box[1]) & (c[:, 1] <= box[3])


def components(mask, neighbours):
    """Connected groups of True hexes, as lists of indices."""
    seen = np.zeros(len(mask), dtype=bool)
    out = []
    for s in np.flatnonzero(mask):
        if seen[s]:
            continue
        seen[s] = True
        comp, stack = [], [s]
        while stack:
            i = stack.pop()
            comp.append(i)
            for j in neighbours[i]:
                if mask[j] and not seen[j]:
                    seen[j] = True
                    stack.append(j)
        out.append(comp)
    return out


def bbox_of(grid, hexes):
    c = grid.centres[np.asarray(hexes)]
    return [round(float(v), 1) for v in (c[:, 0].min(), c[:, 1].min(), c[:, 0].max(), c[:, 1].max())]


# ------------------------------------------------------------------ screens
def _runs(q):
    """(start, end, value) for each run of equal non-zero values in 1-D q."""
    out, i, n = [], 0, len(q)
    while i < n:
        if q[i] == 0:
            i += 1
            continue
        j = i
        while j + 1 < n and q[j + 1] == q[i]:
            j += 1
        out.append((i, j, int(q[i])))
        i = j + 1
    return out


def straight_edges(codes, ok, min_len):
    """Edges that run straight along the rows of the 2-D class array `codes`:
    at least `min_len` columns in a row where class A lies directly above
    class B, the edge staying within one row. `ok` marks the cells that
    count. Returns [(row, col0, col1, A, B)], longest first, each edge once."""
    h = codes.shape[0]
    k = int(codes.max()) + 2
    pair = np.zeros(codes.shape, dtype=int)
    a, b = codes[:-1], codes[1:]
    m = ok[:-1] & ok[1:] & (a != b)
    pair[:-1][m] = (a[m] + 1) * k + b[m] + 1
    found = []
    for y in range(h - 1):
        q = np.where(pair[y] != 0, pair[y], pair[y + 1])
        for i, j, v in _runs(q):
            if j - i + 1 >= min_len and (pair[y, i:j + 1] == v).any():
                found.append((y, i, j, v // k - 1, v % k - 1))
    found.sort(key=lambda r: r[1] - r[2])
    kept = []
    for r in found:
        y, i, j, a_, b_ = r
        dup = any(a_ == p[3] and b_ == p[4] and abs(y - p[0]) <= 1
                  and min(j, p[2]) - max(i, p[1]) + 1 > (j - i + 1) / 2 for p in kept)
        if not dup:
            kept.append(r)
    return kept


def stripes(codes, ok, max_thick, min_len):
    """Thin bands along the rows of `codes`: one class, at most `max_thick`
    cells thick with other counted classes on both sides, running across at
    least `min_len` columns (it may step a row up or down per column).
    Returns [(row at the end, col0, col1, class)], longest first."""
    h, w = codes.shape
    thin = np.zeros(codes.shape, dtype=bool)
    for x in range(w):
        y = 0
        while y < h:
            y1 = y
            while y1 + 1 < h and codes[y1 + 1, x] == codes[y, x]:
                y1 += 1
            if (ok[y, x] and y1 - y + 1 <= max_thick and y > 0 and y1 + 1 < h
                    and ok[y - 1, x] and ok[y1 + 1, x]):
                thin[y:y1 + 1, x] = True
            y = y1 + 1
    length = np.zeros(codes.shape, dtype=int)
    start = np.zeros(codes.shape, dtype=int)
    cont = np.zeros(codes.shape, dtype=bool)        # a later column carries it on
    for x in range(w):
        for y in np.flatnonzero(thin[:, x]):
            best, s, src = 0, x, None
            if x > 0:
                for yy in (y - 1, y, y + 1):
                    if (0 <= yy < h and thin[yy, x - 1] and codes[yy, x - 1] == codes[y, x]
                            and length[yy, x - 1] > best):
                        best, s, src = length[yy, x - 1], start[yy, x - 1], yy
            length[y, x], start[y, x] = best + 1, s
            if src is not None:
                cont[src, x - 1] = True
    ends = [(int(y), int(start[y, x]), int(x), int(codes[y, x]))
            for y, x in zip(*np.nonzero((length >= min_len) & ~cont))]
    ends.sort(key=lambda r: r[1] - r[2])
    kept = []
    for r in ends:
        dup = any(r[3] == p[3] and abs(r[0] - p[0]) <= max_thick + 1
                  and min(r[2], p[2]) - max(r[1], p[1]) + 1 > (r[2] - r[1] + 1) / 2 for p in kept)
        if not dup:
            kept.append(r)
    return kept


def _block_box(grid, idx, y0, y1, x0, x1):
    sub = idx[max(y0, 0):y1 + 1, max(x0, 0):x1 + 1]
    return bbox_of(grid, sub[sub >= 0])


def band_suspects(grid, idx, terrain, years, s):
    """Straight edges and thin bands, in both directions, merged over years."""
    names = sorted({v for v in np.unique(terrain.astype(str))})
    code = {n: i for i, n in enumerate(names)}
    found = {}
    for t, y in enumerate(years):
        col = np.array([code[str(v)] for v in terrain[:, t]])
        ok1 = ~np.isin(terrain[:, t].astype(str), NOT_BIOME)
        c2 = np.where(idx >= 0, col[idx], -1)
        ok2 = np.where(idx >= 0, ok1[idx], False)
        for way, cc, oo in (("east-west", c2, ok2), ("north-south", c2.T, ok2.T)):
            flip = (lambda r0, r1, a0, a1: (r0, r1, a0, a1)) if way == "east-west" else \
                   (lambda r0, r1, a0, a1: (a0, a1, r0, r1))
            for r, i, j, a, b in straight_edges(cc, oo, s["edge_min"]):
                box = _block_box(grid, idx, *flip(r, r + 2, i, j))
                sides = "above" if way == "east-west" else "west of"
                key = ("straight edge", way, f"{names[a]} {sides} {names[b]}",
                       round((box[1] + box[3]) / 2) if way == "east-west" else round((box[0] + box[2]) / 2),
                       round(box[0] / 4) if way == "east-west" else round(box[1] / 4))
                e = found.setdefault(key, {"box": box, "years": [], "length": 0})
                e["years"].append(y)
                if j - i + 1 > e["length"]:
                    e["length"], e["box"] = j - i + 1, box
            for r, i, j, a in stripes(cc, oo, s["stripe_max_thick"], s["stripe_min"]):
                box = _block_box(grid, idx, *flip(r - 2, r + 2, i, j))
                key = ("thin band", way, names[a],
                       round((box[1] + box[3]) / 2) if way == "east-west" else round((box[0] + box[2]) / 2),
                       round(box[0] / 4) if way == "east-west" else round(box[1] / 4))
                e = found.setdefault(key, {"box": box, "years": [], "length": 0})
                e["years"].append(y)
                if j - i + 1 > e["length"]:
                    e["length"], e["box"] = j - i + 1, box
    out = []
    for (kind, way, what, _, _), e in found.items():
        out.append({"kind": kind, "what": f"{what}, {way}, {e['length']} hexes long", "box": e["box"],
                    "years": sorted(set(e["years"])), "score": e["length"] * (1 + 0.1 * len(set(e["years"])))})
    return sorted(out, key=lambda r: -r["score"])


def tile_shares(grid, terrain, years, deg, min_hexes):
    """{(tx, ty): {class: [share per year]}} over land hexes, for tiles with
    at least `min_hexes` land hexes in every year."""
    c = grid.centres
    tx, ty = np.floor(c[:, 0] / deg).astype(int), np.floor(c[:, 1] / deg).astype(int)
    out = {}
    for key in sorted(set(zip(tx.tolist(), ty.tolist()))):
        m = (tx == key[0]) & (ty == key[1])
        sub = terrain[m].astype(str)
        land = sub != "Water"
        if land.sum(axis=0).min() < min_hexes:
            continue
        shares = {}
        for cls in np.unique(sub):
            if cls not in NOT_BIOME:
                shares[cls] = ((sub == cls) & land).sum(axis=0) / land.sum(axis=0)
        out[key] = shares
    return out


def surge_suspects(grid, terrain, years, s):
    """Classes whose share of a tile jumps between consecutive years of
    `years` (a surge), or jumps and comes straight back (a flicker).
    Touching tiles with the same class, year and kind are one suspect."""
    deg = s["tile_degrees"]
    hits = defaultdict(dict)                      # (kind, class, year) -> {tile: change}
    for key, shares in tile_shares(grid, terrain, years, deg, s["tile_min_hexes"]).items():
        for cls, v in shares.items():
            for t in range(1, len(years)):
                d = v[t] - v[t - 1]
                if t + 1 < len(years):
                    back = v[t] - v[t + 1]
                    if abs(d) >= s["flicker"] and abs(back) >= s["flicker"] and d * back > 0:
                        kind = "flicker: appears for one step" if d > 0 else "flicker: vanishes for one step"
                        hits[(kind, cls, years[t])][key] = (float(v[t - 1]), float(v[t]), float(v[t + 1]))
                        continue
                if abs(d) >= s["surge"]:
                    hits[("surge" if d > 0 else "collapse", cls, years[t])][key] = (float(v[t - 1]), float(v[t]))
    out = []
    for (kind, cls, year), tiles in hits.items():
        left = set(tiles)
        while left:
            group, stack = [], [left.pop()]
            while stack:
                k = stack.pop()
                group.append(k)
                for n in [(k[0] + dx, k[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]:
                    if n in left:
                        left.remove(n)
                        stack.append(n)
            box = [min(k[0] for k in group) * deg, min(k[1] for k in group) * deg,
                   (max(k[0] for k in group) + 1) * deg, (max(k[1] for k in group) + 1) * deg]
            worst = max((tiles[k] for k in group), key=lambda v: abs(v[1] - v[0]))
            prev = years[years.index(year) - 1]
            series_ = " -> ".join(f"{100 * x:.0f}%" for x in worst)
            out.append({"kind": kind, "what": f"{cls} share of land, {prev} to {year}"
                        f"{' and back' if len(worst) == 3 else ''}: {series_} in the most changed "
                        f"{deg:g}° tile ({len(group)} tile{'s' if len(group) > 1 else ''})",
                        "box": box, "years": [prev, year] + ([years[years.index(year) + 1]] if len(worst) == 3 else []),
                        "score": abs(worst[1] - worst[0]) * len(group) ** 0.5})
    return sorted(out, key=lambda r: -r["score"])


def climate_suspects(grid, terrain, climate, years, allowed, s):
    """Connected patches of a biome in a Köppen class its row of `allowed`
    ({terrain: [Köppen prefixes]}) doesn't list. Merged over years."""
    found = {}
    for t, y in enumerate(years):
        ter, cli = terrain[:, t].astype(str), climate[:, t].astype(str)
        for cls, prefixes in allowed.items():
            m = (ter == cls) & (cli != "") & (cli != "Ocean")
            bad = m & ~np.array([any(c.startswith(p) for p in prefixes) for c in cli])
            for comp in components(bad, grid.neighbours):
                if len(comp) < s["cluster_min"]:
                    continue
                box = bbox_of(grid, comp)
                top = Counter(cli[comp].tolist()).most_common(2)
                key = (cls, top[0][0][:1], round((box[0] + box[2]) / 10), round((box[1] + box[3]) / 10))
                e = found.setdefault(key, {"box": box, "years": [], "n": 0, "top": top})
                e["years"].append(y)
                e["box"] = [min(e["box"][0], box[0]), min(e["box"][1], box[1]),
                            max(e["box"][2], box[2]), max(e["box"][3], box[3])]
                if len(comp) > e["n"]:
                    e["n"], e["top"] = len(comp), top
    out = []
    for (cls, _, _, _), e in found.items():
        where = ", ".join(f"{c} ({n})" for c, n in e["top"])
        out.append({"kind": "biome in the wrong climate", "what": f"{cls} under Köppen {where}; "
                    f"largest patch {e['n']} hexes", "box": e["box"], "years": sorted(set(e["years"])),
                    "score": e["n"] * (1 + 0.1 * len(set(e["years"])))})
    return sorted(out, key=lambda r: -r["score"])


def floodplain_suspects(grid, terrain, river, years, river_class, s):
    """Hexes that are Floodplain in some year and, in another, still on a
    big river and dry but something else. Touching hexes are one suspect.
    Also returns {year: Counter of terrain on big-river hexes}."""
    ter = terrain.astype(str)
    big = river.astype(float) >= river_class
    fp = ter == "Floodplain"
    lost = big & ~fp & (ter != "Water") & fp.any(axis=1)[:, None]
    out = []
    for comp in components(lost.any(axis=1), grid.neighbours):
        if len(comp) < max(2, s["cluster_min"] // 2):
            continue
        sub = lost[comp]
        yrs = [years[t] for t in np.flatnonzero(sub.any(axis=0))]
        into = Counter(ter[comp][sub].tolist()).most_common(3)
        spans = _spans(yrs, years)
        out.append({"kind": "floodplain lost", "what": f"{len(comp)} big-river hexes that are Floodplain in other "
                    f"years are " + ", ".join(f"{c} ({n} hex-years)" for c, n in into) + f" in {spans}",
                    "box": bbox_of(grid, comp), "years": _sample(yrs),
                    "score": float(sub.sum())})
    on_river = {y: Counter(ter[big[:, t], t].tolist()) for t, y in enumerate(years) if y % 1000 == 0}
    return sorted(out, key=lambda r: -r["score"]), on_river


def _spans(yrs, years):
    """'-9000..-8200, -5000' for the runs of consecutive entries of `years` in `yrs`."""
    pos = sorted(years.index(y) for y in yrs)
    runs, a = [], pos[0]
    for p, q in zip(pos, pos[1:] + [None]):
        if q != p + 1:
            runs.append(f"{years[a]}..{years[p]}" if p > a else f"{years[a]}")
            a = q
    return ", ".join(runs)


def _sample(yrs, n=6):
    """Up to n years spread over yrs, with the first and last."""
    yrs = sorted(set(yrs))
    if len(yrs) <= n:
        return yrs
    return sorted({yrs[round(i * (len(yrs) - 1) / (n - 1))] for i in range(n)})


def speckle_suspects(grid, terrain, years, s):
    """Tiles with many lone hexes: a biome none of the six neighbours shares."""
    deg = 2 * s["tile_degrees"]
    c = grid.centres
    tx, ty = np.floor(c[:, 0] / deg).astype(int), np.floor(c[:, 1] / deg).astype(int)
    tiles = defaultdict(lambda: {"n": [], "cls": Counter()})
    nb = grid.neighbours
    for t, y in enumerate(years):
        ter = terrain[:, t].astype(str)
        cand = np.flatnonzero(~np.isin(ter, NOT_BIOME))
        lone = [i for i in cand if len(nb[i]) == 6 and all(ter[j] != ter[i] for j in nb[i])
                and sum(ter[j] != "Water" for j in nb[i]) >= 4]
        per = Counter((tx[i], ty[i]) for i in lone)
        for k, n in per.items():
            tiles[k]["n"].append((n, y))
        for i in lone:
            tiles[(tx[i], ty[i])]["cls"][ter[i]] += 1
    out = []
    for k, e in tiles.items():
        n, y = max(e["n"])
        if n < s["cluster_min"]:
            continue
        mean = sum(v for v, _ in e["n"]) / len(years)
        out.append({"kind": "speckle", "what": f"up to {n} lone hexes (at {y}; {mean:.0f} per year on average), mostly "
                    + ", ".join(f"{c}" for c, _ in e["cls"].most_common(3)),
                    "box": [k[0] * deg, k[1] * deg, (k[0] + 1) * deg, (k[1] + 1) * deg],
                    "years": _sample([yy for _, yy in sorted(e["n"], reverse=True)[:3]]), "score": float(n)})
    return sorted(out, key=lambda r: -r["score"])


def suspects(cfg, out=None):
    """Run every screen; write suspects.md and suspects.json. Returns a summary line."""
    s = settings(cfg)
    out = out or s["out"]
    os.makedirs(out, exist_ok=True)
    g, feats = load_map(cfg)
    idx = cells(g)
    fine = all_years(cfg)
    coarse = [y for y in fine if y % s["years_step"] == 0]
    kilo = [y for y in fine if y % 1000 == 0]
    ter_fine = series(feats, "terrain", fine)
    pick = lambda ys: ter_fine[:, [fine.index(y) for y in ys]]
    sections = [
        ("Straight edges and thin bands",
         "A biome edge that keeps to one row or column of hexes for a long way, or a band one or two hexes "
         "thick between two other biomes. Rows are 0.5° tall, the same as the climate model's cells, so its "
         "grid shows through where the edge warp doesn't reach. Real zonation (the Sahel) is also "
         "east-west, so look before judging.",
         band_suspects(g, idx, pick(coarse), coarse, s)),
        ("Surges and flickers",
         f"A biome's share of a {s['tile_degrees']:g}° tile changing by {100 * s['surge']:.0f} points between "
         f"keyframes 1000 years apart, or by {100 * s['flicker']:.0f} and straight back.",
         surge_suspects(g, pick(kilo), kilo, s)),
        ("Biomes in the wrong climate",
         "Patches of a biome under a Köppen class that [critic.climate] doesn't list for it. Köppen comes from "
         "the same climate model but not from the drawn maps, and its aridity is nudged toward the terrain "
         "([koeppen.nudge]), so the temperature letters are the independent part.",
         climate_suspects(g, pick(kilo), series(feats, "climate", kilo), kilo, s.get("climate", {}), s)),
    ]
    rc = cfg.get("rivers", {}).get("floodplain", {}).get("river_class", 2)
    fl, on_river = floodplain_suspects(g, ter_fine, series(feats, "river", fine, 0), fine, rc, s)
    sections.append(("Floodplains lost",
                     "Hexes on a big perennial river that are Floodplain in some years and another biome in "
                     "others while the river still runs. [rivers.floodplain] apply_to lists the biomes a "
                     "floodplain may replace; a hex whose biome leaves that list loses its floodplain.", fl))
    sections.append(("Speckle", "Lone hexes of a biome that none of their neighbours share.",
                     speckle_suspects(g, pick(kilo), kilo, s)))

    lines = ["# Terrain suspects", "",
             f"Screens over `{cfg['output']['combined']}` by `python -m pipeline suspects`. A suspect is a place "
             "and years worth looking at, not a verdict. Boxes are lon0 lat0 lon1 lat1.", ""]
    flat, n = [], 0
    for title, blurb, items in sections:
        lines += [f"## {title}", "", blurb, ""]
        if not items:
            lines += ["None.", ""]
            continue
        lines += ["| id | what | box | years | look |", "|---|---|---|---|---|"]
        for it in items[:s["top"]]:
            n += 1
            it["id"] = f"S{n:03d}"
            p = s["pad_degrees"]
            b = it["box"]
            box = [round(b[0] - p, 1), round(b[1] - p, 1), round(b[2] + p, 1), round(b[3] + p, 1)]
            it["look"] = (f".venv/bin/python -m pipeline look --name {it['id']} --box "
                          + " ".join(f"{v:g}" for v in box) + " --years " + " ".join(str(y) for y in _sample(it["years"])))
            lines.append(f"| {it['id']} | {it['kind']}: {it['what']} | {' '.join(f'{v:g}' for v in b)} | "
                         f"{_spans(it['years'], fine) if all(y in fine for y in it['years']) else it['years']} | "
                         f"`{it['look']}` |")
            flat.append({k: it[k] for k in ("id", "kind", "what", "box", "years", "score", "look")})
        if len(items) > s["top"]:
            lines.append(f"\n{len(items) - s['top']} more, lower scored, not listed.")
        lines.append("")
    lines += ["## Terrain on big-river hexes", "",
              "Dry hexes with a river of class " f"{rc} or more, by terrain, every 1000 years.", ""]
    classes = [c for c, _ in sum(on_river.values(), Counter()).most_common() if c != "Water"]
    lines += ["| terrain | " + " | ".join(str(y) for y in on_river) + " |", "|---|" + "---|" * len(on_river)]
    for c in classes:
        lines.append(f"| {c} | " + " | ".join(str(on_river[y].get(c, 0)) for y in on_river) + " |")
    with open(os.path.join(out, "suspects.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(out, "suspects.json"), "w") as f:
        json.dump(flat, f, indent=1, ensure_ascii=False)
    counts = ", ".join(f"{len(items)} {title.lower()}" for title, _, items in sections)
    return f"wrote {out}/suspects.md and suspects.json: {counts}"


# --------------------------------------------------------------------- look
def attribute(final, stages, year, gaps):
    """Per hex, the stage that set its final class at keyframe `year`."""
    get = lambda st: stages.get(st, {}).get(year)
    key, filled, drawn, b4, cal = get("keyframe"), get("filled"), get("drawn"), get("biome4"), get("calibrated")
    out = np.full(len(final), "unknown", dtype=object)
    if key is None or filled is None or drawn is None:
        return out
    gap = np.isin(drawn.astype(str), list(gaps))
    out[~gap] = "drawn"
    out[gap] = "neighbour fill"
    if b4 is not None:
        out[gap & (filled == b4)] = "BIOME4"
    if cal is not None:
        out[gap & (filled == cal) & ((b4 is None) | (cal != b4))] = "calibration"
        out[gap & (filled == cal) & (b4 is not None) & (cal == b4)] = "BIOME4 (calibration agrees)"
    out[key != filled] = "cleanup"
    out[final != key] = "after keyframes"
    return out


ATTRIBUTION = [
    ("drawn", "the drawn map, as reinterpreted"),
    ("BIOME4 (calibration agrees)", "gap: BIOME4, and the calibration agrees"),
    ("BIOME4", "gap: BIOME4 (climate unlike any drawn hex, or calibration off)"),
    ("calibration", "gap: the kNN calibration, against BIOME4"),
    ("neighbour fill", "gap with no model biome: neighbours' majority"),
    ("cleanup", "changed by alpine, upland rule, edge warp or adjacency"),
    ("after keyframes", "changed after the keyframes: sea, coasts, lakes, islands, settled land, floodplain"),
    ("unknown", "no stage record"),
]


def _table(header, rows):
    return ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + \
           ["| " + " | ".join(str(c) for c in r) + " |" for r in rows] + [""]


def _anchors(cfg, box, pad=1.0):
    """Anchor records in the box (padded): [(id, name, lon, lat, {year: [classes]}, reference)]."""
    d = cfg.get("anchors", {}).get("out_dir", "data/terrain")
    wide = [box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad]
    inside = lambda lon, lat: wide[0] <= lon <= wide[2] and wide[1] <= lat <= wide[3]
    out = {}
    p = os.path.join(d, "anchors.csv")
    if os.path.exists(p):
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                if inside(float(r["lon"]), float(r["lat"])):
                    out[r["id"]] = [r["id"], r["name"], float(r["lon"]), float(r["lat"]), {}, r.get("reference", "")]
    p = os.path.join(d, "anchor_biomes.csv")
    if os.path.exists(p):
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                if r["id"] in out and r.get("used", "1") == "1" and r["game_classes"]:
                    out[r["id"]][4].setdefault(int(r["year"]), r["game_classes"].split(";"))
    p = cfg.get("anchors", {}).get("literature", os.path.join(d, "anchors_literature.csv"))
    if os.path.exists(p):
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                if inside(float(r["lon"]), float(r["lat"])):
                    e = out.setdefault(r["id"], [r["id"], r["name"], float(r["lon"]), float(r["lat"]), {}, r["reference"]])
                    e[4][int(r["year"])] = r["game_classes"].split(";")
    return [v for v in out.values() if v[4]]


def _river_state(props, year):
    st = props.get("state")
    if isinstance(st, str):
        st = ast.literal_eval(st)
    cur = None
    for k in sorted(st, key=int):
        if int(k) <= year:
            cur = st[k]
    return cur


def _sheet(path, grid, sel, box, panels, rivers, anchors, title):
    """A grid of maps of the hexes `sel`: panels = [(title, classes per
    selected hex or None, year for the rivers or None)]."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection, PolyCollection
    from matplotlib.patches import Patch

    verts = [np.asarray(grid.rings[i]) for i in sel]
    ncol = min(len(panels), 3 if len(panels) in (3, 5, 6, 9) else 4)
    nrow = -(-len(panels) // ncol)
    aspect = 1 / np.cos(np.radians((box[1] + box[3]) / 2))
    wdeg, hdeg = box[2] - box[0], (box[3] - box[1]) * aspect
    pw = 6.4
    ph = pw * hdeg / wdeg
    fig, axes = plt.subplots(nrow, ncol, figsize=(pw * ncol, (ph + 0.45) * nrow + 1.3), squeeze=False,
                             layout="constrained")
    edge = "#00000022" if wdeg <= 25 else "none"
    seen = Counter()
    for ax, (ptitle, cls, year) in zip(axes.ravel(), panels):
        ax.set_xlim(box[0], box[2])
        ax.set_ylim(box[1], box[3])
        ax.set_aspect(aspect)
        ax.tick_params(labelsize=7, length=2)
        ax.set_title(ptitle, fontsize=11, loc="left", pad=3)
        if cls is None:
            ax.text(0.5, 0.5, "no record", transform=ax.transAxes, ha="center", color="#888888")
            continue
        seen.update(cls.tolist())
        ax.add_collection(PolyCollection(verts, facecolors=[PALETTE.get(c, OTHER) for c in cls],
                                         edgecolors=edge, linewidths=0.3, rasterized=True))
        if year is not None:
            for size_lw, style, state in ((0.5, "solid", "perennial"), (0.5, (0, (3, 2)), "seasonal")):
                segs, lws = [], []
                for f in rivers:
                    if _river_state(f["properties"], year) == state:
                        segs.append(np.asarray(f["geometry"]["coordinates"]))
                        lws.append(size_lw * int(f["properties"].get("size", 1)))
                ax.add_collection(LineCollection(segs, colors="#0b2a8a", linewidths=lws, linestyles=style))
        for n, a in enumerate(anchors, 1):
            if box[0] <= a[2] <= box[2] and box[1] <= a[3] <= box[3]:
                ax.plot(a[2], a[3], "o", ms=5, mfc="white", mec="black", mew=0.8)
                ax.annotate(str(n), (a[2], a[3]), xytext=(3, 3), textcoords="offset points", fontsize=7,
                            bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8))
    for ax in axes.ravel()[len(panels):]:
        ax.set_axis_off()
    handles = [Patch(facecolor=PALETTE.get(c, OTHER), edgecolor="#555555", label=c or "none")
               for c in PALETTE if c in seen] + \
              [Patch(facecolor=OTHER, edgecolor="#555555", label=c) for c in seen if c not in PALETTE]
    fig.legend(handles=handles, loc="outside lower left", ncol=min(len(handles), 8), frameon=False, fontsize=9)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.savefig(path, dpi=100)
    plt.close(fig)


def look(cfg, box, years=None, name=None, out=None):
    """Maps and tables for one box. Returns the list of files written."""
    s = settings(cfg)
    fine = all_years(cfg)
    years = sorted(years) if years else [y for y in fine if y % 1000 == 0]
    bad = [y for y in years if y not in fine]
    if bad:
        raise SystemExit(f"years not in the map ({fine[0]}..{fine[-1]} step {fine[1] - fine[0]}): {bad}")
    name = name or "box_" + "_".join(f"{v:g}" for v in box)
    out = out or os.path.join(s["out"], name)
    os.makedirs(out, exist_ok=True)

    g, feats = load_map(cfg)
    m = (g.bbox[:, 2] >= box[0]) & (g.bbox[:, 0] <= box[2]) & (g.bbox[:, 1] >= box[1]) & (g.bbox[:, 3] <= box[3])
    sel = np.flatnonzero(m)
    if not len(sel):
        raise SystemExit(f"no hexes in box {box}")
    sub = [feats[i] for i in sel]
    ter = series(sub, "terrain", years)
    cli = series(sub, "climate", years)
    riv = series(sub, "river", years, 0).astype(float)
    bd = cfg["output"]["build_dir"]
    stages = read_stages(os.path.join(bd, "stages.npz"), g)
    rpath = cfg.get("rivers", {}).get("geojson")
    rivers = gridmod.load_geojson(rpath)["features"] if rpath and os.path.exists(rpath) else []
    anchors = _anchors(cfg, box)
    with open(os.path.join(bd, "provenance.json")) as f:
        prov = json.load(f).get("terrain", {})
    gaps = cfg.get("paleobiome", {}).get("gaps", ["Land"])
    files = []

    label = lambda y: f"{-y:,} BCE"
    p = os.path.join(out, "years.png")
    _sheet(p, g, sel, box, [(f"{label(y)}  ({prov.get(str(y), '?')})", ter[:, t], y) for t, y in enumerate(years)],
           rivers, anchors, f"Terrain, box {' '.join(f'{v:g}' for v in box)}")
    files.append(p)
    key_years = [y for y in years if y in stages.get("keyframe", {})]
    for y in key_years:
        t = years.index(y)
        # The model has a biome under the sea too: show the final map's water.
        wet = lambda st, a: np.where(ter[:, t] == "Water", "Water", a) if st in ("biome4", "calibrated") else a
        panels = [(text, wet(st, stages[st][y][sel]) if y in stages.get(st, {}) else None, None)
                  for st, text in STAGES] + [("final map", ter[:, t], y)]
        p = os.path.join(out, f"stages_{-y}_bce.png")
        _sheet(p, g, sel, box, panels, rivers, anchors, f"{label(y)} stage by stage, box {' '.join(f'{v:g}' for v in box)}")
        files.append(p)

    L = [f"# Look: {name}", "", f"Box {' '.join(f'{v:g}' for v in box)} ({len(sel)} hexes), years "
         f"{', '.join(str(y) for y in years)}. Maps: " + ", ".join(f"`{os.path.basename(f)}`" for f in files) + ".",
         "Colours are diagnostic, not the game's. Rivers: solid perennial, dashed seasonal. Numbered dots are "
         "the anchors below.", ""]
    if not stages:
        L += ["**No stage record** (`build/stages.npz` missing or for another grid): run `make maps` or "
              "`.venv/bin/python -m pipeline build` to get the stage-by-stage maps and the attribution table.", ""]

    L += ["## Share of land by class", ""]
    land = ter != "Water"
    classes = [c for c, _ in Counter(ter[land].tolist()).most_common()]
    L += _table(["class"] + [str(y) for y in years],
                [[c] + [f"{100 * ((ter[:, t] == c).sum() / max(land[:, t].sum(), 1)):.0f}%" for t in range(len(years))]
                 for c in classes] + [["land hexes"] + [int(land[:, t].sum()) for t in range(len(years))]])

    L += ["## What changed between the years shown", ""]
    for t in range(1, len(years)):
        ch = Counter((a, b) for a, b in zip(ter[:, t - 1], ter[:, t]) if a != b)
        top = ", ".join(f"{a} → {b} {n}" for (a, b), n in ch.most_common(8))
        L.append(f"- {years[t - 1]} to {years[t]}: {sum(ch.values())} hexes change. {top}")
    L.append("")

    if key_years:
        L += ["## Which stage set each class (keyframe years)", "",
              "Hexes of each final class by the stage that last set them:", ""]
        L += [f"- **{k}**: {text}" for k, text in ATTRIBUTION[:-1]] + [""]
        for y in key_years:
            t = years.index(y)
            att = attribute(ter[:, t], {st: {y: d[y][sel]} for st, d in stages.items() if y in d}, y, gaps)
            used = [k for k, _ in ATTRIBUTION if (att == k).any()]
            rows = [[c] + [int(((ter[:, t] == c) & (att == k)).sum()) for k in used]
                    for c, _ in Counter(ter[:, t].tolist()).most_common() if c != "Water"]
            L += [f"### {y}", ""] + _table(["final class"] + used, rows)
            drawn = stages.get("drawn", {}).get(y)
            if drawn is not None:
                ch = Counter((a, b) for a, b in zip(drawn[sel].tolist(), ter[:, t].tolist()) if a != b)
                L += ["Drawn → final, where they differ: " +
                      ", ".join(f"{a} → {b} {n}" for (a, b), n in ch.most_common(10)), ""]
    other = [y for y in years if y not in key_years]
    if other:
        L += ["Years that aren't keyframes are filled between them: " +
              "; ".join(f"{y}: {prov.get(str(y), '?')}" for y in other) + ".", ""]

    L += ["## Climate under each class", "", "The two commonest Köppen classes of each terrain class's hexes.", ""]
    rows = []
    for c in classes:
        row = [c]
        for t in range(len(years)):
            k = Counter(cli[ter[:, t] == c, t].tolist()).most_common(2)
            row.append(", ".join(f"{a} {n}" for a, n in k) or "-")
        rows.append(row)
    L += _table(["class"] + [str(y) for y in years], rows)

    rc = cfg.get("rivers", {}).get("floodplain", {}).get("river_class", 2)
    if (riv >= rc).any():
        L += [f"## Terrain on big-river hexes (river class {rc}+)", ""]
        rcl = [c for c, _ in Counter(ter[riv >= rc].tolist()).most_common()]
        L += _table(["class"] + [str(y) for y in years],
                    [[c] + [int(((ter[:, t] == c) & (riv[:, t] >= rc)).sum()) for t in range(len(years))] for c in rcl])

    if anchors:
        L += ["## Anchors (pollen and literature records)", "",
              "What each record says for the nearest 500-year slice (compatible classes, best first) → what the "
              "map has on the nearest hex. ✗ marks a map class the record doesn't list. Method and caveats: "
              "`data/terrain/SOURCES.md`, `data/terrain/anchors_report.md`.", ""]
        c = g.centres[sel]
        rows = []
        for n, a in enumerate(anchors, 1):
            i = int(np.argmin((c[:, 0] - a[2]) ** 2 + (c[:, 1] - a[3]) ** 2))
            row = [n, a[1], f"{a[2]:.2f}, {a[3]:.2f}"]
            for t, y in enumerate(years):
                near = min(a[4], key=lambda k: abs(k - y))
                if abs(near - y) > 250:
                    row.append("-")
                    continue
                want, have = a[4][near], ter[i, t]
                row.append(f"{'/'.join(want)} → {have}{'' if have in want or have in ('Water', 'Floodplain') else ' ✗'}")
            rows.append(row + [a[5][:120]])
        L += _table(["#", "record", "lon, lat"] + [str(y) for y in years] + ["reference"], rows)
    else:
        L += ["## Anchors", "", "No pollen or literature anchor in or near this box.", ""]

    p = os.path.join(out, "look.md")
    with open(p, "w") as f:
        f.write("\n".join(L) + "\n")
    files.append(p)
    return "wrote " + ", ".join(files)
