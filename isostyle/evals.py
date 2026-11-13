"""Evals for the speculative fill: how smooth it is, and what smoothing costs.

`python -m isostyle evals` fills every layer with the settings in
config.toml's [speculative] table and writes data/isostyle/evals/:

  report.json   every number below, per layer and overall, plus hotspots
  report.md     the same for reading

Smoothness (lower is better; values are scaled to 0..1 of the layer's range):
  rough_os     mean step between an observed cell and a speculative neighbour
  rough_ss     mean step between two speculative neighbours
  rough_oo     the same between two observed neighbours, for comparison only
  cliffs       speculative neighbour pairs more than CLIFF apart, per 1,000
               (rule_edge_cliffs: those whose two cells follow different
               judgements, i.e. the edge of a critic's region or polygon)
  conf_edges   speculative neighbour pairs whose confidence class differs, per
               1,000. The game draws each class at a different strength, so
               these show as lines even where the value is smooth. Reported
               only: no fill setting changes them.
  time_step    mean change of a speculative cell from one slice to the next
  flicker      speculative cell-slices that go up then down (or down then up)
               by more than FLICK each way, per 1,000
  score        the mean of rough_os, rough_ss, cliffs and flicker, each divided
               by its value under the unsmoothed defaults (1.0 = no change)

Guards (a setting that breaks one is rejected, however smooth):
  observed     observed cells keep their values exactly
  coverage     no land cell loses its value
  holdout      hide blocks of observed cells (a tenth of them, each block a
               cell and two rings), refill, and compare with what was hidden:
               mean absolute error must stay within HOLDOUT_SLACK of the
               unsmoothed fill's. This is what stops plain blurring.
  drift        mean move of speculative cells away from the unsmoothed fill
               must stay under DRIFT_MAX, so smoothing cannot erase the
               critics' gradients and river rules
  spread       farming still arrives in order: Anatolia, then the Balkans,
               then central Europe, then the British Isles (cereals, livestock)
  regressions  the cases in data/isostyle/evals/regressions.toml (artefacts a
               critic reported and the numbers confirmed): no more may fail
               than that file's `allowed_failing`

`--search` tries a grid of settings and reports the one that passes every
guard with the fewest failing regression cases, then the lowest score
(search.json). `--check claims.json` tests a critic's claims
against the numbers. `--crop LAYER YEAR LON0 LAT0 LON1 LAT1 OUT.png` draws
one place for a critic to look at.
"""
import itertools
import json
import os
import tomllib
import zlib

import numpy as np

from . import speculative as spec

CLIFF = 0.4
FLICK = 0.15
HOLDOUT_SHARE = 0.10
HOLDOUT_SLACK = (1.05, 0.002)   # allowed: baseline * 1.05 + 0.002
DRIFT_MAX = 0.03
SCORE_PARTS = ("rough_os", "rough_ss", "cliffs", "flicker")
SPREAD = ["Anatolia & Cyprus", "Balkans & Greece", "Central Europe", "British Isles"]
SPREAD_LAYERS = ("cereals", "domestic_livestock")
# Settings the search tries; everything else comes from config.toml. Stage 1
# (2026-11-12) searched blend_rings, smooth_iters and time_smooth; this is
# stage 2, the smooth-critic's proposed fixes as switches.
GRID = {"blend_rings": [8, 12], "blend_conf": [0, 1], "kernel_cap": [0, 1], "hold_rings": [0, 1], "bridge": [0.0, 0.75],
        "time_from_observed": [1, 0]}
TEMPORAL_KINDS = ("flicker", "period_step")
REGRESSIONS = "evals/regressions.toml"


