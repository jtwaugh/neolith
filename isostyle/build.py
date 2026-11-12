"""Surfaces per layer (data/isostyle/layers.toml) and slice, on the game grid.

Inputs: the grid file ([grid] file) and a site table. The site table is
built from the cached radiocarbon dumps and the fetched datasets, and saved
as build/isostyle/units.csv.gz; set [presence] units_file to use your own
table in that format instead (columns lon, lat, y_<layer>,
basis_<layer> and one w_<year> column per slice).
"""
import json
import os

import numpy as np
import pandas as pd

from . import grid as gridmod, layers as layermod, maps, observe, surface


def soil_ph(grid, src_dir):
    """Mean topsoil pH per cell from the SoilGrids 5 km layers (0-30 cm)."""
    import rasterio
    from pyproj import Transformer
    pts = [np.column_stack([grid["lon"], grid["lat"]])]
    for g in grid.geometry:
        pass
    ring = np.array([np.asarray(g.exterior.coords)[:6] for g in grid.geometry])       # (cells, 6, 2)
    cen = pts[0][:, None, :]
    samples = np.concatenate([cen, (ring + cen) / 2], axis=1).reshape(-1, 2)          # centre + 6 inner points
    total, weight = np.zeros(len(samples)), 0.0
    for name, thick in (("phh2o_0-5cm_mean_5000.tif", 5), ("phh2o_5-15cm_mean_5000.tif", 10),
                        ("phh2o_15-30cm_mean_5000.tif", 15)):
        path = os.path.join(src_dir, name)
        if not os.path.exists(path):
            return None
        with rasterio.open(path) as src:
            x, y = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True).transform(samples[:, 0], samples[:, 1])
            v = np.array([s[0] for s in src.sample(zip(x, y))], dtype=float)
            v[(v == src.nodata) | (v <= 0)] = np.nan
        total += v * thick
        weight += thick
    ph = (total / weight / 10.0).reshape(len(grid), 7)                                # stored as pH x 10
    return np.nanmean(ph, axis=1)


def layer_note(L, sigma, borrowed, has_absences, n_absent=0):
    """The sentence under a layer's map titles."""
    sg = f"σ = {sigma:g} km ({'cross-validated' if not borrowed else borrowed})."
    if L["kind"] == "grid":
        return L["note"]
    if L["kind"] == "continuous":
        return f"{sg} Kernel mean of {L['evidence_word']}, shrunk toward the slice mean. {L['note']}".strip()
    if has_absences:
        return (f"{sg} Share of {L['evidence_word']} with the trait among those whose status is known; "
                f"each panel gives the share of weight that is label-derived. {L['note']}").strip()
    if n_absent:
        return (f"{sg} Only {n_absent} recorded absences, too few to draw a boundary: read this mostly as a map of "
                f"where it is recorded. {L['note']}").strip()
    return (f"{sg} No source records absence, so presence is 100% wherever there is evidence: read this as a map "
            f"of where it is recorded, not of where it was absent. {L['note']}").strip()


