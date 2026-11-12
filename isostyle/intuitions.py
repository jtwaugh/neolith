"""Intuition files written by the gap critic: data/isostyle/intuitions/<layer>.toml.

Each file is the critic's reading of one layer's gaps: why the map is empty
where it is empty, and what it would expect there. These are judgements, not
data. They are kept apart from the evidence surfaces so a speculative layer
built from them stays traceable to an argument.

`python -m isostyle intuitions` validates every file and prints a summary.

Schema:

  [meta]
  layer = "pottery"                        # a layer id in layers.toml, or a haplogroup
                                           # set name ("Y haplogroup", "mt haplogroup");
                                           # set files are named y_haplogroup.toml etc.
  written = "2026-11-12"
  dossier = "build/isostyle/gaps/pottery/dossier.json"
  summary = "two or three sentences"

  [[judgement]]                            # one per region and run of slices
  region = "Russia: forest north of 56°N"  # a region name used in the dossier
  slices = [-7000, -6000]                  # slice years it covers
  gap_ids = ["pottery-7000-92"]            # dossier gap ids it answers (may be empty)
  why_empty = ["research_intensity", "publication_access"]   # from CAUSES
  why_note = "short explanation of the causes"
  expected = 0.7                           # value expected if evidence existed: a share 0-1,
                                           # or the layer's units; or "unknown"; for a set,
                                           # a table of clade layer id -> share, e.g.
                                           # expected = { y_i2 = 0.6, y_g2a = 0.3 }
  expected_range = [0.4, 0.9]              # optional
  confidence = "low"                       # low | medium | high
  basis = ["neighbouring_evidence", "literature"]            # from BASES
  reasoning = "the argument, citing dossier numbers"
  literature = [ { cite = "Author year, title", checked = true, url = "..." } ]
  would_settle = "what data or fieldwork would answer it"
  speculative_rule = "how a speculative layer should fill this, in one or two sentences"

  # Optional: the speculative_rule in machine form, applied in order to the
  # judged cells of this region and slices (isostyle/speculative.py). Values
  # are on the layer's scale (for a set file: a clade table like `expected`).
  [[judgement.adjust]]
  kind = "gradient"                        # linear along an axis, clamped beyond the ends
  axis = "lat"                             # "lat" or "lon"
  from = [62.0, 0.5]                       # [coordinate, value]
  to = [66.0, 0.1]
  [[judgement.adjust]]
  kind = "area"                            # value inside a box (within the region)
  bbox = [54.0, 36.0, 62.0, 39.0]          # lon_min, lat_min, lon_max, lat_max
  value = 0.9
  [[judgement.adjust]]
  kind = "coast"                           # value within some distance of the sea of that slice
  within_km = 100
  value = 0.4
  inland = 0.0                             # optional: value for the rest of the region
  [[judgement.adjust]]
  kind = "near"                            # value within a radius of a point
  point = [44.5, 41.7]                     # lon, lat
  radius_km = 150
  value = 0.8
  [[judgement.adjust]]
  kind = "slice_value"                     # a different value for some slices
  slices = [-3000]
  value = 0.35
  [[judgement.adjust]]
  kind = "elevation"                       # value above (or below) a height, from ETOPO1
  above_m = 1500                           # or below_m = 200
  value = 0.1

  [[judgement.adjust]]
  kind = "river"                           # value within some distance of rivers or lakes
  within_km = 30
  names = ["Nile", "Nile (Canopic branch)"]  # traced rivers (build/rivers.geojson); only
                                           # in slices where they flow
  lakes = ["Lake Megachad"]                # optional: lakes at that slice's shoreline
  min_upland_km2 = 20000                   # optional: any HydroRIVERS reach this big
  bbox = [60.0, 36.0, 64.0, 39.0]          # optional: limits the unnamed reaches
  value = 0.7
  outside = 0.05                           # optional: value for the rest of the region
  [[judgement.adjust]]
  kind = "polygon"                         # value inside an outline (lon, lat points)
  points = [[47.0, 30.0], [48.5, 31.5], [47.5, 32.5], [46.0, 31.0]]
  value = 0.0

  Any adjust entry (except slice_value) may also take:
    slices = [-5000, -4000]                # apply only in these slices
    mode = "add"                           # add `value` (may be negative) instead of replacing;
                                           # for gradients, add the interpolated value
  Results are clipped to the layer's range (0-1, or vmin..vmax).
  `value = "unknown"` (area, coast, near, elevation, river, polygon; mode set) withdraws the
  judgement from those cells, which then fall back to extrapolation.
"""
ADJUST_KINDS = {
    "gradient": {"axis", "from", "to"},
    "area": {"bbox", "value"},
    "coast": {"within_km", "value"},
    "near": {"point", "radius_km", "value"},
    "slice_value": {"slices", "value"},
    "elevation": {"value"},
    "river": {"within_km", "value"},
    "polygon": {"points", "value"},
}
import glob
import os
import tomllib

