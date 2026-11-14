"""Where the site list falls short of what its own pattern predicts, and why.

    sites known = land x presence x detection

Presence is what the evidence supports and no more: foragers are denser
near the sea and lakes (the model's own coastal factor, fitted to
ethnographic groups, not to these sites), farmed land carries more sites
than unfarmed, and each epoch has its own level. Detection is how little
later archaeology has been dated nearby, land now under water, and acid soil.

Expected population by productivity is not used: it does not predict where
sites are (data/population/SOURCES.md, "Residuals"). It is carried through
to the output for reference only.

The outputs are residuals, not densities, and never feed expected population.
"""
import csv
import glob
import gzip
import json
import os

import numpy as np

from . import settlements

# Outcomes, in legend order. The first three are visibility reasons.
REASONS = ["drowned", "little dated archaeology nearby", "acid soil",
           "unexplained shortfall", "more sites than expected", "as expected"]
# Categorical slots in fixed order, validated for colour-vision separation;
# "as expected" is a neutral.
COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#d9d8d2"]
RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"]      # one hue, light to dark
INK, INK2, SEA, EMPTY = "#0b0b0b", "#52514e", "#eef1f4", "#f4f3ef"


def hex_area_km2(bbox):
    """Area of flat-topped hexes from their lon/lat boxes: 3/4 x width x height."""
    left, top, right, bottom = bbox.T
    lat = np.radians((top + bottom) / 2)
    return 0.75 * (right - left) * 111.32 * np.cos(lat) * (top - bottom) * 110.57


def at_year(by_year, year):
    """Value of a sparse {year: value} property at `year` (step function)."""
    keys = [int(k) for k in by_year if int(k) <= year]
    return by_year[str(max(keys))] if keys else None


def observed(features, ids, years, half):
    """(N, T) count of sites in each hex with an occupation phase that
    overlaps year +- half."""
    row = {int(h): i for i, h in enumerate(ids)}
    out = np.zeros((len(ids), len(years)), dtype=int)
    for f in features:
        p = f["properties"]
        i = row.get(p.get("hex"))
        if i is None:
            continue
        phases = p.get("occupation") or []
        for t, y in enumerate(years):
            if any(a < y + half and b > y - half for a, b in phases):
                out[i, t] += 1
    return out


def later_dates(cfg, max_bp, bounds):
    """Every dated record younger than `max_bp` radiocarbon years inside
    `bounds` (west, south, east, north) in the cached `make settlements`
    downloads: the research-effort background. Also returns how many dated
    records of any age lie inside the bounds."""
    sc = cfg["settlements"]
    raw, aliases = sc["raw_dir"], sc["xronos"].get("type_aliases")
    dates, seen = [], set()
    for path in sorted(glob.glob(os.path.join(raw, "xronos_*.json"))):
        dates += settlements.parse_xronos(path, seen, aliases)
    labs = {settlements.lab_key(d["labnr"]) for d in dates}
    for spec in sc.get("tables", []):
        path = spec.get("path") or os.path.join(raw, spec["file"])   # in-repo tables give a path
        if os.path.exists(path):
            dates += settlements.parse_table(path, spec, labs, aliases)
    w, s, e, n = bounds
    inside = [d for d in dates if w <= d["lon"] <= e and s <= d["lat"] <= n and d["std"] <= sc["max_std"]]
    return [d for d in inside if d["bp"] <= max_bp], len(inside)


def soil_ph(centres, src_dir):
    """Topsoil pH (SoilGrids 0-30 cm) at each hex centre, or None if the
    layers isostyle fetches aren't there."""
    try:
        import rasterio
        from pyproj import Transformer
    except ImportError:
        return None
    total, weight = np.zeros(len(centres)), 0.0
    for name, thick in (("phh2o_0-5cm_mean_5000.tif", 5), ("phh2o_5-15cm_mean_5000.tif", 10),
                        ("phh2o_15-30cm_mean_5000.tif", 15)):
        path = os.path.join(src_dir, name)
        if not os.path.exists(path):
            return None
        with rasterio.open(path) as src:
            x, y = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True).transform(centres[:, 0], centres[:, 1])
            v = np.array([s[0] for s in src.sample(zip(x, y))], dtype=float)
            v[(v == src.nodata) | (v <= 0)] = np.nan
        total += v * thick
        weight += thick
    return total / weight / 10.0


