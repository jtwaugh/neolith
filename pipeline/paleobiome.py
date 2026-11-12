"""Modelled paleo-biomes (Beyer, Krapp & Manica 2020, BIOME4 at 0.5 degrees)
for hexes the hand-drawn keyframes leave as "Land".

`subset` cuts the 1.3 GB global NetCDF down to our box and years once
(build/biome.npz); `load` and `hex_biomes` read that.
"""
import warnings

import numpy as np

from .raster import Affine, hex_majority

NODATA = -1


def subset(nc_path, out_path, box, bp_min, bp_max, climate_vars=(), monthly_vars=()):
    """Save biome codes for lon/lat `box` (lon0, lat0, lon1, lat1) and slices
    bp_min..bp_max years BP as .npz: biome (t, row, col) int16 with row 0 the
    northernmost, bp (t,), and the pixel-centre transform. Each name in
    `climate_vars` is saved too, as float32 with NaN off land. Each name in
    `monthly_vars` (t, month, lat, lon) is saved as clim_{name} (t, 12, row,
    col), plus its 0 BP slice as modern_{name} (12, row, col) for validation."""
    import netCDF4  # only needed here

    with netCDF4.Dataset(nc_path) as nc:
        lon = np.asarray(nc.variables["longitude"][:], float)
        lat = np.asarray(nc.variables["latitude"][:], float)
        bp = -np.asarray(nc.variables["time"][:], float)  # file: negative BP
        lon0, lat0, lon1, lat1 = box
        ci = np.flatnonzero((lon >= lon0) & (lon <= lon1))
        ri = np.flatnonzero((lat >= lat0) & (lat <= lat1))
        ti = np.flatnonzero((bp >= bp_min) & (bp <= bp_max))
        var = nc.variables["biome"]
        var.set_auto_mask(True)
        rs, cs = slice(ri.min(), ri.max() + 1), slice(ci.min(), ci.max() + 1)
        b = var[ti, rs, cs]
        clim = {}
        for name in climate_vars:
            v = nc.variables[name]
            v.set_auto_mask(True)
            clim[name] = np.ma.filled(v[ti, rs, cs].astype(np.float32), np.nan)
        modern = {}
        t0 = int(np.abs(bp).argmin())
        for name in monthly_vars:
            v = nc.variables[name]
            v.set_auto_mask(True)
            clim[name] = np.ma.filled(v[ti, :, rs, cs].astype(np.float32), np.nan)
            modern[name] = np.ma.filled(v[t0, :, rs, cs].astype(np.float32), np.nan)
    b = np.ma.filled(np.ma.masked_invalid(b.astype(float)), NODATA)
    b = np.where(np.isfinite(b), b, NODATA).astype(np.int16)
    lat_s = lat[ri.min():ri.max() + 1]
    lon_s = lon[ci.min():ci.max() + 1]
    if lat_s[0] < lat_s[-1]:  # make row 0 the north edge
        b, lat_s = b[:, ::-1, :], lat_s[::-1]
        clim = {k: v[..., ::-1, :] for k, v in clim.items()}
        modern = {k: v[:, ::-1, :] for k, v in modern.items()}
    res_x, res_y = lon_s[1] - lon_s[0], lat_s[1] - lat_s[0]
    np.savez_compressed(out_path, biome=b, bp=bp[ti],
                        transform=np.array([res_x, res_y, lon_s[0], lat_s[0]]),
                        **{f"clim_{k}": v for k, v in clim.items()},
                        **{f"modern_{k}": v for k, v in modern.items()})


def load(path):
    """(biome (t, row, col), bp (t,), Affine) from `subset`'s output."""
    d = np.load(path)
    a, e, x0, y0 = d["transform"]
    return d["biome"], d["bp"], Affine(a, e, x0, y0)


def load_climate(path, names):
    """{name: (t, row, col) float array} from `subset`'s output."""
    d = np.load(path)
    missing = [n for n in names if f"clim_{n}" not in d]
    if missing:
        raise KeyError(f"{path} has no {missing}; rerun `python -m pipeline biome`")
    return {n: d[f"clim_{n}"] for n in names}


def bp_index(year, bp):
    """Index of the slice nearest a BCE year (negative int): BP = 1950 - year."""
    return int(np.abs(bp - (1950 - year)).argmin())


