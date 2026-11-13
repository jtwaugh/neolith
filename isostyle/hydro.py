"""Rivers, lakes and polygons for the speculative `river` and `polygon` rules.

Named rivers come from the map pipeline's traced courses, build/rivers.geojson
(stream-network courses and waypoint-traced buried channels; data/rivers/
rivers.toml), with each river's flow state per year: a named river counts
only in slices where it is perennial or seasonal. Unnamed rivers are
GEOGLOWS v2 / TDX-Hydro reaches (pipeline/geoglows.py) with at least `min_upland_km2` of
upstream catchment (cache: build/geoglows/reaches.pkl, reaches of 1,000 km²
and more). Named lakes come from build/lakes.geojson, whose shorelines change
by period.
"""
import ast
import json
import os
import pickle

import numpy as np
from matplotlib.path import Path
from scipy.spatial import cKDTree

R_EARTH = 6371.0088
STEP_KM = 3.0


def _xyz(lon, lat):
    lo, la = np.radians(np.asarray(lon, float)), np.radians(np.asarray(lat, float))
    return np.column_stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])


def _densify(coords):
    c = np.asarray(coords, float)
    if len(c) < 2:
        return c
    out = [c[:1]]
    for a, b in zip(c[:-1], c[1:]):
        d = np.hypot((b[0] - a[0]) * np.cos(np.radians((a[1] + b[1]) / 2)), b[1] - a[1]) * 111.0
        n = max(1, int(np.ceil(d / STEP_KM)))
        t = np.linspace(0, 1, n + 1)[1:, None]
        out.append(a + t * (b - a))
    return np.vstack(out)


def _state_at(state, year):
    if isinstance(state, str):
        try:
            state = ast.literal_eval(state)
        except (ValueError, SyntaxError):
            state = json.loads(state)
    val = None
    for y, s in sorted((int(k), v) for k, v in state.items()):
        if y <= year:
            val = s
    return val if val is not None else "absent"


class Hydro:
    def __init__(self, rivers="build/rivers.geojson", lakes="build/lakes.geojson",
                 reaches="build/geoglows/reaches.pkl"):
        self.rivers = json.load(open(rivers))["features"] if os.path.exists(rivers) else []
        self.lakes = json.load(open(lakes))["features"] if os.path.exists(lakes) else []
        self._reaches_path = reaches
        self._reaches = None
        self._cache = {}

    # -------------------------------------------------------------- names
    def river_names(self):
        return sorted({f["properties"]["name"] for f in self.rivers})

    def lake_names(self):
        return sorted({f["properties"]["name"] for f in self.lakes})

    # ------------------------------------------------------------ distance
    def distance_km(self, lon, lat, year, names=(), lakes=(), min_upland_km2=None, bbox=None):
        """km from each point to the nearest selected water: named rivers
        flowing in `year`, named lakes at their `year` shoreline (0 inside),
        and stream-network reaches with at least min_upland_km2 (inside bbox)."""
        key = (year, tuple(names), tuple(lakes), min_upland_km2, tuple(bbox) if bbox else None)
        if key not in self._cache:
            self._cache[key] = self._build(year, names, lakes, min_upland_km2, bbox)
        tree, polys = self._cache[key]
        d = np.full(len(lon), np.inf)
        if tree is not None:
            ch, _ = tree.query(_xyz(lon, lat))
            d = 2 * R_EARTH * np.arcsin(np.clip(ch / 2, 0, 1))
        pts = np.column_stack([lon, lat])
        for p in polys:
            d[p.contains_points(pts)] = 0.0
        return d

    def _build(self, year, names, lakes, min_upland_km2, bbox):
        lines, polys = [], []
        for f in self.rivers:
            p = f["properties"]
            if p["name"] in names and _state_at(p.get("state", {}), year) != "absent":
                g = f["geometry"]
                parts = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
                lines += [_densify(c) for c in parts]
        for f in self.lakes:
            p = f["properties"]
            if p["name"] not in lakes:
                continue
            lo, hi = p.get("from"), p.get("to")
            if (lo is not None and year < int(lo)) or (hi is not None and year >= int(hi)):
                continue
            # Shorelines are (Multi)LineStrings of closed rings, or polygons.
            g = f["geometry"]
            if g["type"] == "LineString":
                rings = [g["coordinates"]]
            elif g["type"] == "MultiLineString":
                rings = g["coordinates"]
            elif g["type"] == "Polygon":
                rings = [g["coordinates"][0]]
            else:
                rings = [poly[0] for poly in g["coordinates"]]
            for ring in rings:
                ext = np.asarray(ring, float)
                if len(ext) < 2:
                    continue
                lines.append(_densify(ext))
                if len(ext) >= 4 and np.allclose(ext[0], ext[-1]):
                    polys.append(Path(ext))
        if min_upland_km2 is not None:
            r = self.reaches()
            sel = np.flatnonzero(r["upland"] >= min_upland_km2)
            for i in sel:
                c = r["coords"][i]
                if bbox and (c[:, 0].max() < bbox[0] or c[:, 0].min() > bbox[2]
                             or c[:, 1].max() < bbox[1] or c[:, 1].min() > bbox[3]):
                    continue
                lines.append(_densify(c))
        pts = np.vstack(lines) if lines else None
        return (cKDTree(_xyz(pts[:, 0], pts[:, 1])) if pts is not None and len(pts) else None), polys

    def reaches(self):
        if self._reaches is None:
            with open(self._reaches_path, "rb") as f:
                self._reaches = pickle.load(f)
        return self._reaches


def in_polygon(points, lon, lat):
    """True where (lon, lat) lies inside the polygon given as [[lon, lat], ...]."""
    return Path(np.asarray(points, float)).contains_points(np.column_stack([lon, lat]))