def poisson(X, y, offset, iters=60, ridge=1e-8):
    """Poisson regression with a log link by iteratively reweighted least
    squares. Returns (coefficients, their standard errors, deviance)."""
    beta = np.zeros(X.shape[1])
    beta[0] = np.log(max(y.sum(), 0.5) / np.exp(offset).sum()) if np.allclose(X[:, 0], 1) else 0.0
    for _ in range(iters):
        eta = np.clip(X @ beta + offset, -40, 40)
        mu = np.exp(eta)
        z = eta - offset + (y - mu) / mu
        A = X.T @ (X * mu[:, None]) + ridge * np.eye(X.shape[1])
        new = np.linalg.solve(A, X.T @ (mu * z))
        done = np.max(np.abs(new - beta)) < 1e-9
        beta = new
        if done:
            break
    mu = np.exp(np.clip(X @ beta + offset, -40, 40))
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ (X * mu[:, None]) + ridge * np.eye(X.shape[1]))))
    with np.errstate(divide="ignore", invalid="ignore"):
        dev = 2 * np.sum(np.where(y > 0, y * np.log(y / mu), 0.0) - (y - mu))
    return beta, se, float(dev)


def classify(obs, mu, full, parts, min_missing, ratio):
    """Outcome index into REASONS per row.

    obs: sites known; mu: sites the model expects given how visible the hex
    is; full: sites it would expect if nothing hid them; parts: (rows, 3) how
    much each visibility reason lowers ln(mu) below ln(full)."""
    out = np.full(len(obs), REASONS.index("as expected"))
    short = (full - obs >= min_missing) & (obs * ratio <= full)
    hidden = short & (mu * ratio <= full)                 # detection alone explains a shortfall this size
    out[hidden] = np.argmax(parts[hidden], axis=1)
    out[short & ~hidden] = REASONS.index("unexplained shortfall")
    out[(obs - full >= min_missing) & (obs >= full * ratio)] = REASONS.index("more sites than expected")
    return out


