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


def sea_level(year, curve):
    xs, ys = zip(*sorted(curve))
    return float(np.interp(year, xs, ys))


def ocean_mask(elev, level, neighbours, edge, seed_depth):
    """Hexes below `level` that connect to open ocean through other such hexes.

    Seeds are below-level hexes on the grid edge (`edge` mask) and any hex
    deeper than `seed_depth`. Closed basins below sea level
    (Qattara, Caspian) aren't seeds and stay as the rasters draw them.
    """
    below = np.nan_to_num(elev, nan=np.inf) < level
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
