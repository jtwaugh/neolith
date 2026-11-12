"""Dated shoreline overrides (data/coasts/coasts.toml).

The board's coast comes from ETOPO1 and the sea curve, i.e. today's
surface. Where rivers have since filled in what was sea (the Gulf head, the
Po plain, the northern Nile delta), the past coast lay inland of anything the
modern surface can show. Each coast entry gives one or more stages: a polygon
of the area that was sea (or lagoon) and the years it applies. Hexes with at
least `hex_fraction` of their ETOPO cells inside the polygon become Water for
those years; outside them the terrain is left as composed.
"""
import json
import tomllib

import numpy as np

from .raster import hex_pixels, point_in_poly


def hex_fraction(grid, arr, tf, ring):
    """Share of each hex's raster cells whose centres fall inside `ring`."""
    ring = np.asarray(ring, dtype=float)
    x0, y0 = ring.min(axis=0)
    x1, y1 = ring.max(axis=0)
    b = grid.bbox
    out = np.zeros(len(grid))
    for i in np.flatnonzero((b[:, 2] > x0) & (b[:, 0] < x1) & (b[:, 1] > y0) & (b[:, 3] < y1)):
        rr, cc = hex_pixels(grid.rings[i], grid.bbox[i], tf, arr.shape)
        if len(rr):
            inside = point_in_poly(tf.x0 + cc * tf.a, tf.y0 + rr * tf.e, ring)
            out[i] = inside.mean()
    return out


def build(cfg, grid, terrain, arr, tf, years, log=print):
    """Apply the coast stages to `terrain` ({year: array}). Returns
    (terrain, coasts) where coasts lists {key, name, stages: [{from, to,
    polygon, hexes}]} for the GeoJSON."""
    ccfg = cfg["coasts"]
    with open(ccfg["catalogue"], "rb") as f:
        cat = tomllib.load(f)["coast"]
    out = {y: t.copy() for y, t in terrain.items()}
    coasts = []
    for c in cat:
        stages = []
        for s in c["stage"]:
            s = {"to": None, **s}
            if s["to"] is not None and s["to"] <= s["from"]:
                raise ValueError(f"coast {c['key']}: stage to {s['to']} <= from {s['from']}")
            wet = hex_fraction(grid, arr, tf, s["polygon"]) >= ccfg["hex_fraction"]
            hit = [y for y in years if y >= s["from"] and (s["to"] is None or y < s["to"])]
            for y in hit:
                out[y][wet] = "Water"
            stages.append({"from": s["from"], "to": s["to"], "polygon": s["polygon"],
                           "hexes": int(wet.sum())})
            log(f"coasts: {c['name']} from {s['from']}: {int(wet.sum())} hexes, {len(hit)} years")
        coasts.append({"key": c["key"], "name": c["name"], "stages": stages})
    return out, coasts


def write_geojson(path, coasts):
    feats = []
    for c in coasts:
        for s in c["stages"]:
            ring = [list(map(float, p)) for p in s["polygon"]]
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            feats.append({"type": "Feature",
                          "geometry": {"type": "Polygon", "coordinates": [ring]},
                          "properties": {"coast": c["key"], "name": c["name"], "from": s["from"],
                                         "to": s["to"], "hexes": s["hexes"]}})
    with open(path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f)