def run(cfg, grid, feats, sites, expected_rows, log=print):
    """Fit the detection model and return (rows, summary). `feats` are the
    combined map's features, `sites` the settlements', `expected_rows`
    dicts from the converter's CSV."""
    rc = cfg["residuals"]
    years = rc["years"]
    T, N = len(years), len(grid)
    row = {int(h): i for i, h in enumerate(grid.ids)}
    dens = np.full((N, T), np.nan)
    shore = np.full((N, T), np.nan)
    farmed = np.zeros((N, T), bool)
    for r in expected_rows:
        i, y = row.get(int(r["hex"])), int(r["year"])
        if i is not None and y in years:
            dens[i, years.index(y)] = float(r["density_per_km2"])
            farmed[i, years.index(y)] = r["farmed"] == "1"
            if r.get("shore_km"):
                shore[i, years.index(y)] = float(r["shore_km"])
    area = hex_area_km2(grid.bbox)
    # The forager model's coastal factor; farmed land gets none, as in the model.
    c0, c1 = rc["shore_factor"]
    ln_shore = np.log(np.clip(np.nan_to_num(shore, nan=rc["max_shore_km"]), 0, rc["max_shore_km"]) + 10.0)
    presence = np.log(area)[:, None] + np.where(farmed, 0.0, c0 + c1 * ln_shore)

    obs = observed(sites, grid.ids, years, rc["half_window"])
    terrain = np.array([[at_year(f["properties"]["terrain"], y) for y in years] for f in feats], dtype=object)
    water_now = np.array([at_year(f["properties"]["terrain"], rc["today"]) == "Water" for f in feats])
    drowned = (terrain != "Water") & water_now[:, None]

    left, top, right, bottom = grid.bbox.T
    later, n_all = later_dates(cfg, rc["background_max_bp"], (left.min(), bottom.min(), right.max(), top.max()))
    effort, _ = settlements.survey_intensity(grid, later, {"sigma_km": rc["effort_sigma_km"], "thin": 0, "well": 0})
    log(f"residuals: {len(later)} of {n_all} dated records are later than {rc['background_max_bp']} BP (the effort background)")
    ph = soil_ph(grid.centres, rc["soil_dir"])
    acid = np.zeros(N, bool) if ph is None else np.nan_to_num(ph, nan=7.0) < rc["acid_ph"]
    if ph is None:
        log("residuals: no soil pH layers; acid soil left out")

    use = np.isfinite(dens) & (dens > 0)                 # land with people on it: not Water, not Ice
    hi, ti = np.nonzero(use)
    le = np.log1p(effort)
    names = [f"epoch {y}" for y in years] + ["farmed", "ln(1 + later dates per 10,000 km²)", "drowned", "acid soil"]
    X = np.zeros((len(hi), T + 4))
    X[np.arange(len(hi)), ti] = 1.0
    X[:, T] = farmed[hi, ti]
    X[:, T + 1] = le[hi]
    X[:, T + 2] = drowned[hi, ti]
    X[:, T + 3] = acid[hi]
    y, off = obs[hi, ti].astype(float), presence[hi, ti]
    beta, se, dev = poisson(X, y, off)
    mu = np.exp(X @ beta + off)

    # Checks. Is the coastal factor, fixed from ethnography, the size the
    # sites would choose? And does expected population add anything to it?
    la = np.log(area)[hi]
    fo = ~farmed[hi, ti]
    _, _, dev_flat = poisson(X, y, la)
    Xc = np.column_stack([X, np.where(fo, ln_shore[hi, ti], 0.0), np.where(fo, 0.0, ln_shore[hi, ti])])
    bc, sc_, dev_free = poisson(Xc, y, la)
    with np.errstate(divide="ignore"):
        lp = np.log(np.maximum(dens[hi, ti], 1e-9))
    bp, sp, dev_pop = poisson(np.column_stack([X, np.where(dens[hi, ti] > 0, lp, 0.0)]), y, off)

    # Nothing hiding the sites: effort at a well-studied level, dry, not acid.
    best = float(np.quantile(le[np.unique(hi)], rc["effort_quantile"]))
    Xb = X.copy()
    Xb[:, T + 1] = np.maximum(X[:, T + 1], best)
    Xb[:, T + 2] = 0.0
    Xb[:, T + 3] = 0.0
    full = np.exp(Xb @ beta + off)
    parts = np.column_stack([-beta[T + 2] * X[:, T + 2],
                             beta[T + 1] * (Xb[:, T + 1] - X[:, T + 1]),
                             -beta[T + 3] * X[:, T + 3]])
    parts = np.maximum(parts, 0.0)
    reason = classify(y, mu, full, parts, rc["min_missing"], rc["ratio"])

    rows = [{"hex": int(grid.ids[h]), "year": years[t], "expected_per_km2": round(float(dens[h, t]), 5),
             "farmed": int(farmed[h, t]), "later_dates_per_10k_km2": round(float(effort[h]), 2),
             "area_km2": round(float(area[h])),
             "shore_km": "" if np.isnan(shore[h, t]) else int(shore[h, t]), "sites": int(y[k]), "sites_expected": round(float(mu[k]), 3),
             "sites_if_nothing_hid_them": round(float(full[k]), 3), "missing": round(float(full[k] - y[k]), 3),
             "outcome": REASONS[reason[k]]}
            for k, (h, t) in enumerate(zip(hi, ti))]
    by_year = {}
    for t, yr in enumerate(years):
        m = ti == t
        counts = np.bincount(reason[m], minlength=len(REASONS))
        by_year[str(yr)] = {"hexes": int(m.sum()), "sites": int(y[m].sum()),
                            "sites_if_nothing_hid_them": round(float(full[m].sum()), 1),
                            "outcomes": {REASONS[i]: int(c) for i, c in enumerate(counts)}}
    summary = {
        "rows": len(rows), "sites_counted": int(y.sum()), "later_dates": len(later), "all_dates": n_all,
        "soil_ph": ph is not None,
        "coefficients": {n: {"estimate": round(float(b), 4), "se": round(float(s), 4)} for n, b, s in zip(names, beta, se)},
        "deviance": {"no_coast": round(dev_flat, 1), "coast_fixed_from_ethnography": round(dev, 1),
                     "coast_fitted_to_sites": round(dev_free, 1), "plus_expected_population": round(dev_pop, 1)},
        "coast_slope": {"model": c1,
                        "sites_foragers": {"estimate": round(float(bc[-2]), 4), "se": round(float(sc_[-2]), 4)},
                        "sites_farmed": {"estimate": round(float(bc[-1]), 4), "se": round(float(sc_[-1]), 4)}},
        "population_exponent_on_top": {"estimate": round(float(bp[-1]), 4), "se": round(float(sp[-1]), 4)},
        "effort_reference": round(float(np.expm1(best)), 2),
        "by_year": by_year,
    }
    return rows, summary, {"hi": hi, "ti": ti, "missing": full - y, "reason": reason, "terrain": terrain}