def hex_codes(grid, codes, tf, ignore=()):
    """Majority BIOME4 code per hex (NODATA where none). Hexes with no cell
    centre inside take the nearest valid cell within two cells."""
    classes = codes.astype(int)
    classes[np.isin(classes, list(ignore)) | (classes < 0)] = -1
    out = hex_majority(grid, classes, tf, int(classes.max()) + 1 if classes.max() >= 0 else 1)
    c = grid.centres
    for i in np.flatnonzero(out < 0):
        r, k = tf.row(c[i, 1]), tf.col(c[i, 0])
        best, bd = -1, np.inf
        for rr in range(int(np.floor(r)) - 2, int(np.ceil(r)) + 3):
            for cc in range(int(np.floor(k)) - 2, int(np.ceil(k)) + 3):
                if 0 <= rr < classes.shape[0] and 0 <= cc < classes.shape[1] \
                        and classes[rr, cc] >= 0:
                    d = (rr - r) ** 2 + (cc - k) ** 2
                    if d < bd:
                        best, bd = classes[rr, cc], d
        out[i] = best
    return out


# Terrain classes that say nothing about vegetation: not used as training
# labels, and left out of agreement figures.
NON_BIOME = ("Water", "Ice", "Mountains", "Alpine", "Land", "Unknown", "Free", "")


def hex_cells(grid, tf, shape):
    """(rows, cols) of the raster cells inside each hex."""
    from .raster import hex_pixels
    return [hex_pixels(ring, bbox, tf, shape) for ring, bbox in zip(grid.rings, grid.bbox)]


def hex_mean(grid, arr, tf, cells=None):
    """Mean of the non-NaN cells per hex. Hexes with none take the nearest
    non-NaN cell within two cells; NaN if there is none."""
    cells = cells or hex_cells(grid, tf, arr.shape)
    out = np.full(len(grid), np.nan)
    for i, (rr, cc) in enumerate(cells):
        v = arr[rr, cc]
        v = v[np.isfinite(v)]
        if len(v):
            out[i] = v.mean()
    c = grid.centres
    for i in np.flatnonzero(np.isnan(out)):
        r, k = tf.row(c[i, 1]), tf.col(c[i, 0])
        r0, r1 = max(int(np.floor(r)) - 2, 0), min(int(np.ceil(r)) + 3, arr.shape[0])
        k0, k1 = max(int(np.floor(k)) - 2, 0), min(int(np.ceil(k)) + 3, arr.shape[1])
        rr, cc = np.mgrid[r0:r1, k0:k1]
        ok = np.isfinite(arr[r0:r1, k0:k1])
        if ok.any():
            d = (rr - r) ** 2 + (cc - k) ** 2
            j = np.argmin(np.where(ok, d, np.inf))
            out[i] = arr[r0:r1, k0:k1].flat[j]
    return out


# Bioclimatic variables that are temperatures (degC), so shift with elevation.
# BIO2/3/4/7 are ranges or ratios and don't; BIO12-19 are precipitation.
TEMPERATURE_VARS = {"BIO1", "BIO5", "BIO6", "BIO8", "BIO9", "BIO10", "BIO11"}


def cell_elevation(z, z_tf, tf, shape):
    """Mean land elevation (m) of each model cell (`tf`, `shape`) from the
    finer DEM `z` (`z_tf`): the elevation the model's climate stands for.
    Only cells above 0 m count, so coastal cells aren't pulled down by the
    sea floor; a cell with no land is 0."""
    rows = np.rint(tf.row(z_tf.y0 + z_tf.e * np.arange(z.shape[0]))).astype(int)
    cols = np.rint(tf.col(z_tf.x0 + z_tf.a * np.arange(z.shape[1]))).astype(int)
    rr, cc = np.meshgrid(rows, cols, indexing="ij")
    ok = (rr >= 0) & (rr < shape[0]) & (cc >= 0) & (cc < shape[1]) & (np.nan_to_num(z, nan=-1) > 0)
    idx = rr[ok] * shape[1] + cc[ok]
    total = np.bincount(idx, weights=z[ok].astype(float), minlength=shape[0] * shape[1])
    count = np.bincount(idx, minlength=shape[0] * shape[1])
    with np.errstate(invalid="ignore"):
        out = np.where(count > 0, total / np.maximum(count, 1), 0.0)
    return out.reshape(shape)


def elevation_offset(grid, hex_elev, z, z_tf, tf, shape, cells=None):
    """Per hex: its median elevation minus the mean elevation of the model
    cells it samples (metres, 0 where unknown or below sea level). Climate
    at the hex = model climate - lapse rate * offset."""
    zc = hex_mean(grid, cell_elevation(z, z_tf, tf, shape), tf, cells)
    dz = np.maximum(np.nan_to_num(hex_elev, nan=0.0), 0.0) - np.nan_to_num(zc, nan=0.0)
    return np.where(np.isfinite(hex_elev), dz, 0.0)


def features(grid, clim, tf, t, spec, cells=None, shift=None):
    """(N, len(spec)) climate features per hex for slice t. spec: list of
    [name, "log"|"linear"]; "log" takes log1p (precipitation). `shift`
    (degC per hex) is added to the temperature variables (TEMPERATURE_VARS)."""
    cols = []
    for name, scale in spec:
        v = hex_mean(grid, clim[name][t], tf, cells)
        if shift is not None and name in TEMPERATURE_VARS:
            v = v + shift
        cols.append(np.log1p(np.maximum(v, 0)) if scale == "log" else v)
    return np.column_stack(cols)


