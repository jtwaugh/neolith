"""Per-year property arrays: keyframes, fill strategies, sea-level overlay."""
import os
from collections import Counter, deque

import numpy as np

from .elevation import ocean_mask, sea_level
from .grid import load_geojson


def fill(keyframes, years, strategy="hold", neighbours=None):
    """Values for every year from sparse keyframes.

    keyframes: {year: array}. Returns ({year: array}, {year: provenance}).
    "hold": latest earlier keyframe (else the nearest one).
    "fronts": between two keyframes, changes spread as fronts (switch_fraction);
    outside the keyframe range, hold.
    """
    if strategy not in ("hold", "fronts"):
        raise ValueError(f"unknown fill strategy {strategy!r}")
    if strategy == "fronts" and neighbours is None:
        raise ValueError("fronts fill needs grid neighbours")
    ks = sorted(keyframes)
    frac = {}
    out, prov = {}, {}
    for y in years:
        if y in keyframes:
            out[y], prov[y] = keyframes[y], "keyframe"
            continue
        earlier = [k for k in ks if k <= y]
        later = [k for k in ks if k > y]
        if strategy == "fronts" and earlier and later:
            t0, t1 = earlier[-1], later[0]
            if (t0, t1) not in frac:
                frac[t0, t1] = switch_fraction(keyframes[t0], keyframes[t1], neighbours)
            switched = frac[t0, t1] <= (y - t0) / (t1 - t0)
            out[y] = np.where(switched, keyframes[t1], keyframes[t0])
            prov[y] = f"fronts {t0}..{t1}"
            continue
        src = earlier[-1] if earlier else min(ks, key=lambda k: abs(k - y))
        out[y], prov[y] = keyframes[src], f"hold {src}"
    return out, prov


def _bfs(sources, allowed, neighbours):
    """Hop distance from `sources` through hexes in `allowed`; -1 = unreached."""
    dist = np.full(len(neighbours), -1)
    q = deque(sources)
    for i in sources:
        dist[i] = 0
    while q:
        i = q.popleft()
        for j in neighbours[i]:
            if allowed[j] and dist[j] < 0:
                dist[j] = dist[i] + 1
                q.append(j)
    return dist


def switch_fraction(a, b, neighbours):
    """When each hex switches from a to b, as a fraction of the interval (0, 1].

    Hexes that don't change get 0. For each target value B, the hexes
    turning into B advance as a front from hexes already B in `a`: a hex d
    hops from the nearest one switches at (d+1)/(D+1), with D the furthest
    hop in its connected patch. A patch with no B next to it grows out from
    its middle instead (hexes deepest inside it switch first).
    """
    n = len(a)
    changing = np.asarray(a != b)
    frac = np.zeros(n)
    for target in set(b[changing]):
        s = changing & (b == target)
        src = [i for i in np.flatnonzero(s) if any(a[j] == target for j in neighbours[i])]
        dist = _bfs(src, s, neighbours)
        # Unreached patches: depth from the patch edge, inverted.
        rest = s & (dist < 0)
        if rest.any():
            edge = [i for i in np.flatnonzero(rest)
                    if len(neighbours[i]) < 6 or any(not rest[j] for j in neighbours[i])]
            depth = _bfs(edge, rest, neighbours)
            for comp in _components(rest, neighbours):
                dmax = depth[comp].max()
                dist[comp] = dmax - depth[comp]
        for comp in _components(s, neighbours):
            D = dist[comp].max()
            frac[comp] = (dist[comp] + 1) / (D + 1)
    return frac


def _components(mask, neighbours):
    seen = np.zeros(len(mask), dtype=bool)
    for i in np.flatnonzero(mask):
        if seen[i]:
            continue
        comp, q = [i], deque([i])
        seen[i] = True
        while q:
            for j in neighbours[q.popleft()]:
                if mask[j] and not seen[j]:
                    seen[j] = True
                    comp.append(j)
                    q.append(j)
        yield np.array(comp)


