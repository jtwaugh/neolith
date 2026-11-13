"""python -m pipeline build [--config pipeline/config.toml] [--step N] [--out PATH]
python -m pipeline settlements [--config pipeline/config.toml]
python -m pipeline cultures-check [--config pipeline/config.toml]
python -m pipeline biome [--config pipeline/config.toml]   # subset the BIOME4 NetCDF
python -m pipeline anchors [--config pipeline/config.toml]  # pollen anchor records for the biome maps
python -m pipeline suspects                                  # screens for terrain artefacts -> build/critic/terrain/
python -m pipeline attributions                              # ATTRIBUTIONS.md + app credits from data/ATTRIBUTIONS.toml
python -m pipeline look --box LON0 LAT0 LON1 LAT1 [--years Y ...] [--name NAME]   # one region over time, stage by stage"""
import argparse
import json
import os
import time
import tomllib
from collections import Counter

import numpy as np

from . import biome_clean, compose, elevation, emit, grid as gridmod, koeppen, paleobiome, lakes as lakemod, raster, report, rivers


def build(cfg, step=None, out=None):
    t0 = time.time()

    def log(msg):
        print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)

    tc = cfg["time"]
    step = step or tc["step"]
    years = list(range(tc["start"], tc["end"] + 1, step))
    os.makedirs(cfg["output"]["build_dir"], exist_ok=True)

    g = gridmod.load(cfg["grid"]["source"])
    log(f"grid: {len(g)} hexes")

    tcfg = cfg["terrain"]
    palette = [(tuple(c), n) for c, n in tcfg["palette"]]
    raw, unmatched = {}, {}
    for s in tcfg["sources"]:
        raw[s["year"]], unmatched[s["year"]] = raster.sample_terrain(
            g, s["image"], s["world"], palette, tcfg["tolerance"])
        log(f"terrain keyframe {s['year']}")

    leg = compose.legacy(g, cfg["legacy"])
    log("legacy properties loaded")

    arr, tf = elevation.load_asc(cfg["sea"]["elevation"])
    elev = elevation.hex_median(g, arr, tf)
    log(f"elevation: {int(np.isnan(elev).sum())} hexes without cells")

    # Drawn classes the transcription of the source maps got wrong, by region
    # ([[terrain.reinterpret]]), before anything learns from them.
    reinterpreted = {}
    for y in raw:
        raw[y], n = compose.reinterpret(raw[y], g.centres, tcfg.get("reinterpret", []), y)
        if n:
            reinterpreted[y] = n
    if reinterpreted:
        log("reinterpreted drawn classes: " + ", ".join(
            f"{y}: {sum(v.values())}" for y, v in sorted(reinterpreted.items())))

    # Regions of a keyframe drawn from a source map of another time
    # ([[terrain.misdated]]) become biome gaps, filled from the model.
    mrules = tcfg.get("misdated", [])
    misdated_n = {}
    for y in raw:
        raw[y], n = compose.misdated(raw[y], g.centres, mrules, y, elev=elev)
        if n:
            misdated_n[y] = n
    if misdated_n:
        log("mis-dated drawn regions made gaps: " + ", ".join(
            f"{y}: {sum(v.values())}" for y, v in sorted(misdated_n.items())))

    # Drawn Water on high ground outside every modelled lake is a drawing
    # artefact (a coast drawn a hex off, a flicker in one key frame): make it
    # a biome gap, filled like the drawn "Land" ([terrain.high_water]).
    hcfg = cfg["terrain"].get("high_water", {})
    high_water = {}
    if hcfg.get("enabled"):
        with open(cfg["lakes"]["catalogue"], "rb") as f:
            boxes = [lk["box"] for lk in tomllib.load(f)["lake"]] + hcfg.get("keep", [])
        c = g.centres
        in_box = np.zeros(len(g), dtype=bool)
        for b in boxes:
            in_box |= (c[:, 0] >= b[0]) & (c[:, 0] <= b[2]) & (c[:, 1] >= b[1]) & (c[:, 1] <= b[3])
        high = (elev > hcfg["max_elevation"]) & ~in_box
        for y in raw:
            m = high & (raw[y] == "Water")
            if m.any():
                raw[y] = raw[y].copy()
                raw[y][m] = "Land"
                high_water[y] = np.flatnonzero(m)
        log("high drawn water made gaps: " + ", ".join(f"{y}: {len(v)}" for y, v in sorted(high_water.items())))

    # Landform is static and separate from the biome.
    mcfg = cfg["mountains"]
    mfrac = elevation.hex_fraction(g, elevation.mountain_cells(arr, tf, mcfg), tf)
    landform = elevation.landform(mfrac, elev, mcfg)
    mountain = landform >= elevation.MOUNTAINS
    log(f"landform: {int(mountain.sum())} mountain hexes, "
        f"{int((landform == elevation.HIGH_MOUNTAINS).sum())} high, "
        f"{int((landform == elevation.HILLS).sum())} hills")

    # Fill the drawn maps' biome gaps ("Land", and the drawn "Mountains") from
    # modelled biomes. With extend_keyframes, years outside the drawn range get
    # keyframes too: the nearest drawn map, with gap hexes taking that year's
    # model biome.
    pcfg = cfg.get("paleobiome")
    drawn = dict(raw)
    land_stats, biome_bp, model, cal_stats = {}, {}, {}, {}
    biome4 = {}
    cold, shift = {}, None
    # Per keyframe, the hexes whose biome came from the model, not a drawing.
    model_filled = {}
    if pcfg:
        kyears = sorted(set(raw) | set(pcfg.get("extend_keyframes", [])))
        lcfg = pcfg.get("lapse", {})
        if lcfg.get("enabled"):
            biome, _, btf = paleobiome.load(pcfg["data"])
            dz = paleobiome.elevation_offset(g, elev, arr, tf, btf, biome.shape[1:])
            shift = -lcfg["rate"] * dz
            land = np.isfinite(elev) & (elev > 0)
            log(f"lapse: hexes vs model cells, median {np.median(dz[land]):+.0f} m, "
                f"max {dz[land].max():+.0f} m")
        model, biome_bp = paleobiome.hex_biomes(g, pcfg, kyears)
        biome4 = model
        cal_stats = {}
        if pcfg.get("calibrate", {}).get("enabled"):
            ccfg = pcfg["calibrate"]
            lit = (paleobiome.literature_labels(cfg.get("anchors", {}).get("literature"),
                                                cfg.get("anchors", {}).get("holdout", 3), g)
                   if ccfg.get("use_literature") else None)
            # A mis-dated region learns from a keyframe that drew it at the right time.
            borrow, model_ice = {}, {}
            for r in mrules:
                if r.get("model_ice"):
                    for y in r["years"]:
                        model_ice[y] = model_ice.get(y, False) | compose.in_boxes(g.centres, r["boxes"])
                if "train_from" in r:
                    for y in r["years"]:
                        borrow.setdefault(y, []).append((r["train_from"], compose.in_boxes(g.centres, r["boxes"])))
            model, cal_stats = paleobiome.calibrated_biomes(g, pcfg, kyears, drawn, model, shift, lit, borrow,
                                                            model_ice)
            log("paleobiome: calibrated against drawn maps")
            # `fill = "biome4"`: in that rule's boxes the gap takes the model's
            # own biome, not the calibration's (the calibration learns from
            # drawings that may be as rough as the ones distrusted here).
            for r in mrules:
                if r.get("fill") == "biome4":
                    m = compose.rule_mask(g.centres, r, elev)
                    for y in kyears:
                        fill = biome4[y].copy()
                        # `replace`: model classes that don't belong here
                        # (BIOME4's Chaparral on the Russian Plain).
                        for a, b in r.get("replace", {}).items():
                            fill[fill == a] = b
                        model[y] = np.where(m, fill, model[y])
        gaps = tuple(pcfg.get("gaps", ["Land"]))
        for y in kyears:
            base = drawn.get(y)
            if base is None:
                base = drawn[min(drawn, key=lambda k: abs(k - y))]
            raw[y], land_stats[y] = compose.resolve_land(base, model[y], g.neighbours, gaps)
            model_filled[y] = np.isin(base, list(gaps))
        # `ecotone`: in a rule's area and one ring around it, forest hexes
        # next to open land become that class (Steppe-Forest): the forest-
        # steppe BIOME4 has no class for, and a soft seam against the drawing.
        for r in mrules:
            if r.get("ecotone"):
                area = compose.rule_mask(g.centres, r, elev)
                ring = area.copy()
                for i in np.flatnonzero(area):
                    ring[g.neighbours[i]] = True
                forest = ["Boreal Forest", "Temperate Forest", "Woodlands"]
                open_ = r.get("ecotone_open", ["Grassland", "Semi-Desert", "Plains"])
                for y in kyears:
                    t = raw[y]
                    near = np.array([np.isin(t[g.neighbours[i]], open_).any() for i in range(len(t))])
                    raw[y] = np.where(ring & np.isin(t, forest) & near, r["ecotone"], t)
        log(f"paleobiome: {len(kyears)} keyframes, slices BP {sorted(set(biome_bp.values()))}")
        if "treeline" in mcfg:
            cold = paleobiome.treeline(g, pcfg, mcfg["treeline"], kyears, shift)

    keyframes, mtn_stats = {}, {}
    no_cold = np.zeros(len(g), dtype=bool)
    for y, t in raw.items():
        keyframes[y], mtn_stats[y] = compose.apply_alpine(
            t, mountain, cold.get(y, no_cold), g.neighbours)
        d = drawn.get(y)
        if d is not None:
            dm = d == "Mountains"
            mtn_stats[y].update(drawn=int(dm.sum()), kept=int((dm & mountain).sum()),
                                removed=int((dm & ~mountain).sum()),
                                added=int((mountain & ~dm).sum()))
        on = keyframes[y][mountain]
        mtn_stats[y]["biomes"] = Counter(on.tolist()).most_common(6)
    alpine = ", ".join(f"{y}: {st['alpine']}" for y, st in sorted(mtn_stats.items()))
    log(f"alpine hexes by keyframe: {alpine}")

    # The Irano-Anatolian uplands: the drawn maps leave them as Mountains, a
    # gap the drawings never show woodland for in this climate ([biome.upland]).
    ucfg = cfg.get("biome", {}).get("upland", {})
    upland = {}
    if ucfg.get("enabled") and pcfg:
        uclim = paleobiome.hex_climate(g, pcfg, sorted(keyframes), [["BIO12", "linear"], ["BIO6", "linear"]], shift)
        for y in sorted(keyframes):
            keyframes[y], upland[y] = paleobiome.apply_upland(
                keyframes[y], model_filled.get(y, np.zeros(len(g), bool)), elev, g.centres, uclim[y], y, ucfg)
        log("upland rule: " + ", ".join(f"{y}: {n}" for y, n in sorted(upland.items())))

    # Boreal vs Temperate Forest from the model's climate ([biome.forest_type]),
    # so the boreal edge retreats with the warming instead of following the
    # drawn keyframes, which disagree with each other.
    ftcfg = cfg.get("biome", {}).get("forest_type", {})
    if ftcfg.get("enabled") and pcfg:
        ftclim = paleobiome.hex_climate(g, pcfg, sorted(keyframes), [["BIO6", "linear"], ["BIO10", "linear"]], shift)
        ft = {}
        for y in sorted(keyframes):
            keyframes[y], ft[y] = paleobiome.apply_forest_type(keyframes[y], g.centres, ftclim[y], ftcfg, y)
        log("forest-type rule: " + ", ".join(f"{y}: {n}" for y, n in sorted(ft.items())))

    # Dry, warm lowlands of Europe ([biome.dry_lowland]): forest becomes
    # Steppe-Forest or Woodlands where the model is dry enough.
    dcfg = cfg.get("biome", {}).get("dry_lowland", {})
    if dcfg.get("enabled") and pcfg:
        dclim = paleobiome.hex_climate(g, pcfg, sorted(keyframes), [["BIO12", "linear"], ["BIO10", "linear"]], shift)
        dry = {}
        for y in sorted(keyframes):
            keyframes[y], dry[y] = paleobiome.apply_dry_lowland(keyframes[y], elev, g.centres, dclim[y], dcfg)
        log("dry-lowland rule: " + ", ".join(f"{y}: {n}" for y, n in sorted(dry.items())))
    ccfg = cfg.get("biome", {}).get("cold_temperate", {})
    if ccfg.get("enabled") and pcfg:
        cclim = paleobiome.hex_climate(g, pcfg, sorted(keyframes), [["BIO12", "linear"], ["BIO6", "linear"]], shift)
        cold_t = {}
        for y in sorted(keyframes):
            keyframes[y], cold_t[y] = paleobiome.apply_cold_temperate(keyframes[y], g.centres, cclim[y], ccfg, elev)
        log("cold-temperate rule: " + ", ".join(f"{y}: {n}" for y, n in sorted(cold_t.items())))
    lcfg = cfg.get("biome", {}).get("broadleaf_lag", {})
    if lcfg.get("enabled") and pcfg:
        lclim = paleobiome.hex_climate(g, pcfg, sorted(keyframes), [["BIO12", "linear"], ["BIO6", "linear"]], shift)
        lag = {}
        for y in sorted(keyframes):
            keyframes[y], lag[y] = paleobiome.apply_cold_temperate(keyframes[y], g.centres, lclim[y], lcfg, elev, y)
        log("broadleaf-lag rule: " + ", ".join(f"{y}: {n}" for y, n in sorted(lag.items()) if n))
    orules = cfg.get("biome", {}).get("override", [])
    if orules:
        over = {}
        for y in sorted(keyframes):
            keyframes[y], over[y] = paleobiome.apply_overrides(keyframes[y], g.centres, elev, orules, y)
        log("biome overrides: " + ", ".join(f"{y}: {n}" for y, n in sorted(over.items()) if n))

    # Biome cleanup on the keyframes: roughen the model's straight edges, then
    # break up pairs of biomes that should never touch.
    bcfg = cfg.get("biome", {})
    ecfg, acfg = bcfg.get("edges", {}), bcfg.get("adjacency", {})
    clean = {"warped": {}, "adjacency": {}}
    none = np.zeros(len(g), dtype=bool)
    if ecfg.get("enabled"):
        targets = biome_clean.warp_targets(g, ecfg)
        for y in sorted(keyframes):
            mask = ~none if ecfg.get("apply_to", "model") == "all" else model_filled.get(y, none)
            keyframes[y], clean["warped"][y] = biome_clean.warp(keyframes[y], targets, mask)
        log("biome edges: warped " + ", ".join(f"{y}: {n}" for y, n in sorted(clean["warped"].items())))
    forbid = biome_clean.forbid_table(acfg) if acfg.get("enabled") else {}
    if forbid:
        for y in sorted(keyframes):
            keyframes[y], clean["adjacency"][y] = biome_clean.fix_adjacency(
                keyframes[y], g.neighbours, forbid, model_filled.get(y), max_passes=acfg.get("max_passes", 8))

    # What each stage made of every keyframe, for `python -m pipeline look`.
    resolved = dict(raw)
    stage_frames = {"drawn": {y: drawn.get(y, drawn[min(drawn, key=lambda k: abs(k - y))]) for y in keyframes},
                    "biome4": biome4, "calibrated": model if model is not biome4 else {},
                    "filled": resolved, "keyframe": keyframes}

    # Fronts by straight-line distance with a fixed noise field ([time.fronts]):
    # hop counts make fronts with straight north-south sides on this grid.
    fxy, fslow = compose.front_geometry(g, tc.get("fronts", {}))
    terrain, prov = compose.fill(keyframes, years, tc["fill"], g.neighbours, fxy, fslow)
    if forbid:
        # Fronts between keyframes can bring together pairs neither keyframe has.
        kys = sorted(keyframes)
        for y in years:
            if y in keyframes:
                continue
            prev = max((k for k in kys if k <= y), default=kys[0])
            terrain[y], n = biome_clean.fix_adjacency(
                terrain[y], g.neighbours, forbid, model_filled.get(prev), max_passes=acfg.get("max_passes", 8))
            clean["adjacency"][y] = clean["adjacency"].get(y, 0) + n
        log(f"biome adjacency: {sum(clean['adjacency'].values())} hex-years bridged")
    before_water = terrain
    terrain, sea_stats = compose.apply_sea(terrain, elev, g, cfg["sea"])
    if cfg.get("coasts"):
        # Dated shorelines inland of today's (data/coasts/coasts.toml).
        from . import coasts
        terrain, coast_list = coasts.build(cfg, g, terrain, arr, tf, years, log)
        coasts.write_geojson(cfg["coasts"]["geojson"], coast_list)
    props = {"terrain": terrain}
    provenance = {"terrain": prov}
    kcfg = cfg.get("koeppen", {"source": "legacy"})
    legacy_props = ["population_density"]
    if kcfg["source"] == "legacy":
        legacy_props[:0] = ["climate", "koeppen"]
    for p in legacy_props:
        props[p], provenance[p] = compose.fill(leg[p], years, tc["fill"], g.neighbours, fxy, fslow)
    log("composed")

    lakes = []
    if cfg.get("lakes"):
        terrain, lakes = lakemod.build(cfg, g, terrain, arr, tf, years, log)
        props["terrain"] = terrain
        lakemod.write_geojson(cfg["lakes"]["geojson"], lakes)
        log(f"wrote {cfg['lakes']['geojson']}")

    icfg = cfg.get("islands", {})
    if icfg.get("enabled"):
        from . import islands
        cells = islands.hex_cells(g, arr, tf)
        hex_rast = islands.hex_raster(g, arr, tf) if icfg.get("near_shore") else None
        terrain, clean["islands"], clean["majority_land"] = islands.keep_islands(
            terrain, before_water, g, cells, cfg, lakes, icfg, hex_rast)
        props["terrain"] = terrain
        log(f"islands: {sum(r[4] for v in clean['islands'].values() for r in v)} hex-frames made land; "
            f"{sum(clean['majority_land'].values())} drawn-water hex-frames on majority land restored")

    # The settlements `make maps` ships: the `make settlements` output when present.
    spath = next((p for p in (cfg.get("settlements", {}).get("out"),)
                  if p and os.path.exists(p)), None)
    sfeats = gridmod.load_geojson(spath)["features"] if spath else None
    lcfg = cfg.get("settled_land", {})
    from . import coords
    if sfeats and lcfg.get("corrections"):
        sfeats, clean["coord_fixes"], unmatched = coords.apply(sfeats, coords.load(lcfg["corrections"]), g)
        log(f"settlement corrections: {len(clean['coord_fixes'])} applied")
        if unmatched:
            raise ValueError(f"{lcfg['corrections']}: no settlement matches {unmatched}")
    if sfeats:
        # After the corrections, which match names as filed.
        from .settlements import restore_apostrophes
        n = 0
        for f in sfeats:
            name = f["properties"].get("name") or ""
            fixed = restore_apostrophes(name)
            if fixed != name:
                f["properties"]["name"], n = fixed, n + 1
        log(f"settlement names: {n} apostrophes restored")
    if sfeats and lcfg.get("enabled"):
        # After every step that makes Water (sea, coasts, lakes), before
        # anything that reads land (Köppen, rivers, floodplains, population).
        ocean = compose.ocean_masks(elev, g, cfg["sea"], years)
        depth = compose.site_water_depth(sfeats, arr, tf, cfg, lakes, g, ocean, lcfg.get("site_radius", 1),
                                         lcfg.get("coast_cap", 20.0))
        terrain, sfeats, clean["settled_land"] = compose.keep_settled_land(
            terrain, before_water, sfeats, g, lcfg.get("min_land_neighbours", 1), depth,
            lcfg.get("drown_margin", 0.0), lcfg.get("islets", False),
            never={y: elevation.channel_mask(g.centres, cfg["sea"].get("channel", []), year=y) for y in years})
        props["terrain"] = terrain
        sl = clean["settled_land"]
        log(f"settled land: {sum(sl['kept'].values())} hex-frames kept as land under sites above the water; "
            f"{sl['drowned']} occupation phases ended by the water")
    if sfeats and lcfg.get("audit"):
        clean["coord_audit"] = coords.audit(sfeats, terrain, g, arr, tf, lcfg.get("audit_deep_m", 50.0),
                                            lcfg.get("audit_far_km", 25.0))
        coords.write(lcfg["audit"], clean["coord_audit"])
        log(f"coordinate audit: {len(clean['coord_audit'])} suspect sites -> {lcfg['audit']}")
    if sfeats and lcfg.get("out"):
        # What `make maps` hands the converter: occupation as cut above.
        with open(lcfg["out"], "w") as f:
            json.dump({"type": "FeatureCollection", "features": sfeats}, f)

    kstats = None
    if kcfg["source"] == "beyer2020":
        props["koeppen"], provenance["koeppen"], kstats = build_koeppen(
            g, cfg, kcfg, terrain, years, leg, tc["fill"],
            shift if kcfg.get("lapse") else None, (fxy, fslow))
        props["climate"] = {y: koeppen.codes(k) for y, k in props["koeppen"].items()}
        provenance["climate"] = provenance["koeppen"]
        log(f"koeppen: {len(kcfg['years'])} keyframes from monthly climate")
    elif kcfg["source"] != "legacy":
        raise ValueError(f"unknown [koeppen] source {kcfg['source']!r}")

    rcfg = cfg.get("rivers")
    if rcfg:
        segments, props["river"] = rivers.build(cfg, g, terrain, arr, tf, years, log, lakes)
        rivers.write_geojson(rcfg["geojson"], segments)
        log(f"wrote {rcfg['geojson']} ({len(segments)} segments)")
        fcfg = rcfg.get("floodplain", {})
        if fcfg.get("enabled"):
            clean["floodplain"] = {}
            eligible = None
            if fcfg.get("eligibility") == "keyframes":
                eligible = biome_clean.floodplain_eligibility(
                    {y: terrain[y] for y in keyframes if y in terrain}, fcfg)
            for y in years:
                terrain[y], clean["floodplain"][y] = biome_clean.floodplains(
                    terrain[y], props["river"][y], elev, landform, g.neighbours, fcfg, eligible)
            props["terrain"] = terrain
            log(f"floodplains: {max(clean['floodplain'].values())} hexes at most")

    ncfg = cfg.get("productivity", {})
    if ncfg.get("enabled"):
        from . import productivity
        props["npp"], nstats = productivity.build(g, pcfg, ncfg, shift)
        y0, y1 = min(nstats), max(nstats)
        log(f"productivity: {len(nstats)} keyframes; land median {nstats[y0]['median']:.0f} g/m²/yr at {y0}, "
            f"{nstats[y1]['median']:.0f} at {y1}; {nstats[y1]['filled']} shelf hexes filled from neighbours")

    ecfg = cfg.get("edge_sea", {})
    if ecfg.get("enabled"):
        from . import edge_sea
        props["edge_sea_km"], estats = edge_sea.build(g, ecfg, cfg["sea"]["curve"], cfg["sea"]["seed_depth"])
        y0 = min(estats)
        log(f"edge sea: {len(estats)} keyframes; at {y0}, {estats[y0]['hexes']} hexes have sea beyond the map edge "
            f"in reach, {estats[y0]['within_200_km']} within 200 km")

    # Nobody lives on the water: clear population on each year's final Water.
    props["population_density"], clean["water_population"] = biome_clean.clear_water_population(
        props["population_density"], terrain)
    log(f"population: cleared {clean['water_population']} hex-years on water")

    out = out or cfg["output"]["combined"]
    # Static per-hex median elevation (m, present-day datum) for the
    # elevation map mode. Sea level over time is already in `terrain`.
    static = {"elevation": np.round(elev), "landform": landform}
    sketch = elevation.massif(g, arr, tf, landform, mcfg["massif"])
    static["massif"] = np.array([m if m else np.nan for m in sketch], dtype=object)
    log("massif: " + ", ".join(f"{k} {sum(1 for m in sketch if m and m['kind'] == k)}" for k in elevation.MASSIF_KINDS))
    fcfg = cfg.get("farming", {})
    if fcfg.get("enabled"):
        from . import farming
        reached, origin = farming.arrival(g.centres, g.neighbours, terrain, years, fcfg)
        static["farming"] = np.round(reached)
        got = reached[np.isfinite(reached)]
        log(f"farming: front from hex {int(g.ids[origin])} at {fcfg['start']}; reaches {len(got)} hexes by {years[-1]}, "
            f"half of them by {np.median(got):.0f}")
    # Survey intensity (0/1/2) from `make settlements`: where an absence of
    # sites says little. A detection layer, not an input to population.
    survey_path = cfg.get("settlements", {}).get("survey", {}).get("out")
    if survey_path and os.path.exists(survey_path):
        from .settlements import read_survey
        levels = read_survey(survey_path)
        static["survey"] = np.array([levels.get(int(h), np.nan) for h in g.ids], dtype=float)
        log(f"survey: levels for {len(levels)} hexes from {survey_path}")
    emit.write_combined(out, g, props, sparse=cfg["output"].get("sparse", False), static=static)
    bd = cfg["output"]["build_dir"]
    with open(os.path.join(bd, "provenance.json"), "w") as f:
        json.dump({p: {str(y): v for y, v in d.items()} for p, d in provenance.items()}, f, indent=1)
    log(f"wrote {out} ({os.path.getsize(out) / 1e6:.1f} MB)")
    if out == cfg["output"]["combined"]:
        from . import look
        look.write_stages(os.path.join(bd, "stages.npz"), g, stage_frames)

    report.write(bd, g, terrain, drawn, leg["terrain"], prov, sea_stats, unmatched,
                 mtn_stats,
                 cfg.get("report", {}).get("watch", []),
                 land=(land_stats, biome_bp, model, cal_stats),
                 regions=cfg.get("report", {}).get("regions", []),
                 koeppen=(props["koeppen"], kstats),
                 clean={**clean, "high_water": (high_water, elev), "reinterpreted": reinterpreted, "upland": upland,
                        "misdated": misdated_n, "misdated_rules": mrules,
                        "reinterpret_rules": tcfg.get("reinterpret", [])}, settlements=sfeats,
                 islands_watch=cfg.get("islands", {}).get("watch", []))
    log(f"wrote {bd}/report.md and previews")