CAUSES = {
    "research_intensity": "few excavations or dates in this region and period",
    "publication_access": "data exist but in closed, regional-language or print-only publications",
    "not_in_open_compilations": "data published but not in any open compilation used here",
    "submerged": "the land is now under the sea",
    "ice": "under ice or just deglaciated",
    "preservation": "the material does not survive (acid soils, erosion, aridity)",
    "recovery_methods": "excavation methods miss it (no sieving or flotation)",
    "recording_practice": "sources do not record this material or attribute",
    "label_gaps": "dated sites carry no usable culture label",
    "low_population": "probably few people lived here",
    "true_absence": "probably genuinely absent",
    "dataset_edge": "the region lies outside a key dataset's coverage",
    "sampling_bias": "evidence exists but is skewed to some site types or contexts",
    "burial_practice": "the dead were cremated, exposed or not buried in recoverable places",
    "unknown": "no good explanation",
}
BASES = {"neighbouring_evidence", "other_layer", "literature", "environment", "analogy", "dossier_statistics", "intuition"}
CONFIDENCE = {"low", "medium", "high"}


def validate(path, layer_ids, regions=None, sets=None, hydro=None):
    """List of problems in one intuition file (empty if fine). hydro:
    (river names, lake names) to check `river` entries against."""
    sets = sets or {}
    errs = []
    try:
        d = tomllib.load(open(path, "rb"))
    except Exception as e:
        return [f"not valid TOML: {e}"]
    meta = d.get("meta", {})
    is_set = meta.get("layer") in sets
    if meta.get("layer") not in layer_ids and not is_set:
        errs.append(f"meta.layer {meta.get('layer')!r} is not a layer id or set name")
    if not meta.get("summary"):
        errs.append("meta.summary is missing")
    js = d.get("judgement", [])
    if not js:
        errs.append("no [[judgement]] entries")
    for k, j in enumerate(js, 1):
        where = f"judgement {k} ({j.get('region', '?')})"
        for f in ("region", "slices", "why_empty", "expected", "confidence", "basis", "reasoning", "would_settle",
                  "speculative_rule"):
            if f not in j or j[f] in ("", []):
                errs.append(f"{where}: missing {f}")
        if regions is not None and j.get("region") not in regions:
            errs.append(f"{where}: region not in the dossier")
        bad = set(j.get("why_empty", [])) - set(CAUSES)
        if bad:
            errs.append(f"{where}: unknown causes {sorted(bad)}")
        bad = set(j.get("basis", [])) - BASES
        if bad:
            errs.append(f"{where}: unknown bases {sorted(bad)}")
        if j.get("confidence") not in CONFIDENCE:
            errs.append(f"{where}: confidence must be one of {sorted(CONFIDENCE)}")
        e = j.get("expected")
        if is_set and isinstance(e, dict):
            bad = set(e) - set(sets[meta["layer"]])
            if bad or not all(isinstance(v, (int, float)) for v in e.values()):
                errs.append(f"{where}: expected must map this set's clade ids to shares (bad: {sorted(bad)})")
        elif not (e == "unknown" or isinstance(e, (int, float))):
            errs.append(f"{where}: expected must be a number or \"unknown\"" + (" or a clade table" if is_set else ""))
        for a in j.get("adjust", []):
            kind = a.get("kind")
            if kind not in ADJUST_KINDS:
                errs.append(f"{where}: adjust kind {kind!r} is not one of {sorted(ADJUST_KINDS)}")
                continue
            miss = ADJUST_KINDS[kind] - set(a)
            if miss:
                errs.append(f"{where}: adjust {kind} needs {sorted(miss)}")
                continue
            vals = [a.get("value"), a.get("inland")] + ([a["from"][1], a["to"][1]] if kind == "gradient" else [])
            for v in vals:
                if v is None or (v == "unknown" and kind in ("area", "coast", "near", "elevation", "river", "polygon")
                                 and a.get("mode", "set") == "set"):
                    continue
                if is_set:
                    if not isinstance(v, dict) or set(v) - set(sets[meta["layer"]]):
                        errs.append(f"{where}: adjust {kind} values must be clade tables for this set")
                elif not isinstance(v, (int, float)):
                    errs.append(f"{where}: adjust {kind} values must be numbers")
            if kind == "river":
                if not (a.get("names") or a.get("lakes") or a.get("min_upland_km2")):
                    errs.append(f"{where}: river needs names, lakes or min_upland_km2")
                if hydro is not None:
                    bad = set(a.get("names", [])) - hydro[0]
                    bad |= set(a.get("lakes", [])) - hydro[1]
                    if bad:
                        errs.append(f"{where}: unknown river or lake names {sorted(bad)}")
            if kind == "polygon" and (len(a["points"]) < 3 or any(len(p) != 2 for p in a["points"])):
                errs.append(f"{where}: polygon needs at least three [lon, lat] points")
            if kind == "elevation" and ("above_m" in a) == ("below_m" in a):
                errs.append(f"{where}: elevation needs exactly one of above_m, below_m")
            if a.get("mode", "set") not in ("set", "add"):
                errs.append(f"{where}: adjust mode must be set or add")
            if kind == "gradient" and a["axis"] not in ("lat", "lon"):
                errs.append(f"{where}: gradient axis must be lat or lon")
            if kind == "area" and (len(a["bbox"]) != 4 or a["bbox"][0] >= a["bbox"][2] or a["bbox"][1] >= a["bbox"][3]):
                errs.append(f"{where}: area bbox must be [lon_min, lat_min, lon_max, lat_max]")
        for ref in j.get("literature", []):
            if "cite" not in ref or "checked" not in ref:
                errs.append(f"{where}: each literature entry needs cite and checked")
    return errs


