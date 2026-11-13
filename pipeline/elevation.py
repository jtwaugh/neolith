"""Elevation raster -> which hexes are open sea in a given year, and which
are mountains."""
import os
from collections import deque

import numpy as np

from .raster import Affine, hex_pixels


def load_asc(path):
    """Read an ESRI ASCII grid; caches the array next to it as .npy."""
    header = {}
    with open(path) as f:
        for _ in range(6):
            k, v = f.readline().split()
            header[k.lower()] = float(v)
    cache = path + ".npy"
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(path):
        arr = np.load(cache)
    else:
        arr = np.loadtxt(path, skiprows=6, dtype=np.float32)
        np.save(cache, arr)
    arr[arr == header["nodata_value"]] = np.nan
    nrows, cs = int(header["nrows"]), header["cellsize"]
    if "xllcenter" in header:
        x0, yll = header["xllcenter"], header["yllcenter"]
    else:
        x0, yll = header["xllcorner"] + cs / 2, header["yllcorner"] + cs / 2
    # Row 0 is the northernmost row.
    return arr, Affine(cs, -cs, x0, yll + (nrows - 1) * cs)


def hex_median(grid, arr, tf):
    """Median elevation per hex (NaN where the hex has no cells)."""
    out = np.full(len(grid), np.nan)
    for i, (ring, bbox) in enumerate(zip(grid.rings, grid.bbox)):
        rr, cc = hex_pixels(ring, bbox, tf, arr.shape)
        if len(rr):
            out[i] = np.nanmedian(arr[rr, cc])
    return out


def _spread(a, k, axis, fn):
    """Running max/min (`fn`) of `a` over +-k cells along `axis`."""
    pad = [(k, k) if ax == axis else (0, 0) for ax in range(a.ndim)]
    p = np.pad(a, pad, mode="edge")
    n = a.shape[axis]
    out = a.copy()
    for s in range(2 * k + 1):
        out = fn(out, np.take(p, np.arange(s, s + n), axis=axis))
    return out


def local_relief(z, dy, dx, radius):
    """Max minus min elevation within `radius` metres of each cell (a square
    window). dy: cell height in metres; dx: cell width per row."""
    ky = max(1, round(radius / dy))
    hi = _spread(z, ky, 0, np.maximum)
    lo = _spread(z, ky, 0, np.minimum)
    kx = np.maximum(1, np.rint(radius / dx).astype(int))
    out = np.empty_like(z)
    for k in np.unique(kx):
        rows = kx == k
        out[rows] = (_spread(hi[rows], k, 1, np.maximum)
                     - _spread(lo[rows], k, 1, np.minimum))
    return out


def mountain_cells(arr, tf, cfg):
    """Mountain mask per raster cell, after Kapos et al. 2000 (UNEP-WCMC):
    high ground counts outright, lower ground only if steep or rugged."""
    z = np.nan_to_num(arr, nan=0.0).astype(np.float64)
    lat = tf.y0 + np.arange(z.shape[0]) * tf.e
    dy = abs(tf.e) * 111_320.0
    dx = abs(tf.a) * 111_320.0 * np.cos(np.radians(lat))
    gy, gx = np.gradient(z)
    slope = np.degrees(np.arctan(np.hypot(gx / dx[:, None], gy / dy)))
    rugged = local_relief(z, dy, dx, cfg["relief_radius"]) > cfg["relief"]
    out = np.zeros(z.shape, dtype=bool)
    for b in cfg["bands"]:
        ok = z >= b["above"]
        if "slope" in b or b.get("rugged"):
            cond = np.zeros(z.shape, dtype=bool)
            if "slope" in b:
                cond |= slope >= b["slope"]
            if b.get("rugged"):
                cond |= rugged
            ok &= cond
        out |= ok
    return out


def hex_fraction(grid, mask, tf):
    """Share of each hex's cells that are set in `mask` (0 with no cells)."""
    out = np.zeros(len(grid))
    for i, (ring, bbox) in enumerate(zip(grid.rings, grid.bbox)):
        rr, cc = hex_pixels(ring, bbox, tf, mask.shape)
        if len(rr):
            out[i] = mask[rr, cc].mean()
    return out