def build_koeppen(g, cfg, kcfg, terrain, years, leg, strategy, shift=None, front=(None, None)):
    """Köppen per year: classify each key frame's monthly climate (moved to
    each hex's elevation by `shift`, degC per hex, if given), nudge it
    toward that year's terrain, align it with that year's water, fill between
    key frames, then re-align every year with its own sea level and lakes.
    Returns ({year: int array}, {year: provenance}, stats)."""
    pcfg = cfg["paleobiome"]
    ky = kcfg["years"]
    sm = kcfg.get("smooth", {})
    cls = koeppen.hex_classes(g, pcfg, ky, paleobiome.hex_codes,
                              sm.get("months", 3), sm.get("slices", 1), shift)
    ncfg = kcfg.get("nudge", {})
    force = kcfg.get("force", {})
    frames, stats = {}, {"bp": {}, "nudged": {}, "raw": {}}
    for y in ky:
        k, humid, bp = cls[y]
        stats["bp"][y], stats["raw"][y] = bp, k
        if ncfg.get("enabled"):
            k, nudged = koeppen.nudge(k, humid, terrain[y], ncfg.get("wanted", {}))
            stats["nudged"][y] = nudged
        frames[y] = koeppen.align(k, terrain[y], g.neighbours, force, g.centres)
    filled, prov = compose.fill(frames, years, strategy, g.neighbours, *front)
    out = {y: koeppen.align(filled[y], terrain[y], g.neighbours, force, g.centres)
           for y in years}
    stats["modern"] = koeppen.modern(g, pcfg, paleobiome.hex_codes, shift)
    stats["lapse"] = shift is not None
    stats["legacy"] = leg["koeppen"][max(leg["koeppen"])].astype(int)
    stats["terrain"] = terrain
    return out, prov, stats


