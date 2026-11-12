"""Phase 1 data audit: how much dated evidence each cell has in each slice.

Writes, under [output] build_dir:
  grid.gpkg            the analysis grid with country and land columns
  dates.csv.gz         one row per radiocarbon date in the region
  site_phases.csv.gz   one row per provisional site-phase
  weights.npz          slice weights w[i, j] per site-phase, mass per date
and under [output] audit_dir:
  gap_cells.csv.gz     per cell and slice: counts and status
  tables.json          the summary tables quoted in AUDIT.md
  *.png                the gap maps
"""
import json
import os
import tomllib
from collections import Counter

import numpy as np
import pandas as pd

from pipeline.cultures import Table

from . import context, dates as datemod, grid as gridmod, plots


def run(cfg, log=print):
    out, aud = cfg["output"]["build_dir"], cfg["output"]["audit_dir"]
    os.makedirs(out, exist_ok=True)
    os.makedirs(aud, exist_ok=True)
    cc, dc = cfg["context"], cfg["dates"]
    years, half = gridmod.slices(cfg["time"])
    pcfg = tomllib.load(open(dc["pipeline_config"], "rb"))

    grid = gridmod.get(cfg)
    log(f"grid: {len(grid)} cells, {len(years)} slices of ±{half:g} years")

    # ---- context layers
    ctry = context.countries(cc["countries"], grid.crs)
    grid["country"] = context.nearest_country(grid["x"].values, grid["y"].values, ctry, 60)
    grid["region"] = [context.region_name(c) for c in grid["country"]]
    levels = context.sea_level(pcfg["sea"]["curve"], years)
    lf = context.land_fractions(grid, cc["etopo"], levels)
    land_then, land_now = lf[:, :-1], lf[:, -1]
    grid["land_now"] = land_now.round(3)
    is_land = land_then >= cc["land_min"]
    drowned = is_land & ((land_then - land_now[:, None]) >= cc["drowned_min"])
    icy = context.ice(grid, cc["terrain"], years) & is_land
    log(f"land cells today: {(land_now >= cc['land_min']).sum()}; drowned-since cells at "
        f"{years[0]}: {drowned[:, 0].sum()}; ice cells at {years[0]}: {icy[:, 0].sum()}")

    # ---- dates
    d, counts = datemod.load(cfg, pcfg["settlements"]["tables"], cfg["region"])
    d["cell_ix"] = gridmod.locate(grid, d["lon"].values, d["lat"].values)
    counts["dates_off_grid"] = int((d["cell_ix"] < 0).sum())
    d = d[d["cell_ix"] >= 0].reset_index(drop=True)
    mass, median = datemod.slice_mass(d["bp"].values, d["std"].values, dc["curve"], years, half)
    d["cal_median"] = median
    d["in_window"] = mass.sum(axis=1)
    d["phase_id"] = datemod.phases(d)
    px, py = d["lon"].values, d["lat"].values
    from pyproj import Transformer
    sx, sy = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True).transform(px, py)
    d["country"] = context.nearest_country(sx, sy, ctry, 60)
    d["region"] = [context.region_name(c) for c in d["country"]]
    counts["dates_with_mass_in_window"] = int((d["in_window"] > 0.01).sum())
    counts["expected_dates_in_window"] = float(mass.sum())
    counts["dates_std_over_200"] = int(((d["std"] > 200) & (d["in_window"] > 0.01)).sum())
    log(f"dates on grid: {len(d)}; expected dates inside the slices: {mass.sum():.0f}")

    # ---- provisional site-phases and their slice weights
    table = Table.load(cc["cultures"])
    g = d.groupby("phase_id", sort=True)
    ph = g.agg(site_id=("site_id", "first"), site=("site", "first"), lon=("lon", "first"),
               lat=("lat", "first"), cell_ix=("cell_ix", "first"), country=("country", "first"),
               region=("region", "first"), n_dates=("bp", "size"),
               labels=("labels", "first"), site_type=("site_type", lambda s: Counter(s).most_common(1)[0][0]),
               datasets=("dataset", lambda s: "|".join(sorted(set(s))))).reset_index()
    pix = d["phase_id"].values - 1
    psum = np.zeros((len(ph), len(years)))
    np.add.at(psum, pix, mass)
    w = psum / ph["n_dates"].values[:, None]        # share of p_i(t) in slice j
    kinds, cults, stages = [], [], []
    for labs in ph["labels"]:
        hits = [h for h in (table.match(x) for x in labs) if h]
        cs = sorted({i for k, i in hits if k == "culture"})
        ss = sorted({i for k, i in hits if k == "stage"})
        kinds.append("culture" if cs else "stage" if ss else "unmapped" if labs else "none")
        cults.append("|".join(cs))
        stages.append("|".join(ss))
    ph["label_kind"], ph["cultures"], ph["stages"] = kinds, cults, stages
    ph["weight_in_window"] = w.sum(axis=1).round(4)
    ph["cell"] = grid["cell"].values[ph["cell_ix"].values]
    d["cell"] = grid["cell"].values[d["cell_ix"].values]

    # ---- per cell and slice
    n_cells, n_sl = len(grid), len(years)
    cell_d = d["cell_ix"].values
    n_dates = np.zeros((n_cells, n_sl))
    np.add.at(n_dates, cell_d, mass)
    w_sum = np.zeros((n_cells, n_sl))
    np.add.at(w_sum, ph["cell_ix"].values, w)
    present = psum >= dc["present_min_dates"]
    n_phase = np.zeros((n_cells, n_sl), dtype=int)
    np.add.at(n_phase, ph["cell_ix"].values, present.astype(int))
    ssum = np.zeros((d["site_id"].max() + 1, n_sl))
    np.add.at(ssum, d["site_id"].values, mass)
    site_cell = np.full(d["site_id"].max() + 1, -1)
    site_cell[d["site_id"].values] = cell_d
    spres = (ssum >= dc["present_min_dates"]) & (site_cell >= 0)[:, None]
    n_site = np.zeros((n_cells, n_sl), dtype=int)
    np.add.at(n_site, site_cell[site_cell >= 0], spres[site_cell >= 0].astype(int))
    labelled = np.zeros((n_cells, n_sl), dtype=int)
    lab_ok = ph["label_kind"].isin(["culture"]).values
    np.add.at(labelled, ph["cell_ix"].values[lab_ok], present[lab_ok].astype(int))

    status = np.where(~is_land, "sea", np.where(n_phase > 0, "evidence",
             np.where(icy, "ice", np.where(drowned, "drowned", "no evidence"))))
    long = pd.DataFrame({
        "cell": np.repeat(grid["cell"].values, n_sl), "slice": np.tile(years, n_cells),
        "n_site_phases": n_phase.ravel(), "n_sites": n_site.ravel(),
        "sum_w": w_sum.ravel().round(3), "n_dates": n_dates.ravel().round(2),
        "n_culture_labelled_phases": labelled.ravel(),
        "land_share": land_then.ravel().round(2), "status": status.ravel()})
    long[long["status"] != "sea"].to_csv(os.path.join(aud, "gap_cells.csv.gz"), index=False)

    # ---- outputs
    grid.to_file(os.path.join(out, "grid.gpkg"), driver="GPKG")
    dd = d.drop(columns=["cell_ix"]).copy()
    for c in ("labels", "compilations"):
        dd[c] = dd[c].map("|".join)
    dd.to_csv(os.path.join(out, "dates.csv.gz"), index=False)
    pp = ph.drop(columns=["cell_ix"]).copy()
    pp["labels"] = pp["labels"].map("|".join)
    pp.to_csv(os.path.join(out, "site_phases.csv.gz"), index=False)
    np.savez_compressed(os.path.join(out, "weights.npz"), years=years, w=w.astype(np.float32),
                        phase_id=ph["phase_id"].values, date_mass=mass)

    # ---- summary tables
    T = {"counts": counts, "slices": [int(y) for y in years], "half_width": float(half),
         "grid": {"cells": n_cells, "cell_km": cfg["grid"]["cell_km"], "crs": cfg["grid"]["crs"],
                  "land_cells_today": int((land_now >= cc["land_min"]).sum())}}
    land_cs = is_land.sum(axis=0)
    T["by_slice"] = [{
        "slice": int(y), "land_cells": int(land_cs[j]),
        "cells_with_evidence": int((n_phase[:, j] > 0).sum()),
        "share_with_evidence": round(float((n_phase[:, j] > 0).sum() / land_cs[j]), 3),
        "cells_with_2plus_sites": int((n_site[:, j] >= 2).sum()),
        "drowned_cells": int(drowned[:, j].sum()), "ice_cells": int(icy[:, j].sum()),
        "expected_dates": round(float(n_dates[:, j].sum()), 0),
        "site_phases": int(present[:, j].sum()), "sites": int(spres[:, j].sum()),
        "phases_with_culture_label": int((present[:, j] & lab_ok).sum()),
        "phases_with_stage_only": int((present[:, j] & (ph["label_kind"] == "stage").values).sum()),
        "phases_unlabelled": int((present[:, j] & ph["label_kind"].isin(["none", "unmapped"]).values).sum()),
    } for j, y in enumerate(years)]

    names = context.country_table(ctry)
    today = land_now >= cc["land_min"]
    rows = []
    for key, col in (("region", "region"), ("country", "country")):
        for val, cells in grid[today].groupby(col).groups.items():
            ix = grid.index.get_indexer(cells)
            if key == "country" and len(ix) < 5:
                continue
            dsel = (d[col] == val).values
            ev = (n_phase[ix] > 0)
            lnd = is_land[ix]
            area = len(ix) * grid.geometry.area.iloc[0] / 1e6
            rows.append({"level": key, "name": names.get(val, val) if key == "country" else val,
                         "code": val if key == "country" else "", "land_cells": len(ix),
                         "sites": int(d.loc[dsel & (d["in_window"] > 0.5).values, "site_id"].nunique()),
                         "expected_dates": round(float(mass[dsel].sum()), 0),
                         "dates_per_1000km2": round(float(mass[dsel].sum()) / area * 1000, 2),
                         "share_cell_slices_with_evidence": round(float(ev.sum() / max(lnd.sum(), 1)), 3),
                         "share_cells_ever_with_evidence": round(float(ev.any(axis=1).mean()), 3),
                         "share_evidence_early": round(float(ev[:, years < -6000].sum() / max(lnd[:, years < -6000].sum(), 1)), 3),
                         "share_evidence_late": round(float(ev[:, years >= -6000].sum() / max(lnd[:, years >= -6000].sum(), 1)), 3)})
    T["by_area"] = sorted(rows, key=lambda r: (r["level"] != "region", -r["dates_per_1000km2"]))

    comp = {}
    inw = d["in_window"].values
    for i, cs in enumerate(d["compilations"]):
        for c in cs:
            e = comp.setdefault(c, {"expected_dates": 0.0, "regions": Counter(), "slices": np.zeros(n_sl)})
            e["expected_dates"] += inw[i]
            e["regions"][d["region"].iat[i]] += inw[i]
            e["slices"] += mass[i]
    T["by_compilation"] = sorted(({
        "name": c, "expected_dates": round(e["expected_dates"]),
        "regions": {k: round(v) for k, v in e["regions"].most_common() if v >= 1},
        "by_millennium": {str(int(m)): round(float(e["slices"][(years >= m) & (years < m + 1000)].sum()))
                          for m in range(-10000, -2999, 1000)},
    } for c, e in comp.items()), key=lambda r: -r["expected_dates"])

    pw = ph[ph["weight_in_window"] >= 0.5]
    T["labels"] = {"site_phases_mostly_in_window": len(pw),
                   "by_kind": pw["label_kind"].value_counts().to_dict(),
                   "by_kind_and_region": pw.groupby(["region", "label_kind"]).size().unstack(fill_value=0).to_dict("index"),
                   "top_cultures": Counter(c for s in pw["cultures"] for c in s.split("|") if c).most_common(40),
                   "cultures_with_pottery_trait": sorted(e["id"] for e in table.cultures if e.get("traits", {}).get("pottery"))}
    mat = Counter()
    for m, v in zip(d["material"], inw):
        mat[m or "(not given)"] += v
    T["dated_materials"] = [(m, round(v)) for m, v in mat.most_common(40)]
    st = Counter()
    for m, v in zip(d["site_type"], inw):
        st[m or "(not given)"] += v
    T["site_types"] = [(m, round(v)) for m, v in st.most_common(30)]
    json.dump(T, open(os.path.join(aud, "tables.json"), "w"), indent=1, ensure_ascii=False)

    # ---- maps
    layers = dict(grid=grid, ctry=ctry, years=years, is_land=is_land, drowned=drowned, icy=icy, region=cfg["region"])
    plots.small_multiples(n_phase, "Site-phases with dated evidence, per cell and slice",
                          "provisional site-phases with ≥ 0.5 expected dates in the slice",
                          os.path.join(aud, "gap_site_phases.png"), **layers)
    plots.small_multiples(n_dates, "Radiocarbon dates per cell and slice",
                          "expected number of dates (sum of calibrated probability inside the slice)",
                          os.path.join(aud, "gap_dates.png"), **layers)
    plots.small_multiples(labelled, "Site-phases that carry a named culture label",
                          "site-phases whose source label matches a culture in data/cultures/cultures.toml",
                          os.path.join(aud, "gap_culture_labels.png"), **layers)
    plots.coverage(n_phase, os.path.join(aud, "gap_coverage.png"), **layers)
    plots.timeline(T["by_slice"], os.path.join(aud, "gap_timeline.png"))
    log(f"wrote {aud}/ and {out}/")
    return T
