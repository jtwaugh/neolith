"""Settlement coordinate corrections and the coordinate audit.

Corrections (data/settlements/corrections.toml, `[[fix]]` entries) are hand
edits the map build applies to the shipped settlements before anything reads
their position. An entry names a site and where it is now (`was`, matched
within 0.02°), and gives one of:
- `to = [lon, lat]`: the right position (the hex is reassigned);
- `drop = true`: a duplicate of another entry, removed;
- `rename = "..."`: the record carries another site's name (the old name is
  kept as `filed_as`); may be combined with `to`;
- `submerged = true`: the site really is under water today, so the audit
  doesn't flag it as a coordinate error.
Every entry has a `source` (a link) and a `note`; data/settlements/SOURCES.md
lists the sources (test_sources.py checks).

The audit (data/settlements/coordinate_audit.csv) lists sites whose
coordinates look wrong, one row per site with every reason:
- `at_sea`: the highest ETOPO1 cell within one cell of the site is more than
  `deep_m` below sea level and its hex is Water in a frame it is occupied
  (a site below sea level on dry land, as in the Jordan Valley, is fine), or
  it is lower than any dry land in the box (`lowest_land_m`);
- `offshore`: on a Water hex with no land neighbour in every occupied frame;
- `same_name_far`: another site with the same name is over `far_km` away;
- `hint`: a sign-flipped or swapped position that would be on dry land.
"""
import csv
import math
import os
import re
import tomllib
from collections import defaultdict

import numpy as np

from .compose import alive_frames, phases


def load(path):
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        return tomllib.load(f).get("fix", [])


def _hex_of(grid, lon, lat):
    """Id of the hex containing a point (nearest centre among bbox hits)."""
    from .raster import point_in_poly
    b = grid.bbox
    hit = np.flatnonzero((b[:, 0] <= lon) & (b[:, 2] >= lon) & (b[:, 3] <= lat) & (b[:, 1] >= lat))
    for i in hit:
        if point_in_poly(np.array([lon]), np.array([lat]), grid.rings[i])[0]:
            return int(grid.ids[i])
    return None


def apply(feats, fixes, grid):
    """Returns (feats, applied [(name, action)], unmatched [name])."""
    out, applied, used = [], [], set()
    for f in feats:
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"][:2]
        fix = next((k for k, x in enumerate(fixes)
                    if x["name"] == p.get("name") and abs(x["was"][0] - lon) <= 0.02
                    and abs(x["was"][1] - lat) <= 0.02), None)
        if fix is None:
            out.append(f)
            continue
        x = fixes[fix]
        used.add(fix)
        if x.get("drop"):
            applied.append((p["name"], "drop"))
            continue
        f = {**f, "properties": dict(p)}
        if x.get("rename"):
            f["properties"]["filed_as"] = p["name"]
            f["properties"]["name"] = x["rename"]
            applied.append((p["name"], "renamed"))
        if "to" in x:
            f["geometry"] = {"type": "Point", "coordinates": [float(x["to"][0]), float(x["to"][1])]}
            h = _hex_of(grid, *x["to"])
            if h is None:
                applied.append((p["name"], "moved off the grid; dropped"))
                continue
            f["properties"]["hex"] = h
            f["properties"]["moved_from"] = [lon, lat]
            applied.append((p["name"], "moved"))
        if x.get("submerged"):
            f["properties"]["submerged"] = True
            applied.append((p["name"], "submerged"))
        out.append(f)
    unmatched = [x["name"] for k, x in enumerate(fixes) if k not in used]
    return out, applied, unmatched


def _km(a, b):
    p = math.pi / 180
    h = (math.sin((b[1] - a[1]) * p / 2) ** 2
         + math.cos(a[1] * p) * math.cos(b[1] * p) * math.sin((b[0] - a[0]) * p / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(min(1.0, h)))


def _norm(name):
    base = re.split(r"[,(]", name.lower())[0]
    return re.sub(r"[^a-z0-9]+", " ", base).strip()


def _ground(arr, tf, lon, lat, r=1):
    R, C = int(round(float(tf.row(lat)))), int(round(float(tf.col(lon))))
    if not (0 <= R < arr.shape[0] and 0 <= C < arr.shape[1]):
        return np.nan
    w = arr[max(R - r, 0):R + r + 1, max(C - r, 0):C + r + 1]
    return float(np.nanmax(w)) if np.isfinite(w).any() else np.nan


def audit(feats, terrain, grid, arr, tf, deep_m=50.0, far_km=25.0, lowest_land_m=450.0):
    """Rows {name, lon, lat, hex, reasons, ground_m, hint} for suspect sites."""
    years = sorted(terrain)
    index = {h: i for i, h in enumerate(grid.ids)}
    water = {y: terrain[y] == "Water" for y in years}
    by_name = defaultdict(list)
    for k, f in enumerate(feats):
        n = _norm(f["properties"].get("name", ""))
        if len(n) >= 4:
            by_name[n].append(k)
    rows = []
    for k, f in enumerate(feats):
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"][:2]
        i = index.get(p.get("hex"))
        reasons = []
        z = _ground(arr, tf, lon, lat)
        alive = alive_frames(phases(p, years), years) if i is not None else []
        wet = [y for y in alive if water[y][i]]
        # No dry land in the box is lower than the Dead Sea shore (about -430 m).
        if not p.get("submerged") and ((wet and z < -deep_m) or z < -lowest_land_m):
            reasons.append("at_sea")
        if alive and len(wet) == len(alive) and all(all(water[y][j] for j in grid.neighbours[i]) for y in wet):
            reasons.append("offshore")
        same = [j for j in by_name.get(_norm(p.get("name", "")), []) if j != k]
        far = [j for j in same if _km((lon, lat), feats[j]["geometry"]["coordinates"][:2]) > far_km]
        if far:
            reasons.append("same_name_far")
        if not reasons:
            continue
        hints = []
        for label, (x, y) in (("lon sign", (-lon, lat)), ("lat/lon swapped", (lat, lon))):
            if -180 <= x <= 180 and -90 <= y <= 90:
                gz = _ground(arr, tf, x, y, 0)
                near = [j for j in same if _km((x, y), feats[j]["geometry"]["coordinates"][:2]) <= far_km]
                if np.isfinite(gz) and gz > 0 and (near or "at_sea" in reasons or "offshore" in reasons):
                    hints.append(f"{label}: {x:.4f}, {y:.4f} is dry ({gz:.0f} m)"
                                 + (" next to a same-name site" if near else ""))
        rows.append({"name": p.get("name", ""), "lon": lon, "lat": lat, "hex": p.get("hex"),
                     "reasons": ";".join(reasons), "ground_m": "" if not np.isfinite(z) else round(z),
                     "same_name_km": ";".join(str(round(_km((lon, lat), feats[j]["geometry"]["coordinates"][:2])))
                                              for j in far[:3]),
                     "hint": " | ".join(hints), "sources": ";".join(p.get("sources", []))})
    return rows


def write(path, rows):
    cols = ["name", "lon", "lat", "hex", "reasons", "ground_m", "same_name_km", "hint", "sources"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["reasons"].split(";")[0] != "at_sea",
                                             "offshore" not in r["reasons"], r["name"])):
            w.writerow(r)