FLAT, HILLS, MOUNTAINS, HIGH_MOUNTAINS = 0, 1, 2, 3
LANDFORM_NAMES = ("flat", "hills", "mountains", "high mountains")


def landform(frac, elev, cfg):
    """Static landform class per hex from its share of mountain cells
    (`mountain_cells`) and median elevation: MOUNTAINS at `min_fraction`,
    HIGH_MOUNTAINS when also at `high_elevation` m or more, HILLS at
    `hills_fraction`, else FLAT."""
    out = np.full(len(frac), FLAT, dtype=np.int8)
    out[frac >= cfg["hills_fraction"]] = HILLS
    mtn = frac >= cfg["min_fraction"]
    out[mtn] = MOUNTAINS
    out[mtn & (np.nan_to_num(elev, nan=0.0) >= cfg["high_elevation"])] = HIGH_MOUNTAINS
    return out


SQRT3_2 = 3 ** 0.5 / 2
MASSIF_KINDS = ("massif", "ridge", "cone", "plateau")


def massif(grid, arr, tf, landform, cfg):
    """A sketch of each hilly or mountain hex's high ground for the board's
    peaks (neolith_core::massif); None elsewhere. Per hex, over its raster
    cells:

    - floor: the 10th-percentile elevation (of the cells above sea level
      when they are at least a quarter of the hex);
    - summits: up to three local maxima (highest within `peak_window` cells)
      at least `min_prominence` m above the floor and `separation` apart,
      highest first, as hex-local [x, y, metres above the floor] (corners on
      the unit circle, +x east, +y north; both axes in degrees of arc). A
      hex whose high ground runs on into a neighbour may have none, and then
      takes its highest cell if that clears `min_prominence`. Valleys hold
      no maxima, so summits keep off the rivers;
    - strike and coherence: the structure tensor of the gradient (in metres)
      over the cells above the median. The strike is the ridge line, 90°
      from the dominant slope direction, and is turned into hex-local
      degrees anticlockwise from +x. Coherence 0..1 is how cleanly the
      slopes line up;
    - kind: "plateau" (median at least `plateau_elevation`, relief, 95th
      minus 10th percentile, under `plateau_relief`), "cone" (one summit at
      least `cone_ratio` times the next, relief at least `cone_relief`,
      coherence under `cone_coherence`), "ridge" (coherence at least
      `ridge_coherence`), else "massif".
    """
    z = np.nan_to_num(arr, nan=0.0).astype(np.float64)
    lat = tf.y0 + np.arange(z.shape[0]) * tf.e
    dy = abs(tf.e) * 111_320.0
    dx = abs(tf.a) * 111_320.0 * np.cos(np.radians(lat))
    gy, gx = np.gradient(z)
    gx = gx / dx[:, None]   # east
    gy = -gy / dy           # north (row 0 is the northernmost)
    k = cfg["peak_window"]
    peak = _spread(_spread(z, k, 0, np.maximum), k, 1, np.maximum)
    out = [None] * len(grid)
    for i, (ring, bbox) in enumerate(zip(grid.rings, grid.bbox)):
        if landform[i] < HILLS:
            continue
        rr, cc = hex_pixels(ring, bbox, tf, z.shape)
        if len(rr) < 8:
            continue
        zh = z[rr, cc]
        # A coastal hex's floor is its land's, not the sea bed's (a basin
        # below sea level, such as the Dead Sea's, keeps its own).
        land = zh[zh > 0]
        floor = float(np.percentile(land if len(land) >= 0.25 * len(zh) else zh, 10))
        med = float(np.median(zh))
        relief = float(np.percentile(zh, 95)) - floor
        left, top, right, bottom = bbox
        cx, cy = (left + right) / 2, (top + bottom) / 2
        hw, hh = abs(right - left) / 2, abs(top - bottom) / 2
        hx = (tf.x0 + cc * tf.a - cx) / hw
        hy = (tf.y0 + rr * tf.e - cy) / hh * SQRT3_2
        cand = np.nonzero((zh >= peak[rr, cc]) & (zh - floor >= cfg["min_prominence"]))[0]
        if not len(cand) and zh.max() - floor >= cfg["min_prominence"]:
            cand = np.array([int(np.argmax(zh))])
        cand = cand[np.argsort(-zh[cand], kind="stable")]
        summits = []
        for c in cand:
            x, y = float(hx[c]), float(hy[c])
            if all((x - s[0]) ** 2 + (y - s[1]) ** 2 >= cfg["separation"] ** 2 for s in summits):
                summits.append([round(x, 2), round(y, 2), round(float(zh[c] - floor))])
            if len(summits) == 3:
                break
        up = zh >= med
        ex, ny = gx[rr, cc][up], gy[rr, cc][up]
        jxx, jyy, jxy = float((ex * ex).sum()), float((ny * ny).sum()), float((ex * ny).sum())
        tr = jxx + jyy
        coh = float(np.hypot(jxx - jyy, 2 * jxy) / tr) if tr > 0 else 0.0
        slope = 0.5 * np.arctan2(2 * jxy, jxx - jyy)
        ridge = slope + np.pi / 2
        # On the ground -> hex-local (x in degrees of longitude).
        strike = float(np.degrees(np.arctan2(np.sin(ridge), np.cos(ridge) / np.cos(np.radians(cy)))) % 180.0)
        if med >= cfg["plateau_elevation"] and relief < cfg["plateau_relief"]:
            kind = "plateau"
        elif (summits and relief >= cfg["cone_relief"] and coh < cfg["cone_coherence"]
              and (len(summits) == 1 or summits[0][2] >= cfg["cone_ratio"] * summits[1][2])):
            kind = "cone"
        elif coh >= cfg["ridge_coherence"]:
            kind = "ridge"
        else:
            kind = "massif"
        out[i] = {"kind": kind, "strike": round(strike, 1), "coherence": round(coh, 3),
                  "floor": round(floor), "summits": summits}
    return out


