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


def _km(a, b):
    """(len(a), len(b)) approximate distances in km between lon/lat rows."""
    lat = np.radians((a[:, 1][:, None] + b[:, 1][None, :]) / 2)
    dx = (a[:, 0][:, None] - b[:, 0][None, :]) * np.cos(lat)
    dy = a[:, 1][:, None] - b[:, 1][None, :]
    return 111.2 * np.hypot(dx, dy)


def _knn(train_x, train_y, query_x, k, exclude_self=False, train_ll=None, query_ll=None, max_km=None):
    """Majority label and mean distance of the k nearest training rows. With
    `max_km`, only training rows within that many km of the query (lon/lat
    rows `train_ll`, `query_ll`) count; a query with none gets "" and an
    infinite distance."""
    labels = np.unique(train_y)
    lab_idx = np.searchsorted(labels, train_y)
    pred = np.empty(len(query_x), dtype=object)
    dist = np.empty(len(query_x))
    tn = (train_x ** 2).sum(1)
    kk = min(k, len(train_x) - 1) if exclude_self else min(k, len(train_x))
    for s in range(0, len(query_x), 1000):
        q = query_x[s:s + 1000]
        d = np.maximum((q ** 2).sum(1)[:, None] + tn[None, :] - 2 * q @ train_x.T, 0)
        if exclude_self:
            d[np.arange(len(q)), np.arange(s, s + len(q))] = np.inf
        if max_km is not None:
            d[_km(query_ll[s:s + len(q)], train_ll) > max_km] = np.inf
        nn = np.argpartition(d, kk - 1, axis=1)[:, :kk]
        nd = np.sqrt(np.take_along_axis(d, nn, axis=1))
        ok = np.isfinite(nd)
        # Distance-weighted vote, so the nearest neighbours settle near-ties.
        votes = np.zeros((len(q), len(labels)))
        np.add.at(votes, (np.arange(len(q))[:, None], lab_idx[nn]), np.where(ok, 1 / (0.1 + np.where(ok, nd, 0)), 0))
        any_ok = ok.any(1)
        pred[s:s + len(q)] = np.where(any_ok, labels[votes.argmax(1)], "")
        with np.errstate(invalid="ignore"):
            dist[s:s + len(q)] = np.where(any_ok, np.nanmean(np.where(ok, nd, np.nan), 1), np.inf)
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

    def __init__(self, x, labels, k, max_distance_quantile, factor=1.0, ll=None, max_km=None):
        ok = np.isfinite(x).all(1)
        self.mu, self.sd = x[ok].mean(0), x[ok].std(0) + 1e-9
        self.x, self.y, self.k = (x[ok] - self.mu) / self.sd, labels[ok], k
        self.ll = None if ll is None else np.asarray(ll, float)[ok]
        self.max_km = max_km if ll is not None else None
        _, d = _knn(self.x, self.y, self.x, k, exclude_self=True, train_ll=self.ll, query_ll=self.ll,
                    max_km=self.max_km)
        d = d[np.isfinite(d)]
        self.max_dist = factor * float(np.quantile(d, max_distance_quantile))

    def predict(self, x, ll=None):
        """Labels for climate rows x; with `max_km`, `ll` are their lon/lat."""
        out = np.full(len(x), "", dtype=object)
        ok = np.isfinite(x).all(1)
        q_ll = None if ll is None or self.max_km is None else np.asarray(ll, float)[ok]
        pred, d = _knn(self.x, self.y, (x[ok] - self.mu) / self.sd, self.k, train_ll=self.ll, query_ll=q_ll,
                       max_km=self.max_km if q_ll is not None else None)
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