def run(cfg, log=print):
    from . import layers as layermod
    import json
    reg = layermod.Registry.load(cfg["presence"]["layers"])
    files = sorted(glob.glob(os.path.join(cfg["output"]["out_dir"], "intuitions", "*.toml")))
    if not files:
        log("intuitions: none yet")
        return True
    ok = True
    from .hydro import Hydro
    h = Hydro()
    hydro_names = (set(h.river_names()), set(h.lake_names()))
    sets = {}
    for L in reg:
        if L["set"]:
            sets.setdefault(L["set"], []).append(L["id"])
    for p in files:
        layer = os.path.basename(p)[:-5]
        members = next((ids for name, ids in sets.items() if name.lower().replace(" ", "_") == layer), None)
        dlayer = members[0] if members else layer
        dpath = os.path.join(cfg["output"]["build_dir"], "gaps", dlayer, "dossier.json")
        regions = set(json.load(open(dpath))["layer"]["coverage_by_region"]) if os.path.exists(dpath) else None
        errs = validate(p, set(reg.ids), regions, sets, hydro_names)
        d = tomllib.load(open(p, "rb")) if not any("not valid TOML" in e for e in errs) else {}
        n = len(d.get("judgement", []))
        log(f"intuitions: {os.path.basename(p)}: {n} judgements, " + ("OK" if not errs else f"{len(errs)} problems"))
        for e in errs:
            log(f"  - {e}")
        ok &= not errs
    return ok
