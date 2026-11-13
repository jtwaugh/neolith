"""Lakes as a time-varying layer (data/lakes/lakes.toml).

Each lake has a seed point and a water-level curve (metres, interpolated
linearly between keys). Its extent in a year is the part of the ETOPO raster
the water reaches from the seed at that level: a minimax ("priority flood")
pass from the seed gives, for every cell in the lake's window, the level the
lake must reach to cover it. The lake can't rise above its lowest outlet
(the spill level, where the flood first reaches the window edge), so a level
above the outlet is held at the outlet instead of pouring down the valley.

Outputs:
- terrain: hexes mostly under a lake become Water; hexes the drawn maps have
  as Water inside the lake's basin, but which the lake doesn't reach that
  year, take their neighbours' land class (as for exposed sea floor);
- shorelines: closed polylines at each distinct level, for drawing the real
  shape over the hexes;
- levels per lake and year, for spillway rivers (rivers.toml `spill`).
"""
import heapq
import tomllib

import numpy as np

from .compose import fill_from_neighbours
from .raster import hex_pixels
from .rivers import simplify

NB8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def level_fn(keys):
    """[[year, metres], ...] -> year -> metres (linear, held outside)."""
    xs, ys = zip(*sorted(keys))
    return lambda y: float(np.interp(y, xs, ys))


def cell_km2(tf, rows):
    """Area (km²) of a raster cell in each of `rows` (absolute row indices)."""
    lat = np.radians(tf.y0 + np.asarray(rows) * tf.e)
    return abs(tf.a * 111.32) * abs(tf.e * 110.57) * np.cos(lat)


def split_ties(need, order):
    """Cells sharing a whole-metre `need` get fractions of that metre in flood
    order, so a flat floor fills ring by ring instead of all at once."""
    o = np.asarray(order)
    v = need.ravel()[o]
    start = np.r_[0, np.flatnonzero(v[1:] != v[:-1]) + 1]
    size = np.diff(np.r_[start, len(v)])
    rank = np.arange(len(v)) - np.repeat(start, size)
    out = need.copy()
    out.ravel()[o] = v + rank / np.repeat(size, size) * 0.999
    return out


def area_fn(need, km2):
    """area (km²) -> the lowest level at which the lake covers at least that
    area (-inf for no lake, inf if the window can't hold it). `km2` is the
    cell area per row of `need`."""
    a = np.broadcast_to(km2[:, None], need.shape).ravel()
    v = need.ravel()
    ok = np.isfinite(v)
    order = np.argsort(v[ok], kind="stable")
    lv = v[ok][order]
    cum = np.cumsum(a[ok][order])

    # Total area at each distinct level (the DEM is in whole metres, so a
    # flat floor floods in big steps): pick the level whose area is nearest
    # the target by ratio, rather than the first one past it.
    last = np.r_[lv[1:] != lv[:-1], True]
    lvls, areas = lv[last], cum[last]

    def f(area):
        if area <= 0:
            return -np.inf
        k = int(np.searchsorted(areas, area))
        if k >= len(lvls):
            return np.inf
        if k > 0 and area / areas[k - 1] < areas[k] / area:
            k -= 1
        return float(lvls[k])
    return f


def covered_km2(need, km2, level):
    return float(((need <= level) * km2[:, None]).sum())


def dam_cells(line, tf, rs, cs):
    """Window (row, col) cells along a polyline, 4-connected so the 8-way
    flood can't slip through diagonally."""
    out = []
    for (x0, y0), (x1, y1) in zip(line, line[1:]):
        n = int(max(abs(tf.col(x1) - tf.col(x0)), abs(tf.row(y1) - tf.row(y0))) * 4) + 2
        prev = None
        for t in np.linspace(0, 1, n):
            r = int(round(tf.row(y0 + (y1 - y0) * t))) - rs.start
            c = int(round(tf.col(x0 + (x1 - x0) * t))) - cs.start
            if prev and prev[0] != r and prev[1] != c:
                out.append((prev[0], c))
            out.append((r, c))
            prev = (r, c)
    return out


def window(arr, tf, box):
    """Row/col slices of the raster covering box = [lon0, lat0, lon1, lat1]."""
    c0, c1 = sorted((int(np.floor(tf.col(box[0]))), int(np.ceil(tf.col(box[2])))))
    r0, r1 = sorted((int(np.floor(tf.row(box[3]))), int(np.ceil(tf.row(box[1])))))
    return (slice(max(r0, 0), min(r1 + 1, arr.shape[0])),
            slice(max(c0, 0), min(c1 + 1, arr.shape[1])))