def sea_level(year, curve):
    xs, ys = zip(*sorted(curve))
    return float(np.interp(year, xs, ys))


def channel_open(ch, year):
    """Whether a `[[sea.channel]]` is open in `year` (its optional `from`
    and `until` years; None: open in every year)."""
    if year is None:
        return True
    return (ch.get("from") is None or year >= ch["from"]) and (ch.get("until") is None or year < ch["until"])


def channel_mask(centres, channels, step=0.05, year=None):
    """Hexes along each `[[sea.channel]]` line (lon, lat waypoints): the
    nearest hex centre to points every `step` degrees along it, which on a
    hex grid much coarser than `step` is a connected chain of hexes. With
    `year`, only the channels open that year (`from`/`until`)."""
    c = np.asarray(centres, dtype=np.float64)
    out = np.zeros(len(c), dtype=bool)
    for ch in channels:
        if not channel_open(ch, year):
            continue
        pts = np.asarray(ch["line"], dtype=np.float64)
        for a, b in zip(pts[:-1], pts[1:]):
            n = max(int(np.ceil(np.hypot(*(b - a)) / step)), 1)
            for p in a + (b - a) * np.linspace(0.0, 1.0, n + 1)[:, None]:
                out[np.argmin(np.hypot(*(c - p).T))] = True
    return out


def ocean_mask(elev, level, neighbours, edge, seed_depth, always=None):
    """Hexes below `level` that connect to open ocean through other such hexes.

    Seeds are below-level hexes on the grid edge (`edge` mask) and any hex
    deeper than `seed_depth`. Closed basins below sea level
    (Qattara, Caspian) aren't seeds and stay as the rasters draw them.
    Hexes in `always` (see `channel_mask`) count as below every level: sea
    channels too narrow for the hex grid that stayed open at lowstand.
    """
    below = np.nan_to_num(elev, nan=np.inf) < level
    if always is not None:
        below |= always
    seen = np.zeros(len(elev), dtype=bool)
    q = deque(i for i in np.flatnonzero(below)
              if edge[i] or elev[i] < seed_depth)
    for i in q:
        seen[i] = True
    while q:
        for j in neighbours[q.popleft()]:
            if below[j] and not seen[j]:
                seen[j] = True
                q.append(j)
    return seen