class Bench:
    """The prepared inputs plus everything that does not depend on the fill
    settings: neighbour pairs, hold-out masks, ring distances, and the
    unsmoothed baseline fill."""

    def __init__(self, cfg, log=print, layers=None):
        self.cfg, self.log = cfg, log
        self.prep = spec.prepare(cfg, log, layers)
        NB = self.NB = self.prep["NB"]
        n = len(NB)
        i, j = np.repeat(np.arange(n), 6), NB.ravel()
        keep = j > i
        self.I, self.J = i[keep], j[keep]
        self.lon, self.lat = self.prep["grid"]["lon"].values, self.prep["grid"]["lat"].values
        self.hide, self.rings, self.rings_h, self.base = {}, {}, {}, {}
        for m, P in self.prep["layers"].items():
            self.hide[m] = self._holdout(m, P)
            self.rings[m] = spec.layer_rings(P, NB)
            self.rings_h[m] = spec.layer_rings(P, NB, self.hide[m])
            self.base[m] = self.fill(m, spec.DEFAULTS)
        log(f"evals: prepared {len(self.prep['layers'])} layers")

    def _holdout(self, m, P):
        """Blocks of observed cells to hide: a seed cell and two rings."""
        NB = self.NB
        hide = np.zeros(P["obs"].shape, bool)
        for j in range(len(hide)):
            seen = np.flatnonzero(P["now"][j] & ~np.isnan(P["obs"][j]))
            if len(seen) < 40:
                continue
            rng = np.random.default_rng(zlib.crc32(m.encode()) + j)
            block = np.zeros(hide.shape[1], bool)
            block[rng.choice(seen, max(1, int(HOLDOUT_SHARE * len(seen) / 12)), replace=False)] = True
            for _ in range(2):
                nb = NB[block].ravel()
                block[nb[nb >= 0]] = True
            hide[j] = block & ~np.isnan(P["obs"][j]) & P["now"][j]
        return hide

    def fill(self, m, par, holdout=False):
        P = self.prep["layers"][m]
        return spec.fill_layer(P, self.NB, par, self.hide[m] if holdout else None, self.rings_h[m] if holdout else self.rings[m])

    def scaled(self, m, V):
        lo, hi = self.prep["layers"][m]["range"]
        return (V - lo) / (hi - lo)

    # ------------------------------------------------------------ metrics
    def layer_metrics(self, m, par, filled=None):
        P = self.prep["layers"][m]
        V, basis, conf, ref = filled or self.fill(m, par)
        X, X0 = self.scaled(m, V), self.scaled(m, self.base[m][0])
        fixed = basis == "observed"
        specc = ~fixed & ~np.isnan(X)
        I, J = self.I, self.J
        tot = {k: [0.0, 0] for k in ("oo", "os", "ss")}
        cliffs = edges = cedges = 0
        for j in range(len(X)):
            a, b = X[j, I], X[j, J]
            ok = ~np.isnan(a) & ~np.isnan(b)
            d = np.abs(a - b)
            fi, fj = fixed[j, I], fixed[j, J]
            for k, sel in (("oo", ok & fi & fj), ("os", ok & (fi ^ fj)), ("ss", ok & ~fi & ~fj)):
                tot[k][0] += d[sel].sum()
                tot[k][1] += int(sel.sum())
            c = ok & ~fi & ~fj & (d > CLIFF)
            cliffs += int(c.sum())
            edges += int((ref[j, I][c] != ref[j, J][c]).sum())
            cedges += int((ok & ~fi & ~fj & (conf[j, I] != conf[j, J])).sum())
        mean = {k: (s / c if c else 0.0) for k, (s, c) in tot.items()}
        D = X[1:] - X[:-1]
        tv = ~np.isnan(D) & (specc[1:] | specc[:-1])
        d1, d2 = D[:-1], D[1:]
        with np.errstate(invalid="ignore"):
            fl = specc[1:-1] & (d1 * d2 < 0) & (np.minimum(np.abs(d1), np.abs(d2)) > FLICK)
        nspec = max(int(specc.sum()), 1)
        Vh = self.fill(m, par, holdout=True)[0]
        hid = self.hide[m]
        err = np.abs(self.scaled(m, Vh) - self.scaled(m, P["obs"]))[hid]
        obs = ~np.isnan(P["obs"]) & P["land"]
        return {
            "rough_oo": mean["oo"], "rough_os": mean["os"], "rough_ss": mean["ss"],
            "cliffs": 1000 * cliffs / max(tot["ss"][1], 1), "rule_edge_cliffs": 1000 * edges / max(tot["ss"][1], 1),
            "conf_edges": 1000 * cedges / max(tot["ss"][1], 1),
            "time_step": float(np.abs(D[tv]).mean()) if tv.any() else 0.0,
            "flicker": 1000 * int(fl.sum()) / nspec,
            "holdout": float(np.nanmean(err)) if hid.any() else 0.0,
            "drift": float(np.abs(X - X0)[specc].mean()) if specc.any() else 0.0,
            "coverage": float((~np.isnan(V) & P["land"]).sum() / max(P["land"].sum(), 1)),
            "observed_moved": float(np.nanmax(np.abs(V - P["obs"])[obs])) if obs.any() else 0.0,
        }

    def spread(self, par, fills=None):
        """First slice at which each region's mean passes 0.5, per farming
        layer; ok when the order of SPREAD holds."""
        out = {}
        region, years = self.prep["region"], self.prep["years"]
        for m in SPREAD_LAYERS:
            if m not in self.prep["layers"]:
                continue
            V = (fills or {}).get(m) or self.fill(m, par)
            P = self.prep["layers"][m]
            first = []
            for r in SPREAD:
                hit = [y for j, y in enumerate(years) if np.nanmean(V[0][j][(region == r) & P["now"][j]]) >= 0.5]
                first.append(hit[0] if hit else None)
            seq = [10**9 if f is None else f for f in first]
            out[m] = {"first": dict(zip(SPREAD, first)), "ok": all(a <= b for a, b in zip(seq, seq[1:]))}
        return out

    def box_stats(self, m, year, bbox, filled, kind="spatial"):
        """Steps inside a box: neighbour steps touching a speculative cell, or
        (temporal kinds) the change of speculative cells to the next slice."""
        years = self.prep["years"]
        j = years.index(int(year))
        V, basis = filled[0], filled[1]
        X = self.scaled(m, V)
        inb = (self.lon >= bbox[0]) & (self.lon <= bbox[2]) & (self.lat >= bbox[1]) & (self.lat <= bbox[3])
        if kind in TEMPORAL_KINDS:
            k = min(j + 1, len(years) - 1)
            d = np.abs(X[k] - X[j])
            sel = ~np.isnan(d) & ((basis[j] != "observed") | (basis[k] != "observed"))
            return d[sel & inb], d[sel]
        I, J = self.I, self.J
        d = np.abs(X[j, I] - X[j, J])
        sel = ~np.isnan(d) & ~((basis[j, I] == "observed") & (basis[j, J] == "observed"))
        return d[sel & inb[I] & inb[J]], d[sel]

    def hotspots(self, fills, top=40):
        """The largest steps that touch a speculative cell, clustered so one
        place is reported once per layer and slice; and the largest changes
        between slices by region."""
        years, region = self.prep["years"], self.prep["region"]
        I, J = self.I, self.J
        space, timeh = [], []
        for m, (V, basis, conf, ref) in fills.items():
            X = self.scaled(m, V)
            for j, y in enumerate(years):
                d = np.abs(X[j, I] - X[j, J])
                fi, fj = basis[j, I] == "observed", basis[j, J] == "observed"
                idx = np.flatnonzero(~np.isnan(d) & ~(fi & fj) & (d >= 0.25))
                idx = idx[np.argsort(-d[idx])]
                taken = []
                for p in idx:
                    lo, la = self.lon[I[p]], self.lat[I[p]]
                    if any(abs(lo - a) < 5 and abs(la - b) < 5 for a, b in taken):
                        continue
                    taken.append((lo, la))
                    near = idx[(np.abs(self.lon[I[idx]] - lo) < 5) & (np.abs(self.lat[I[idx]] - la) < 5)]
                    kind = "seam" if fi[p] ^ fj[p] else ("rule_edge" if ref[j, I[p]] != ref[j, J[p]] else "speculative_step")
                    space.append({"layer": m, "year": y, "kind": kind, "step": round(float(d[p]), 3), "pairs": int(len(near)),
                                  "bbox": [round(float(lo - 5), 1), round(float(la - 5), 1), round(float(lo + 5), 1), round(float(la + 5), 1)],
                                  "region": str(region[I[p]]), "judgements": sorted({str(ref[j, I[p]]), str(ref[j, J[p]])} - {""})})
                    if len(taken) == 5:
                        break
                if j + 1 < len(years):
                    dt = np.abs(X[j + 1] - X[j])
                    big = ~np.isnan(dt) & (dt >= 0.4) & ((basis[j] != "observed") | (basis[j + 1] != "observed"))
                    for r in np.unique(region[big]):
                        sel = big & (region == r)
                        timeh.append({"layer": m, "year": y, "to": years[j + 1], "region": str(r), "cells": int(sel.sum()),
                                      "mean_change": round(float(dt[sel].mean()), 3)})
        space.sort(key=lambda h: -h["step"] * np.log1p(h["pairs"]))
        timeh.sort(key=lambda h: -h["cells"] * h["mean_change"])
        return space[:top], timeh[:top]

    # ----------------------------------------------------------- evaluate
    def evaluate(self, par, full=False):
        fills = {m: self.fill(m, par) for m in self.prep["layers"]}
        layers = {m: self.layer_metrics(m, par, fills[m]) for m in fills}
        keys = next(iter(layers.values())).keys()
        overall = {k: float(np.mean([v[k] for v in layers.values()])) for k in keys}
        overall["observed_moved"] = max(v["observed_moved"] for v in layers.values())
        overall["coverage"] = min(v["coverage"] for v in layers.values())
        res = {"settings": par, "overall": overall, "spread": self.spread(par, fills), "regressions": self.regressions(fills)}
        if full:
            res["layers"] = layers
            res["hotspots"], res["time_hotspots"] = self.hotspots(fills)
        return res

    def regressions(self, fills):
        path = os.path.join(self.cfg["output"]["out_dir"], REGRESSIONS)
        doc = tomllib.load(open(path, "rb")) if os.path.exists(path) else {}
        cases = doc.get("case", [])
        self.allowed_failing = doc.get("allowed_failing", 0)
        out = []
        for c in cases:
            if c["layer"] not in fills:
                continue
            box, _ = self.box_stats(c["layer"], c["year"], c["bbox"], fills[c["layer"]], c.get("kind", "spatial"))
            v = float(np.percentile(box, 95)) if len(box) else 0.0
            out.append({"name": c.get("name", ""), "layer": c["layer"], "year": c["year"], "p95_step": round(v, 3), "max": c["max"],
                        "ok": v <= c["max"]})
        return out


