"""Rivers as time-varying polylines (data/rivers/rivers.toml).

Each catalogued river is either traced downstream along the GEOGLOWS v2
(TDX-Hydro) stream network from a
headwater point (`from`, optionally stopping near `to`) or given as
hand-entered waypoints (`points`). Rivers that reach the sea are extended
across the shelf exposed at the lowest sea level of the run, following the
lowest spill path in the ETOPO raster (priority flood). Each year a river
ends where it runs into that year's Water hexes, so shelf reaches appear and
drown with the sea-level curve; the catalogue's `state` keys say when a river
is perennial, seasonal or absent.

Outputs: river segments (each with a fixed course and a `state` step
function) for build/rivers.geojson, and a per-hex `river` class per year
(0 none, 1 minor or seasonal, 2 major perennial).
"""
import heapq
import json
import tomllib
from collections import deque

import numpy as np

STATES = ("absent", "seasonal", "perennial")


# ------------------------------------------------------------ GEOGLOWS v2

def load_reaches(cfg, box, sea_hex=None):
    """Reaches with at least `min_upland` km² upstream inside `box`
    (lon0, lat0, lon1, lat1), from the GEOGLOWS v2 / TDX-Hydro streams
    (pipeline/geoglows.py). Cached."""
    from . import geoglows
    return geoglows.load(cfg, box, sea_hex)


def nearest_reach(r, point, min_upland=0.0):
    """Index of the reach passing closest to `point` with enough upland."""
    best, bd = None, np.inf
    p = np.asarray(point)
    for i in np.flatnonzero(r["upland"] >= min_upland):
        c = r["coords"][i]
        if abs(c[:, 0].mean() - p[0]) > 3 or abs(c[:, 1].mean() - p[1]) > 3:
            continue
        d = np.min(np.hypot(c[:, 0] - p[0], c[:, 1] - p[1]))
        if d < bd:
            best, bd = i, d
    if best is None:
        raise ValueError(f"no reach with upland >= {min_upland} km² near {point}")
    return best, bd


def trace(r, start, to=None, stop=()):
    """Points from reach `start` downstream to the outlet, to the point
    nearest `to`, or to the confluence with a reach in `stop` (already
    drawn by another river). Returns (points, reaches_sea, reaches used)."""
    index = r.get("_index")
    if index is None:
        index = r["_index"] = {rid: i for i, rid in enumerate(r["id"])}
    out, i, used = [], start, []
    sea = False
    while True:
        used.append(i)
        c = r["coords"][i]
        out.append(c if not out else c[1:])
        n = r["next"][i]
        if n == 0 or n not in index or index[n] in used:
            sea = n == 0 and r["endorheic"][i] == 0
            break
        i = index[n]
        if i in stop:
            out.append(r["coords"][i][:1])
            break
    pts = np.concatenate(out)
    if to is not None:
        k = int(np.argmin(np.hypot(pts[:, 0] - to[0], pts[:, 1] - to[1])))
        return pts[:k + 1], False, used
    return pts, sea, used


# --------------------------------------------------------------- geometry

def simplify(pts, tol):
    """Douglas-Peucker."""
    if len(pts) < 3:
        return pts
    keep = np.zeros(len(pts), dtype=bool)
    keep[[0, -1]] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        seg = pts[b] - pts[a]
        rel = pts[a + 1:b] - pts[a]
        n = np.hypot(*seg)
        d = (np.abs(seg[0] * rel[:, 1] - seg[1] * rel[:, 0]) / n if n
             else np.hypot(rel[:, 0], rel[:, 1]))
        k = int(np.argmax(d))
        if d[k] > tol:
            m = a + 1 + k
            keep[m] = True
            stack += [(a, m), (m, b)]
    return pts[keep]


def resample(pts, step):
    """Points every `step` degrees along the line (ends kept)."""
    seg = np.hypot(*np.diff(pts, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    if s[-1] == 0:
        return pts[:1]
    t = np.linspace(0, s[-1], max(2, int(np.ceil(s[-1] / step)) + 1))
    return np.column_stack([np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])])


