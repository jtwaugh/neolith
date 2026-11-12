"""Biome cleanup: the model-derived parts of the terrain made to read like a
map rather than a resampled grid.

- `warp`: roughens the straight row/column edges that come from filling
  hexes off the 0.5 degree BIOME4 grid (one model cell per hex), by sampling
  each model-filled hex's biome at a smoothly displaced position. The
  displacement field is one fixed field for every year, so edges wiggle the
  same way over time instead of shimmering.
- `fix_adjacency`: replaces biome pairs that should never touch (extreme
  desert against boreal forest, say) with a bridging biome.
- `floodplains`: green river bottomland where a big perennial river crosses
  dry or open country.
- `clear_water_population`: no population on hexes that are Water that year.

Config: [biome.edges], [biome.adjacency], [rivers.floodplain]; each stage
has an `enabled` flag.
"""
import numpy as np

from . import elevation
from .paleobiome import NON_BIOME
from .rivers import HexLocator


def _hex_size(grid):
    b = grid.bbox
    return abs(b[0, 2] - b[0, 0]), abs(b[0, 1] - b[0, 3])


def value_noise(xy, period, seed):
    """Smooth value noise in -1..1 at points `xy` (N, 2): random values on a
    square lattice of spacing `period`, blended with smoothstep weights."""
    rng = np.random.default_rng(seed)
    p = xy / period
    lo = np.floor(p).astype(int)
    lo -= lo.min(axis=0)
    f = p - np.floor(p)
    shape = lo.max(axis=0) + 2
    lattice = rng.uniform(-1.0, 1.0, size=tuple(shape))
    s = f * f * (3 - 2 * f)
    x0, y0 = lo[:, 0], lo[:, 1]
    v00, v10 = lattice[x0, y0], lattice[x0 + 1, y0]
    v01, v11 = lattice[x0, y0 + 1], lattice[x0 + 1, y0 + 1]
    a = v00 + (v10 - v00) * s[:, 0]
    b = v01 + (v11 - v01) * s[:, 0]
    return a + (b - a) * s[:, 1]


def warp_targets(grid, cfg):
    """For each hex, the hex its biome is sampled from (-1: none): its centre
    displaced by `amplitude` hexes of two value-noise fields (x and y) with a
    `period` of that many hexes, plus a finer octave for the small kinks."""
    w, h = _hex_size(grid)
    c = grid.centres
    seed = cfg.get("seed", 7)
    period = cfg.get("period", 4.0) * w
    amp = cfg.get("amplitude", 1.2) * w
    d = np.zeros_like(c)
    for axis in (0, 1):
        n = (value_noise(c, period, seed + axis) * 0.7
             + value_noise(c + 13.7 * w, period / 2.3, seed + 10 + axis) * 0.3)
        d[:, axis] = n * amp
    return HexLocator(grid).locate(c + d)


def warp(terrain, targets, mask):
    """`terrain` with each `mask` hex given the biome at its warp target,
    where both are land biomes (Water, Ice, Alpine etc. never move). Returns
    (terrain, number changed)."""
    out = terrain.copy()
    land = ~np.isin(terrain, NON_BIOME)
    ok = mask & land & (targets >= 0)
    idx = np.flatnonzero(ok)
    src = terrain[targets[idx]]
    take = ~np.isin(src, NON_BIOME)
    out[idx[take]] = src[take]
    return out, int((out != terrain).sum())


def forbid_table(cfg):
    """{frozenset(a, b): bridge} from [biome.adjacency] forbid = [[a, b, bridge], ...]."""
    return {frozenset((a, b)): bridge for a, b, bridge in cfg.get("forbid", [])}


def fix_adjacency(terrain, neighbours, forbid, prefer=None, fixed=("Water", "Ice", "Alpine"),
                  max_passes=8):
    """Replace one side of every forbidden neighbouring pair with the pair's
    bridging biome, until none is left (or `max_passes`). The side changed is
    the `prefer` (model-filled) one if just one is, else the one with fewer
    neighbours of its own biome; `fixed` biomes are never changed. Returns
    (terrain, number of hexes changed)."""
    out = terrain.copy()
    prefer = np.zeros(len(out), dtype=bool) if prefer is None else prefer
    names = set(n for pair in forbid for n in pair)
    total = 0
    for _ in range(max_passes):
        change = {}
        for i in np.flatnonzero(np.isin(out, list(names))):
            a = out[i]
            for j in neighbours[i]:
                if j < i:
                    continue
                bridge = forbid.get(frozenset((a, out[j])))
                if bridge is None:
                    continue
                k = _side(out, neighbours, i, j, prefer, fixed)
                if k is not None:
                    change.setdefault(k, bridge)
        if not change:
            break
        for k, v in change.items():
            out[k] = v
        total += len(change)
    return out, total


def _side(t, neighbours, i, j, prefer, fixed):
    can = [k for k in (i, j) if t[k] not in fixed]
    if len(can) < 2:
        return can[0] if can else None
    if prefer[i] != prefer[j]:
        return i if prefer[i] else j
    own = [sum(t[n] == t[k] for n in neighbours[k]) for k in (i, j)]
    return i if own[0] < own[1] else j if own[1] < own[0] else max(i, j)


def floodplains(terrain, river, elev, landform, neighbours, cfg):
    """Floodplain hexes for one year: hexes on a big perennial river (class
    2) in one of the `apply_to` biomes and not on mountains, then their flat
    neighbours (same biomes) no more than `max_rise` m above them. Returns
    (terrain, number changed)."""
    apply_to = cfg.get("apply_to", [])
    open_ = np.isin(terrain, apply_to) & (landform < elevation.MOUNTAINS)
    core = open_ & (river >= cfg.get("river_class", 2))
    out = terrain.copy()
    out[core] = "Floodplain"
    rise = cfg.get("max_rise", 30.0)
    for _ in range(cfg.get("spread", 1)):
        grow = []
        for i in np.flatnonzero(out == "Floodplain"):
            for j in neighbours[i]:
                if (open_[j] and out[j] != "Floodplain" and landform[j] == elevation.FLAT
                        and np.isfinite(elev[j]) and np.isfinite(elev[i])
                        and elev[j] - elev[i] <= rise):
                    grow.append(j)
        out[grow] = "Floodplain"
    return out, int((out == "Floodplain").sum() - (terrain == "Floodplain").sum())


def clear_water_population(pop, terrain):
    """Population 0 wherever the year's terrain is Water. Returns
    ({year: array}, hex-years cleared)."""
    out, n = {}, 0
    for y, p in pop.items():
        wet = (terrain[y] == "Water") & (p != 0)
        p = p.copy()
        p[wet] = 0.0
        out[y] = p
        n += int(wet.sum())
    return out, n
