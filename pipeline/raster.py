"""Georeferenced rasters -> per-hex values (replaces QGIS zonal statistics)."""
from collections import Counter

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


class Affine:
    """Pixel-centre transform: lon = x0 + col*a, lat = y0 + row*e."""

    def __init__(self, a, e, x0, y0):
        self.a, self.e, self.x0, self.y0 = a, e, x0, y0

    @classmethod
    def from_world_file(cls, path):
        # World file lines: A, D, B, E, C, F; C/F is the upper-left pixel centre.
        a, d, b, e, c, f = (float(l) for l in open(path).read().split())
        if d or b:
            raise ValueError(f"{path}: rotated world files aren't supported")
        return cls(a, e, c, f)

    def col(self, lon):
        return (np.asarray(lon) - self.x0) / self.a

    def row(self, lat):
        return (np.asarray(lat) - self.y0) / self.e


def point_in_poly(x, y, ring):
    """Even-odd test of points (x, y arrays) against a polygon ring."""
    ring = np.asarray(ring, dtype=float)
    inside = np.zeros(np.shape(x), dtype=bool)
    for (x1, y1), (x2, y2) in zip(ring, np.roll(ring, -1, axis=0)):
        if y1 == y2:
            continue
        crosses = (y1 > y) != (y2 > y)
        xint = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
        inside ^= crosses & (x < xint)
    return inside


def hex_pixels(ring, bbox, tf, shape):
    """(rows, cols) of raster pixels whose centres fall inside the hex."""
    left, top, right, bottom = bbox
    c0, c1 = sorted((tf.col(left), tf.col(right)))
    r0, r1 = sorted((tf.row(top), tf.row(bottom)))
    cols = np.arange(max(int(np.ceil(c0)), 0), min(int(np.floor(c1)), shape[1] - 1) + 1)
    rows = np.arange(max(int(np.ceil(r0)), 0), min(int(np.floor(r1)), shape[0] - 1) + 1)
    if not len(cols) or not len(rows):
        return rows[:0], cols[:0]
    rr, cc = np.meshgrid(rows, cols, indexing="ij")
    lon = tf.x0 + cc * tf.a
    lat = tf.y0 + rr * tf.e
    m = point_in_poly(lon, lat, ring)
    return rr[m], cc[m]


def classify_image(rgba, palette, tolerance):
    """Class index per pixel; -1 = transparent or no palette colour in range.

    Returns (classes, unmatched) where unmatched counts pixel RGBs that
    didn't vote.
    """
    rgb = rgba[..., :3].astype(np.int64)
    key = (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]
    uniq, inv = np.unique(key, return_inverse=True)
    cols = np.stack([uniq >> 16, (uniq >> 8) & 255, uniq & 255], axis=1).astype(float)
    pal = np.array([c for c, _ in palette], dtype=float)
    dist = np.linalg.norm(cols[:, None, :] - pal[None, :, :], axis=2)
    best = dist.argmin(axis=1)
    best[dist.min(axis=1) > tolerance] = -1
    inv = inv.reshape(key.shape)
    classes = best[inv]
    opaque = rgba[..., 3] > 0 if rgba.shape[-1] == 4 else np.ones(key.shape, bool)
    classes[~opaque] = -1
    counts = np.bincount(inv[opaque], minlength=len(uniq))
    unmatched = Counter({tuple(int(v) for v in cols[i]): int(counts[i])
                         for i in np.flatnonzero((best == -1) & (counts > 0))})
    return classes, unmatched


def hex_majority(grid, classes, tf, nclasses):
    """Majority class per hex; -1 where no pixel voted."""
    out = np.full(len(grid), -1)
    for i, (ring, bbox) in enumerate(zip(grid.rings, grid.bbox)):
        rr, cc = hex_pixels(ring, bbox, tf, classes.shape)
        v = classes[rr, cc]
        v = v[v >= 0]
        if len(v):
            out[i] = np.bincount(v, minlength=nclasses).argmax()
    return out


def sample_terrain(grid, image_path, world_path, palette, tolerance):
    """Terrain name per hex from one keyframe; returns (names, unmatched)."""
    rgba = np.asarray(Image.open(image_path).convert("RGBA"))
    classes, unmatched = classify_image(rgba, palette, tolerance)
    idx = hex_majority(grid, classes, Affine.from_world_file(world_path), len(palette))
    names = np.array([n for _, n in palette] + ["Unknown"], dtype=object)
    return names[idx], unmatched  # idx -1 -> "Unknown"