def run(cfg, log=print):
    out, bdir = cfg["output"]["out_dir"], cfg["output"]["build_dir"]
    os.makedirs(os.path.join(out, "maps"), exist_ok=True)
    sc, pc = cfg["surface"], cfg["presence"]
    registry = layermod.Registry.load(pc["layers"])
    years = np.array(cfg["time"]["slices"])
    half = np.diff(years).min() / 2
    edges = np.column_stack([years - half, years + half])
    grid, terrain = gridmod.load_game(cfg["grid"]["file"], years)
    land, ice = terrain != "Water", terrain == "Ice"
    log(f"grid: {len(grid)} cells; land per slice {land.sum(axis=0).tolist()}")
    ph = soil_ph(grid, os.path.join(bdir, "sources"))
    acid_cells = None if ph is None else np.nan_to_num(ph, nan=7.0) < sc["bone_ph_min"]

    # ---- observation units, by unit type
    occ_ids = [L["id"] for L in registry.by_unit("occupation")]
    if pc.get("units_file"):
        units = pd.read_csv(pc["units_file"])
        W = units[[f"w_{y}" for y in years]].values
        for m in occ_ids:
            units[f"basis_{m}"] = units[f"basis_{m}"].fillna("")
        counts = {"units_file": pc["units_file"], "units_in_window": len(units)}
    else:
        units, W, counts = observe.build(cfg, grid, years, edges, registry, log)
        save = units.drop(columns=["cell_ix"]).copy()
        save["cell"] = grid["cell"].values[units["cell_ix"].values]
        for c in ("labels", "cultures", "stages"):
            save[c] = save[c].map("|".join)
        for j, y in enumerate(years):
            save[f"w_{y}"] = W[:, j].round(4)
        save.to_csv(os.path.join(bdir, "units.csv.gz"), index=False)
    tables = {"occupation": (units, W)}
    for unit, fn in EXTRA_UNITS.items():
        if registry.by_unit(unit):
            tables[unit] = fn(cfg, grid, years, edges, registry, counts, log)

    cv = maps.Canvas(grid, "build/isostyle/naturalearth/ne_50m_admin_0_countries.shp")
    summary = {"slices": years.tolist(), "half_width": float(half), "counts": counts, "layers": {},
               "groups": registry.groups,
               "e_min": sc["e_min"], "alpha": sc["alpha"], "cutoff": sc["cutoff"], "bootstrap": sc["bootstrap"],
               "bone_ph_min": sc["bone_ph_min"],
               "acid_cells": None if acid_cells is None else int((acid_cells & land[:, -1]).sum())}
    results, oks, contrast, sigmas, all_segs, rows = {}, {}, {}, {}, {}, []

    def sel_of(L):
        u, w = tables[L["unit"]]
        return u, w, u[f"y_{L['id']}"].notna().values

    # Kernel widths: cross-validated where a layer has >= 20 presences and
    # absences; the rest borrow (layers.toml `sigma`).
    for L in registry:
        if L["kind"] == "grid" or L["unit"] not in tables:
            continue
        u, w, known = sel_of(L)
        y = u.loc[known, f"y_{L['id']}"].values
        if L["kind"] == "continuous":
            contrast[L["id"]] = False
            continue
        contrast[L["id"]] = bool((y == 0).sum() >= 20 and (y == 1).sum() >= 20)
        if contrast[L["id"]] and L["sigma"] == "cv":
            cvres = surface.cross_validate(u.loc[known, "lon"].values, u.loc[known, "lat"].values,
                                           w[known], y, sc["sigma_km"], sc["cutoff"], sc["alpha"])
            sigmas[L["id"]] = min(cvres, key=lambda s: cvres[s]["log_loss"])
            summary["layers"][L["id"]] = {"cv": {str(k): v for k, v in cvres.items()}}
            log(f"{L['id']}: sigma {sigmas[L['id']]} km by cross-validation "
                + ", ".join(f"{k}:{v['log_loss']:.4f}" for k, v in cvres.items()))
    default = sc["sigma_km"][len(sc["sigma_km"]) // 2]

    for k, L in enumerate(registry):
        m = L["id"]
        if L["kind"] == "grid":
            res = GRID_LAYERS[m](cfg, grid, years, L, log)
            if res is None:
                continue
            ok = land & ~ice & ~np.isnan(res["f"])
            results[m], oks[m], contrast[m] = res, ok, False
            all_segs[m] = maps.presence(cv, os.path.join(out, "maps", f"presence_{m}.png"), L, years, res, ok,
                                        land, ice, None, L["levels"], layer_note(L, 0, "", False),
                                        [""] * len(years))
            summary["layers"][m] = {"kind": "grid", "sigma_km": None, "has_absences": False}
            rows += surface_rows(grid, years, land, ice, m, res, ok, None, sc)
            continue
        if L["unit"] not in tables:
            log(f"{m}: no {L['unit']} units; skipped")
            continue
        u, w, sel = sel_of(L)
        if not sel.any():
            log(f"{m}: no units with a known status; skipped")
            continue
        if m in sigmas:
            borrowed = ""
        elif L["sigma"] != "cv" and L["sigma"] in sigmas:
            borrowed = f"from {registry[L['sigma']]['name'].lower()}"
        else:
            borrowed = "default; too few absences to cross-validate" if L["kind"] != "continuous" else "default"
        sg = sigmas.setdefault(m, sigmas.get(L["sigma"], default))
        y = u.loc[sel, f"y_{m}"].values.astype(float)
        lab = (u.loc[sel, f"basis_{m}"] == "label").values
        res = surface.surfaces(grid["lon"].values, grid["lat"].values, u.loc[sel, "lon"].values,
                               u.loc[sel, "lat"].values, w[sel], y, lab, w, u["lon"].values,
                               u["lat"].values, sg, sc["cutoff"], sc["alpha"], sc["e_min"],
                               sc["bootstrap"], sc["seed"] + k,
                               threshold=L["levels"][len(L["levels"]) // 2] if L["kind"] == "continuous" else 0.5)
        acid = acid_cells if "acid" in L["mask"] else None
        ok = land & ~ice & (res["E"] >= sc["e_min"])
        if acid is not None:
            ok &= ~acid[:, None]
        results[m], oks[m] = res, ok
        wsum = w[sel].sum(axis=0)
        lsum = (w[sel] * lab[:, None]).sum(axis=0)
        word = L["evidence_word"]
        heads = [f"{wsum[j]:.0f} {word}" + (f", {100 * lsum[j] / max(wsum[j], 1e-9):.0f}% by label" if lab.any() else "")
                 for j in range(len(years))]
        note = layer_note(L, sg, borrowed, contrast[m], int((y == 0).sum()) if L["kind"] != "continuous" else 0)
        all_segs[m] = maps.presence(cv, os.path.join(out, "maps", f"presence_{m}.png"), L, years, res, ok, land, ice,
                                    acid, L["levels"], note, heads)
        maps.evidence(cv, os.path.join(out, "maps", f"evidence_{m}.png"), L, years, res, land, ice, acid,
                      sc["e_min"], sg)
        if contrast[m] or L["kind"] == "continuous":
            maps.uncertainty(cv, os.path.join(out, "maps", f"uncertainty_{m}.png"), L, years, res, ok, land, ice, acid,
                             sc["bootstrap"])
        info = summary["layers"].setdefault(m, {})
        info.update({"kind": L["kind"], "sigma_km": sg, "sigma_from": borrowed, "has_absences": contrast[m],
                     "n_absent": int((y == 0).sum()) if L["kind"] != "continuous" else None,
                     "units_known": int(sel.sum()),
                     "f0": [round(float(v), 3) for v in res["f0"]],
                     "by_slice": [{"slice": int(yv), "occupations": round(float(wsum[j]), 1),
                                   "label_share": round(float(lsum[j] / max(wsum[j], 1e-9)), 3),
                                   "land_cells": int((land[:, j] & ~ice[:, j]).sum()),
                                   "cells_unmasked": int(ok[:, j].sum()),
                                   "cells_firm": int((ok[:, j] & ((res["boot_above"][:, j] >= 0.9) | (res["boot_above"][:, j] <= 0.1))).sum())}
                                  for j, yv in enumerate(years)]})
        rows += surface_rows(grid, years, land, ice, m, res, ok, acid, sc)
        log(f"{m}: surfaces and maps done (sigma {sg} km)")
    for gname in registry.groups:
        members = [L for L in registry if L["group"] == gname and L["id"] in results]
        if members:
            slug = gname.lower().replace(" & ", "_").replace(" ", "_")
            maps.overlay(cv, os.path.join(out, "maps", f"overlay_{slug}.png"), years, members, results, oks,
                         land, ice, contrast, gname)
    maps.contours_geojson(os.path.join(out, "contours.geojson"), all_segs)
    pd.concat(rows).to_csv(os.path.join(out, "surfaces.csv.gz"), index=False)
    json.dump(summary, open(os.path.join(out, "summary.json"), "w"), indent=1)
    log(f"wrote {out}/")
    return summary


def surface_rows(grid, years, land, ice, m, res, ok, acid, sc):
    rows = []
    for j, yv in enumerate(years):
        keep = land[:, j]
        reason = np.where(ice[:, j], "ice", np.where(res["E"][:, j] < sc["e_min"], "low evidence", ""))
        if acid is not None:
            reason = np.where((reason == "") & acid, "acid soil", reason)
        rows.append(pd.DataFrame({
            "cell": grid["cell"].values[keep], "slice": int(yv), "layer": m,
            "evidence": res["E"][keep, j].round(3), "presence": np.where(ok[keep, j], res["f"][keep, j], np.nan).round(3),
            "masked": ~ok[keep, j], "mask_reason": reason[keep],
            "label_share": res["label_share"][keep, j].round(3),
            "recorded_share_of_all_dated": res["recorded_share"][keep, j].round(3),
            "evidence_all_dated": res["E_all"][keep, j].round(3),
            "boot_share_above_50": np.where(ok[keep, j], res["boot_above"][keep, j], np.nan).round(3),
            "boot_share_enough_evidence": res["boot_valid"][keep, j].round(3)}))
    return rows


# Unit types beyond occupations: unit -> function(cfg, grid, years, edges,
# registry, counts, log) returning (units with y_/basis_ columns, W). Filled
# by the pollen and people modules.
EXTRA_UNITS = {}
# Grid layers: layer id -> function(cfg, grid, years, layer, log) returning a
# result dict like surface.surfaces (f, E, ...) or None.
GRID_LAYERS = {}
