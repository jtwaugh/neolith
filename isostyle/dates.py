"""Radiocarbon dates -> sites, provisional site-phases and slice weights.

Reads the raw downloads cached by `make settlements`. Unlike that step,
nothing is dropped by site type (graves and hoards carry ornaments and
bone tools), and each date keeps its whole calibrated distribution. Single
dates rejected in data/settlements/records.toml (`[[reject]]`: filed under
the wrong site or older than anything on it) are dropped here too.
"""
import csv
import glob
import json
import os
import re
from collections import defaultdict

import numpy as np
import pandas as pd

from pipeline.settlements import _clean, fix_mojibake, lab_key, load_curve, load_rejects, merge_spellings

# Compilations named in XRONOS reference lists, for the per-source coverage
# table. Order matters: the first pattern that matches a reference wins.
COMPILATIONS = [
    ("EUROEVOL", r"euroevol|manningtimpson"), ("RADON-B", r"radon-b"), ("RADON", r"radon|kiel db"),
    ("14SEA", r"14sea"), ("CalPal", r"calpal"), ("p3k14c", r"p3k14c"), ("NERD", r"\bnerd\b|palmisano"),
    ("IRDD", r"irdd"), ("PACEA/Vermeersch", r"pacea|vermeersch"), ("AIDA", r"\baida\b"), ("BDA", r"\bbda\b"),
    ("EUBAR", r"eubar"), ("AgriChange", r"agrichange"), ("Katsianis (Aegean)", r"katsianis"),
    ("MedAfriCarbon", r"medafricarbon"), ("CONTEXT", r"^context$"), ("Bevan 2017 (Britain/Ireland)", r"bevan ?2017"),
    ("Balsera (Iberia)", r"balsera"), ("Solheim (Norway)", r"solheim"), ("Larsson 2019", r"larsson 2019"),
    ("Banadora", r"banadora"), ("CBA index", r"cba radiocarbon"),
]
_COMP = [(n, re.compile(p)) for n, p in COMPILATIONS]


def compilations(refs):
    out = []
    for r in refs:
        low = r.lower()
        for name, pat in _COMP:
            if pat.search(low):
                out.append(name)
                break
    return sorted(set(out))


def _labels(m):
    vals = {p.get("periode") for p in m.get("periods") or []}
    vals |= {p.get("typochronological_unit") for p in m.get("typochronological_units") or []}
    return sorted(v.strip() for v in vals if v and v.strip())


def read_xronos(raw_dir):
    """Every XRONOS measurement in the cached dumps, once. Also returns the
    number of records that had no usable coordinates, age or site name."""
    rows, seen, bad = [], set(), 0
    for path in sorted(glob.glob(os.path.join(raw_dir, "xronos_*.json"))):
        for row in json.load(open(path)) or []:
            m = row["measurement"]
            if m["id"] in seen:
                continue
            seen.add(m["id"])
            try:
                lat, lon, bp, std = float(m["lat"]), float(m["lng"]), float(m["bp"]), float(m["std"])
            except (TypeError, ValueError):
                bad += 1
                continue
            name = fix_mojibake(_clean(m.get("site")))
            if not name or std <= 0:
                bad += 1
                continue
            refs = sorted({r for x in m.get("reference") or [] if (r := _clean(x.get("reference")))})
            rows.append({"site": name, "lon": lon, "lat": lat, "bp": bp, "std": std,
                         "labnr": _clean(m.get("labnr")), "site_type": _clean(m.get("site_type")).lower(),
                         "labels": _labels(m), "material": _clean(m.get("material")).lower(),
                         "stated_country": _clean(m.get("country")), "dataset": "xronos",
                         "compilations": compilations(refs)})
    return rows, bad


