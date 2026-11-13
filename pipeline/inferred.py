"""Inferred settlements from data/settlements/inferred.toml.

Each [[rule]] carries out one place plan's `[[speculate]] target =
"settlements"`: points spaced along river branches and set off the channel
(`branches`), or spaced along the shore of the slice's own sea level inside
a box (`coast`), or at named places (`points`); kept on land, and dropped where a recorded site already
stands in the hex (so ingesting real sites retires the guesses). The output,
data/settlements/inferred.geojson, is for the app only (neolith-convert
--inferred): it never joins the recorded settlements, so no residual,
survey intensity, culture or importance step sees it. Inferred never
replaces recorded.
"""
import json
import math
import os
import tomllib

import numpy as np

from . import elevation, look
from .compose import phases
from .coords import _hex_of
from .settlements import site_id

KM_PER_DEG = 111.32
# Slices are millennia: a slice year y stands for [y, y + SLICE).
SLICE = 1000


def load(path):
    with open(path, "rb") as f:
        return tomllib.load(f).get("rule", [])


def shown(rule):
    """A rule with `show = false` is kept, checked and documented but writes
    no points, so the app does not show it."""
    return rule.get("show", True) is not False


def load_rivers(path):
    with open(path, "rb") as f:
        return {r["key"]: r for r in tomllib.load(f)["river"]}


def flows(river, year):
    """Whether a rivers.toml entry's `state` (a step function, absent before
    its first key) has the river perennial or seasonal in `year`."""
    keys = sorted((int(k), v) for k, v in river.get("state", {}).items())
    cur = "absent"
    for k, v in keys:
        if k <= year:
            cur = v
    return cur in ("perennial", "seasonal")


def _xy(lon, lat, lat0):
    return np.array([lon * KM_PER_DEG * math.cos(math.radians(lat0)), lat * KM_PER_DEG])


def along(points, spacing_km, shift=0.0):
    """[(lon, lat, unit normal (x, y) in km space)] every spacing_km down a
    polyline [[lon, lat], ...], the first at shift * spacing_km."""
    pts = np.asarray(points, float)
    lat0 = float(pts[:, 1].mean())
    xy = np.array([_xy(lo, la, lat0) for lo, la in pts])
    seg = np.diff(xy, axis=0)
    length = np.hypot(seg[:, 0], seg[:, 1])
    cum = np.concatenate([[0.0], np.cumsum(length)])
    out, s = [], shift * spacing_km
    while s <= cum[-1]:
        i = min(int(np.searchsorted(cum, s, side="right")) - 1, len(seg) - 1)
        t = (s - cum[i]) / length[i] if length[i] else 0.0
        p = xy[i] + seg[i] * t
        d = seg[i] / (length[i] or 1.0)
        out.append((p, np.array([-d[1], d[0]]), lat0))
        s += spacing_km
    return [(p[0] / (KM_PER_DEG * math.cos(math.radians(lat0))), p[1] / KM_PER_DEG, n) for p, n, lat0 in out]


def candidates(rule, rivers, slice_year, shift):
    """Points for one rule in one slice, before the land and clearing checks:
    [(lon, lat, branch key)]."""
    out, offsets, k = [], rule["offset_km"], 0
    for key in rule["branches"]:
        river = rivers[key]
        if not flows(river, slice_year):
            continue
        for lon, lat, n in along(river["points"], rule["spacing_km"], shift):
            off = offsets[k % len(offsets)] * (1 if k % 2 == 0 else -1)
            k += 1
            lat2 = lat + n[1] * off / KM_PER_DEG
            lon2 = lon + n[0] * off / (KM_PER_DEG * math.cos(math.radians(lat)))
            if not (rule.get("min_lat", -90) <= lat2 <= rule.get("max_lat", 90)
                    and rule.get("min_lon", -180) <= lon2 <= rule.get("max_lon", 180)):
                continue
            out.append((round(lon2, 4), round(lat2, 4), key))
    return out


