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
neighbours' majority, else the nearest land hex's. Hexes on a sea
channel (`[[sea.channel]]`) are never made land.

Grouping by hex neighbours joins a near-shore island to the mainland when the
hex between them holds land of both (Dahlak to the Buri peninsula, Farasan to
the Tihama), and the mainland is left alone. With `near_shore`, a second pass
finds islands on the raster itself: ETOPO1 cells above the frame's water,
grouped into 8-connected landmasses. A landmass of at most `max_hexes` mean
hexes is an island; islands that share a hex are one group. A group with any
hex in a hex-neighbour landmass the first pass skipped as too big is treated
as above, counting a land hex as showing it only where the group has more of
the hex's cells than any other land, and ranking Water hexes by the group's
own share of them.
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


def hex_raster(grid, arr, tf):
    """The raster cells of every hex, flattened: (arr, flat cell indices,
    owning hex per cell, km2 per cell). Cells outside every hex or with no
    elevation are left out."""
    idx, own = [], []
    for i, (ring, bbox) in enumerate(zip(grid.rings, grid.bbox)):
        rr, cc = hex_pixels(ring, bbox, tf, arr.shape)
        if len(rr):
            idx.append(rr * arr.shape[1] + cc)
            own.append(np.full(len(rr), i))
    idx = np.concatenate(idx) if idx else np.zeros(0, dtype=np.int64)
    own = np.concatenate(own) if own else np.zeros(0, dtype=np.int64)
    ok = np.isfinite(arr.ravel()[idx])
    idx, own = idx[ok], own[ok]
    lat = tf.y0 + (idx // arr.shape[1]) * tf.e
    km2 = abs(tf.a * 111.32 * tf.e * 110.57) * np.cos(np.radians(lat))
    return arr, idx, own, km2


def near_shore_groups(raster, level, big, area, icfg):
    """Islands on the raster that touch a hex in a too-big hex landmass.
    Yields (hexes, the group's share of each hex's cells, whether the group
    has the most land cells of each hex, the group's land km2)."""
    from scipy import ndimage
    arr, idx, own, km2 = raster
    n = len(level)
    land = np.zeros(arr.size, dtype=bool)
    up = arr.ravel()[idx] > level[own]
    land[idx[up]] = True
    lab, nlab = ndimage.label(land.reshape(arr.shape), structure=np.ones((3, 3), dtype=bool))
    lab = lab.ravel()[idx]
    if not nlab:
        return
    comp_km2 = np.bincount(lab, weights=km2, minlength=nlab + 1)
    is_island = comp_km2 <= icfg["max_hexes"] * area.mean()
    is_island[0] = False
    sel = is_island[lab]
    if not sel.any():
        return
    # Islands sharing a hex are one group (union-find over island labels).
    parent = np.arange(nlab + 1)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    pairs = np.unique(np.stack([own[sel], lab[sel]], axis=1), axis=0)
    first = {}
    for h, c in pairs:
        if h in first:
            ra, rb = find(first[h]), find(c)
            if ra != rb:
                parent[rb] = ra
        else:
            first[h] = c
    root = np.array([find(c) for c in range(nlab + 1)])
    total = np.bincount(own, minlength=n)
    # Land cells per (hex, label) to find what holds most of each hex's land.
    lp = lab > 0
    key = own[lp].astype(np.int64) * (nlab + 1) + np.where(is_island[lab[lp]], root[lab[lp]], lab[lp])
    uk, cnt = np.unique(key, return_counts=True)
    kh, kc = uk // (nlab + 1), uk % (nlab + 1)
    most = np.zeros(n, dtype=np.int64)
    np.maximum.at(most, kh, cnt)
    gkm2 = np.bincount(root[lab[sel]], weights=km2[sel], minlength=nlab + 1)
    for g in np.unique(root[lab[sel]]):
        m = kc == g
        hexes, c = kh[m], cnt[m]
        if not big[hexes].any():
            continue
        yield hexes, c / np.maximum(total[hexes], 1), c >= most[hexes], float(gkm2[g])


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


def keep_islands(terrain, before, grid, cells, cfg, lakes, icfg, raster=None):
    """Returns (terrain, {year: [(component size, area km2, wanted, had, added)]},
    {year: hexes restored as majority land}). `raster` (from `hex_raster`) turns
    on the near-shore pass when `icfg["near_shore"]` is set."""
    area = hex_area_km2(grid)
    centres = grid.centres
    out, stats, restored = {}, {}, {}
    maj = icfg.get("restore_majority_land")
    # Sea channels ([[sea.channel]]) stay Water whatever their land share.
    from .elevation import channel_mask
    chans = cfg["sea"].get("channel", [])
    for y in sorted(terrain):
        channel = channel_mask(centres, chans, year=y)
        t = terrain[y]
        lv, _ = lake_levels_at(lakes, centres[:, 0], centres[:, 1], y)
        level = water_levels(grid, y, cfg, lakes, lv)
        frac = land_fraction(cells, level)
        changed, rows = None, []
        # Drawn Water on a hex that is mostly land at that year's water level
        # and not in a lake: the drawing put the coast a hex off.
        b = before.get(y)
        if maj and b is not None:
            fix = np.flatnonzero((t == "Water") & (b == "Water") & (frac >= maj) & ~np.isfinite(lv) & ~channel)
            if len(fix):
                changed = t.copy()
                for i in fix:
                    changed[i] = land_class(changed, i, None, grid.neighbours, centres, changed != "Water")
                restored[y] = len(fix)
                t = changed
        big = np.zeros(len(centres), dtype=bool)
        for comp in components(frac > icfg["min_any_fraction"], grid.neighbours):
            if len(comp) > icfg["max_hexes"]:
                big[comp] = True
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
                    if t[i] == "Water" and frac[i] >= icfg["min_hex_fraction"] and not channel[i]]
            add = cand[:want - have]
            if not add:
                continue
            if changed is None:
                changed = t.copy()
            for i in add:
                changed[i] = land_class(changed, i, before.get(y), grid.neighbours, centres,
                                        changed != "Water")
            rows.append((len(comp), round(land_km2), want, have, len(add)))
        if raster is not None and icfg.get("near_shore") and big.any():
            cur = t if changed is None else changed
            for hexes, share, have_mask, land_km2 in near_shore_groups(raster, level, big, area, icfg):
                if land_km2 < icfg["min_area_km2"]:
                    continue
                want = max(1, int(round(land_km2 / area[hexes].mean())))
                have = int((have_mask & (cur[hexes] != "Water")).sum())
                if have >= want:
                    continue
                order = np.argsort(-share)
                add = [int(hexes[k]) for k in order
                       if cur[hexes[k]] == "Water" and share[k] >= icfg["min_hex_fraction"] and not channel[hexes[k]]]
                add = add[:want - have]
                if not add:
                    continue
                if changed is None:
                    changed = t.copy()
                    cur = changed
                for i in add:
                    changed[i] = land_class(changed, i, before.get(y), grid.neighbours, centres, changed != "Water")
                rows.append((len(hexes), round(land_km2), want, have, len(add)))
        out[y] = t if changed is None else changed
        stats[y] = rows
    return out, stats, restored
