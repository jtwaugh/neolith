"""Exotic places, for the exotic critic (.claude/agents/exotic-critic.md).

`data/places/places.toml` lists straits, river mouths, islands, oases, passes
and drowned plains: places where someone looking at the map expects to find
something. This module measures how empty each one is in our data.

- `run`: one dossier per place under [places] out (`<key>/dossier.md`,
  `dossier.json`, `sheet.png`) and a ranked `index.md` / `index.json`. A
  dossier holds, per epoch, the land and sea in the box, the sites in it and
  near it, the distance to the nearest site, and what the missing-sites
  residuals say; then the sites themselves, likely duplicates, doubtful
  coordinates, survey intensity, what the speculative isostyle layers hold,
  and the rivers, lakes and coasts on record there.
- `check`: validates the plans the critic writes in `data/places/plans/`.

Everything here reads built products and changes none of them. The ranking
is emptiness, i.e. where to look first. It is not a verdict and nothing
downstream reads it: expected densities never see site counts.
"""
import csv
import difflib
import glob
import gzip
import json
import os
import re
import tomllib
from collections import Counter, defaultdict

import numpy as np

from . import grid as gridmod
from . import look
from .residuals import hex_area_km2

KINDS = ("strait", "river_mouth", "delta", "confluence", "island", "oasis", "lake_shore", "pass", "isthmus",
         "drowned_plain", "headland", "ad_hoc")
VERDICTS = ("research", "speculate", "leave")
CONFIDENCE = ("low", "medium", "high")
RESEARCH_STATUS = ("open", "done", "dropped")
DEFAULTS = {
    "out": "build/critic/places", "catalogue": "data/places/places.toml", "plans": "data/places/plans",
    "sources": "data/places/SOURCES.md", "near_km": 100.0, "far_km": 300.0, "pad_degrees": 2.0,
    "sheet_years": [-10000, -8000, -6000, -5000, -4000, -3000],
    "survey": "data/settlements/survey.csv.gz", "speculative": "data/isostyle/speculative/speculative.csv.gz",
    "layers": "data/isostyle/layers.toml", "top": 25,
}
NOT_LAND = ("Water", "Ice", "")
# Causes of emptiness beyond isostyle's list, which is about layers, not places.
EXTRA_CAUSES = {"buried": "under later sediment (delta or floodplain silt, dunes, colluvium)"}


def settings(cfg):
    return {**DEFAULTS, **cfg.get("places", {})}


# ---------------------------------------------------------------- catalogue
def load_catalogue(path):
    with open(path, "rb") as f:
        return tomllib.load(f)["place"]


def catalogue_problems(places, bounds=None):
    """Problems in the catalogue (empty if fine). bounds: lon0, lat0, lon1,
    lat1 of the map; every box must lie inside it."""
    errs, seen = [], set()
    for p in places:
        k = p.get("key", "?")
        for field in ("key", "name", "kind", "box", "why"):
            if not p.get(field):
                errs.append(f"{k}: no {field}")
        if not re.fullmatch(r"[a-z0-9_]+", str(k)):
            errs.append(f"{k}: key must be lower-case letters, digits and underscores")
        if k in seen:
            errs.append(f"{k}: key used twice")
        seen.add(k)
        if p.get("kind") not in KINDS:
            errs.append(f"{k}: kind {p.get('kind')!r} not one of {', '.join(KINDS)}")
        b = p.get("box") or []
        if len(b) != 4 or not (b[0] < b[2] and b[1] < b[3]):
            errs.append(f"{k}: box must be [lon0, lat0, lon1, lat1] with lon0 < lon1 and lat0 < lat1")
        elif bounds and not (bounds[0] <= b[0] and b[2] <= bounds[2] and bounds[1] <= b[1] and b[3] <= bounds[3]):
            errs.append(f"{k}: box {b} reaches outside the map {[round(float(v), 2) for v in bounds]}")
    return errs


# ----------------------------------------------------------------- geometry
def km(lon0, lat0, lon1, lat1):
    """Great-circle distance in km; any argument may be an array."""
    a0, a1 = np.radians(lat0), np.radians(lat1)
    d = np.sin((a1 - a0) / 2) ** 2 + np.cos(a0) * np.cos(a1) * np.sin(np.radians(lon1 - lon0) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(d, 0, 1)))