def shelf_path(mouth, arr, tf, level, window, max_z=50.0):
    """Cells from `mouth` down the lowest spill path to sea at `level`
    (priority flood from the open sea inside a window around the mouth).
    Returns (lon, lat) points, starting at the mouth; empty if the mouth is
    already at sea at that level."""
    c0 = int(round(tf.col(mouth[0])))
    r0 = int(round(tf.row(mouth[1])))
    k = int(round(window / abs(tf.a)))
    ra, rb = max(r0 - k, 0), min(r0 + k + 1, arr.shape[0])
    ca, cb = max(c0 - k, 0), min(c0 + k + 1, arr.shape[1])
    z = np.nan_to_num(arr[ra:rb, ca:cb].astype(np.float64), nan=1e9)
    h, w = z.shape
    mr, mc = r0 - ra, c0 - ca
    if not (0 <= mr < h and 0 <= mc < w):
        return np.zeros((0, 2))
    sea = z < level
    # Open sea: below-level cells connected to the window edge or very deep water.
    open_ = np.zeros_like(sea)
    q = deque()
    for rr, cc in zip(*np.nonzero(sea)):
        if rr in (0, h - 1) or cc in (0, w - 1) or z[rr, cc] < -500:
            open_[rr, cc] = True
            q.append((rr, cc))
    nb8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    while q:
        rr, cc = q.popleft()
        for dr, dc in nb8:
            a, b = rr + dr, cc + dc
            if 0 <= a < h and 0 <= b < w and sea[a, b] and not open_[a, b]:
                open_[a, b] = True
                q.append((a, b))
    if open_[mr, mc]:
        return np.zeros((0, 2))
    recv = np.full((h, w, 2), -1, dtype=np.int32)
    done = open_.copy()
    heap = [(z[rr, cc], rr, cc) for rr, cc in zip(*np.nonzero(open_))]
    heapq.heapify(heap)
    while heap and not done[mr, mc]:
        zz, rr, cc = heapq.heappop(heap)
        for dr, dc in nb8:
            a, b = rr + dr, cc + dc
            if 0 <= a < h and 0 <= b < w and not done[a, b] and z[a, b] < max_z:
                done[a, b] = True
                recv[a, b] = (rr, cc)
                heapq.heappush(heap, (max(z[a, b], zz), a, b))
    if not done[mr, mc]:
        return np.zeros((0, 2))
    path = [(mr, mc)]
    while not open_[path[-1]]:
        path.append(tuple(recv[path[-1]]))
    rows = np.array([p[0] for p in path]) + ra
    cols = np.array([p[1] for p in path]) + ca
    return np.column_stack([tf.x0 + cols * tf.a, tf.y0 + rows * tf.e])


# ------------------------------------------------------------------- hexes

class HexLocator:
    """Point -> hex index: on a regular hex grid the containing hex is the
    one with the nearest centre."""

    def __init__(self, grid):
        b = grid.bbox
        self.w = abs(b[0, 2] - b[0, 0])
        self.h = abs(b[0, 1] - b[0, 3])
        self.c = grid.centres
        x0 = self.c[:, 0].min()
        self.x0 = x0
        self.gx = np.rint((self.c[:, 0] - x0) / (0.75 * self.w)).astype(int)
        self.cells = {}
        for i, (gx, y) in enumerate(zip(self.gx, self.c[:, 1])):
            self.cells[(gx, int(np.rint(y / self.h * 2)))] = i

    def locate(self, pts):
        out = np.full(len(pts), -1)
        for k, (x, y) in enumerate(pts):
            gx = int(np.rint((x - self.x0) / (0.75 * self.w)))
            best, bd = -1, np.inf
            for cx in (gx - 1, gx, gx + 1):
                gy = int(np.rint(y / self.h * 2))
                for cy in range(gy - 2, gy + 3):
                    i = self.cells.get((cx, cy))
                    if i is not None:
                        d = (self.c[i, 0] - x) ** 2 + (self.c[i, 1] - y) ** 2
                        if d < bd:
                            best, bd = i, d
            if bd <= self.w ** 2:
                out[k] = best
        return out


# -------------------------------------------------------------- catalogue