class Shore:
    """The coastline of the elevation raster at a given sea level, for
    `coast` rules: land cells (2 arc-min) with an open-sea cell beside them.
    Open sea is as edge_sea.open_sea has it, so closed basins below sea
    level stay land."""

    def __init__(self, z, tf, curve, seed_depth):
        self.z, self.tf, self.curve, self.seed_depth = z, tf, curve, seed_depth
        self._sea = {}

    def sea(self, year):
        level = elevation.sea_level(year, self.curve)
        if level not in self._sea:
            from .edge_sea import open_sea
            self._sea[level] = open_sea(self.z, level, self.seed_depth)
        return self._sea[level]

    def cells(self, year, box):
        """[(lon, lat, shore)] of coast cells in `box` (west, south, east,
        north), north to south; `shore` numbers the connected land masses in
        the box, largest first (0 is the largest)."""
        from scipy import ndimage
        tf, sea = self.tf, self.sea(year)
        west, south, east, north = box
        r0, r1 = sorted((int(np.floor((north - tf.y0) / tf.e)), int(np.ceil((south - tf.y0) / tf.e))))
        c0, c1 = int(np.floor((west - tf.x0) / tf.a)), int(np.ceil((east - tf.x0) / tf.a))
        r0, c0 = max(r0 - 1, 0), max(c0 - 1, 0)
        r1, c1 = min(r1 + 2, sea.shape[0]), min(c1 + 2, sea.shape[1])
        s = sea[r0:r1, c0:c1]
        land = ~s & np.isfinite(self.z[r0:r1, c0:c1])
        wet = np.zeros_like(s)
        wet[1:] |= s[:-1]
        wet[:-1] |= s[1:]
        wet[:, 1:] |= s[:, :-1]
        wet[:, :-1] |= s[:, 1:]
        labels, n = ndimage.label(land, structure=np.ones((3, 3)))
        sizes = ndimage.sum(land, labels, range(1, n + 1))
        rank = {lab: k for k, lab in enumerate(np.argsort(-sizes, kind="stable") + 1)}
        out = []
        for r, c in zip(*np.nonzero(land & wet)):
            lon, lat = tf.x0 + (c0 + c) * tf.a, tf.y0 + (r0 + r) * tf.e
            if west <= lon <= east and south <= lat <= north:
                out.append((float(lon), float(lat), rank[labels[r, c]]))
        return out


def km(a, b):
    """Rough km between (lon, lat) points (equirectangular; short ranges)."""
    lat0 = math.radians((a[1] + b[1]) / 2)
    return math.hypot((a[0] - b[0]) * math.cos(lat0), a[1] - b[1]) * KM_PER_DEG


def coast_candidates(rule, cells, ok):
    """Points for one coast rule in one slice: [(lon, lat, shore)]. `cells`:
    Shore.cells for the slice; `ok(lon, lat)`: whether the point may stand
    (on a board hex that is land while it lives). The `prefer` points are
    placed first, each at the nearest usable coast cell within `prefer_km`;
    then coast cells north to south, each kept if it is at least
    `spacing_km` from every point so far; at most `max_points` in all."""
    c = rule["coast"]
    usable = [p for p in cells if ok(p[0], p[1])]
    out = []
    for a in c.get("prefer", []):
        near = [p for p in usable if km(p, a) <= c.get("prefer_km", 15.0)]
        if near:
            best = min(near, key=lambda p: km(p, a))
            if all(km(best, q) >= c["spacing_km"] for q in out):
                out.append(best)
    for p in usable:
        if all(km(p, q) >= c["spacing_km"] for q in out):
            out.append(p)
    out = out[:c.get("max_points", len(out))]
    return [(round(lo, 4), round(la, 4), sh) for lo, la, sh in out]


def point_candidates(rule):
    """Points for a `points` rule: the places it names, in order, as
    [(lon, lat, 0)]. For shores the sea-level coast does not see (lakes
    on a plateau or in a closed basin) and for single named places."""
    return [(round(float(lo), 4), round(float(la), 4), 0) for lo, la in rule["points"]["at"]]


def tag_for(rule, start):
    """The rule's [rule.tag] if it applies in the slice starting at `start`.
    It goes to the first point placed on each of the box's `shores` largest
    land masses (the preferred places come first)."""
    t = rule.get("tag")
    return t if t and start in t["slices"] else None


