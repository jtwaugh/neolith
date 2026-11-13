"""Distance from each hex to the nearest open sea beyond the map's edge.

The app measures a hex's distance to water from the map's own Water hexes.
A coast that lies off the map (the Gulf of Guinea south of the bottom edge,
the Atlantic off Senegal west of the left edge) is invisible to that, and
land near it reads as deep inland. This fills the gap from a wider, coarser
ETOPO1 window: per key frame, the sea cells outside the grid's box at that
year's sea level, and each hex centre's great-circle distance to the nearest.

An input to expected population (data/population/SOURCES.md, "Distance to
the sea"), so it uses no site or date counts. Sea inside the map's box is
left to the hexes; lakes off the map are not counted.
"""
import numpy as np

from . import elevation

EARTH_KM = 6371.0
NONE = 65535  # no sea beyond the edge within `max_km`


def open_sea(z, level, seed_depth):
    """Cells below `level` connected (4-way) to a cell deeper than
    `seed_depth` or to the raster's edge: open ocean, not closed basins."""
    from scipy import ndimage
    below = np.nan_to_num(z, nan=np.inf) < level
    labels, _ = ndimage.label(below)
    edge = np.zeros(z.shape, dtype=bool)
    edge[0], edge[-1], edge[:, 0], edge[:, -1] = True, True, True, True
    seeds = np.unique(labels[below & (edge | (z < seed_depth))])
    return np.isin(labels, seeds[seeds > 0])


def unit(lon, lat):
    lon, lat = np.radians(lon), np.radians(lat)
    return np.column_stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])


def distances(centres, box, z, tf, level, seed_depth, max_km):
    """Km (whole, int) from each (lon, lat) in `centres` to the nearest
    open-sea cell of raster `z` whose centre lies outside `box` (west, south,
    east, north); NONE beyond `max_km` or when there is no such cell."""
    from scipy.spatial import cKDTree
    sea = open_sea(z, level, seed_depth)
    rows, cols = np.nonzero(sea)
    lon, lat = tf.x0 + cols * tf.a, tf.y0 + rows * tf.e
    west, south, east, north = box
    off = (lon < west) | (lon > east) | (lat < south) | (lat > north)
    out = np.full(len(centres), NONE, dtype=int)
    if not off.any():
        return out
    chord, _ = cKDTree(unit(lon[off], lat[off])).query(unit(centres[:, 0], centres[:, 1]))
    km = 2.0 * EARTH_KM * np.arcsin(np.clip(chord / 2.0, 0.0, 1.0))
    near = km <= max_km
    out[near] = np.rint(km[near]).astype(int)
    return out


def build(grid, cfg, curve, seed_depth):
    """({year: int array (N,)}, stats) for cfg["years"]."""
    z, tf = elevation.load_asc(cfg["elevation"])
    b = grid.bbox
    box = (b[:, 0].min(), b[:, 3].min(), b[:, 2].max(), b[:, 1].max())
    out, stats = {}, {}
    for y in cfg["years"]:
        out[y] = distances(grid.centres, box, z, tf, elevation.sea_level(y, curve), seed_depth, cfg["max_km"])
        got = out[y][out[y] != NONE]
        stats[y] = {"hexes": int(len(got)), "within_200_km": int((got <= 200).sum())}
    return out, stats