def hex_monthly(grid, monthly, tf, cells=None):
    """(N, 12) per-hex means of a (12, row, col) monthly field, over the
    cells that are finite in every month. Hexes with none take the nearest
    such cell within two cells (as `hex_mean`); NaN if there is none."""
    monthly = np.asarray(monthly)
    cells = cells or hex_cells(grid, tf, monthly.shape[1:])
    ok = np.isfinite(monthly).all(0)
    out = np.full((len(grid), monthly.shape[0]), np.nan)
    for i, (rr, cc) in enumerate(cells):
        keep = ok[rr, cc]
        if keep.any():
            out[i] = monthly[:, rr[keep], cc[keep]].mean(1)
    c = grid.centres
    for i in np.flatnonzero(np.isnan(out[:, 0])):
        r, k = tf.row(c[i, 1]), tf.col(c[i, 0])
        r0, r1 = max(int(np.floor(r)) - 2, 0), min(int(np.ceil(r)) + 3, ok.shape[0])
        k0, k1 = max(int(np.floor(k)) - 2, 0), min(int(np.ceil(k)) + 3, ok.shape[1])
        sub = ok[r0:r1, k0:k1]
        if sub.any():
            rr, cc = np.mgrid[r0:r1, k0:k1]
            d = np.where(sub, (rr - r) ** 2 + (cc - k) ** 2, np.inf)
            j = np.unravel_index(np.argmin(d), d.shape)
            out[i] = monthly[:, r0 + j[0], k0 + j[1]]
    return out


def above_treeline(T, cfg):
    """True where monthly mean temperatures T (N, 12, degC) give too cold
    or short a growing season for trees (Paulsen & Körner 2014): the season
    is the months above `season_min`, at 365/12 days each, and trees need
    its mean to reach `season_mean` over at least `season_days` days.
    NaN rows are False."""
    season = T > cfg["season_min"]
    days = season.sum(1) * 365.0 / 12.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mean = np.nanmean(np.where(season, T, np.nan), axis=1)
    cold = (days < cfg["season_days"]) | ~(np.nan_to_num(mean, nan=-np.inf) >= cfg["season_mean"])
    return cold & np.isfinite(T).all(1)


def treeline(grid, cfg, tcfg, years, shift=None):
    """{year: bool per hex} above the treeline (`above_treeline` with
    `tcfg`), from each year's monthly temperature in cfg["data"], smoothed
    as for Köppen when the file has the 0 BP slice, plus `shift` (degC per
    hex)."""
    from . import koeppen
    _, bp, tf = load(cfg["data"])
    d = np.load(cfg["data"])
    T, P = d["clim_temperature"], d["clim_precipitation"]
    cells = hex_cells(grid, tf, T.shape[2:])
    out, done = {}, {}
    for y in years:
        t = bp_index(y, bp)
        if t not in done:
            if "modern_temperature" in d:
                Tt, _ = koeppen.smoothed(T, P, d["modern_temperature"], d["modern_precipitation"], t)
            else:
                Tt = T[t]
            Th = hex_monthly(grid, Tt, tf, cells)
            if shift is not None:
                Th = Th + shift[:, None]
            done[t] = above_treeline(Th, tcfg)
        out[y] = done[t]
    return out


def _knn(train_x, train_y, query_x, k, exclude_self=False):
    """Majority label and mean distance of the k nearest training rows."""
    labels = np.unique(train_y)
    lab_idx = np.searchsorted(labels, train_y)
    pred = np.empty(len(query_x), dtype=object)
    dist = np.empty(len(query_x))
    tn = (train_x ** 2).sum(1)
    for s in range(0, len(query_x), 1000):
        q = query_x[s:s + 1000]
        d = np.maximum((q ** 2).sum(1)[:, None] + tn[None, :] - 2 * q @ train_x.T, 0)
        if exclude_self:
            d[np.arange(len(q)), np.arange(s, s + len(q))] = np.inf
        nn = np.argpartition(d, k, axis=1)[:, :k]
        nd = np.sqrt(np.take_along_axis(d, nn, axis=1))
        # Distance-weighted vote, so the nearest neighbours settle near-ties.
        votes = np.zeros((len(q), len(labels)))
        np.add.at(votes, (np.arange(len(q))[:, None], lab_idx[nn]), 1 / (0.1 + nd))
        pred[s:s + len(q)] = labels[votes.argmax(1)]
        dist[s:s + len(q)] = nd.mean(1)
    return pred, dist