def build(rules, rivers, grid, feats, sites, years, log=print, shore=None):
    """Inferred site features. grid/feats: the built map (look.load_map);
    sites: the recorded settlements, for clearing; years: frame years;
    shore: a Shore, needed by `coast` rules."""
    terrain = look.series(feats, "terrain", years)
    index = {int(i): n for n, i in enumerate(grid.ids)}
    occupied = {}  # hex id -> [(start, end)] of recorded sites
    for f in sites:
        if not f.get("geometry"):
            continue
        h = _hex_of(grid, *f["geometry"]["coordinates"][:2])
        if h is not None:
            occupied.setdefault(h, []).extend(phases(f["properties"], years))
    step = SLICE
    out, report = [], []
    for rule in rules:
        slices = sorted(rule["slices"])
        spans = [(slices[0], slices[-1] + step)] if rule.get("persist") else [(y, y + step) for y in slices]
        shifts = rule.get("shift", 0.0)
        n, dropped = 0, {"water": 0, "cleared": 0, "off the map": 0}
        for j, (start, end) in enumerate(spans):
            shift = shifts[j % len(shifts)] if isinstance(shifts, list) else shifts
            live = [y for y in years if start <= y < end]
            later = [y for y in years if y >= end]

            def land(h):
                return h is not None and all(terrain[index[h], years.index(y)] != "Water" for y in live)

            if "coast" in rule:
                pts = coast_candidates(rule, shore.cells(start, rule["coast"]["box"]),
                                       lambda lo, la: land(_hex_of(grid, lo, la)))
            elif "points" in rule:
                pts = point_candidates(rule)
            else:
                # A persistent site needs its branch flowing from the start.
                pts = candidates(rule, rivers, start, shift)
            tag, tagged_shores = tag_for(rule, start), set()
            for lon, lat, key in pts:
                h = _hex_of(grid, lon, lat)
                if h is None:
                    dropped["off the map"] += 1
                    continue
                if not land(h):
                    dropped["water"] += 1
                    continue
                if rule.get("clear") == "hex" and any(a < end and b > start for a, b in occupied.get(h, [])):
                    dropped["cleared"] += 1
                    continue
                n += 1
                name = f"Inferred {rule['label']} {n}"
                key_ = f"inferred:{rule['key']}:{n}"
                info = {"rule": rule["key"], "plan": rule["plan"], "confidence": rule["confidence"]}
                if "points" not in rule:
                    info["shore" if "coast" in rule else "branch"] = key
                refs = [f"Inferred ({rule['confidence']} confidence): {rule['reasoning']}",
                        f"Rule {rule['key']} in data/settlements/inferred.toml, from {rule['plan']}"]
                flooded = next((y for y in later if terrain[index[h], years.index(y)] == "Water"), None)
                if flooded is not None:
                    info["drowned"] = flooded
                    refs.append(f"Its hex is under the sea by {-flooded} BCE.")
                if tag and key < tag.get("shores", 2) and key not in tagged_shores:
                    tagged_shores.add(key)
                    info["tag"] = tag["name"]
                    refs.append(f"Tagged {tag['name']} ({tag['confidence']} confidence): {tag['reasoning']}")
                out.append({"type": "Feature", "id": site_id(key_),
                            "geometry": {"type": "Point", "coordinates": [lon, lat]},
                            "properties": {
                                "name": name, "founding": start, "abandoned": end,
                                "occupation": [[start, end]], "type": rule["kind"], "population": {},
                                "importance": 0, "evidence": 0, "sources": ["inferred"],
                                "references": refs, "inferred": info, "key": key_}})
        report.append((rule["key"], n, dropped))
        log(f"{rule['key']}: {n} inferred sites; dropped " + ", ".join(f"{v} {k}" for k, v in dropped.items()))
    return out, report


def run(cfg, log=print):
    ic = cfg["inferred"]
    grid, feats = look.load_map(cfg)
    spath = cfg.get("settled_land", {}).get("out")
    if not spath or not os.path.exists(spath):
        spath = cfg["settlements"]["out"]
    with open(spath) as f:
        sites = json.load(f)["features"]
    years = look.all_years(cfg)
    rules = load(ic["rules"])
    for r in rules:
        if not os.path.exists(r["plan"]):
            raise ValueError(f"{ic['rules']}: rule {r['key']}: no plan {r['plan']}")
    hidden = [r["key"] for r in rules if not shown(r)]
    if hidden:
        log(f"not shown (show = false): {', '.join(hidden)}")
    rules = [r for r in rules if shown(r)]
    shore = None
    if any("coast" in r for r in rules):
        z, tf = elevation.load_asc(cfg["sea"]["elevation"])
        shore = Shore(z, tf, cfg["sea"]["curve"], cfg["sea"]["seed_depth"])
    out, _ = build(rules, load_rivers(ic["rivers"]), grid, feats, sites, years, log, shore)
    with open(ic["out"], "w") as f:
        json.dump({"type": "FeatureCollection", "features": out}, f, ensure_ascii=False, indent=1)
    log(f"wrote {ic['out']}: {len(out)} inferred settlements")
    return out