def km_to_box(lon, lat, box):
    """Distance in km from points to a box (0 inside it)."""
    return km(lon, lat, np.clip(lon, box[0], box[2]), np.clip(lat, box[1], box[3]))


def active(sites, years, half):
    """(sites, years) bool: the site has an occupation phase overlapping
    year +- half, as in residuals.observed."""
    out = np.zeros((len(sites), len(years)), dtype=bool)
    for i, f in enumerate(sites):
        for a, b in f["properties"].get("occupation") or []:
            for t, y in enumerate(years):
                if a < y + half and b > y - half:
                    out[i, t] = True
    return out


def duplicates(rows, same_km=3.0, alike=0.8):
    """Pairs of sites that look like one place entered twice: within
    `same_km` of each other, or in the same hex with similar names."""
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.casefold())
    out = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            d = float(km(a["lon"], a["lat"], b["lon"], b["lat"]))
            r = difflib.SequenceMatcher(None, norm(a["name"]), norm(b["name"])).ratio()
            if d <= same_km or (a["hex"] == b["hex"] and r >= alike):
                out.append({"a": a["name"], "b": b["name"], "km": round(d, 1), "name_likeness": round(r, 2)})
    return out


# ------------------------------------------------------------------ context
def _read_gz(path):
    if not path or not os.path.exists(path):
        return []
    with gzip.open(path, "rt", newline="") as f:
        return list(csv.DictReader(f))


def context(cfg, s, want_hexes=None):
    """Everything the dossiers read, loaded once."""
    rc = cfg["residuals"]
    years = list(rc["years"])
    g, feats = look.load_map(cfg)
    spath = cfg.get("settled_land", {}).get("out")
    if not spath or not os.path.exists(spath):
        spath = "data/settlements/settlements.geojson"
    sites = [f for f in gridmod.load_geojson(spath)["features"] if f.get("geometry")]
    c = {
        "years": years, "half": rc["half_window"], "grid": g, "feats": feats,
        "terrain": look.series(feats, "terrain", years), "area": hex_area_km2(g.bbox),
        "sites": sites, "sites_path": spath,
        "site_xy": np.array([f["geometry"]["coordinates"][:2] for f in sites], dtype=float).reshape(-1, 2),
        "site_on": active(sites, years, rc["half_window"]),
        "residuals": defaultdict(dict), "survey": {}, "spec": defaultdict(list),
        "rivers": [], "lakes": [], "coasts": [], "audit": [],
    }
    for r in _read_gz(rc["out"]):
        c["residuals"][int(r["hex"])][int(r["year"])] = r
    for r in _read_gz(s["survey"]):
        c["survey"][int(r["hex"])] = (float(r["records_per_10k_km2"]), int(r["level"]))
    if want_hexes is not None and os.path.exists(s["speculative"]):
        with gzip.open(s["speculative"], "rt", newline="") as f:
            for r in csv.DictReader(f):
                if int(r["cell"]) in want_hexes:
                    c["spec"][int(r["cell"])].append(r)
    rpath = cfg.get("rivers", {}).get("geojson")
    if rpath and os.path.exists(rpath):
        c["rivers"] = gridmod.load_geojson(rpath)["features"]
    for key, name, path in (("lakes", "lake", "data/lakes/lakes.toml"), ("coasts", "coast", "data/coasts/coasts.toml")):
        path = cfg.get(key, {}).get("catalogue", path)
        if os.path.exists(path):
            with open(path, "rb") as f:
                c[key] = tomllib.load(f).get(name, [])
    apath = cfg.get("settled_land", {}).get("audit")
    if apath and os.path.exists(apath):
        with open(apath, newline="") as f:
            c["audit"] = list(csv.DictReader(f))
    return c


def hexes_in(g, box):
    """Indices of hexes whose own box touches `box`."""
    return np.flatnonzero((g.bbox[:, 2] >= box[0]) & (g.bbox[:, 0] <= box[2])
                          & (g.bbox[:, 1] >= box[1]) & (g.bbox[:, 3] <= box[3]))


