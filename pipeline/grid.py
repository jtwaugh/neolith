"""Canonical hex grid: ids, geometry, bboxes and adjacency."""
import json
from dataclasses import dataclass
from functools import lru_cache

import numpy as np


@lru_cache(maxsize=None)
def load_geojson(path):
    with open(path) as f:
        return json.load(f)


@dataclass
class Grid:
    ids: np.ndarray           # (N,) hex id
    rings: list               # outer ring [[lon, lat], ...] per hex
    bbox: np.ndarray          # (N, 4) left, top, right, bottom
    neighbours: list          # per hex, list of neighbour indices

    def __len__(self):
        return len(self.ids)

    @property
    def centres(self):
        return np.column_stack([(self.bbox[:, 0] + self.bbox[:, 2]) / 2,
                                (self.bbox[:, 1] + self.bbox[:, 3]) / 2])


def from_features(features):
    ids = np.array([f["properties"]["id"] for f in features])
    rings = [f["geometry"]["coordinates"][0] for f in features]
    bbox = np.array([[f["properties"][k] for k in ("left", "top", "right", "bottom")]
                     for f in features], dtype=float)
    return Grid(ids, rings, bbox, adjacency(bbox))


def load(path):
    return from_features(load_geojson(path)["features"])


# Flat-topped offset neighbours, same tables as the 2023 prototype's game/hex_processing.py.
_DX = [0, 1, 1, 0, -1, -1]
_DY_EVEN = [-1, 0, 1, 1, 1, 0]
_DY_ODD = [-1, -1, 0, 1, 0, -1]


def adjacency(bbox):
    """Neighbour indices per hex, via the grid formula in SPEC §5."""
    left, top, right, bottom = bbox.T
    w = abs(left[0] - right[0]) * 3 / 4
    h = abs(top[0] - bottom[0])
    gx = np.rint((left - left.min()) / w).astype(int)
    off = np.where(gx % 2 == 0, -h / 2, 0.0)
    gy = np.rint((top - top.min() + off) / h).astype(int)
    cell = {(x, y): i for i, (x, y) in enumerate(zip(gx, gy))}
    out = []
    for x, y in zip(gx, gy):
        dys = _DY_EVEN if x % 2 == 0 else _DY_ODD
        out.append([cell[k] for k in ((x + dx, y + dy) for dx, dy in zip(_DX, dys)) if k in cell])
    return out