def _state_fn(keys):
    """{"-10000": "perennial", ...} -> year -> state (absent before the first key)."""
    ks = sorted((int(y), s) for y, s in keys.items())
    for _, s in ks:
        if s not in STATES:
            raise ValueError(f"unknown river state {s!r}; use one of {STATES}")

    def at(year):
        cur = "absent"
        for y, s in ks:
            if y <= year:
                cur = s
        return cur
    return at


def _spill_fn(spill, lakes, name):
    """Year -> state for a river that flows only while a lake overflows."""
    lk = lakes.get(spill["lake"])
    if lk is None:
        raise ValueError(f"{name}: spill lake {spill['lake']!r} is not in the lakes catalogue")
    above = spill["above"]
    if above == "outlet":
        above = lk["spill"] - 1.0
    flowing = spill.get("state", "perennial")
    if flowing not in STATES:
        raise ValueError(f"{name}: unknown spill state {flowing!r}")
    return lambda y: flowing if lk["raw"][y] >= above else "absent"


def _changes(seq):
    """[(year, value)] -> {str(year): value} at changes only."""
    out, prev = {}, object()
    for y, v in seq:
        if v != prev:
            out[str(y)] = v
        prev = v
    return out


def build(cfg, grid, terrain, arr, tf, years, log=print, lakes=()):
    """Returns (segments, hex_river). segments: list of dicts with name,
    river key, size, points (N, 2), state {year: state}. hex_river:
    {year: int array} of river classes per hex.

    lakes (from pipeline.lakes.build) drive spillway rivers: a river with
    `spill = { lake = "...", above = metres | "outlet" }` flows (as its
    `state` value, default perennial) only while the lake is that high; one
    with `lake = "..."` extends from its mouth to that lake at its lowest."""
    rcfg = cfg["rivers"]
    with open(rcfg["catalogue"], "rb") as f:
        cat = tomllib.load(f)["river"]
    b = grid.bbox
    box = [b[:, 0].min(), b[:, 3].min(), b[:, 2].max(), b[:, 1].max()]
    reaches = None
    loc = HexLocator(grid)
    if any("from" in rv for rv in cat):
        hcfg = dict(rcfg["geoglows"])
        from .geoglows import sea_hex_fn
        with open(cfg["lakes"]["catalogue"], "rb") as f:
            lake_cat = tomllib.load(f).get("lake", [])
        reaches = load_reaches(hcfg, box, sea_hex_fn(grid, arr, tf, cfg["sea"], loc.locate,
                                                     lake_cat, hcfg.get("marine_lakes", ())))
        log(f"rivers: {len(reaches['id'])} GEOGLOWS reaches ({int(reaches['endorheic'].sum())} endorheic)")
    lowest = min(_sea(y, cfg["sea"]["curve"]) for y in years)
    water = {y: terrain[y] == "Water" for y in years}
    step = rcfg["sample"]

    by_key = {lk["key"]: lk for lk in lakes}
    segments = []
    # Reaches and shelf cells already drawn: a later river (a tributary)
    # stops where it meets them, so confluences aren't drawn twice.
    used_reaches, used_cells = set(), set()

    def add(rv, pts, state):
        """Segments of one river course: each year it ends where the run of
        Water hexes at its mouth begins."""
        pts = resample(pts, step)
        hexes = loc.locate(pts)
        inside = hexes >= 0
        if not inside.any():
            log(f"rivers: ⚠ {rv['name']} lies outside the grid")
            return
        # Keep the stretch inside the grid (first to last inside sample).
        idx = np.flatnonzero(inside)
        pts, hexes = pts[idx[0]:idx[-1] + 1], hexes[idx[0]:idx[-1] + 1]
        # Each year the river ends where the trailing run of Water hexes starts.
        end = {}
        for y in years:
            wet = (hexes < 0) | water[y][np.maximum(hexes, 0)]
            dry = np.flatnonzero(~wet)
            end[y] = int(dry[-1]) + 1 if len(dry) else 0
        cuts = sorted(set(end.values()) - {0})
        prev = 0
        for c in cuts:
            a = max(prev - 1, 0)
            seq = [(y, state(y) if end[y] >= c else "absent") for y in years]
            if any(s != "absent" for _, s in seq) and c - a >= 2:
                seg_pts = simplify(pts[a:c], rcfg["simplify"])
                segments.append({
                    "river": rv["key"], "name": rv["name"], "size": int(rv["size"]),
                    "part": "main" if prev == 0 else "shelf",
                    "points": seg_pts, "hexes": hexes[a:c],
                    "state": _changes(seq), "state_fn": dict(seq),
                })
            prev = c

    for rv in cat:
        state = _state_fn(rv["state"])
        if "spill" in rv:
            state = _spill_fn(rv["spill"], by_key, rv["name"])
        if "points" in rv:
            pts = np.asarray(rv["points"], dtype=float)
            sea = rv.get("shelf", False)
        else:
            start, d = nearest_reach(reaches, rv["from"], rv.get("min_upland", 0.0))
            if d > rcfg["snap_max"]:
                log(f"rivers: ⚠ {rv['name']}: `from` is {d:.2f}° from the nearest reach")
            pts, sea, used = trace(reaches, start, rv.get("to"), used_reaches)
            used_reaches.update(used)
            if "before" in rv:
                # Waypoints from the parent river to the start of the trace
                # (a dry distributary the stream network has as its own channel).
                pts = np.concatenate([np.asarray(rv["before"], dtype=float), pts])
            if "then" in rv:
                pts = np.concatenate([pts, np.asarray(rv["then"], dtype=float)])
            sea = rv.get("shelf", sea)
        level = lowest
        if "lake" in rv:
            level = min(v for v in by_key[rv["lake"]]["level"].values() if np.isfinite(v))
            sea = True
        if sea:
            ext = shelf_path(pts[-1], arr, tf, level, rcfg["shelf_window"])
            cells = [(int(round(tf.row(y))), int(round(tf.col(x)))) for x, y in ext]
            for k, c in enumerate(cells):
                if c in used_cells:
                    ext = ext[:k + 1]
                    break
            used_cells.update(cells[:len(ext)])
            if len(ext) > 1:
                pts = np.concatenate([pts, ext[1:]])
        add(rv, pts, state)
    # Rivers out of lakes held at their outlet (lakes.toml `outflow`), one
    # per spill point, flowing in the years the lake drained over it.
    n_out = 0
    for lk in lakes:
        oc = lk.get("outflow_cfg")
        for k, (pts, ys) in enumerate(lk.get("outflow", [])):
            if len(pts) < 2:
                continue
            on = set(ys)
            rv = {"key": f"{lk['key']}-outflow-{k + 1}", "name": oc["name"], "size": oc.get("size", 2)}
            add(rv, np.asarray(pts, dtype=float), lambda y, on=on: "perennial" if y in on else "absent")
            n_out += 1
    log(f"rivers: {len(cat)} rivers, {n_out} lake outflows -> {len(segments)} segments")

    # Per-hex class: the largest class of any active river with enough length in it.
    min_n = max(1, int(round(rcfg["hex_min_length"] / step)))
    hex_river = {}
    for y in years:
        cls = np.zeros(len(grid), dtype=np.int64)
        for s in segments:
            st = s["state_fn"][y]
            if st == "absent":
                continue
            c = 2 if (st == "perennial" and s["size"] >= 2) else 1
            h = s["hexes"][s["hexes"] >= 0]
            ids, n = np.unique(h, return_counts=True)
            ids = ids[n >= min_n]
            cls[ids] = np.maximum(cls[ids], c)
        hex_river[y] = cls
    return segments, hex_river


def _sea(year, curve):
    xs, ys = zip(*sorted(curve))
    return float(np.interp(year, xs, ys))


def write_geojson(path, segments):
    feats = []
    for i, s in enumerate(segments):
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString",
                         "coordinates": [[round(float(x), 4), round(float(y), 4)]
                                         for x, y in s["points"]]},
            "properties": {"id": i + 1, "river": s["river"], "name": s["name"],
                           "size": s["size"], "part": s["part"], "state": s["state"]},
        })
    with open(path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f)