# ------------------------------------------------------------------ dossier
def _site_row(f, d_km):
    p = f["properties"]
    lon, lat = f["geometry"]["coordinates"][:2]
    return {"name": p.get("name", ""), "lon": round(lon, 4), "lat": round(lat, 4), "hex": p.get("hex"),
            "founding": p.get("founding"), "abandoned": p.get("abandoned"), "type": p.get("type", ""),
            "n_dates": p.get("n_dates", 0), "sources": p.get("sources", []), "culture": p.get("culture", ""),
            "recorded": p.get("evidence", 1), "km_from_box": round(float(d_km), 1)}


def dossier(place, c, s):
    """Measurements of one place, as a dict."""
    box, g, years = place["box"], c["grid"], c["years"]
    sel = hexes_in(g, box)
    ids = [int(g.ids[i]) for i in sel]
    ter = c["terrain"][sel] if len(sel) else np.empty((0, len(years)), dtype=object)
    land = ~np.isin(ter, NOT_LAND)
    last = land[:, -1] if len(sel) else np.zeros(0, dtype=bool)
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2

    xy = c["site_xy"]
    d_box = km_to_box(xy[:, 0], xy[:, 1], box) if len(xy) else np.zeros(0)
    d_mid = km(xy[:, 0], xy[:, 1], cx, cy) if len(xy) else np.zeros(0)
    inside, near = d_box == 0, (d_box > 0) & (d_box <= s["near_km"])

    epochs = []
    for t, y in enumerate(years):
        on = c["site_on"][:, t] if len(xy) else np.zeros(0, dtype=bool)
        res = [c["residuals"].get(h, {}).get(y) for h in ids]
        res = [r for r in res if r]
        epochs.append({
            "year": y,
            "land_hexes": int(land[:, t].sum()), "water_hexes": int((ter[:, t] == "Water").sum()),
            "drowned_later": int((land[:, t] & ~last).sum()),
            "terrain": dict(Counter(v for v in ter[:, t].tolist() if v).most_common(4)),
            "sites_in_box": int((inside & on).sum()), "sites_near": int((near & on).sum()),
            "nearest_site_km": round(float(d_mid[on].min()), 0) if on.any() else None,
            "sites_expected": round(sum(float(r["sites_expected"]) for r in res), 2) if res else None,
            "missing": round(sum(float(r["missing"]) for r in res), 2) if res else None,
            "outcomes": dict(Counter(r["outcome"] for r in res).most_common()),
            "expected_per_km2": round(float(np.mean([float(r["expected_per_km2"]) for r in res])), 4) if res else None,
        })

    in_rows = sorted((_site_row(c["sites"][i], 0) for i in np.flatnonzero(inside)), key=lambda r: r["founding"] or 0)
    near_rows = sorted((_site_row(c["sites"][i], d_box[i]) for i in np.flatnonzero(near)),
                       key=lambda r: r["km_from_box"])
    window = lambda r: (r["abandoned"] or 0) > years[0] - c["half"] and (r["founding"] or 0) < years[-1] + c["half"]

    surv = [c["survey"][h] for h in ids if h in c["survey"]]
    spec = defaultdict(lambda: {"basis": Counter(), "values": defaultdict(list)})
    for h in ids:
        for r in c["spec"].get(h, []):
            if r["land"] == "1" and r["value"] not in ("", "nan"):
                e = spec[r["layer"]]
                e["basis"][r["basis"]] += 1
                e["values"][int(r["slice"])].append(float(r["value"]))
    layers = {k: {"basis": dict(v["basis"].most_common()),
                  "mean_by_slice": {y: round(float(np.mean(a)), 3) for y, a in sorted(v["values"].items())}}
              for k, v in spec.items()}

    rivers = {}
    for f in c["rivers"]:
        pts = np.asarray(f["geometry"]["coordinates"], dtype=float).reshape(-1, 2)
        if ((pts[:, 0] >= box[0]) & (pts[:, 0] <= box[2]) & (pts[:, 1] >= box[1]) & (pts[:, 1] <= box[3])).any():
            st = f["properties"].get("state") or {}
            rivers.setdefault(f["properties"].get("name", "?"), {}).update(st if isinstance(st, dict) else {})
    hit = lambda b: b and b[0] <= box[2] and b[2] >= box[0] and b[1] <= box[3] and b[3] >= box[1]
    lakes = [x["name"] for x in c["lakes"] if hit(x.get("box"))]
    coasts = []
    for x in c["coasts"]:
        pts = [p for st in x.get("stage", []) for p in st.get("polygon", [])]
        if pts and hit([min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]):
            coasts.append(x["name"])
    pad = 0.5
    audit = [r for r in c["audit"] if box[0] - pad <= float(r["lon"]) <= box[2] + pad
             and box[1] - pad <= float(r["lat"]) <= box[3] + pad]

    empty_share = float(np.mean([e["sites_in_box"] == 0 for e in epochs]))
    dists = [e["nearest_site_km"] if e["nearest_site_km"] is not None else s["far_km"] for e in epochs]
    far = float(np.median(np.minimum(dists, s["far_km"])) / s["far_km"])
    return {
        "key": place["key"], "name": place["name"], "kind": place["kind"], "box": box, "why": place.get("why", ""),
        "hexes": ids, "area_km2": round(float(c["area"][sel].sum())) if len(sel) else 0,
        "ever_land": bool(land.any()),
        "emptiness": round(empty_share + far, 2), "epochs_without_sites": int(round(empty_share * len(epochs))),
        "sites_in_box_all_time": len(in_rows), "sites_in_box_in_period": sum(window(r) for r in in_rows),
        "epochs": epochs, "sites_in_box": in_rows, "sites_near": near_rows,
        "duplicates": duplicates(in_rows), "coordinate_audit": audit,
        "survey": {"records_per_10k_km2": round(float(np.mean([a for a, _ in surv])), 2),
                   "level": round(float(np.mean([b for _, b in surv])), 2)} if surv else None,
        "speculative_layers": layers, "rivers": rivers, "lakes": lakes, "coasts": coasts,
        "missing_peak": max((e["missing"] or 0 for e in epochs), default=0),
    }


