"""Sample units: individual ancient genomes from the Allen Ancient DNA
Resource (AADR v66.p1, Mallick et al. 2024, Harvard Dataverse
doi:10.7910/DVN/FFIDCW, CC0).

One unit per individual that passes AADR's assessment (Pass,
PROVISIONAL_PASS, MERGE_PASS), with coordinates and a mean date; its slice
weights are a normal distribution with AADR's date mean and standard
deviation (at least 25 years). Share layers in layers.toml name a haplogroup
field ("y" or "mt") and the clade prefixes they cover; a sample is 1 if its
haplogroup starts with one of them, 0 if it has a call of that kind but not
in the clade, and unknown if it has no call (females have no Y call).
"""
import os
from math import erf, sqrt

import numpy as np
import pandas as pd

COLS = {2: "individual", 10: "bp", 11: "sd", 14: "group", 15: "locality", 17: "lat", 18: "lon", 26: "snps",
        30: "sex", 35: "y_isogg", 36: "y_manual", 38: "mt", 47: "assessment"}
NOCALL = r"^(\.\.|n/a|nan|na|)$|^n/a"


def load_aadr(path):
    d = pd.read_csv(path, sep="\t", low_memory=False, encoding_errors="replace")
    d = d.rename(columns={d.columns[i]: n for i, n in COLS.items()})[list(COLS.values())]
    for c in ("bp", "sd", "lat", "lon", "snps"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    ok = d["assessment"].astype(str).str.upper().str.replace("MERGE_", "").str.replace("PROVISIONAL_", "").str.startswith("PASS")
    d = d[ok & d["bp"].gt(0) & d["lat"].notna() & d["lon"].notna()]
    d = d.sort_values("snps", ascending=False).drop_duplicates("individual")
    ym = d["y_manual"].astype(str).str.strip()
    yi = d["y_isogg"].astype(str).str.strip()
    d["y"] = np.where(ym.str.contains(NOCALL, case=False), yi, ym)
    d.loc[pd.Series(d["y"], index=d.index).astype(str).str.contains(NOCALL, case=False), "y"] = ""
    d["mt"] = d["mt"].astype(str).str.strip()
    d.loc[d["mt"].str.contains(NOCALL, case=False), "mt"] = ""
    return d.reset_index(drop=True)


def normal_mass(mean_year, sd, edges):
    """Share of N(mean, sd) inside each slice (years signed)."""
    cdf = np.vectorize(lambda z: 0.5 * (1 + erf(z / sqrt(2))))
    a = (edges[:, 0][None, :] - mean_year[:, None]) / sd[:, None]
    b = (edges[:, 1][None, :] - mean_year[:, None]) / sd[:, None]
    return cdf(b) - cdf(a)


def in_clade(values, prefixes, exclude=()):
    v = pd.Series(values).astype(str)
    hit = np.zeros(len(v), dtype=bool)
    for p in prefixes:
        hit |= v.str.startswith(p).values
    for x in exclude:
        hit &= ~v.str.startswith(x).values
    return hit


def units(cfg, grid, years, edges, registry, counts, log=print):
    from . import grid as gridmod
    path = os.path.join(cfg["output"]["build_dir"], "sources", "aadr_v66.p1_1240K.anno")
    if not os.path.exists(path):
        log("people: AADR annotation missing (run `python -m isostyle fetch`); sample layers skipped")
        return None
    d = load_aadr(path)
    d["cell_ix"] = gridmod.locate(grid, d["lon"].values, d["lat"].values)
    d = d[d["cell_ix"] >= 0].reset_index(drop=True)
    W = normal_mass((1950 - d["bp"]).values.astype(float), np.maximum(d["sd"].fillna(25).values, 25.0), edges)
    keep = W.sum(axis=1) > 1e-4
    d, W = d[keep].reset_index(drop=True), W[keep]
    u = d.assign(site=d["locality"].astype(str), source="AADR v66.p1: " + d["group"].astype(str), dating="aDNA",
                 grave=True, n_dates=0, site_id=-1)
    sets = {}
    for L in registry.by_unit("sample"):
        m = L["id"]
        if L["kind"] == "presence_only":
            u[f"y_{m}"], u[f"basis_{m}"] = 1.0, "recorded"
            continue
        field = L["field"]
        call = u[field].astype(str).str.len() > 0
        if L.get("other"):
            others = [x for x in registry.by_unit("sample") if x.get("set") == L["set"] and not x.get("other")]
            hit = ~np.any([in_clade(u[field], x["prefixes"], x.get("exclude", ())) for x in others], axis=0)
        else:
            hit = in_clade(u[field], L["prefixes"], L.get("exclude", ()))
        u[f"y_{m}"] = np.where(call, hit.astype(float), np.nan)
        u[f"basis_{m}"] = np.where(call, "recorded", "")
        sets.setdefault(L["set"], []).append(m)
    counts["sample_units"] = int(len(u))
    counts["samples_with_y"] = int((u["y"].astype(str).str.len() > 0).sum())
    counts["samples_with_mt"] = int((u["mt"].astype(str).str.len() > 0).sum())
    for s, ids in sets.items():
        counts[s] = {m: int((u[f"y_{m}"] == 1).sum()) for m in ids}
        log(f"{s}: {counts[s]}")
    u.drop(columns=["cell_ix"]).assign(**{f"w_{y}": W[:, k].round(4) for k, y in enumerate(years)}).to_csv(
        os.path.join(cfg["output"]["build_dir"], "sample_units.csv.gz"), index=False)
    return u, W