def judge(res, base, allowed_failing=0):
    """Score against the unsmoothed baseline and apply the guards."""
    o, b = res["overall"], base["overall"]
    eps = 1e-4
    score = float(np.mean([(o[k] + eps) / (b[k] + eps) for k in SCORE_PARTS]))
    failing = sum(not r["ok"] for r in res["regressions"])
    guards = {
        "observed": o["observed_moved"] == 0.0,
        "coverage": o["coverage"] >= b["coverage"] - 1e-9,
        "holdout": o["holdout"] <= b["holdout"] * HOLDOUT_SLACK[0] + HOLDOUT_SLACK[1],
        "drift": o["drift"] <= DRIFT_MAX,
        "spread": all(v["ok"] for v in res["spread"].values()) or not all(v["ok"] for v in base["spread"].values()),
        "regressions": failing <= allowed_failing,
    }
    return score, guards


def _md(res, base, score, guards):
    o, b = res["overall"], base["overall"]
    lines = ["# Speculative fill: evals", "", f"Settings: `{json.dumps(res['settings'])}`", "",
             f"**Score {score:.3f}** (1.000 = the unsmoothed fill). Guards: "
             + ", ".join(f"{k} {'ok' if v else 'FAIL'}" for k, v in guards.items()) + ".", "",
             "| Metric | Now | Unsmoothed |", "|---|---|---|"]
    for k in ("rough_os", "rough_ss", "rough_oo", "cliffs", "rule_edge_cliffs", "conf_edges", "time_step", "flicker", "holdout", "drift", "coverage"):
        lines.append(f"| {k} | {o[k]:.4f} | {b[k]:.4f} |")
    lines += ["", "## Spread order", ""]
    for m, v in res["spread"].items():
        lines.append(f"- {m}: " + ", ".join(f"{r} {('never' if y is None else -y)}" for r, y in v["first"].items())
                     + (" (ok)" if v["ok"] else " (OUT OF ORDER)"))
    if res["regressions"]:
        lines += ["", "## Regression cases", ""] + [
            f"- {'ok' if r['ok'] else 'FAIL'}: {r['name']} ({r['layer']}, {-r['year']} BCE): {r['p95_step']} against {r['max']}"
            for r in res["regressions"]]
    lines += ["", "## Per layer", "", "| Layer | rough_os | rough_ss | cliffs | flicker | time_step | holdout | drift |", "|---|---|---|---|---|---|---|---|"]
    for m, v in res["layers"].items():
        lines.append(f"| {m} | {v['rough_os']:.3f} | {v['rough_ss']:.3f} | {v['cliffs']:.1f} | {v['flicker']:.1f} | {v['time_step']:.3f} | {v['holdout']:.3f} | {v['drift']:.3f} |")
    lines += ["", "## Largest steps in space", "", "| Layer | Year | Kind | Step | Pairs | Region | Box (lon0, lat0, lon1, lat1) |", "|---|---|---|---|---|---|---|"]
    for h in res["hotspots"]:
        lines.append(f"| {h['layer']} | {-h['year']} BCE | {h['kind']} | {h['step']} | {h['pairs']} | {h['region']} | {h['bbox']} |")
    lines += ["", "## Largest changes between slices", "", "| Layer | From | To | Region | Cells | Mean change |", "|---|---|---|---|---|---|"]
    for h in res["time_hotspots"]:
        lines.append(f"| {h['layer']} | {-h['year']} BCE | {-h['to']} BCE | {h['region']} | {h['cells']} | {h['mean_change']} |")
    return "\n".join(lines) + "\n"


