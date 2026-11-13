"""Per-year property arrays: keyframes, fill strategies, sea-level overlay."""
import heapq
import os
from collections import Counter, deque

import numpy as np

from .elevation import ocean_mask, sea_level
from .grid import load_geojson


def fill(keyframes, years, strategy="hold", neighbours=None, xy=None, slowness=None):
    """Values for every year from sparse keyframes.

    keyframes: {year: array}. Returns ({year: array}, {year: provenance}).
    "hold": latest earlier keyframe (else the nearest one).
    "fronts": between two keyframes, changes spread as fronts (switch_fraction);
    outside the keyframe range, hold. `xy` and `slowness` go to switch_fraction.
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
                frac[t0, t1] = switch_fraction(keyframes[t0], keyframes[t1], neighbours, xy, slowness)
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


def _nearest(sources, allowed, neighbours, xy):
    """Straight-line distance from each `allowed` hex to the nearest of
    `sources`, found by spreading each source's identity through `allowed`
    (each hex keeps the source closest to it in a straight line among those
    its neighbours offer); -1 = unreached. Unlike hop counts, this gives
    round fronts, not the hexagons with straight sides that hops make."""
    dist = np.full(len(neighbours), -1.0)
    owner = np.full(len(neighbours), -1)
    heap = [(0.0, i, i) for i in sources]
    heapq.heapify(heap)
    while heap:
        d, i, o = heapq.heappop(heap)
        if owner[i] >= 0:
            continue
        owner[i], dist[i] = o, d
        for j in neighbours[i]:
            if allowed[j] and owner[j] < 0:
                heapq.heappush(heap, (float(np.hypot(*(xy[j] - xy[o]))), j, o))
    return dist


def switch_fraction(a, b, neighbours, xy=None, slowness=None):
    """When each hex switches from a to b, as a fraction of the interval (0, 1].

    Hexes that don't change get 0. For each target value B, the hexes
    turning into B advance as a front from hexes already B in `a`: a hex at
    distance d from the nearest one switches at (d+1)/(D+1), with D the
    furthest in its connected patch. A patch with no B next to it grows out
    from its middle instead (hexes deepest inside it switch first).

    Distance is hops through the patch, or with `xy` (hex centres in a plane,
    in hex widths) the straight-line distance to the nearest source reached
    through the patch, times `slowness` (per hex, about 1) if given, so a
    front fed from a straight edge doesn't stay straight.
    """
    n = len(a)
    changing = np.asarray(a != b)
    frac = np.zeros(n)

    def distance(src, allowed):
        if xy is None:
            return _bfs(src, allowed, neighbours).astype(float)
        d = _nearest(src, allowed, neighbours, xy)
        return np.where(d >= 0, d * (1.0 if slowness is None else slowness), -1.0)

    for target in set(b[changing]):
        s = changing & (b == target)
        src = [i for i in np.flatnonzero(s) if any(a[j] == target for j in neighbours[i])]
        dist = distance(src, s)
        # Unreached patches: depth from the patch edge, inverted.
        rest = s & (dist < 0)
        if rest.any():
            edge = [i for i in np.flatnonzero(rest)
                    if len(neighbours[i]) < 6 or any(not rest[j] for j in neighbours[i])]
            depth = distance(edge, rest)
            for comp in _components(rest, neighbours):
                dmax = depth[comp].max()
                dist[comp] = dmax - depth[comp]
        for comp in _components(s, neighbours):
            D = dist[comp].max()
            frac[comp] = (dist[comp] + 1) / (D + 1)
    return frac


def front_geometry(grid, cfg):
    """(xy, slowness) for the fronts fill from [time.fronts]: hex centres in
    hex widths with longitude shrunk by cos(latitude), and a smooth fixed
    noise field 1 + noise * value_noise. (None, None) when metric = "hops"."""
    if cfg.get("metric", "hops") != "distance":
        return None, None
    from .biome_clean import value_noise
    c = grid.centres
    w = abs(grid.bbox[0, 2] - grid.bbox[0, 0])
    xy = np.column_stack([c[:, 0] * np.cos(np.radians(c[:, 1])), c[:, 1]]) / w
    amp = cfg.get("noise", 0.0)
    slow = None
    if amp:
        period = cfg.get("noise_period", 6.0)
        n = (value_noise(xy, period, cfg.get("seed", 11)) * 0.7
             + value_noise(xy + 13.7, period / 2.3, cfg.get("seed", 11) + 1) * 0.3)
        slow = 1.0 + amp * n
    return xy, slow


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


def fill_from_neighbours(values, todo, neighbours, exclude=("Water",), default=None):
    """Give each hex in `todo` the majority value of its settled neighbours,
    growing inward until nothing changes; leftovers get `default`.

    Leftovers are hexes with no usable neighbour at all, e.g. an island the
    low sea exposes amid Water. With `default` None each takes the majority
    of the nearest ring (in hex steps, across excluded hexes) holding a
    usable value: the nearest coast's biome, not a made-up class. (This used
    to be "Plains", a placeholder that is not a biome and showed as one.)
    Only with no usable value anywhere does a hex still get "Plains"."""
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
    if default is not None:
        for i in pending:
            values[i] = default
        return values
    found = {}
    for i in pending:
        seen, ring = {i}, [i]
        while ring:
            ring = [j for k in ring for j in neighbours[k] if j not in seen and not seen.add(j)]
            c = Counter(values[j] for j in ring if j not in pending and values[j] not in exclude)
            if c:
                found[i] = max(sorted(c), key=c.__getitem__)
                break
    for i in pending:
        values[i] = found.get(i, "Plains")
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



def phases(props, years):
    """A settlement's occupation phases [(start, end)] (end exclusive, as the
    game reads them), else founding..abandoned, else founding onward."""
    occ = props.get("occupation")
    if occ:
        return [(int(a), int(b)) for a, b in occ]
    start = props["founding"] if props.get("founding") is not None else years[0]
    end = props["abandoned"] if props.get("abandoned") is not None else years[-1] + 1
    return [(int(start), int(end))]


def frame_of(year, years):
    """The frame shown at `year`: the latest frame year at or before it
    (the first frame for anything earlier)."""
    k = int(np.searchsorted(years, year, side="right")) - 1
    return years[max(k, 0)]


def alive_frames(ph, years):
    """Frame years in which any phase is occupied (the frame's span
    [frame, next frame) overlaps [start, end))."""
    nxt = list(years[1:]) + [years[-1] + (years[-1] - years[-2] if len(years) > 1 else 1)]
    return [y for y, n in zip(years, nxt) if any(a < n and b > y for a, b in ph)]


def lake_levels_at(lakes, lon, lat, year):
    """Per point (arrays lon, lat): the level of the modelled lake whose
    shoreline that year encloses it, and the lake's key ("" if none). Lake
    levels count only inside the lake: the Baltic's box also holds the
    Arctic coast, the Mega-Chad box dry desert."""
    from .raster import point_in_poly
    lon, lat = np.atleast_1d(np.asarray(lon, float)), np.atleast_1d(np.asarray(lat, float))
    level = np.full(len(lon), -np.inf)
    key = np.full(len(lon), "", dtype=object)
    for lk in lakes:
        for sh in lk.get("shapes", []):
            if sh.get("level") is None or not sh["rings"] or year < sh["from"] or (sh["to"] is not None and year >= sh["to"]):
                continue
            inside = np.zeros(len(lon), dtype=bool)
            for ring in sh["rings"]:
                r = np.asarray(ring, float)
                box = (lon >= r[:, 0].min()) & (lon <= r[:, 0].max()) & (lat >= r[:, 1].min()) & (lat <= r[:, 1].max())
                if box.any():
                    hit = np.zeros(len(lon), dtype=bool)
                    hit[box] = point_in_poly(lon[box], lat[box], r)
                    inside ^= hit                         # even-odd: islands are holes
            better = inside & (sh["level"] > level)
            level[better], key[better] = sh["level"], lk["key"]
    return level, key


def ocean_masks(elev, grid, sea, years):
    """{year: hexes connected to open ocean below that year's sea level}."""
    from .elevation import ocean_mask
    edge = np.array([len(n) < 6 for n in grid.neighbours])
    return {y: ocean_mask(elev, sea_level(y, sea["curve"]), grid.neighbours, edge, sea["seed_depth"]) for y in years}


def site_water_depth(settlements, arr, tf, cfg, lakes, grid, ocean, radius=1, coast_cap=20.0):
    """depth(n, year) for `keep_settled_land`: how deep that year's water
    stands over settlement n's ground (negative: the site is above it), and
    which water.

    Ground: the highest ETOPO1 cell within `radius` cells of the site (a
    2-arc-minute cell on a coast averages cliff and sea floor; the site is
    on the dry part), less the glacio-isostatic uplift still to come after
    the year (pipeline/isostasy.py; zero outside the Fennoscandian dome).
    Water: a modelled lake's level where that year's shoreline encloses the
    site; else global mean sea level ([sea] curve) where the site's hex is
    connected to open ocean (`ocean`, {year: mask}), or a neighbour is and
    the site's ground is within `coast_cap` m of the sea (beyond that it is
    a basin behind higher ground: the Jordan Valley next to a coastal hex);
    else none (an inland basin below sea level, as at Qattara, isn't the sea)."""
    from . import isostasy
    icfg, curve = cfg.get("isostasy"), cfg["sea"]["curve"]
    index = {h: i for i, h in enumerate(grid.ids)}
    sites = []
    for f in settlements:
        lon, lat = f["geometry"]["coordinates"][:2]
        r, c = int(round(float(tf.row(lat)))), int(round(float(tf.col(lon))))
        win = arr[max(r - radius, 0):r + radius + 1, max(c - radius, 0):c + radius + 1]
        z = float(np.nanmax(win)) if win.size and np.isfinite(win).any() else np.inf
        i = index.get(f["properties"].get("hex"))
        sites.append((lon, lat, z, i, [] if i is None else list(grid.neighbours[i])))
    cache = {}

    def depth(n, year):
        """(metres of water over the site's ground, water: "sea", a lake key, or "none")."""
        if (n, year) in cache:
            return cache[(n, year)]
        lon, lat, z, own, near = sites[n]
        if icfg:
            z = z - float(isostasy.uplift(lon, lat, year, icfg))
        lv, key = lake_levels_at(lakes, lon, lat, year)
        sea = sea_level(year, curve) - z
        if np.isfinite(lv[0]):
            out = (float(lv[0]) - z, key[0])
        elif year in ocean and own is not None and (
                ocean[year][own] or (sea <= coast_cap and any(ocean[year][j] for j in near))):
            out = (sea, "sea")
        else:
            out = (-np.inf, "none")
        cache[(n, year)] = out
        return out
    return depth


def keep_settled_land(terrain, before, settlements, grid, min_land_neighbours=1, depth=None, margin=0.0,
                      islets=False):
    """Settlements arrive on land, and leave only when the water really
    reaches them.

    `depth(n, year)` gives the water over settlement n's ground that year
    and its source (`site_water_depth`); without it, a hex turning Water
    counts as the site going under. The site is there in the frame its
    phase starts, so it was dry then: a modelled depth d0 > 0 at the start
    is the model's own error at that spot (shore sites sit within metres of
    the water). It counts as under water later only where the depth exceeds
    max(d0, 0) + `margin`.
    For each occupation phase, from the frame where it starts:
    - On land, or on Water touching at least `min_land_neighbours` land
      hexes (a shore drawn a hex off, not the site): the hex is kept land
      in every frame of the phase where the map has it Water but the site
      is above the water. The first frame where the water has risen over
      it (as above) ends the phase: abandoned to the water (`drowned` is set). A kept hex takes
      its own biome from `before` (terrain before water was overlaid) when
      that is land, else its land neighbours' majority.
    - On Water with no land neighbour: with `islets`, a site whose ground is
      above the water is on an islet too small for the grid, and its hex is
      kept land as above. Otherwise it is left alone (wrong coordinates) and
      shows in the report. If the map turns it land later, it is treated as
      on land from then.

    Returns (terrain, settlements, stats). `settlements` are copies with
    `occupation` cut and `drowned` (the first year the water ended a phase)
    set; stats has "kept" {year: hexes}, "drowned" (phases cut), "cuts"
    [(name, year, water, depth at start, depth then)] and "wet_starts"
    [(name, start frame, water, depth)]: phases that start more than
    `margin` under the modelled water, which a dated site can't be (a
    wrong water level, or wrong coordinates)."""
    import copy
    years = sorted(terrain)
    index = {h: i for i, h in enumerate(grid.ids)}
    keep = {y: set() for y in years}
    out_feats, drowned, cuts, wet_starts = [], 0, [], []
    for n, f in enumerate(settlements):
        f = copy.deepcopy(f)
        p = f["properties"]
        i = index.get(p.get("hex"))
        out_feats.append(f)
        if i is None:
            continue
        cut, new = None, []
        for a, b in phases(p, years):
            if b <= years[0] or a > years[-1]:
                new.append([a, b])
                continue
            k0 = frame_of(a, years)
            state, end, d0 = None, b, 0.0
            if depth:
                d, body = depth(n, k0)
                d0 = max(d, 0.0)
                if d > margin:
                    wet_starts.append((p.get("name", "?"), k0, body, round(d, 1)))
            for k in years:
                if k < k0 or k >= b:
                    continue
                t = terrain[k]
                wet = t[i] == "Water"
                coastal = sum(t[j] != "Water" for j in grid.neighbours[i]) >= min_land_neighbours
                if state is None:                      # the frame the phase starts: it is there
                    state = "offshore" if wet and not coastal else "on"
                    if state == "offshore" and islets and depth and depth(n, k)[0] < 0:
                        state = "on"                    # an islet too small for the grid: its hex is land
                elif not wet:
                    state = "on"                        # the map has caught up with the site
                elif state == "on" and (depth is None or depth(n, k)[0] > d0 + margin):
                    end, cut = k, k if cut is None else cut
                    if depth:
                        d, body = depth(n, k)
                        cuts.append((p.get("name", "?"), k, body, round(d0, 1), round(d, 1)))
                    break
                if wet and state == "on":
                    keep[k].add(i)
            if end > a:
                new.append([a, end])
            drowned += end < b
        if cut is not None:
            p["drowned"] = cut
            p["occupation"] = new
    out, stats = {}, {}
    for y in years:
        hits = sorted(keep[y])
        t = terrain[y]
        if hits:
            t = t.copy()
            own = before.get(y)
            todo = np.zeros(len(t), dtype=bool)
            for i in hits:
                if own is not None and own[i] not in ("Water", "Land", ""):
                    t[i] = own[i]
                else:
                    todo[i] = True
            if todo.any():
                t = fill_from_neighbours(t, todo, grid.neighbours, exclude=("Water", "Alpine"))
        out[y], stats[y] = t, len(hits)
    return out, out_feats, {"kept": stats, "drowned": drowned, "cuts": cuts, "wet_starts": wet_starts}


def in_boxes(centres, boxes):
    """Hexes centred in any of `boxes` ([lon0, lat0, lon1, lat1] each)."""
    m = np.zeros(len(centres), dtype=bool)
    for b in boxes:
        m |= ((centres[:, 0] >= b[0]) & (centres[:, 0] <= b[2])
              & (centres[:, 1] >= b[1]) & (centres[:, 1] <= b[3]))
    return m


def misdated(t, centres, rules, year, gap="Land"):
    """Drawn keyframes copied from a source map of another time, by region
    ([[terrain.misdated]]): every class except `keep` (default Water) on
    hexes centred in the rule's `boxes` becomes a biome gap, filled from the
    climate model like any other. Returns (terrain, {rule index: hexes})."""
    out, n = t, {}
    for k, r in enumerate(rules):
        if year not in r["years"]:
            continue
        m = in_boxes(centres, r["boxes"]) & ~np.isin(t, r.get("keep", ["Water"])) & (t != gap)
        if m.any():
            out = out.copy() if out is t else out
            out[m] = gap
            n[k] = int(m.sum())
    return out, n


def reinterpret(t, centres, rules, year):
    """Drawn classes the transcription got wrong, by region: each rule
    {from, to, box [lon0, lat0, lon1, lat1], years (optional [first, last])}
    turns `from` into `to` on hexes centred in the box. Returns (terrain,
    {rule index: hexes changed})."""
    out, n = t, {}
    for k, r in enumerate(rules):
        ys = r.get("years")
        if ys and not (ys[0] <= year <= ys[1]):
            continue
        b = r["box"]
        m = ((t == r["from"]) & (centres[:, 0] >= b[0]) & (centres[:, 0] <= b[2])
             & (centres[:, 1] >= b[1]) & (centres[:, 1] <= b[3]))
        if m.any():
            out = out.copy() if out is t else out
            out[m] = r["to"]
            n[k] = int(m.sum())
    return out, n
