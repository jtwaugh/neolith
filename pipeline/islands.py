"""Keep islands on the map.

A hex is Water when most of it is (the sea overlay, the drawn keyframes), so
an island smaller than a hex or two, or one split across hex edges, loses
every vote and drops out: Gotland, Bornholm, Menorca and Malta all vanished.

Per frame, each hex's land fraction is the share of its ETOPO1 cells above
that frame's water: the level of a modelled lake whose shoreline that year
encloses the hex centre, else global sea level, on a surface corrected for
glacio-isostatic uplift still to come. First, drawn Water on a hex that is
at least `restore_majority_land` land at that level, outside every lake, is
a coast drawn a hex off and becomes land. Hexes with any land are grouped into
landmasses through hex neighbours. A landmass of at most `max_hexes` hexes
whose land area is at least `min_area_km2` should show
max(1, round(area / mean hex area)) land hexes; if it shows fewer, its
Water hexes with the most land become land, best first, as long as they
are at least `min_hex_fraction` land. Bigger landmasses (the mainland) are
left alone. A new land hex takes its own pre-water biome, else its land
neighbours' majority, else the nearest land hex's.
"""
import math

import numpy as np

from .compose import lake_levels_at
from .raster import hex_pixels


def hex_cells(grid, arr, tf):
    """Per hex, its cells' elevations sorted ascending (empty if none)."""
    out = []
    for ring, bbox in zip(grid.rings, grid.bbox):
        rr, cc = hex_pixels(ring, bbox, tf, arr.shape)
        v = arr[rr, cc].astype(np.float64) if len(rr) else np.zeros(0)
        out.append(np.sort(v[np.isfinite(v)]))
    return out


def hex_area_km2(grid):
    """Approximate area of each hex: 3/4 of its bbox (a flat-topped hex)."""
    b = grid.bbox
    lat = (b[:, 1] + b[:, 3]) / 2
    w = np.abs(b[:, 2] - b[:, 0]) * 111.32 * np.cos(np.radians(lat))
    h = np.abs(b[:, 1] - b[:, 3]) * 110.57
    return 0.75 * w * h


def land_fraction(cells, level):
    """Share of each hex's cells above `level` (one level per hex)."""
    out = np.zeros(len(cells))
    for i, c in enumerate(cells):
        if len(c):
            out[i] = 1.0 - np.searchsorted(c, level[i], side="right") / len(c)
    return out


def water_levels(grid, year, cfg, lakes, lake_level=None):
    """Per hex: the water level (m) relative to today's surface that year:
    the level of a modelled lake whose shoreline encloses the hex centre,
    else global sea level, plus the uplift still to come there.
    `lake_level` is `lake_levels_at`'s level for the centres, if already known."""
    from . import isostasy
    from .elevation import sea_level
    c = grid.centres
    lv = lake_level if lake_level is not None else lake_levels_at(lakes, c[:, 0], c[:, 1], year)[0]
    level = np.where(np.isfinite(lv), lv, sea_level(year, cfg["sea"]["curve"]))
    if cfg.get("isostasy"):
        level = level + isostasy.uplift(c[:, 0], c[:, 1], year, cfg["isostasy"])
    return level


def components(mask, neighbours):
    """Connected groups of hexes in `mask`, as lists of indices."""
    seen = np.zeros(len(mask), dtype=bool)
    out = []
    for s in np.flatnonzero(mask):
        if seen[s]:
            continue
        stack, comp = [s], []
        seen[s] = True
        while stack:
            i = stack.pop()
            comp.append(i)
            for j in neighbours[i]:
                if mask[j] and not seen[j]:
                    seen[j] = True
                    stack.append(j)
        out.append(comp)
    return out


def land_class(t, i, before, neighbours, centres, land):
    """The class a hex that becomes land takes."""
    if before is not None and before[i] not in ("Water", "Land", "", "Ice"):
        return before[i]
    near = [t[j] for j in neighbours[i] if t[j] not in ("Water", "Alpine", "Ice")]
    if near:
        vals, counts = np.unique(near, return_counts=True)
        return vals[counts.argmax()]
    cand = np.flatnonzero(land)
    if not len(cand):
        return "Grassland"
    d = (centres[cand, 0] - centres[i, 0]) ** 2 * math.cos(math.radians(centres[i, 1])) ** 2 \
        + (centres[cand, 1] - centres[i, 1]) ** 2
    return t[cand[int(d.argmin())]]


def keep_islands(terrain, before, grid, cells, cfg, lakes, icfg):
    """Returns (terrain, {year: [(component size, area km2, wanted, had, added)]},
    {year: hexes restored as majority land})."""
    area = hex_area_km2(grid)
    centres = grid.centres
    out, stats, restored = {}, {}, {}
    maj = icfg.get("restore_majority_land")
    for y in sorted(terrain):
        t = terrain[y]
        lv, _ = lake_levels_at(lakes, centres[:, 0], centres[:, 1], y)
        frac = land_fraction(cells, water_levels(grid, y, cfg, lakes, lv))
        changed, rows = None, []
        # Drawn Water on a hex that is mostly land at that year's water level
        # and not in a lake: the drawing put the coast a hex off.
        b = before.get(y)
        if maj and b is not None:
            fix = np.flatnonzero((t == "Water") & (b == "Water") & (frac >= maj) & ~np.isfinite(lv))
            if len(fix):
                changed = t.copy()
                for i in fix:
                    changed[i] = land_class(changed, i, None, grid.neighbours, centres, changed != "Water")
                restored[y] = len(fix)
                t = changed
        for comp in components(frac > icfg["min_any_fraction"], grid.neighbours):
            if len(comp) > icfg["max_hexes"]:
                continue
            comp = np.array(comp)
            land_km2 = float((frac[comp] * area[comp]).sum())
            if land_km2 < icfg["min_area_km2"]:
                continue
            want = max(1, int(round(land_km2 / area[comp].mean())))
            land = (t[comp] != "Water")
            have = int(land.sum())
            if have >= want:
                continue
            cand = [i for i in comp[np.argsort(-frac[comp])]
                    if t[i] == "Water" and frac[i] >= icfg["min_hex_fraction"]]
            add = cand[:want - have]
            if not add:
                continue
            if changed is None:
                changed = t.copy()
            for i in add:
                changed[i] = land_class(changed, i, before.get(y), grid.neighbours, centres,
                                        changed != "Water")
            rows.append((len(comp), round(land_km2), want, have, len(add)))
        out[y] = t if changed is None else changed
        stats[y] = rows
    return out, stats, restored