def write_rows(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def maps(out_dir, grid, years, extra, bins):
    """Two small-multiple figures: how many sites are missing, and why."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from matplotlib.patches import Patch

    verts = [np.asarray(r) for r in grid.rings]
    left, top, right, bottom = grid.bbox.T
    bounds = (left.min(), right.max(), bottom.min(), top.max())
    hi, ti, terrain = extra["hi"], extra["ti"], extra["terrain"]

    def figure(title, subtitle, colour_of, handles, name, ncol):
        fig, axes = plt.subplots(2, 4, figsize=(17.2, 13.4))
        fig.patch.set_facecolor("#fcfcfb")
        for t, (ax, yr) in enumerate(zip(axes.ravel(), years)):
            col = np.where(terrain[:, t] == "Water", SEA, EMPTY).astype(object)
            m = ti == t
            col[hi[m]] = colour_of(m)
            ax.add_collection(PolyCollection(verts, facecolors=list(col), edgecolors="none", rasterized=True))
            ax.set_xlim(bounds[0], bounds[1])
            ax.set_ylim(bounds[2], bounds[3])
            ax.set_aspect(1.41, adjustable="box", anchor="N")
            ax.set_axis_off()
            ax.set_title(f"{-yr:,} BCE", fontsize=10.5, color=INK, loc="left", pad=3)
        fig.suptitle(title, x=0.012, ha="left", fontsize=15, fontweight="bold", color=INK)
        fig.text(0.012, 0.962, subtitle, fontsize=9.5, color=INK2, va="top")
        fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.012, 0.006), frameon=False, fontsize=9.5,
                   ncol=ncol, labelcolor=INK)
        fig.subplots_adjust(left=0.008, right=0.992, top=0.925, bottom=0.055, wspace=0.02, hspace=0.07)
        os.makedirs(out_dir, exist_ok=True)
        fig.savefig(os.path.join(out_dir, name), dpi=110)
        plt.close(fig)

    ramp = np.array([EMPTY] + RAMP, dtype=object)
    labels = ["fewer than %g" % bins[0]] + [f"{a:g}–{b:g}" for a, b in zip(bins[:-1], bins[1:])] + [f"{bins[-1]:g} or more"]
    figure("Sites the list is missing",
           "Sites each hex would have if nothing hid them, less the sites known. What a hex should have comes from its "
           "area, epoch, whether it is farmed and how near water it is, not from productivity.",
           lambda m: ramp[np.digitize(extra["missing"][m], bins)],
           [Patch(color=c, label=l) for c, l in zip(ramp, labels)], "missing_sites.png", len(ramp))
    cat = np.array(COLOURS, dtype=object)
    figure("Why sites are missing",
           "The largest thing lowering each hex's visibility where that explains the shortfall; otherwise the shortfall is "
           "unexplained: fewer people lived there than its neighbours' pattern suggests, or something else hides them.",
           lambda m: cat[extra["reason"][m]],
           [Patch(color=c, label=l) for c, l in zip(COLOURS, REASONS)], "outcomes.png", len(COLOURS))
