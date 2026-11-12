"""Pollen-based land cover on a 1° grid: the LandClimII REVEALS reconstruction
(Fyfe et al. 2021, PANGAEA 937075, CC BY 4.0; Githumbi et al. 2022, ESSD 14:1581).

25 time windows: 0-100, 100-350 and 350-700 BP, then 500-year windows from
700 to 11,700 BP. A slice takes the mean of the windows at least half inside
it (so 10,000 BCE, 11,450-12,450 BP, uses only 11,200-11,700 BP); each hex
takes the 1° cell containing its centre. Cells without a reconstruction stay
empty (masked). Firmness is the probability, from the reconstruction's
standard error, that the cell is at or above the layer's middle level.
"""
import io
import os
import re
import zipfile
from math import erf, sqrt

import numpy as np
import pandas as pd


def window_bounds(k):
    """Time window k (1-25) as (young, old) in cal BP."""
    if k == 1:
        return 0, 100
    if k == 2:
        return 100, 350
    if k == 3:
        return 350, 700
    return 700 + 500 * (k - 4), 1200 + 500 * (k - 4)


def read(path, column):
    """{window: DataFrame(lon, lat, mean, se)} for one REVEALS column."""
    z = zipfile.ZipFile(path)
    out = {}
    for name in z.namelist():
        m = re.search(r"/TW(\d+)\.RV\.estimates", name)
        if not m:
            continue
        k = int(m.group(1))
        mean = pd.read_csv(io.BytesIO(z.read(name)))
        se_name = name.replace("means", "standarderrors").replace("estimates", "standarderrors")
        se = pd.read_csv(io.BytesIO(z.read(se_name))) if se_name in z.namelist() else None
        df = mean[["lonDD", "latDD", column]].rename(columns={"lonDD": "lon", "latDD": "lat", column: "mean"})
        df["se"] = se[column].values if se is not None else np.nan
        # Every window lists all 420 cells; a cell without a reconstruction in
        # that window is a row of zeros, not 0% cover. Drop those rows.
        lct = [c for c in ("ET", "ST", "OL") if c in mean.columns]
        df = df[mean[lct].sum(axis=1).values > 0]
        out[k] = df
    return out


def surface(cfg, grid, years, L, log=print):
    path = os.path.join(cfg["output"]["build_dir"], "sources", L["file"])
    if not os.path.exists(path):
        log(f"{L['id']}: {L['file']} missing (run `python -m isostyle fetch`); skipped")
        return None
    wins = read(path, L["column"])
    half = np.diff(years).min() / 2
    C, S = len(grid), len(years)
    f, se = np.full((C, S), np.nan), np.full((C, S), np.nan)
    key = lambda lon, lat: (np.floor(np.asarray(lon)).astype(int), np.floor(np.asarray(lat)).astype(int))
    gx, gy = key(grid["lon"].values, grid["lat"].values)
    for j, y in enumerate(years):
        young, old = -y + 1950 - half, -y + 1950 + half
        # Windows at least half inside the slice.
        use = [k for k in wins
               if min(window_bounds(k)[1], old) - max(window_bounds(k)[0], young) >= 0.5 * (window_bounds(k)[1] - window_bounds(k)[0])]
        if not use:
            continue
        stack = pd.concat([wins[k] for k in use])
        agg = stack.groupby(["lon", "lat"]).agg(mean=("mean", "mean"), se=("se", lambda s: np.sqrt((s ** 2).mean() / len(s))))
        lut = {key(lo, la): (m, e) for (lo, la), (m, e) in zip(agg.index, agg[["mean", "se"]].values)}
        for i in range(C):
            v = lut.get((gx[i], gy[i]))
            if v is not None and not np.isnan(v[0]):
                f[i, j], se[i, j] = v
    mid = L["levels"][len(L["levels"]) // 2]
    z = (f - mid) / np.where(se > 0, se, np.nan)
    above = np.where(np.isnan(f), np.nan, np.where(np.isnan(z), (f >= mid).astype(float),
                                                   0.5 * (1 + np.vectorize(erf)(np.nan_to_num(z) / sqrt(2)))))
    have = ~np.isnan(f)
    log(f"{L['id']}: {int(have.any(axis=1).sum())} hexes with a reconstruction; per slice {have.sum(axis=0).tolist()}")
    zero = np.zeros((C, S))
    return {"f": f, "E": np.where(have, 1e6, 0.0), "label_share": zero, "E_all": zero, "recorded_share": zero,
            "boot_above": above, "boot_valid": have.astype(float), "f0": np.nanmean(f, axis=0), "se": se}
