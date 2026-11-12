"""Occupation units and what each says about each occupation layer.

A unit is an occupation episode of a radiocarbon-dated site, or a record of
an external dataset that matched no dated episode. For each layer whose
`unit` is "occupation" (data/isostyle/layers.toml) a unit is 1 (present),
0 (absent) or NaN (not known), with a basis:
  recorded  a dataset records it there, a dated sample is of it, or the
            dated site's type shows it
  label     implied by the unit's culture or stage label (label_presence.toml)
"""
from collections import Counter
import re
import tomllib

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from pipeline.cultures import Table

from . import dates as datemod, grid as gridmod, sources

R_EARTH = 6371.0088


def unit_xyz(lon, lat):
    lo, la = np.radians(np.asarray(lon, float)), np.radians(np.asarray(lat, float))
    return np.column_stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])


def chord(km):
    return 2 * np.sin(km / R_EARTH / 2)


def _fits(entry, year, margin):
    lo, hi = entry.get("start"), entry.get("end")
    return (lo is None or year >= lo - margin) and (hi is None or year <= hi + margin)


def _label_vote(rule, cultures, stages, year, country=""):
    """1, 0 or NaN from a layer's label rules; cultures beat stages. In the
    countries listed in `present_stages_absent_in_countries`, a stage label
    that would imply presence implies absence instead."""
    frm = rule.get("from", {})
    for ids, pres, absn in ((cultures, "present_cultures", "absent_cultures"),
                            (stages, "present_stages", "absent_stages")):
        if pres == "present_stages" and country in rule.get("present_stages_absent_in_countries", ()):
            only = set(rule.get("present_stages_absent_in_countries_stages", rule[pres]))
            if any(i in rule[absn] or i in only for i in ids):
                return 0.0
            ids = [i for i in ids if i not in only]
        yes = any(i in rule[pres] and year >= frm.get(i, -1e9) for i in ids)
        no = any(i in rule[absn] for i in ids)
        if yes != no:
            return 1.0 if yes else 0.0
        if yes and no:
            return np.nan
    return np.nan


def episode_countries(lon, lat, path="build/isostyle/naturalearth/ne_50m_admin_0_countries.shp"):
    """Modern country (Natural Earth NAME) of each point, "" if none."""
    import geopandas as gpd
    c = gpd.read_file(path)[["NAME", "geometry"]]
    p = gpd.GeoDataFrame(geometry=gpd.points_from_xy(lon, lat), crs=4326)
    j = gpd.sjoin(p, c, how="left", predicate="within")
    return j[~j.index.duplicated()]["NAME"].fillna("").values


def uniform_weights(tpq, taq, edges):
    """Share of a uniform distribution on [tpq, taq] inside each slice."""
    tpq, taq = np.asarray(tpq, float)[:, None], np.asarray(taq, float)[:, None]
    a, b = edges[:, 0][None, :], edges[:, 1][None, :]
    return np.clip(np.minimum(taq, b) - np.maximum(tpq, a), 0, None) / (taq - tpq)


def merge_groups(ext, W):
    """Records sharing a group, layer and state (the dates of one published
    phase) become one record: mean distribution, widest span."""
    ext = ext.copy()
    ext["n_c14"] = ext["bp"].notna().astype(int)
    grouped = ext["group"].ne("").values
    if not grouped.any():
        return ext, W
    key = ext["group"] + "|" + ext["layer"] + "|" + ext["present"].astype(str)
    g = ext[grouped].assign(k=key[grouped].values)
    codes, uniq = pd.factorize(g["k"])
    Wg = np.zeros((len(uniq), W.shape[1]))
    np.add.at(Wg, codes, W[grouped])
    n = np.bincount(codes)
    agg = g.groupby(codes).agg({"layer": "first", "present": "first", "site": "first", "lon": "first", "lat": "first",
                                "tpq": "min", "taq": "max", "bp": "first", "std": "first", "grave": "max",
                                "source": "first", "group": "first", "cell_ix": "first", "n_c14": "sum"})
    out = pd.concat([ext[~grouped], agg], ignore_index=True)
    return out, np.vstack([W[~grouped], Wg / n[:, None]])