def minimax(z, seed, order=None, outlet=None, route=None):
    """For each cell, the lowest water level at which a lake started at
    `seed` (row, col) covers it, and the spill level: the level at which the
    lake first reaches the window edge (inf if never). If `order` is a list,
    the cells' flat indices are appended to it in flood order (ties spread
    outward first-in, first-out). `outlet`, a boolean mask, limits where the
    lake can spill (default: anywhere on the window edge). If `route` is a
    dict, route["saddle"] is set to the spill point: the highest cell on the
    flood's way from the seed to the outlet it first reaches (None if it
    never spills)."""
    h, w = z.shape
    need = np.full(z.shape, np.inf)
    sr, sc = seed
    need[sr, sc] = z[sr, sc]
    heap = [(z[sr, sc], 0, sr, sc)]
    seq = 0
    done = np.zeros(z.shape, dtype=bool)
    spill = np.inf
    prev = np.full(z.shape, -1, dtype=np.int64) if route is not None else None
    if route is not None:
        route["saddle"] = None
    while heap:
        lv, _, r, c = heapq.heappop(heap)
        if done[r, c]:
            continue
        done[r, c] = True
        if order is not None:
            order.append(r * w + c)
        if spill == np.inf and (outlet[r, c] if outlet is not None else (r in (0, h - 1) or c in (0, w - 1))):
            spill = lv
            if route is not None:
                # Back along the way the flood came; the saddle is the
                # cell nearest the seed at the spill level.
                k, sad = r * w + c, (r, c)
                while k >= 0:
                    rr, cc = divmod(int(k), w)
                    if z[rr, cc] >= spill:
                        sad = (rr, cc)
                    k = prev[rr, cc]
                route["saddle"] = sad
        for dr, dc in NB8:
            a, b = r + dr, c + dc
            if 0 <= a < h and 0 <= b < w and not done[a, b]:
                v = max(lv, z[a, b])
                if v < need[a, b]:
                    need[a, b] = v
                    if prev is not None:
                        prev[a, b] = r * w + c
                    seq += 1
                    heapq.heappush(heap, (v, seq, a, b))
    return need, spill


def outflow_path(z, need, spill, sea, outlet, saddle, relief=5.0):
    """The river out of a lake held at its outlet: (row, col) cells from the
    spill point (the saddle: the cell at the spill level the lake's flood
    crosses to reach an outlet) down to the sea, or None.

    The way down is a least-cost path over the cells outside the lake's
    basin (need >= spill) and no higher than the spill (water runs
    downhill from it) to a cell below `sea` connected to an `outlet`
    cell (open sea at the window edge) through other cells below `sea`.
    Each step costs its length times 1 + (height above the sea) / `relief`,
    so the path keeps to valley floors and the shortest way to the coast."""
    from scipy import ndimage
    h, w = z.shape
    if saddle is None or not np.isfinite(spill):
        return None
    lab, _ = ndimage.label(z < sea, structure=np.ones((3, 3)))
    ids = np.unique(lab[outlet & (lab > 0)])
    target = np.isin(lab, ids[ids > 0])
    if not target.any():
        target = outlet
    # Not along the lake's rim: cells next to the lake (other than near the
    # saddle) are its shore, and a path along them never leaves the basin.
    lake = need < spill
    rim = ndimage.binary_dilation(lake, structure=np.ones((3, 3))) & ~lake
    rows, cols = np.mgrid[0:h, 0:w]
    near = np.maximum(abs(rows - saddle[0]), abs(cols - saddle[1])) <= 2
    ok = (need >= spill) & (z <= spill) & ~(rim & ~near)
    start = tuple(saddle)
    dist = np.full(z.shape, np.inf)
    prev = np.full(z.shape, -1, dtype=np.int64)
    dist[start] = 0.0
    heap = [(0.0, start[0], start[1])]
    end = None
    while heap:
        d, r, c = heapq.heappop(heap)
        if d > dist[r, c]:
            continue
        if target[r, c]:
            end = (r, c)
            break
        for dr, dc in NB8:
            a, b = r + dr, c + dc
            if 0 <= a < h and 0 <= b < w and (ok[a, b] or target[a, b]):
                nd = d + np.hypot(dr, dc) * (1.0 + max(z[a, b] - sea, 0.0) / relief)
                if nd < dist[a, b]:
                    dist[a, b], prev[a, b] = nd, r * w + c
                    heapq.heappush(heap, (nd, a, b))
    if end is None:
        return None
    path, k = [], end[0] * w + end[1]
    while k >= 0:
        path.append(divmod(int(k), w))
        k = prev[path[-1]]
    return path[::-1]