def read_table(path, spec, seen_labs):
    """A CSV/TSV date table; skips lab numbers already in seen_labs."""
    col = spec["columns"]
    csv.field_size_limit(1 << 30)
    out = []
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        for r in csv.DictReader(f, delimiter=spec.get("delimiter", ",")):
            lab = lab_key(r.get(col["labnr"]))
            if not lab or lab in seen_labs:
                continue
            try:
                lon, lat = float(r[col["lon"]]), float(r[col["lat"]])
                bp, std = float(r[col["bp"]]), float(r[col["std"]])
            except (TypeError, ValueError):
                continue
            name = _clean(r.get(col["site"]))
            if not name or std <= 0:
                continue
            seen_labs.add(lab)
            labels = sorted({v for c in (col.get("period"), "PhaseCode") if c and (v := _clean(r.get(c)))
                             and v.lower() not in ("n/a", "n/d", "na")})
            out.append({"site": name, "lon": lon, "lat": lat, "bp": bp, "std": std,
                        "labnr": _clean(r[col["labnr"]]), "site_type": "", "labels": labels,
                        "material": _clean(r.get("Material")).lower(),
                        "stated_country": _clean(r.get("Country")), "dataset": spec["name"],
                        "compilations": [{"p3k14c": "p3k14c", "neonet": "NeoNet", "neonetatl": "NeoNet"}.get(spec["name"], spec["name"])]})
    return out


def records_path(dc):
    """The records.toml that `make settlements` uses, from pipeline/config.toml."""
    import tomllib
    path = dc.get("pipeline_config")
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return tomllib.load(f).get("settlements", {}).get("records")


def load(cfg, tables, region):
    """All date rows inside the region box, as a DataFrame with site ids.

    Returns (dates, counts); counts records what was read and set aside.
    """
    dc = cfg["dates"]
    rows, bad = read_xronos(dc["raw_dir"])
    counts = {"xronos_records": len(rows) + bad, "xronos_unusable": bad}
    seen = {k for r in rows if (k := lab_key(r["labnr"]))}
    for spec in tables:
        # Downloaded tables have a `file` in the raw dir; tables kept in the
        # repository (aadr, literature) have a `path`, read in place.
        path = spec["path"] if "path" in spec else os.path.join(dc["raw_dir"], spec["file"])
        if not os.path.exists(path):
            counts[f"{spec['name']}_missing"] = 1
            continue
        extra = read_table(path, spec, seen)
        counts[f"{spec['name']}_added"] = len(extra)
        rows += extra
    rejects = load_rejects(records_path(dc))
    before = len(rows)
    rows = [r for r in rows if (r["site"], lab_key(r["labnr"])) not in rejects]
    counts["rejected"] = before - len(rows)
    rows = [r for r in rows if region["lon_min"] <= r["lon"] <= region["lon_max"]
            and region["lat_min"] <= r["lat"] <= region["lat_max"]]
    counts["in_region"] = len(rows)

    # Sites: one per name and point, with spellings folded together.
    groups = defaultdict(list)
    for i, r in enumerate(rows):
        groups[(r["site"], round(r["lon"], 4), round(r["lat"], 4))].append(i)
    keep, site_rows = [], []
    for sid, (name, lon, lat, idx, _aliases) in enumerate(
            merge_spellings(groups, dc["same_km"], dc["same_name_km"], dc.get("share_km", 0.0),
                            lambda i: (lab_key(rows[i]["labnr"]), (rows[i]["bp"], rows[i]["std"]))), start=1):
        # One row per measurement: compiled sources repeat a date per database.
        by_lab, by_age, kept = {}, {}, []
        for i in idx:
            r = rows[i]
            lab, age = lab_key(r["labnr"]), (r["bp"], r["std"])
            k = by_lab.get(lab) if lab else None
            if k is None:
                k = by_age.get(age)
            if k is None:
                k = len(kept)
                kept.append(dict(r, site_id=sid, site=name, lon=lon, lat=lat))
            else:
                kept[k]["labels"] = sorted({*kept[k]["labels"], *r["labels"]})
                kept[k]["compilations"] = sorted({*kept[k]["compilations"], *r["compilations"]})
                kept[k]["site_type"] = kept[k]["site_type"] or r["site_type"]
                kept[k]["material"] = kept[k]["material"] or r["material"]
            if lab:
                by_lab.setdefault(lab, k)
            by_age.setdefault(age, k)
        keep += kept
        site_rows.append(sid)
    counts["sites_in_region"] = len(site_rows)
    counts["dates_in_region_deduplicated"] = len(keep)
    return pd.DataFrame(keep), counts