def build(cfg, grid, years, edges, registry, log=print):
    dc, pc = cfg["dates"], cfg["presence"]
    LAYERS = [L["id"] for L in registry.by_unit("occupation")]
    direct = [L for L in registry.by_unit("occupation") if L.get("dated_material_re") or L.get("site_type_re")]
    pcfg = tomllib.load(open(dc["pipeline_config"], "rb"))
    d, counts = datemod.load(cfg, pcfg["settlements"]["tables"], cfg["region"])
    d["cell_ix"] = gridmod.locate(grid, d["lon"].values, d["lat"].values)
    d = d[d["cell_ix"] >= 0].reset_index(drop=True)
    mass, med, lo, hi = datemod.calibrate(d["bp"].values, d["std"].values, dc["curve"], years, None, edges=edges)
    d["cal_median"], d["cal_lo"], d["cal_hi"] = med, lo, hi
    d["episode"] = datemod.episodes(d, dc["episode_gap"])
    keep = (d["episode"] > 0).values
    d, mass = d[keep].reset_index(drop=True), mass[keep]
    counts["dates_calibrated_on_grid"] = len(d)
    grave_re = re.compile("|".join(dc["grave_types"]))
    d["grave"] = d["site_type"].map(lambda t: bool(grave_re.search(t)))
    # A date whose sample material, or whose site's type, shows a layer.
    for L in direct:
        hit = np.zeros(len(d), dtype=bool)
        # A site's type applies to all its dates; dates older than the
        # structure can be (layers.toml `not_before`) are not evidence of it.
        recent = (d["cal_median"].values >= L["not_before"]) if L.get("not_before") is not None else np.ones(len(d), bool)
        if L.get("dated_material_re"):
            hit |= d["material"].map(lambda t, rx=L["dated_material_re"]: bool(rx.search(t))).values
        if L.get("site_type_re"):
            hit |= d["site_type"].map(lambda t, rx=L["site_type_re"]: bool(rx.search(t))).values
        d[f"dm_{L['id']}"] = hit & recent

    eid, inv = np.unique(d["episode"].values, return_inverse=True)
    n = np.bincount(inv)
    W = np.zeros((len(eid), len(years)))
    np.add.at(W, inv, mass)
    W /= n[:, None]
    g = d.groupby(inv)
    ep = pd.DataFrame({
        "site_id": g["site_id"].first(), "site": g["site"].first(), "lon": g["lon"].first(),
        "lat": g["lat"].first(), "cell_ix": g["cell_ix"].first(), "n_dates": n,
        "start": g["cal_lo"].min(), "end": g["cal_hi"].max(), "median": g["cal_median"].median(),
        "grave": g["grave"].mean() > 0.5, "dating": "c14",
        "site_type": g["site_type"].agg(lambda s: Counter(t for t in s if t).most_common(1)[0][0] if any(s) else ""),
        "labels": g["labels"].agg(lambda s: sorted({x for labs in s for x in labs})),
        "source": g["dataset"].agg(lambda s: "|".join(sorted(set(s)))),
    }).reset_index(drop=True)
    for L in direct:
        ep[f"dm_{L['id']}"] = g[f"dm_{L['id']}"].any().values
    # Records that name a date by lab number mark that date's episode.
    lj = sources.load_labjoin(cfg, log)
    labjoin_pos = {m: np.zeros(len(ep), dtype=bool) for m in LAYERS}
    if len(lj):
        from .dates import lab_key
        ep_of_lab = {}
        for k, lab in zip(inv, d["labnr"].fillna("").astype(str).values):
            if (key := lab_key(lab)):
                ep_of_lab.setdefault(key, k)
        hits = 0
        for layer, lab in zip(lj["layer"], lj["labnr"].fillna("").astype(str)):
            k = ep_of_lab.get(lab_key(lab))
            if k is not None:
                labjoin_pos[layer][k] = True
                hits += 1
        counts["labjoin_records"] = int(len(lj))
        counts["labjoin_matched"] = hits
        log(f"lab-number records: {hits} of {len(lj)} matched a dated episode")

    table = Table.load(pc["cultures"])
    rules = tomllib.load(open(pc["rules"], "rb"))
    cults, stages = [], []
    for labs, year in zip(ep["labels"], ep["median"]):
        hits = [table.match(x) for x in labs]
        ids = [i for h in hits if h for k, i in [h] if _fits(table.entries[i], year, dc["range_margin"])]
        cults.append(sorted({i for i in ids if table.entries[i]["kind"] == "culture"}))
        stages.append(sorted({i for i in ids if table.entries[i]["kind"] == "stage"}))
    ep["cultures"], ep["stages"] = cults, stages
    in_win = W.sum(axis=1) > 0.01
    counts["episodes"] = int(len(ep))
    counts["episodes_in_window"] = int(in_win.sum())
    counts["sites_with_episode_in_window"] = int(ep.loc[in_win, "site_id"].nunique())
    log(f"episodes: {len(ep)} at {ep['site_id'].nunique()} sites; {in_win.sum()} overlap the slices")

    # ---- external records: mark a matching episode, else add a unit
    ext = sources.load(cfg, log)
    unknown = sorted(set(ext["layer"]) - set(LAYERS))
    if unknown:
        raise ValueError(f"source records name layers not in the registry: {unknown}")
    ext["cell_ix"] = gridmod.locate(grid, ext["lon"].values, ext["lat"].values)
    ext = ext[ext["cell_ix"] >= 0].reset_index(drop=True)
    c14 = ext["bp"].notna().values
    Wx = np.zeros((len(ext), len(years)))
    if c14.any():
        mx, medx, lox, hix = datemod.calibrate(ext.loc[c14, "bp"].values, ext.loc[c14, "std"].values,
                                               dc["curve"], years, None, edges=edges)
        Wx[c14] = mx
        ext.loc[c14, "tpq"], ext.loc[c14, "taq"] = lox, hix
    Wx[~c14] = uniform_weights(ext.loc[~c14, "tpq"], ext.loc[~c14, "taq"], edges)
    keep = ext["tpq"].notna().values
    ext, Wx = ext[keep].reset_index(drop=True), Wx[keep]
    ext, Wx = merge_groups(ext, Wx)
    # Recorded presence and absence per episode; presence wins where both.
    pos = {m: np.zeros(len(ep), dtype=bool) for m in LAYERS}
    neg = {m: np.zeros(len(ep), dtype=bool) for m in LAYERS}
    ep_country = episode_countries(ep["lon"].values, ep["lat"].values)
    for L in direct:
        pos[L["id"]] |= ep[f"dm_{L['id']}"].values
    for m in LAYERS:
        pos[m] |= labjoin_pos[m]
    tree = cKDTree(unit_xyz(ep["lon"], ep["lat"]))
    near = tree.query_ball_point(unit_xyz(ext["lon"], ext["lat"]), chord(pc["match_km"]))
    es, ee = ep["start"].values, ep["end"].values
    matched = np.zeros(len(ext), dtype=bool)
    for k, idx in enumerate(near):
        idx = np.asarray(idx, dtype=int)
        hit = idx[(es[idx] <= ext["taq"].iat[k]) & (ee[idx] >= ext["tpq"].iat[k])] if len(idx) else idx
        if len(hit):
            (pos if ext["present"].iat[k] else neg)[ext["layer"].iat[k]][hit] = True
            matched[k] = True
    counts["external_records"] = int(len(ext))
    counts["external_matched_to_episode"] = int(matched.sum())
    counts["external_by_source"] = {s: {"records": int(n), "matched": int(mt)} for s, n, mt in
                                    zip(*np.unique(ext["source"], return_counts=True),
                                        [int(matched[(ext["source"] == s).values].sum()) for s in np.unique(ext["source"])])}
    ex = ext[~matched].reset_index(drop=True)
    Wex = Wx[~matched]
    # One added unit per place, span, layer and state, however many records.
    extra = pd.DataFrame({
        "site_id": -1 - np.arange(len(ex)), "site": ex["site"].astype(str), "lon": ex["lon"], "lat": ex["lat"],
        "cell_ix": ex["cell_ix"], "n_dates": ex["n_c14"].astype(int), "start": ex["tpq"], "end": ex["taq"],
        "median": (ex["tpq"] + ex["taq"]) / 2, "grave": ex["grave"].astype(bool),
        "dating": np.where(ex["n_c14"] > 0, "c14", "range"), "labels": [[] for _ in range(len(ex))],
        "source": ex["source"], "cultures": [[] for _ in range(len(ex))], "stages": [[] for _ in range(len(ex))],
        "site_type": ""})
    dup = extra.assign(m=ex["layer"], p=ex["present"]).duplicated(["site", "lon", "lat", "start", "end", "m", "p"]).values
    extra, Wex, ex = extra[~dup].reset_index(drop=True), Wex[~dup], ex[~dup].reset_index(drop=True)

    units = pd.concat([ep.drop(columns=[f"dm_{L['id']}" for L in direct]), extra], ignore_index=True)
    units["dated_site"] = np.arange(len(units)) < len(ep)
    Wall = np.vstack([W, Wex])
    for m in LAYERS:
        y = np.full(len(units), np.nan)
        basis = np.full(len(units), "", dtype=object)
        rule = rules.get(m)
        if rule:
            lab = np.array([_label_vote(rule, c, s, yr, ct) for c, s, yr, ct in
                            zip(ep["cultures"], ep["stages"], ep["median"], ep_country)])
            ok = ~np.isnan(lab)
            y[:len(ep)][ok] = lab[ok]
            basis[:len(ep)][ok] = "label"
        mine = (ex["layer"] == m).values
        absent = np.concatenate([neg[m], mine & (ex["present"] == 0).values])
        present = np.concatenate([pos[m], mine & (ex["present"] == 1).values])
        y[absent], basis[absent] = 0.0, "recorded"
        y[present], basis[present] = 1.0, "recorded"
        units[f"y_{m}"], units[f"basis_{m}"] = y, basis
    keep = Wall.sum(axis=1) > 1e-4
    units, Wall = units[keep].reset_index(drop=True), Wall[keep]
    counts["units_in_window"] = int(len(units))
    counts["grave_units"] = int(units["grave"].sum())
    for m in LAYERS:
        b = units[f"basis_{m}"]
        y = units[f"y_{m}"]
        counts[f"{m}"] = {"present_recorded": int(((b == "recorded") & (y == 1)).sum()),
                          "absent_recorded": int(((b == "recorded") & (y == 0)).sum()),
                          "present_label": int(((b == "label") & (units[f"y_{m}"] == 1)).sum()),
                          "absent_label": int(((b == "label") & (units[f"y_{m}"] == 0)).sum()),
                          "unknown": int((b == "").sum())}
        log(f"{m}: {counts[m]}")
    return units, Wall, counts