def run(cfg, log=print, layers=None):
    out = os.path.join(cfg["output"]["out_dir"], "evals")
    os.makedirs(out, exist_ok=True)
    bench = Bench(cfg, log, layers)
    base = bench.evaluate(dict(spec.DEFAULTS))
    res = bench.evaluate(spec.params(cfg), full=True)
    score, guards = judge(res, base, bench.allowed_failing)
    res.update(score=score, guards=guards, baseline=base["overall"])
    json.dump(res, open(os.path.join(out, "report.json"), "w"), indent=1)
    open(os.path.join(out, "report.md"), "w").write(_md(res, base, score, guards))
    log(f"evals: score {score:.3f}; guards " + ", ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in guards.items()))
    log(f"evals: wrote {out}/report.md")
    return all(guards.values())


def search(cfg, log=print, layers=None):
    out = os.path.join(cfg["output"]["out_dir"], "evals")
    os.makedirs(out, exist_ok=True)
    bench = Bench(cfg, log, layers)
    base = bench.evaluate(dict(spec.DEFAULTS))
    rows = []
    for combo in itertools.product(*GRID.values()):
        par = {**spec.params(cfg), **dict(zip(GRID, combo))}
        res = bench.evaluate(par)
        score, guards = judge(res, base, bench.allowed_failing)
        failing = sum(not r["ok"] for r in res["regressions"])
        rows.append({"settings": par, "score": score, "failing": failing, "guards": guards, "passes": all(guards.values()),
                     "overall": res["overall"]})
        log(f"evals: {dict(zip(GRID, combo))}: failing cases {failing}, score {score:.3f}, holdout {res['overall']['holdout']:.4f}, drift {res['overall']['drift']:.4f}"
            + ("" if rows[-1]["passes"] else " REJECTED: " + ", ".join(k for k, v in guards.items() if not v)))
    ok = [r for r in rows if r["passes"]]
    # Fewest failing regression cases first, then the smoothest.
    best = min(ok, key=lambda r: (r["failing"], r["score"])) if ok else None
    json.dump({"baseline": base["overall"], "best": best, "tried": rows}, open(os.path.join(out, "search.json"), "w"), indent=1)
    log(f"evals: best passing settings {best['settings'] if best else None} (score {best['score']:.3f})" if best else "evals: nothing passed")
    return best


def check(cfg, claims_path, log=print):
    """Test a critic's claims. A claim is confirmed when the 95th-percentile
    step inside its box is at least 0.1 and above the layer's own 95th
    percentile for steps of that sort in that slice."""
    claims = json.load(open(claims_path))
    claims = claims.get("claims", claims) if isinstance(claims, dict) else claims
    bench = Bench(cfg, log, sorted({c["layer"] for c in claims}))
    par = spec.params(cfg)
    fills = {m: bench.fill(m, par) for m in bench.prep["layers"]}
    out = []
    for c in claims:
        if c["layer"] not in fills or int(c["year"]) not in bench.prep["years"]:
            out.append({**c, "confirmed": False, "why": "unknown layer or year"})
            continue
        kind = c.get("kind", "")
        if kind == "coastline_hole":
            j = bench.prep["years"].index(int(c["year"]))
            P = bench.prep["layers"][c["layer"]]
            b = c["bbox"]
            inb = (bench.lon >= b[0]) & (bench.lon <= b[2]) & (bench.lat >= b[1]) & (bench.lat <= b[3])
            holes = int((P["land"][j] & np.isnan(fills[c["layer"]][0][j]) & inb).sum())
            out.append({**c, "confirmed": holes > 0, "land_cells_without_value": holes})
            continue
        box, everywhere = bench.box_stats(c["layer"], c["year"], c["bbox"], fills[c["layer"]], kind)
        v = float(np.percentile(box, 95)) if len(box) else 0.0
        ref = float(np.percentile(everywhere, 95)) if len(everywhere) else 0.0
        out.append({**c, "confirmed": bool(len(box) and v >= 0.1 and v > ref), "p95_step_in_box": round(v, 3),
                    "p95_step_layer": round(ref, 3), "steps_in_box": int(len(box))})
    dest = os.path.splitext(claims_path)[0] + ".checked.json"
    json.dump(out, open(dest, "w"), indent=1)
    log(f"evals: {sum(c['confirmed'] for c in out)} of {len(out)} claims confirmed -> {dest}")
    return out


def crop(cfg, layer, year, bbox, dest, log=print):
    """One layer, slice and place, as the game colours it: plasma by value,
    greyer where less certain, observed cells outlined."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    bench_prep = spec.prepare(cfg, log, [layer])
    P = bench_prep["layers"][layer]
    V, basis, conf, ref = spec.fill_layer(P, bench_prep["NB"], spec.params(cfg))
    years, grid = bench_prep["years"], bench_prep["grid"]
    j = years.index(int(year))
    lon, lat = grid["lon"].values, grid["lat"].values
    inb = np.flatnonzero((lon >= bbox[0] - 1) & (lon <= bbox[2] + 1) & (lat >= bbox[1] - 1) & (lat <= bbox[3] + 1) & P["now"][j])
    lo, hi = P["range"]
    x = np.clip((V[j][inb] - lo) / (hi - lo), 0, 1)
    strength = np.array([{"observed": 1.0, "high": 0.7, "medium": 0.48, "low": 0.3}.get(c, 0.15) for c in conf[j][inb]])[:, None]
    grey = np.array([0.604, 0.596, 0.576])
    rgb = plt.get_cmap("plasma")(np.nan_to_num(x))[:, :3] * strength + grey * (1 - strength)
    rgb[np.isnan(x)] = (0.2, 0.2, 0.2)
    verts = [np.asarray(grid.geometry.iloc[i].exterior.coords) for i in inb]
    fig, ax = plt.subplots(figsize=(9, 9 * (bbox[3] - bbox[1]) * 1.41 / max(bbox[2] - bbox[0], 1e-6)))
    ax.set_facecolor("#5f7f9c")
    edge = np.where((basis[j][inb] == "observed")[:, None], np.array([[0, 0, 0, 0.55]]), np.array([[0, 0, 0, 0.0]]))
    ax.add_collection(PolyCollection(verts, facecolors=rgb, edgecolors=edge, linewidths=0.4))
    ax.set_xlim(bbox[0], bbox[2])
    ax.set_ylim(bbox[1], bbox[3])
    ax.set_aspect(1.41)
    ax.set_title(f"{layer}, {-int(year):,} BCE. Outlined cells are observed; greyer cells are less certain speculation.", fontsize=9, loc="left")
    fig.savefig(dest, dpi=110, bbox_inches="tight")
    plt.close(fig)
    log(f"evals: wrote {dest}")