def calibrate(bp, std, curve_path, years, half, cal_range=(2500, 14500), chunk=2048, edges=None):
    """Share of each date's calibrated distribution inside each slice.

    Returns (mass, median, lo, hi): mass is (n_dates, n_slices); median and
    the 95% range lo..hi are signed years. Dates whose distribution lies
    outside cal_range (cal BP) get zero mass and NaN years. `half` is one
    half-width, or `edges` gives (start, end) per slice.
    """
    cal, mu, sig = load_curve(curve_path)
    sel = (cal >= cal_range[0]) & (cal <= cal_range[1])
    cal, mu, sig = cal[sel], mu[sel], sig[sel]
    year = 1950 - cal
    which = np.full(len(cal), -1)
    for j, t in enumerate(years):
        a, b = (t - half, t + half) if edges is None else edges[j]
        which[(year >= a) & (year < b)] = j
    onehot = np.zeros((len(cal), len(years)), dtype=np.float64)
    onehot[which >= 0, which[which >= 0]] = 1.0

    bp, std = np.asarray(bp, float), np.asarray(std, float)
    mass = np.zeros((len(bp), len(years)), dtype=np.float32)
    median = np.full(len(bp), np.nan)
    lo, hi = median.copy(), median.copy()
    # Only dates whose 4-sigma span stays on the cut-down curve are calibrated;
    # the rest are far outside every slice.
    ok = (bp - 4 * std > mu.min() + 300) & (bp + 4 * std < mu.max() - 300)
    idx = np.flatnonzero(ok)
    for s in range(0, len(idx), chunk):
        ii = idx[s:s + chunk]
        b, e = bp[ii, None], std[ii, None]
        var = e ** 2 + sig[None, :] ** 2
        p = np.exp(-(b - mu[None, :]) ** 2 / (2 * var)) / np.sqrt(var)
        tot = p.sum(axis=1, keepdims=True)
        good = tot[:, 0] > 0
        p = np.divide(p, tot, out=np.zeros_like(p), where=tot > 0)
        mass[ii] = p @ onehot
        cdf = np.cumsum(p, axis=1)          # the grid runs young to old
        median[ii] = np.where(good, year[(cdf >= 0.5).argmax(axis=1)], np.nan)
        hi[ii] = np.where(good, year[(cdf >= 0.025).argmax(axis=1)], np.nan)
        lo[ii] = np.where(good, year[(cdf >= 0.975).argmax(axis=1)], np.nan)
    return mass, median, lo, hi


def slice_mass(bp, std, curve_path, years, half, **kw):
    return calibrate(bp, std, curve_path, years, half, **kw)[:2]


def episodes(dates, gap):
    """Occupation episodes: within a site, dates are chained while their 95%
    calibrated ranges (columns cal_lo, cal_hi) overlap or lie within `gap`
    years of each other. Returns the episode id per row (0 = not calibrated)."""
    out = np.zeros(len(dates), dtype=int)
    ok = dates["cal_lo"].notna().values
    d = dates[ok].sort_values(["site_id", "cal_lo"])
    site, lo, hi = d["site_id"].values, d["cal_lo"].values, d["cal_hi"].values
    ids = np.zeros(len(d), dtype=int)
    eid, reach = 0, -np.inf
    for k in range(len(d)):
        if k == 0 or site[k] != site[k - 1] or lo[k] > reach + gap:
            eid += 1
            reach = hi[k]
        else:
            reach = max(reach, hi[k])
        ids[k] = eid
    out[dates.index.get_indexer(d.index)] = ids
    return out


def phases(dates):
    """Provisional site-phases: the dates of one site that carry the same set
    of period/culture labels. Dates without labels form one phase per site.
    Returns the phase id per date row."""
    key = dates["site_id"].astype(str) + "\x1f" + dates["labels"].map("|".join)
    return pd.factorize(key)[0] + 1