class Calibration:
    """Drawn biome as a function of model climate, learned on the hexes where
    the drawn keyframe has a biome (kNN in standardised climate space).

    `predict` returns "" where the query's mean distance to its k nearest
    training hexes is more than `factor` times the `max_distance_quantile`
    of the training hexes' own such distances: nothing drawn has a climate
    like it, so the caller keeps the model's own biome there. (Drawn hexes
    are densely packed in climate space, so the quantile alone is too tight:
    a factor of 1 rejects hexes whose every feature is within the drawn range.)
    """

    def __init__(self, x, labels, k, max_distance_quantile, factor=1.0):
        ok = np.isfinite(x).all(1)
        self.mu, self.sd = x[ok].mean(0), x[ok].std(0) + 1e-9
        self.x, self.y, self.k = (x[ok] - self.mu) / self.sd, labels[ok], k
        _, d = _knn(self.x, self.y, self.x, k, exclude_self=True)
        self.max_dist = factor * float(np.quantile(d, max_distance_quantile))

    def predict(self, x):
        out = np.full(len(x), "", dtype=object)
        ok = np.isfinite(x).all(1)
        pred, d = _knn(self.x, self.y, (x[ok] - self.mu) / self.sd, self.k)
        pred[d > self.max_dist] = ""
        out[ok] = pred
        return out


def block_cv(x, labels, centres, k, block_deg=10.0):
    """Share of labels recovered when each block_deg x block_deg tile is
    predicted from the others (spatially held out, so not flattered by
    neighbouring hexes sharing a climate)."""
    ok = np.isfinite(x).all(1)
    x, labels, centres = x[ok], labels[ok], centres[ok]
    x = (x - x.mean(0)) / (x.std(0) + 1e-9)
    tile = np.floor(centres / block_deg).astype(int)
    tid = tile[:, 0] * 1000 + tile[:, 1]
    hit = 0
    for t in np.unique(tid):
        m = tid == t
        if m.all():
            continue
        pred, _ = _knn(x[~m], labels[~m], x[m], k)
        hit += int((pred == labels[m]).sum())
    return hit / len(labels)


def to_terrain(codes, mapping):
    """BIOME4 codes -> terrain names; "" where unmapped or NODATA."""
    names = np.full(len(codes), "", dtype=object)
    for code, name in mapping.items():
        names[codes == int(code)] = name
    return names


def hex_biomes(grid, cfg, years):
    """{year: terrain name per hex} for each BCE year, from cfg["data"]."""
    biome, bp, tf = load(cfg["data"])
    ignore = cfg.get("ignore_codes", [])
    out, used = {}, {}
    for y in years:
        t = bp_index(y, bp)
        out[y] = to_terrain(hex_codes(grid, biome[t], tf, ignore), cfg["classes"])
        used[y] = int(bp[t])
    return out, used


def calibrated_biomes(grid, cfg, years, drawn, model, shift=None):
    """Gap biomes for each year from the drawn maps' biome-climate relation.

    For year y, a Calibration is trained on the drawn keyframe nearest y
    (its biome hexes, with the model climate of that keyframe's year) and
    applied to the model climate of y. Hexes whose climate is unlike any
    drawn hex keep `model[y]`. `shift` (degC per hex) moves the model's
    temperatures to each hex's elevation. Returns ({year: names}, {year: stats}).
    """
    c = cfg["calibrate"]
    spec = c["features"]
    clim = load_climate(cfg["data"], [n for n, _ in spec])
    _, bp, tf = load(cfg["data"])
    cells = hex_cells(grid, tf, next(iter(clim.values())).shape[1:])
    feats, fits, out, stats = {}, {}, {}, {}

    def feat(y):
        t = bp_index(y, bp)
        if t not in feats:
            feats[t] = features(grid, clim, tf, t, spec, cells, shift)
        return feats[t]

    for y in years:
        ty = y if y in drawn else min(drawn, key=lambda k: abs(k - y))
        if ty not in fits:
            lab = drawn[ty]
            m = ~np.isin(lab, NON_BIOME + tuple(cfg.get("gaps", ())))
            x = feat(ty)
            raw_m = m & ~np.isin(model[ty], NON_BIOME)
            fits[ty] = (Calibration(x[m], lab[m], c["k"], c["max_distance_quantile"],
                                    c.get("max_distance_factor", 1.0)),
                        block_cv(x[m], lab[m], grid.centres[m], c["k"], c["block_degrees"]),
                        float((model[ty][raw_m] == lab[raw_m]).mean()))
        cal, cv, raw_agree = fits[ty]
        pred = cal.predict(feat(y))
        out[y] = np.where(pred != "", pred, model[y])
        stats[y] = {"trained_on": ty, "cv": cv, "raw": raw_agree, "pred": pred}
    return out, stats