def legacy(grid, cfg):
    """climate/koeppen/population_density (and terrain, for comparison) from
    the committed per-epoch files. Returns {prop: {year: array}}."""
    lookup = {int(k): v for k, v in cfg["population_lookup"].items()}
    pos = {int(h): i for i, h in enumerate(grid.ids)}
    out = {p: {} for p in ("terrain", "climate", "koeppen", "population_density")}
    for y in cfg["years"]:
        path = os.path.join(cfg["dir"], f"{-y}_bce.geojson")
        n = len(grid)
        cols = {"terrain": np.empty(n, object), "climate": np.empty(n, object),
                "koeppen": np.zeros(n), "population_density": np.zeros(n)}
        for f in load_geojson(path)["features"]:
            p, i = f["properties"], pos[f["properties"]["id"]]
            cols["terrain"][i] = p["terrain"]
            cols["climate"][i] = p["climate"]
            cols["koeppen"][i] = p["koeppen"]
            idx = p.get("population_density_index")
            cols["population_density"][i] = (lookup.get(int(idx), p["population_density"])
                                              if idx is not None else p["population_density"])
        for k, v in cols.items():
            out[k][y] = v
    return out


def fill_from_neighbours(values, todo, neighbours, exclude=("Water",), default="Plains"):
    """Give each hex in `todo` the majority value of its settled neighbours,
    growing inward until nothing changes; leftovers get `default`."""
    values = values.copy()
    pending = set(np.flatnonzero(todo))
    while pending:
        settled = {}
        for i in pending:
            c = Counter(values[j] for j in neighbours[i]
                        if j not in pending and values[j] not in exclude)
            if c:
                settled[i] = max(sorted(c), key=c.__getitem__)
        if not settled:
            break
        for i, v in settled.items():
            values[i] = v
        pending -= settled.keys()
    for i in pending:
        values[i] = default
    return values


def resolve_land(terrain, biome, neighbours, gaps=("Land",)):
    """Replace `gaps` hexes (no biome in the drawn keyframe: "Land", and the
    drawn "Mountains", a landform) with `biome` (terrain names, "" = none).
    Gap hexes with no biome take their neighbours' majority, growing inward.
    Returns (terrain, stats)."""
    gap = np.isin(terrain, list(gaps))
    out = terrain.copy()
    have = gap & (biome != "")
    out[have] = biome[have]
    rest = gap & ~have
    out = fill_from_neighbours(out, rest, neighbours,
                               exclude=("Water", "Ice", "Mountains", "Alpine", "Unknown", *gaps))
    return out, {"gap": int(gap.sum()), "model": int(have.sum()),
                 "neighbours": int(rest.sum())}


def apply_alpine(terrain, mountain, cold, neighbours, keep=("Water", "Ice")):
    """One keyframe's biome on mountain hexes. Any drawn "Mountains" left (no
    model to fill them) take their neighbours' majority biome; then hexes
    that are `mountain` (landform) and `cold` (above the treeline) become
    Alpine unless the keyframe has them under `keep`. Returns (terrain, stats).
    """
    left = terrain == "Mountains"
    out = fill_from_neighbours(terrain, left, neighbours, exclude=("Water", "Ice", "Mountains"))
    covered = np.isin(out, keep)
    alpine = mountain & cold & ~covered
    out[alpine] = "Alpine"
    return out, {"mountain": int(mountain.sum()), "alpine": int(alpine.sum()),
                 "covered": int((mountain & covered).sum()), "neighbours": int(left.sum())}


def apply_sea(terrain, elev, grid, sea):
    """Overlay physical water on terrain per year. Returns (terrain, stats)."""
    edge = np.array([len(n) < 6 for n in grid.neighbours])
    ocean_now = ocean_mask(elev, 0.0, grid.neighbours, edge, sea["seed_depth"])
    out, stats = {}, {}
    for y, t in terrain.items():
        level = sea_level(y, sea["curve"])
        ocean = ocean_mask(elev, level, grid.neighbours, edge, sea["seed_depth"])
        t = t.copy()
        flooded = ocean & (t != "Water")
        t[ocean] = "Water"
        # Modern sea floor that the raster draws as Water but was dry then.
        exposed = ~ocean & ocean_now & (t == "Water")
        out[y] = fill_from_neighbours(t, exposed, grid.neighbours,
                                      exclude=("Water", "Alpine"))
        stats[y] = {"sea_level": level, "flooded": int(flooded.sum()),
                    "exposed": int(exposed.sum())}
    return out, stats