def contours(mask):
    """Closed rings (as (row, col) float arrays) around the True cells of a
    boolean grid: marching squares on cell centres, so ring vertices lie
    halfway between a wet and a dry cell."""
    m = np.pad(mask, 1)
    h, w = m.shape
    # Edge midpoints in doubled integer coordinates (2r, 2c) of the padded grid.
    segs = {}

    def link(a, b):
        segs.setdefault(a, []).append(b)
        segs.setdefault(b, []).append(a)

    tl, tr, br, bl = m[:-1, :-1], m[:-1, 1:], m[1:, 1:], m[1:, :-1]
    code = tl * 8 + tr * 4 + br * 2 + bl * 1
    for r, c in zip(*np.nonzero((code > 0) & (code < 15))):
        k = code[r, c]
        top, right = (2 * r, 2 * c + 1), (2 * r + 1, 2 * c + 2)
        bottom, left = (2 * r + 2, 2 * c + 1), (2 * r + 1, 2 * c)
        pairs = {1: [(left, bottom)], 2: [(bottom, right)], 3: [(left, right)],
                 4: [(top, right)], 5: [(left, top), (bottom, right)],
                 6: [(top, bottom)], 7: [(left, top)], 8: [(left, top)],
                 9: [(top, bottom)], 10: [(top, right), (left, bottom)],
                 11: [(top, right)], 12: [(left, right)], 13: [(bottom, right)],
                 14: [(left, bottom)]}[k]
        for a, b in pairs:
            link(a, b)
    rings = []
    while segs:
        start = next(iter(segs))
        ring, prev, cur = [start], None, start
        while True:
            nxt = [p for p in segs[cur] if p != prev]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            segs[prev].remove(cur)
            segs[cur].remove(prev)
            if not segs[prev]:
                del segs[prev]
            if cur == start:
                break
            ring.append(cur)
        for p in ring:
            if p in segs and not segs[p]:
                del segs[p]
        # Back to unpadded cell coordinates.
        rings.append(np.array(ring, dtype=float) / 2.0 - 1.0)
    return rings