def literature_labels(path, holdout_k, grid):
    """{year: [(hex index, class)]} from data/terrain/anchors_literature.csv:
    each anchor's first class per slice, at the hex nearest it, for the
    anchors not held out (pipeline.anchors.holdout), so the held-out ones
    still test the map."""
    import csv
    import os
    from .anchors import holdout
    out = {}
    if not path or not os.path.exists(path):
        return out
    c = grid.centres
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if holdout(r["id"], holdout_k):
                continue
            lon, lat = float(r["lon"]), float(r["lat"])
            i = int(np.argmin(((c[:, 0] - lon) * np.cos(np.radians(lat))) ** 2 + (c[:, 1] - lat) ** 2))
            out.setdefault(int(r["year"]), []).append((i, r["game_classes"].split(";")[0]))
    return out


def calibrated_biomes(grid, cfg, years, drawn, model, shift=None, anchors=None, borrow=None, model_ice=None):
    """Gap biomes for each year from the drawn maps' biome-climate relation.

    For year y, a Calibration is trained on the drawn keyframe nearest y
    (its biome hexes, with the model climate of that keyframe's year) and
    applied to the model climate of y. Hexes whose climate is unlike any
    drawn hex keep `model[y]`. `shift` (degC per hex) moves the model's
    temperatures to each hex's elevation. With `max_km`, only drawn hexes
    that near count, so a Zagros gap doesn't borrow Morocco's Chaparral.
    `anchors` ({year: [(hex, class)]}, `literature_labels`) are added to the
    training for the keyframe of their year, each `anchor_weight` times: they
    give the classes the drawings never use for these climates (the drawn maps
    leave the Irano-Anatolian uplands as "Mountains"). `borrow` ({keyframe:
    [(other keyframe, hex mask)]}) adds the drawn biomes of another keyframe
    on the masked hexes, with that keyframe's climate, to a keyframe's
    training: a region whose own drawing is mis-dated learns from a drawing
    of it that isn't. `model_ice` ({year: hex mask}): there, where the model
    has land ice the hex keeps it (ice is a boundary condition of the model
    run, not something to learn from climate); elsewhere the calibration's
    class wins as usual. Returns ({year: names}, {year: stats}).
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
            tx, ty_lab, tll = x[m], lab[m], grid.centres[m]
            extra = (anchors or {}).get(ty, [])
            if extra:
                w = int(c.get("anchor_weight", 1))
                idx = np.repeat([i for i, _ in extra], w)
                tx = np.vstack([tx, x[idx]])
                ty_lab = np.concatenate([ty_lab, np.repeat([k for _, k in extra], w).astype(object)])
                tll = np.vstack([tll, grid.centres[idx]])
            for oy, mask in (borrow or {}).get(ty, []):
                ol = drawn[oy]
                om = mask & ~np.isin(ol, NON_BIOME + tuple(cfg.get("gaps", ())))
                tx = np.vstack([tx, feat(oy)[om]])
                ty_lab = np.concatenate([ty_lab, ol[om]])
                tll = np.vstack([tll, grid.centres[om]])
            fits[ty] = (Calibration(tx, ty_lab, c["k"], c["max_distance_quantile"],
                                    c.get("max_distance_factor", 1.0), ll=tll, max_km=c.get("max_km") or None),
                        block_cv(x[m], lab[m], grid.centres[m], c["k"], c["block_degrees"]),
                        float((model[ty][raw_m] == lab[raw_m]).mean()))
        cal, cv, raw_agree = fits[ty]
        pred = cal.predict(feat(y), grid.centres)
        ice = (model[y] == "Ice") & (model_ice or {}).get(y, False)
        out[y] = np.where((pred != "") & ~ice, pred, model[y])
        stats[y] = {"trained_on": ty, "cv": cv, "raw": raw_agree, "pred": pred}
    return out, stats


def hex_climate(grid, cfg, years, spec, shift=None):
    """{year: (N, len(spec)) climate per hex} for the model slice nearest
    each year (`features`, temperatures moved by `shift`)."""
    clim = load_climate(cfg["data"], [n for n, _ in spec])
    _, bp, tf = load(cfg["data"])
    cells = hex_cells(grid, tf, next(iter(clim.values())).shape[1:])
    done, out = {}, {}
    for y in years:
        t = bp_index(y, bp)
        if t not in done:
            done[t] = features(grid, clim, tf, t, spec, cells, shift)
        out[y] = done[t]
    return out


def upland_class(year, precip, coldest, ucfg):
    """The class the upland rule gives a hex, or "" to leave it: woodland
    after `woodland_from` where annual precipitation reaches
    `woodland_precip`, else forest-steppe from `forest_steppe_precip`, else
    grassland; nothing where winters are mild (coldest month above
    `max_coldest`, the Mediterranean) or the land is drier than `min_precip`."""
    if not np.isfinite(precip) or not np.isfinite(coldest):
        return ""
    if coldest > ucfg["max_coldest"] or precip < ucfg["min_precip"]:
        return ""
    if year >= ucfg["woodland_from"] and precip >= ucfg["woodland_precip"]:
        return "Woodlands"
    return "Steppe-Forest" if precip >= ucfg["forest_steppe_precip"] else "Grassland"


def forest_type(coldest, warm, year, fcfg, lat=None):
    """Boreal vs Temperate Forest for one climate (arrays): Boreal where the
    coldest month's minimum is below `boreal_coldest` or the warmest quarter
    below `boreal_warm`; Temperate from `temperate_coldest` up; in between
    (cool mixed forest) Temperate only from `mixed_from` (broadleaf trees
    there) and where the warmest quarter reaches `mixed_warm`. Never
    Temperate at or north of `temperate_max_lat` (with `lat`)."""
    mixed = (year >= fcfg["mixed_from"]) & (warm >= fcfg["mixed_warm"])
    temperate = (coldest >= fcfg["temperate_coldest"]) | mixed
    boreal = (coldest < fcfg["boreal_coldest"]) | (warm < fcfg["boreal_warm"]) | ~temperate
    if lat is not None and "temperate_max_lat" in fcfg:
        boreal = boreal | (np.asarray(lat) >= fcfg["temperate_max_lat"])
    return np.where(boreal, "Boreal Forest", "Temperate Forest")


def apply_forest_type(t, centres, clim, fcfg, year):
    """`forest_type` on every Boreal or Temperate Forest hex in `box`. clim:
    (N, 2) BIO6, BIO10. Hexes without climate keep their class. Returns
    (terrain, hexes changed)."""
    b = fcfg["box"]
    m = (np.isin(t, ["Boreal Forest", "Temperate Forest"])
         & (centres[:, 0] >= b[0]) & (centres[:, 0] <= b[2])
         & (centres[:, 1] >= b[1]) & (centres[:, 1] <= b[3])
         & np.isfinite(clim[:, 0]) & np.isfinite(clim[:, 1]))
    want = forest_type(clim[:, 0], clim[:, 1], year, fcfg, centres[:, 1])
    ch = m & (want != t)
    if not ch.any():
        return t, 0
    out = t.copy()
    out[ch] = want[ch]
    return out, int(ch.sum())


def dry_lowland_class(cls, precip, warm, dcfg):
    """The class the dry-lowland rule gives a forest hex, or "" to leave it:
    Steppe-Forest below `steppe_forest_precip` mm a year, else Woodlands below
    `woodland_precip`, where the warmest quarter (BIO10) is at least
    `min_warm` degC; only `apply_to` classes change."""
    if cls not in dcfg["apply_to"] or not np.isfinite(precip) or not np.isfinite(warm):
        return ""
    if warm < dcfg["min_warm"]:
        return ""
    if precip < dcfg["steppe_forest_precip"]:
        return "Steppe-Forest"
    if precip < dcfg["woodland_precip"] and cls != "Woodlands":
        return "Woodlands"
    return ""


def apply_dry_lowland(t, elev, centres, clim, dcfg):
    """Apply `dry_lowland_class` to every hex (drawn or filled) in `box`
    below `max_elevation`. clim: (N, 2) annual precipitation (mm) and
    warmest-quarter mean (degC). Returns (terrain, hexes changed)."""
    b = dcfg["box"]
    cand = np.flatnonzero((np.nan_to_num(elev, nan=1e9) < dcfg["max_elevation"])
                          & (centres[:, 0] >= b[0]) & (centres[:, 0] <= b[2])
                          & (centres[:, 1] >= b[1]) & (centres[:, 1] <= b[3]))
    out, n = t, 0
    for i in cand:
        k = dry_lowland_class(t[i], clim[i, 0], clim[i, 1], dcfg)
        if k and k != t[i]:
            if out is t:
                out = t.copy()
            out[i] = k
            n += 1
    return out, n


def apply_cold_temperate(t, centres, clim, ccfg, elev=None, year=None):
    """Temperate Forest where the coldest month's minimum (BIO6) is below
    `max_coldest` (no test without it) becomes Steppe-Forest below
    `steppe_forest_precip` mm a year, else Boreal Forest, in `box` (and only
    up to the year `until`, if given). clim: (N, 2) BIO12, BIO6. Returns
    (terrain, hexes changed)."""
    if "until" in ccfg and (year is None or year > ccfg["until"]):
        return t, 0
    b = ccfg["box"]
    m = ((t == "Temperate Forest") & (centres[:, 0] >= b[0]) & (centres[:, 0] <= b[2])
         & (centres[:, 1] >= b[1]) & (centres[:, 1] <= b[3]))
    if "max_coldest" in ccfg:
        m &= np.isfinite(clim[:, 1]) & (clim[:, 1] < ccfg["max_coldest"])
    if elev is not None and "max_elevation" in ccfg:
        m &= np.nan_to_num(elev, nan=1e9) < ccfg["max_elevation"]
    if not m.any():
        return t, 0
    out = t.copy()
    out[m] = np.where(clim[m, 0] < ccfg["steppe_forest_precip"], "Steppe-Forest", "Boreal Forest")
    return out, int(m.sum())


def apply_overrides(t, centres, elev, rules, year):
    """[[biome.override]]: in each rule's `boxes`, below `max_elevation`
    (optional), for years in [first, last], hexes of a class in `from`
    (default: every land biome) become `to`. Last rule wins. Returns
    (terrain, hexes changed)."""
    from .compose import in_boxes
    out, n = t, 0
    for r in rules:
        y0, y1 = r["years"]
        if not (y0 <= year <= y1):
            continue
        m = in_boxes(centres, r["boxes"])
        if "max_elevation" in r:
            m &= np.nan_to_num(elev, nan=1e9) < r["max_elevation"]
        src = r.get("from")
        m &= np.isin(t, src) if src else ~np.isin(t, NON_BIOME + ("Alpine", "Floodplain"))
        m &= out != r["to"]
        if m.any():
            out = out.copy() if out is t else out
            out[m] = r["to"]
            n += int(m.sum())
    return out, n


def apply_upland(t, gap, elev, centres, clim, year, ucfg):
    """Apply `upland_class` to gap-filled hexes (`gap`) in `box` at or above
    `min_elevation` that aren't Alpine, Water or Ice. clim: (N, 2) annual
    precipitation (mm) and coldest-month minimum (degC). Returns (terrain,
    hexes changed)."""
    b = ucfg["box"]
    cand = np.flatnonzero(gap & (elev >= ucfg["min_elevation"])
                          & (centres[:, 0] >= b[0]) & (centres[:, 0] <= b[2])
                          & (centres[:, 1] >= b[1]) & (centres[:, 1] <= b[3])
                          & ~np.isin(t, ["Alpine", "Water", "Ice"]))
    out, n = t, 0
    for i in cand:
        k = upland_class(year, clim[i, 0], clim[i, 1], ucfg)
        if k and k != t[i]:
            if out is t:
                out = t.copy()
            out[i] = k
            n += 1
    return out, n
