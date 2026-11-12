"""Net primary productivity per hex per key frame, by the Miami model
(Lieth 1973) from the annual mean temperature and annual precipitation of the
same Beyer et al. 2020 model run as the biomes and Köppen classes. Grams of
dry matter per square metre per year.

An input to expected population (data/population/SOURCES.md), so it uses no
site or date counts. The Miami model, not the climate model's own `npp`,
because the forager-density model (Tallavaara et al. 2018) was fitted on it."""
import numpy as np

from . import paleobiome


def fill_from_neighbours(values, neighbours, passes):
    """NaN hexes take the mean of their non-NaN neighbours, `passes` rings
    deep (exposed shelf beyond the model's land cells). Returns the filled
    array and how many hexes were filled."""
    out, filled = values.copy(), 0
    for _ in range(passes):
        todo = np.flatnonzero(np.isnan(out))
        new = {}
        for i in todo:
            v = out[neighbours[i]]
            v = v[np.isfinite(v)]
            if len(v):
                new[i] = v.mean()
        if not new:
            break
        for i, v in new.items():
            out[i] = v
        filled += len(new)
    return out, filled


def miami(temperature, precipitation):
    """Miami-model productivity (g dry matter/m²/yr) from annual mean
    temperature (degC) and annual precipitation (mm): whichever of the two
    limits it more. Constants as in Tallavaara et al.'s script."""
    by_t = 3000.0 / (1.0 + np.exp(1.315 - 0.119 * np.asarray(temperature, dtype=float)))
    by_p = 3000.0 * (1.0 - np.exp(-0.000664 * np.asarray(precipitation, dtype=float)))
    return np.minimum(by_t, by_p)


def build(grid, pcfg, cfg, shift=None):
    """({year: int array (N,)}, stats) for cfg["years"]. `shift` (degC per
    hex) moves the model temperature to each hex's elevation. Hexes the model
    has no land cell near (open sea) are 0; the app shows no productivity on
    a hex that is Water in a given year, whatever is stored."""
    names = [cfg["temperature"], cfg["precipitation"]]
    clim = paleobiome.load_climate(pcfg["data"], names)
    _, bp, tf = paleobiome.load(pcfg["data"])
    cells = paleobiome.hex_cells(grid, tf, clim[names[0]].shape[1:])
    step = cfg.get("round", 1)
    out, stats = {}, {}
    for y in cfg["years"]:
        t = paleobiome.bp_index(y, bp)
        temp = paleobiome.hex_mean(grid, clim[names[0]][t], tf, cells)
        if shift is not None:
            temp = temp + np.where(np.isfinite(shift), shift, 0.0)
        v = miami(temp, paleobiome.hex_mean(grid, clim[names[1]][t], tf, cells))
        v, filled = fill_from_neighbours(v, grid.neighbours, cfg.get("fill_rings", 0))
        sea = np.isnan(v)
        v = np.where(sea, 0.0, np.clip(v, 0.0, None))
        out[y] = (np.round(v / step) * step).astype(int)
        land = out[y][~sea]
        stats[y] = {"bp": int(bp[t]), "filled": int(filled), "no_data": int(sea.sum()),
                    "median": float(np.median(land)), "max": int(land.max())}
    return out, stats