def build(cfg, grid, terrain, arr, tf, years, log=print):
    """Apply lakes to `terrain` ({year: array}). Returns (terrain, lakes)
    where lakes is a list of dicts: key, name, level {year: metres
    (effective)}, raw {year: metres (curve)}, spill, shapes [{level,
    rings, from, to}]."""
    lcfg = cfg["lakes"]
    with open(lcfg["catalogue"], "rb") as f:
        cat = tomllib.load(f)["lake"]
    out = {y: t.copy() for y, t in terrain.items()}
    lakes = []
    for lk in cat:
        if lk.get("level") == "sea-or-outlet":
            lakes.append(_sea_or_outlet(lk, cfg, grid, out, arr, tf, years, log))
            continue
        rs, cs = window(arr, tf, lk["box"])
        z = np.nan_to_num(arr[rs, cs].astype(np.float64), nan=1e9)
        if "dam" in lk:
            # A barrier the modern DEM no longer shows (a dune dam, say).
            for r, c in dam_cells(lk["dam"]["line"], tf, rs, cs):
                if 0 <= r < z.shape[0] and 0 <= c < z.shape[1]:
                    z[r, c] = max(z[r, c], lk["dam"]["top"])
        seed = (int(round(tf.row(lk["seed"][1]))) - rs.start,
                int(round(tf.col(lk["seed"][0]))) - cs.start)
        order = [] if "area" in lk else None
        need, spill = minimax(z, seed, order)
        if order:
            need = split_ties(need, order)
        km2 = cell_km2(tf, np.arange(rs.start, rs.stop))
        if ("level" in lk) == ("area" in lk):
            raise ValueError(f"lake {lk['key']}: give exactly one of level or area")
        if "level" in lk:
            curve = level_fn(lk["level"])
        else:
            # Target area (km²): the level that floods that much from the seed.
            to_level, by_area = area_fn(need, km2), level_fn(lk["area"])
            curve = lambda y: to_level(by_area(y))  # noqa: E731
        raw = {y: curve(y) for y in years}
        # Held just under the outlet, so the flood doesn't run out of it.
        eff = {y: min(v, spill - 0.5) for y, v in raw.items()}
        # `until`: from that year the lake is no longer a lake (e.g. it has
        # joined the ocean): no shoreline, and the terrain is left to the sea.
        until = lk.get("until")
        if until is not None:
            eff = {y: (-np.inf if y >= until else v) for y, v in eff.items()}
        if "area" in lk:
            want = max(level_fn(lk["area"])(y) for y in years)
            got = max(covered_km2(need, km2, v) for v in eff.values())
            if got < 0.9 * want:
                log(f"lakes: {lk['name']}: WARNING the window holds only {got:.0f} km² "
                    f"below its {spill:.0f} m outlet (target {want:.0f} km²)")

        # Hexes in the window and their raster cells (window-relative).
        b = grid.bbox
        box = lk["box"]
        in_box = np.flatnonzero((b[:, 2] > box[0]) & (b[:, 0] < box[2]) &
                                (b[:, 1] > box[1]) & (b[:, 3] < box[3]))
        cells = {}
        for i in in_box:
            rr, cc = hex_pixels(grid.rings[i], grid.bbox[i], tf, arr.shape)
            ok = (rr >= rs.start) & (rr < rs.stop) & (cc >= cs.start) & (cc < cs.stop)
            if ok.any():
                cells[i] = (rr[ok] - rs.start, cc[ok] - cs.start)

        def wet_hexes(level):
            return np.array([i for i, (rr, cc) in cells.items()
                             if (need[rr, cc] <= level).mean() >= lcfg["hex_fraction"]], dtype=int)

        top = max(eff.values())
        # The basin: what the lake covers at its highest, plus drawn Water
        # the water could reach a little above that (drawn shorelines differ).
        margin = lk.get("basin_margin", lcfg["basin_margin"])
        basin = set(wet_hexes(top + margin).tolist())
        cache, stats = {}, []
        for y in years:
            if until is not None and y >= until:
                continue
            lv = round(eff[y], 1) if np.isfinite(eff[y]) else eff[y]
            if lv not in cache:
                cache[lv] = wet_hexes(lv)
            wet = np.zeros(len(grid), dtype=bool)
            wet[cache[lv]] = True
            t = out[y]
            was_water = t == "Water"
            exposed = np.zeros(len(grid), dtype=bool)
            exposed[list(basin)] = True
            exposed &= was_water & ~wet
            t[wet] = "Water"
            out[y] = fill_from_neighbours(t, exposed, grid.neighbours,
                                          exclude=("Water", "Alpine"))
            stats.append((y, int(wet.sum()), int(exposed.sum())))

        # Shorelines: a new shape when the level moves by shore_step or more.
        shapes, last = [], None
        for y in years:
            lv = eff[y]
            if last is None or (lv != last and not abs(lv - last) < lcfg["shore_step"]):
                rings = []
                for ring in (contours(need <= lv) if np.isfinite(lv) else []):
                    if len(ring) < lcfg["min_ring_cells"]:
                        continue
                    lonlat = np.column_stack([tf.x0 + (ring[:, 1] + cs.start) * tf.a,
                                              tf.y0 + (ring[:, 0] + rs.start) * tf.e])
                    lonlat = simplify(np.vstack([lonlat, lonlat[:1]]), lcfg["simplify"])
                    if len(lonlat) >= 4:
                        rings.append(lonlat)
                if shapes:
                    shapes[-1]["to"] = y
                shapes.append({"level": round(lv, 1) if np.isfinite(lv) else None,
                               "rings": rings, "from": y, "to": None})
                last = lv
        lo = min(s[1] for s in stats)
        hi = max(s[1] for s in stats)
        wet = [v for v in eff.values() if np.isfinite(v)]
        if not wet:
            log(f"lakes: {lk['name']}: WARNING never present")
            wet = [top]
        log(f"lakes: {lk['name']}: spill {spill:.0f} m, level {min(wet):.0f}"
            f"–{max(wet):.0f} m, up to {covered_km2(need, km2, max(wet)):.0f} km², "
            f"{lo}–{hi} hexes, {len(shapes)} shorelines")
        lakes.append({"key": lk["key"], "name": lk["name"], "spill": spill,
                      "level": eff, "raw": raw, "shapes": shapes})
    return out, lakes