def main():
    ap = argparse.ArgumentParser(prog="python -m pipeline")
    ap.add_argument("command", choices=["build", "settlements", "biome", "cultures-check", "anchors", "residuals",
                                        "look", "suspects", "places", "places-check", "inferred",
                                        "attributions"])
    ap.add_argument("--config", default="pipeline/config.toml")
    ap.add_argument("--step", type=int)
    ap.add_argument("--out")
    ap.add_argument("--box", nargs=4, type=float, metavar=("LON0", "LAT0", "LON1", "LAT1"))
    ap.add_argument("--years", nargs="*", type=int)
    ap.add_argument("--name")
    a = ap.parse_args()
    if a.command == "attributions":
        from . import attributions
        print(attributions.write())
        return
    with open(a.config, "rb") as f:
        cfg = tomllib.load(f)
    from .lock import build_lock
    with build_lock(cfg["output"]["build_dir"]):
        run(a, cfg)


def run(a, cfg):
    if a.command == "biome":
        b = cfg["paleobiome"]
        paleobiome.subset(b["source"], b["data"], b["box"], b["bp_min"], b["bp_max"],
                          [n for n, _ in b.get("calibrate", {}).get("features", [])]
                          + [v for k in ("temperature", "precipitation")
                             if (v := cfg.get("productivity", {}).get(k))
                             and v not in [n for n, _ in b.get("calibrate", {}).get("features", [])]],
                          b.get("monthly_vars", []))
    elif a.command == "residuals":
        import csv
        import json
        from . import residuals
        rc = cfg["residuals"]
        g = gridmod.load(cfg["output"]["combined"])
        feats = gridmod.load_geojson(cfg["output"]["combined"])["features"]
        sites = gridmod.load_geojson(cfg["settled_land"]["out"])["features"]
        with open(rc["expected"], newline="") as f:
            expected = list(csv.DictReader(f))
        rows, summary, extra = residuals.run(cfg, g, feats, sites, expected)
        residuals.write_rows(rc["out"], rows)
        with open(rc["summary"], "w") as f:
            json.dump(summary, f, indent=1, ensure_ascii=False)
        residuals.maps(rc["maps"], g, rc["years"], extra, rc["map_bins"])
        print(f"wrote {rc['out']} ({len(rows)} rows), {rc['summary']} and maps in {rc['maps']}")
    elif a.command == "inferred":
        from . import inferred
        inferred.run(cfg)
    elif a.command == "cultures-check":
        import os
        from . import cultures
        cc = cfg["settlements"]["cultures"]
        cultures.check(cc["table"], cc["wikipedia_cache"], os.path.join(cc["out_dir"], "wikipedia.json"))
    elif a.command == "anchors":
        from . import anchors
        anchors.build(cfg)
    elif a.command in ("look", "suspects"):
        from . import look
        if a.command == "look":
            if not a.box:
                raise SystemExit("look needs --box LON0 LAT0 LON1 LAT1")
            print(look.look(cfg, a.box, a.years, a.name, a.out))
        else:
            print(look.suspects(cfg, a.out))
    elif a.command == "places":
        from . import places
        print(places.run(cfg, a.name, a.box, a.out))
    elif a.command == "places-check":
        from . import places
        if places.check(cfg):
            raise SystemExit(1)
    elif a.command == "settlements":
        from . import settlements
        settlements.build(cfg, gridmod.load(cfg["grid"]["source"]))
    else:
        build(cfg, a.step, a.out)


if __name__ == "__main__":
    main()