def _bce(y):
    return "—" if y is None else (f"{-y:,} BCE" if y < 0 else f"{y} CE")


def dossier_md(d, s, sheet=None):
    T = look._table
    L = [f"# {d['name']} ({d['kind'].replace('_', ' ')})", "", d["why"], "",
         f"Box {' '.join(f'{v:g}' for v in d['box'])}: {len(d['hexes'])} hexes, about {d['area_km2']:,} km². "
         f"Emptiness {d['emptiness']} of 2 (share of epochs with no site in the box, plus how far the nearest "
         f"site is, capped at {s['far_km']:g} km). It says where to look, not what is true.", ""]
    if sheet:
        L += [f"Map: `{sheet}` (terrain, rivers; black dots are sites occupied in that epoch, grey rings other "
              "sites, the red frame is the box).", ""]
    if not d["hexes"]:
        L += ["**No hexes in this box.**", ""]
    elif not d["ever_land"]:
        L += ["**No hex in this box is land in any epoch**: on this board the place is open water. Check the "
              "box, then the coast and island rules.", ""]
    L += ["## By epoch", "",
          "Sites count if a dated occupation phase overlaps the epoch ± "
          "half a millennium. `expected` and `missing` are the missing-sites residuals summed over the box's "
          "hexes: sites the site list's own pattern predicts, and how many more there would be if nothing hid "
          "them. They are not population.", ""]
    L += T(["Epoch", "Land / water hexes", "Drowned later", "Terrain", "Sites in box", f"Within {s['near_km']:g} km",
            "Nearest site (km from centre)", "Expected", "Missing", "Reading"],
           [[_bce(e["year"]), f"{e['land_hexes']} / {e['water_hexes']}", e["drowned_later"],
             ", ".join(f"{k} {v}" for k, v in e["terrain"].items()), e["sites_in_box"], e["sites_near"],
             "none" if e["nearest_site_km"] is None else f"{e['nearest_site_km']:g}",
             "—" if e["sites_expected"] is None else e["sites_expected"],
             "—" if e["missing"] is None else e["missing"],
             "; ".join(f"{k} ×{v}" for k, v in e["outcomes"].items()) or "—"] for e in d["epochs"]])
    L += [f"## Sites in the box ({len(d['sites_in_box'])}, {d['sites_in_box_in_period']} with dates in the period)", ""]
    site_rows = lambda rows: [[r["name"], f"{r['lon']:g}, {r['lat']:g}", r["hex"], _bce(r["founding"]),
                               _bce(r["abandoned"]), r["type"], r["n_dates"], r["culture"] or "",
                               ", ".join(r["sources"]), "" if r["recorded"] else "inferred"] for r in rows]
    head = ["Site", "Lon, lat", "Hex", "From", "To", "Type", "Dates", "Culture", "Sources", ""]
    L += T(head, site_rows(d["sites_in_box"])) if d["sites_in_box"] else ["None.", ""]
    L += [f"## Sites within {s['near_km']:g} km of the box ({len(d['sites_near'])}; nearest 20 shown)", ""]
    L += T(head[:-1] + ["Km from box"], [r[:-1] + [n["km_from_box"]] for r, n in
                                         zip(site_rows(d["sites_near"][:20]), d["sites_near"][:20])]) \
        if d["sites_near"] else ["None.", ""]
    if d["duplicates"]:
        L += ["## Possibly the same site twice", ""]
        L += T(["A", "B", "Km apart", "Name likeness"], [[x["a"], x["b"], x["km"], x["name_likeness"]]
                                                         for x in d["duplicates"]])
    if d["coordinate_audit"]:
        L += ["## Doubtful coordinates nearby (`data/settlements/coordinate_audit.csv`)", ""]
        L += T(["Site", "Lon, lat", "Reasons", "Hint"], [[r["name"], f"{r['lon']}, {r['lat']}", r["reasons"], r["hint"]]
                                                         for r in d["coordinate_audit"]])
    L += ["## Around it", ""]
    if d["survey"]:
        L.append(f"- Survey intensity: {d['survey']['records_per_10k_km2']} dated records per 10,000 km², "
                 f"mean level {d['survey']['level']} (0 unsurveyed, 1 thin, 2 well surveyed).")
    L.append("- Rivers on record: " + ("; ".join(
        f"{n} ({', '.join(f'{st} from {_bce(int(y))}' for y, st in sorted(v.items(), key=lambda kv: int(kv[0])))})"
        for n, v in sorted(d["rivers"].items())) or "none") + ".")
    L.append("- Lakes on record: " + (", ".join(d["lakes"]) or "none") + ".")
    L.append("- Coast changes on record: " + (", ".join(d["coasts"]) or "none") + ".")
    L.append("")
    if d["speculative_layers"]:
        L += ["## What the speculative evidence layers hold here", "",
              "Mean value over the box's land hexes at the first, middle and last slice, and how the values "
              "were reached (observed, judged by the gap critic, blended, extrapolated).", ""]
        rows = []
        for k, v in sorted(d["speculative_layers"].items()):
            m = v["mean_by_slice"]
            ys = sorted(m)
            pick = [ys[0], ys[len(ys) // 2], ys[-1]] if ys else []
            rows.append([k, " → ".join(f"{m[y]:g}" for y in pick),
                         ", ".join(f"{b} {n}" for b, n in v["basis"].items())])
        L += T(["Layer", "Value", "Basis (hex-slices)"], rows)
    return "\n".join(L) + "\n"


def sheet(path, d, c, s):
    """Small multiples of the place: terrain, rivers and sites per epoch."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection, PolyCollection
    from matplotlib.patches import Patch, Rectangle

    g, years, b, pad = c["grid"], c["years"], d["box"], s["pad_degrees"]
    view = [b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad]
    sel = hexes_in(g, view)
    if not len(sel):
        return None
    verts = [np.asarray(g.rings[i]) for i in sel]
    show = [y for y in s["sheet_years"] if y in years] or years
    ncol = 3
    nrow = -(-len(show) // ncol)
    aspect = 1 / np.cos(np.radians((view[1] + view[3]) / 2))
    pw = 5.2
    ph = pw * (view[3] - view[1]) * aspect / (view[2] - view[0])
    fig, axes = plt.subplots(nrow, ncol, figsize=(pw * ncol, (ph + 0.4) * nrow + 1.2), squeeze=False,
                             layout="constrained")
    xy = c["site_xy"]
    inview = (xy[:, 0] >= view[0]) & (xy[:, 0] <= view[2]) & (xy[:, 1] >= view[1]) & (xy[:, 1] <= view[3]) \
        if len(xy) else np.zeros(0, dtype=bool)
    seen = Counter()
    for ax, y in zip(axes.ravel(), show):
        t = years.index(y)
        cls = c["terrain"][sel, t]
        seen.update(cls.tolist())
        ax.set_xlim(view[0], view[2])
        ax.set_ylim(view[1], view[3])
        ax.set_aspect(aspect)
        ax.tick_params(labelsize=7, length=2)
        ax.add_collection(PolyCollection(verts, facecolors=[look.PALETTE.get(v, look.OTHER) for v in cls],
                                         edgecolors="#00000022", linewidths=0.3, rasterized=True))
        segs = [np.asarray(f["geometry"]["coordinates"]) for f in c["rivers"]
                if look._river_state(f["properties"], y) in ("perennial", "seasonal")]
        ax.add_collection(LineCollection(segs, colors="#0b2a8a", linewidths=0.7))
        on = c["site_on"][:, t] if len(xy) else inview
        ax.plot(xy[inview & ~on, 0], xy[inview & ~on, 1], "o", ms=3.5, mfc="none", mec="#777777", mew=0.6)
        ax.plot(xy[inview & on, 0], xy[inview & on, 1], "o", ms=4, mfc="black", mec="white", mew=0.5)
        ax.add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1], fill=False, ec="#d4002a", lw=1.4))
        e = d["epochs"][t]
        ax.set_title(f"{_bce(y)}: {e['sites_in_box']} in box, {e['sites_near']} near", fontsize=10, loc="left", pad=3)
    for ax in axes.ravel()[len(show):]:
        ax.set_axis_off()
    handles = [Patch(facecolor=look.PALETTE.get(k, look.OTHER), edgecolor="#555555", label=k or "none")
               for k in look.PALETTE if k in seen]
    fig.legend(handles=handles, loc="outside lower left", ncol=min(len(handles), 8), frameon=False, fontsize=8)
    fig.suptitle(f"{d['name']}: box {' '.join(f'{v:g}' for v in b)}", x=0.01, ha="left", fontsize=12,
                 fontweight="bold")
    fig.savefig(path, dpi=90)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------- run
def index_md(ds, s, planned):
    L = ["# Exotic places, emptiest first", "",
         "From `python -m pipeline places`. Emptiness (0–2) is the share of epochs with no site in the box plus "
         f"the median distance to the nearest site (capped at {s['far_km']:g} km). It ranks where to look. It is "
         "not a finding, and a low score is not a clean bill: a delta with five sites may still be missing fifty.",
         ""]
    L += look._table(
        ["Place", "Kind", "Emptiness", "Epochs with no site (of 8)", "Sites in box (in period)",
         "Within reach", "Peak missing", "Reading at −5000", "Plan", "Dossier"],
        [[d["name"], d["kind"].replace("_", " "), d["emptiness"], d["epochs_without_sites"],
          d["sites_in_box_in_period"], len(d["sites_near"]), d["missing_peak"],
          "; ".join(next((e["outcomes"] for e in d["epochs"] if e["year"] == -5000), {})) or "—",
          planned.get(d["key"], ""), f"`{d['key']}/dossier.md`"] for d in ds])
    sea = [d["name"] for d in ds if d["hexes"] and not d["ever_land"]]
    if sea:
        L += ["Never land on this board: " + ", ".join(sea) + ".", ""]
    return "\n".join(L) + "\n"


def run(cfg, name=None, box=None, out=None, log=print):
    """Write the dossiers and the index. Returns the index path (or the
    dossier path when one place is asked for)."""
    s = settings(cfg)
    out = out or s["out"]
    places = load_catalogue(s["catalogue"])
    if box:
        places = [{"key": name or "box_" + "_".join(f"{v:g}" for v in box), "name": name or "Ad hoc box",
                   "kind": "ad_hoc", "box": list(box), "why": "Asked for by box."}]
    elif name:
        places = [p for p in places if p["key"] == name]
        if not places:
            raise SystemExit(f"no place {name!r} in {s['catalogue']}")
    g = gridmod.load(cfg["output"]["combined"])
    errs = catalogue_problems(places, [g.bbox[:, 0].min(), g.bbox[:, 3].min(), g.bbox[:, 2].max(), g.bbox[:, 1].max()])
    if errs:
        raise SystemExit("places catalogue:\n  " + "\n  ".join(errs))
    want = {int(g.ids[i]) for p in places for i in hexes_in(g, p["box"])}
    c = context(cfg, s, want)
    ds = []
    for p in places:
        d = dossier(p, c, s)
        pdir = os.path.join(out, p["key"])
        os.makedirs(pdir, exist_ok=True)
        pic = sheet(os.path.join(pdir, "sheet.png"), d, c, s)
        with open(os.path.join(pdir, "dossier.md"), "w") as f:
            f.write(dossier_md(d, s, pic))
        with open(os.path.join(pdir, "dossier.json"), "w") as f:
            json.dump(d, f, indent=1, ensure_ascii=False)
        ds.append(d)
        log(f"  {p['key']}: emptiness {d['emptiness']}, {d['sites_in_box_in_period']} sites in box")
    if len(places) == 1:
        return os.path.join(out, places[0]["key"], "dossier.md")
    ds.sort(key=lambda d: (-d["emptiness"], -d["missing_peak"]))
    planned = {}
    for path in glob.glob(os.path.join(s["plans"], "*.toml")):
        try:
            with open(path, "rb") as f:
                planned[os.path.basename(path)[:-5]] = tomllib.load(f).get("meta", {}).get("verdict", "?")
        except tomllib.TOMLDecodeError:
            planned[os.path.basename(path)[:-5]] = "unreadable"
    with open(os.path.join(out, "index.md"), "w") as f:
        f.write(index_md(ds, s, planned))
    with open(os.path.join(out, "index.json"), "w") as f:
        json.dump([{k: d[k] for k in ("key", "name", "kind", "box", "emptiness", "epochs_without_sites",
                                      "sites_in_box_in_period", "missing_peak", "ever_land")} for d in ds],
                  f, indent=1, ensure_ascii=False)
    return os.path.join(out, "index.md")


# -------------------------------------------------------------------- plans
URL = re.compile(r"https?://[^\s\"'<>)\]]+")


def plan_problems(path, places, layer_ids, years, sources_text, near_km=100.0):
    """Problems in one plan file (empty if fine)."""
    from isostyle.intuitions import ADJUST_KINDS, BASES
    from isostyle.intuitions import CAUSES as LAYER_CAUSES
    CAUSES = {**LAYER_CAUSES, **EXTRA_CAUSES}
    try:
        with open(path, "rb") as f:
            d = tomllib.load(f)
    except Exception as e:
        return [f"not valid TOML: {e}"]
    errs = []
    m = d.get("meta", {})
    key = os.path.basename(path)[:-5]
    by_key = {p["key"]: p for p in places}
    if m.get("place") != key:
        errs.append(f"meta.place {m.get('place')!r} must match the file name {key!r}")
    place = by_key.get(key)
    if not place:
        errs.append(f"{key!r} is not a key in the places catalogue")
    if m.get("verdict") not in VERDICTS:
        errs.append(f"meta.verdict {m.get('verdict')!r} not one of {', '.join(VERDICTS)}")
    if m.get("confidence") not in CONFIDENCE:
        errs.append(f"meta.confidence {m.get('confidence')!r} not one of {', '.join(CONFIDENCE)}")
    for field in ("written", "summary", "really_empty"):
        if not str(m.get(field, "")).strip():
            errs.append(f"meta.{field} is missing")
    why = m.get("why_empty")
    if not isinstance(why, list) or (not why and m.get("verdict") != "leave"):
        errs.append("meta.why_empty must be a list of causes (it may be empty only for verdict leave)")
    for w in why if isinstance(why, list) else []:
        if w not in CAUSES:
            errs.append(f"meta.why_empty: {w!r} is not a cause in isostyle/intuitions.py or \"buried\"")
    known, research, spec = d.get("known_site", []), d.get("research", []), d.get("speculate", [])
    if m.get("verdict") == "research" and not (known or research):
        errs.append("verdict research needs at least one [[known_site]] or [[research]]")
    if m.get("verdict") == "speculate" and not spec:
        errs.append("verdict speculate needs at least one [[speculate]]")

    for i, k in enumerate(known, 1):
        w = f"known_site {i} ({k.get('name', '?')})"
        for field in ("name", "cite", "what"):
            if not str(k.get(field, "")).strip():
                errs.append(f"{w}: no {field}")
        if not isinstance(k.get("checked"), bool):
            errs.append(f"{w}: checked must be true or false")
        elif k["checked"] and not URL.search(str(k.get("url", ""))):
            errs.append(f"{w}: checked = true needs the url you opened")
        if k.get("coordinates") not in ("published", "approximate"):
            errs.append(f"{w}: coordinates must be \"published\" or \"approximate\"")
        if not all(isinstance(k.get(x), (int, float)) for x in ("lon", "lat")):
            errs.append(f"{w}: lon and lat must be numbers")
        elif place and float(km_to_box(k["lon"], k["lat"], place["box"])) > near_km:
            errs.append(f"{w}: {k['lon']}, {k['lat']} is more than {near_km:g} km from the place's box")
        if not all(isinstance(k.get(x), int) for x in ("start", "end")) or k["start"] > k["end"]:
            errs.append(f"{w}: start and end must be whole years (BCE negative), start first")
    for i, r in enumerate(research, 1):
        for field in ("what", "yields"):
            if not str(r.get(field, "")).strip():
                errs.append(f"research {i}: no {field}")
        # Follow-through, counted by `python -m pipeline state`: open (the
        # default), done (ingested; say where in `done_in`) or dropped (say why).
        if r.get("status", "open") not in RESEARCH_STATUS:
            errs.append(f"research {i}: status {r.get('status')!r} not one of {', '.join(RESEARCH_STATUS)}")
    for i, x in enumerate(spec, 1):
        w = f"speculate {i}"
        t = str(x.get("target", ""))
        if t != "settlements" and not (t.startswith("isostyle:") and t[9:] in layer_ids):
            errs.append(f"{w}: target {t!r} must be \"settlements\" or \"isostyle:<layer id>\"")
        sl = x.get("slices")
        if not isinstance(sl, list) or not sl or any(y not in years for y in sl):
            errs.append(f"{w}: slices must be a list of years from {years}")
        if x.get("confidence") not in CONFIDENCE:
            errs.append(f"{w}: confidence {x.get('confidence')!r} not one of {', '.join(CONFIDENCE)}")
        for field in ("rule", "reasoning"):
            if not str(x.get(field, "")).strip():
                errs.append(f"{w}: no {field}")
        for b in x.get("basis", []):
            if b not in BASES:
                errs.append(f"{w}: basis {b!r} is not one of {', '.join(sorted(BASES))}")
        for a in x.get("adjust", []):
            need = ADJUST_KINDS.get(a.get("kind"))
            if need is None:
                errs.append(f"{w}: adjust kind {a.get('kind')!r} is not one isostyle knows")
            elif need - set(a):
                errs.append(f"{w}: adjust {a['kind']} lacks {', '.join(sorted(need - set(a)))}")
    with open(path) as f:
        for u in sorted(set(URL.findall(f.read()))):
            if u.rstrip(".,;") not in sources_text:
                errs.append(f"link not listed in the places SOURCES.md: {u}")
    return errs


def check(cfg, log=print):
    """Validate the catalogue and every plan. Returns the number of problems."""
    s = settings(cfg)
    places = load_catalogue(s["catalogue"])
    n = 0
    for e in catalogue_problems(places):
        log(f"{s['catalogue']}: {e}")
        n += 1
    with open(s["layers"], "rb") as f:
        layer_ids = {x["id"] for x in tomllib.load(f).get("layer", [])}
    text = open(s["sources"]).read() if os.path.exists(s["sources"]) else ""
    paths = sorted(glob.glob(os.path.join(s["plans"], "*.toml")))
    for path in paths:
        for e in plan_problems(path, places, layer_ids, list(cfg["residuals"]["years"]), text, s["near_km"]):
            log(f"{path}: {e}")
            n += 1
    log(f"{len(places)} places, {len(paths)} plans, {n} problems")
    return n