def write_geojson(path, lakes):
    import json
    feats = []
    for lk in lakes:
        for k, s in enumerate(lk["shapes"]):
            if not s["rings"]:
                continue
            feats.append({
                "type": "Feature",
                "geometry": {"type": "MultiLineString",
                             "coordinates": [[[round(float(x), 4), round(float(y), 4)] for x, y in r]
                                             for r in s["rings"]]},
                "properties": {"lake": lk["key"], "name": lk["name"], "level": s["level"],
                               "from": s["from"], "to": s["to"]},
            })
    with open(path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f)


def _sea_or_outlet(lk, cfg, grid, out, arr, tf, years, log):
    """A basin that is open sea when the global sea can get in and otherwise
    a lake held at its lowest outlet (the Baltic), on a surface corrected for
    glacio-isostatic uplift (pipeline/isostasy.py). Recomputed every year:
    the uplift moves the outlets. Updates `out` in place; returns the lake
    dict. Ice hexes are left alone. Only adds Water (the sea step already
    handles the open sea), and draws a shoreline only in lake stages."""
    from . import isostasy
    from .compose import sea_level

    lcfg, icfg = cfg["lakes"], cfg["isostasy"]
    k = int(lk.get("downsample", 1))
    rs, cs = window(arr, tf, lk["box"])
    z = np.nan_to_num(arr[rs, cs].astype(np.float64), nan=1e9)
    h, w = (z.shape[0] // k) * k, (z.shape[1] // k) * k
    # Block minimum keeps narrow straits open at the coarser resolution.
    z = z[:h, :w].reshape(h // k, k, w // k, k).min(axis=(1, 3))
    tfk = type(tf)(tf.a * k, tf.e * k, tf.x0 + (cs.start + (k - 1) / 2) * tf.a,
                   tf.y0 + (rs.start + (k - 1) / 2) * tf.e)
    # Outlets: window-edge cells in today's open sea (an edge on land isn't
    # a way out).
    outlet = np.zeros(z.shape, dtype=bool)
    outlet[[0, -1], :] = True
    outlet[:, [0, -1]] = True
    outlet &= z < lk.get("outlet_depth", -20.0)
    rows, cols = np.mgrid[0:z.shape[0], 0:z.shape[1]]
    lon, lat = tfk.x0 + cols * tfk.a, tfk.y0 + rows * tfk.e
    rate = isostasy.rate(lon, lat, icfg) * icfg["scale"] * icfg["tau"]
    # One dam or a list of them, each with its own `from`/`until` years.
    dams = lk.get("dam", [])
    dams = [dams] if isinstance(dams, dict) else dams
    dams = [(d, [(r, c) for r, c in dam_cells(d["line"], tfk, slice(0, z.shape[0]), slice(0, z.shape[1]))
                 if 0 <= r < z.shape[0] and 0 <= c < z.shape[1]]) for d in dams]
    seed = (int(round(tfk.row(lk["seed"][1]))), int(round(tfk.col(lk["seed"][0]))))

    b = grid.bbox
    box = lk["box"]
    cells = {}
    for i in np.flatnonzero((b[:, 2] > box[0]) & (b[:, 0] < box[2]) & (b[:, 1] > box[1]) & (b[:, 3] < box[3])):
        rr, cc = hex_pixels(grid.rings[i], grid.bbox[i], tfk, z.shape)
        if len(rr):
            cells[i] = (rr, cc)

    # `clear`: for hexes centred in its box, from its year, the model is
    # authoritative: drawn Water it doesn't reach becomes land (modern sea
    # floor excepted).
    clear = lk.get("clear")
    clearable = np.zeros(len(grid), dtype=bool)
    if clear:
        cb = clear["box"]
        cx, cy = (b[:, 0] + b[:, 2]) / 2, (b[:, 1] + b[:, 3]) / 2
        for i in np.flatnonzero((cx > cb[0]) & (cx < cb[2]) & (cy > cb[1]) & (cy < cb[3])):
            rr, cc = hex_pixels(grid.rings[i], grid.bbox[i], tf, arr.shape)
            if len(rr) and np.nanmedian(arr[rr, cc]) > 0:
                clearable[i] = True

    start, until = lk.get("from"), lk.get("until")
    eff, shapes, last, last_year, last_kind, stats = {}, [], None, None, None, []
    out_paths, outflow = {}, {}
    for y in years:
        if (start is not None and y < start) or (until is not None and y >= until):
            eff[y] = -np.inf
            if shapes and shapes[-1]["to"] is None:
                shapes[-1]["to"] = y
            continue
        zy = z - rate * np.expm1((1950 - y) / 1000.0 / icfg["tau"])
        for d, dcells in dams:
            if (d.get("from") is None or y >= d["from"]) and (d.get("until") is None or y < d["until"]):
                for r, c in dcells:
                    zy[r, c] = max(zy[r, c], d["top"])
        # The ice sheet dams the water: no flow through the board's Ice hexes
        # (until `ice_until`, when the drawn ice no longer matches the
        # dated deglaciation).
        if lk.get("ice_until") is None or y < lk["ice_until"]:
            for i in np.flatnonzero(out[y] == "Ice"):
                if i in cells:
                    zy[cells[i]] = 1e4
        route = {}
        need, spill = minimax(zy, seed, outlet=outlet, route=route)
        g = sea_level(y, cfg["sea"]["curve"])
        lake = g < spill
        lv = spill - 0.5 if lake else g
        eff[y] = lv
        t = out[y]
        wet = np.zeros(len(grid), dtype=bool)
        for i, (rr, cc) in cells.items():
            wet[i] = (need[rr, cc] <= lv).mean() >= lcfg["hex_fraction"]
        wet &= t != "Ice"
        t[wet] = "Water"
        if clear and y >= clear.get("from", -np.inf):
            drop = clearable & (t == "Water") & ~wet
            out[y] = t = fill_from_neighbours(t, drop, grid.neighbours,
                                              exclude=("Water", "Alpine"))
        stats.append((y, "lake" if lake else "sea", round(lv, 1), int(wet.sum())))
        # The river out of the lake (`outflow`): one path per spill point,
        # traced in the first year that point is the outlet.
        if lake and lk.get("outflow"):
            if route["saddle"] is not None:
                key = tuple(int(v) for v in route["saddle"])
                if key not in out_paths:
                    cells_ = outflow_path(zy, need, spill, g, outlet, key)
                    out_paths[key] = None if cells_ is None else np.column_stack(
                        [tfk.x0 + np.array([c for _, c in cells_]) * tfk.a,
                         tfk.y0 + np.array([r for r, _ in cells_]) * tfk.e])
                outflow[y] = key
        # A shoreline in lake stages only; a new shape when the level moves
        # or every `shore_years` (the uplift reshapes it).
        if (last is None or lake != last_kind or abs(lv - last) >= lcfg["shore_step"]
                or y - last_year >= lcfg.get("shore_years", 500)):
            rings = []
            if lake:
                # No shoreline across the ice sheet.
                shore = need <= lv
                for i in np.flatnonzero(t == "Ice"):
                    if i in cells:
                        shore[cells[i]] = False
                for ring in contours(shore):
                    if len(ring) < lcfg["min_ring_cells"] // max(k, 1):
                        continue
                    ll = np.column_stack([tfk.x0 + ring[:, 1] * tfk.a, tfk.y0 + ring[:, 0] * tfk.e])
                    ll = simplify(np.vstack([ll, ll[:1]]), lcfg["simplify"])
                    if len(ll) >= 4:
                        rings.append(ll)
            if shapes:
                shapes[-1]["to"] = y
            shapes.append({"level": round(lv, 1), "rings": rings, "from": y, "to": None})
            last, last_year, last_kind = lv, y, lake
    if until is not None and shapes:
        shapes[-1]["to"] = until
    phases, prev = [], None
    for y, kind, lv, n in stats:
        if kind != prev:
            phases.append(f"{kind} from {y} ({lv:.0f} m, {n} hexes)")
            prev = kind
    log(f"lakes: {lk['name']}: " + "; ".join(phases))
    res = {"key": lk["key"], "name": lk["name"], "spill": np.inf,
           "level": eff, "raw": eff, "shapes": shapes}
    if lk.get("outflow"):
        # [(points, years)] per spill point the lake drained over.
        res["outflow"] = [(pts, sorted(y for y, k in outflow.items() if k == key))
                          for key, pts in out_paths.items() if pts is not None]
        res["outflow_cfg"] = lk["outflow"]
        for key, pts in out_paths.items():
            ys = sorted(y for y, k in outflow.items() if k == key)
            where = "no way down" if pts is None else f"{pts[0][0]:.2f}E {pts[0][1]:.2f}N to {pts[-1][0]:.2f}E {pts[-1][1]:.2f}N"
            log(f"lakes: {lk['name']} outflow {ys[0]}..{ys[-1]}: {where}")
    return res
