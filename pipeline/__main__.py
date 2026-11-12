"""python -m pipeline build [--config pipeline/config.toml] [--step N] [--out PATH]
python -m pipeline settlements [--config pipeline/config.toml]
python -m pipeline cultures-check [--config pipeline/config.toml]
python -m pipeline biome [--config pipeline/config.toml]   # subset the BIOME4 NetCDF"""
import argparse
import json
import os
import time
import tomllib
from collections import Counter

import numpy as np

from . import compose, elevation, emit, grid as gridmod, koeppen, paleobiome, lakes as lakemod, raster, report, rivers


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
    cold, shift = {}, None
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
        cal_stats = {}
        if pcfg.get("calibrate", {}).get("enabled"):
            model, cal_stats = paleobiome.calibrated_biomes(g, pcfg, kyears, drawn, model, shift)
            log("paleobiome: calibrated against drawn maps")
        gaps = tuple(pcfg.get("gaps", ["Land"]))
        for y in kyears:
            base = drawn.get(y)
            if base is None:
                base = drawn[min(drawn, key=lambda k: abs(k - y))]
            raw[y], land_stats[y] = compose.resolve_land(base, model[y], g.neighbours, gaps)
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

    terrain, prov = compose.fill(keyframes, years, tc["fill"], g.neighbours)
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
        props[p], provenance[p] = compose.fill(leg[p], years, tc["fill"], g.neighbours)
    log("composed")

    lakes = []
    if cfg.get("lakes"):
        terrain, lakes = lakemod.build(cfg, g, terrain, arr, tf, years, log)
        props["terrain"] = terrain
        lakemod.write_geojson(cfg["lakes"]["geojson"], lakes)
        log(f"wrote {cfg['lakes']['geojson']}")

    kstats = None
    if kcfg["source"] == "beyer2020":
        props["koeppen"], provenance["koeppen"], kstats = build_koeppen(
            g, cfg, kcfg, terrain, years, leg, tc["fill"],
            shift if kcfg.get("lapse") else None)
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

    out = out or cfg["output"]["combined"]
    # Static per-hex median elevation (m, present-day datum) for the
    # elevation map mode. Sea level over time is already in `terrain`.
    static = {"elevation": np.round(elev), "landform": landform}
    emit.write_combined(out, g, props, sparse=cfg["output"].get("sparse", False), static=static)
    bd = cfg["output"]["build_dir"]
    with open(os.path.join(bd, "provenance.json"), "w") as f:
        json.dump({p: {str(y): v for y, v in d.items()} for p, d in provenance.items()}, f, indent=1)
    log(f"wrote {out} ({os.path.getsize(out) / 1e6:.1f} MB)")

    report.write(bd, g, terrain, drawn, leg["terrain"], prov, sea_stats, unmatched,
                 mtn_stats,
                 cfg.get("report", {}).get("watch", []),
                 land=(land_stats, biome_bp, model, cal_stats),
                 regions=cfg.get("report", {}).get("regions", []),
                 koeppen=(props["koeppen"], kstats))
    log(f"wrote {bd}/report.md and previews")


def build_koeppen(g, cfg, kcfg, terrain, years, leg, strategy, shift=None):
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
    filled, prov = compose.fill(frames, years, strategy, g.neighbours)
    out = {y: koeppen.align(filled[y], terrain[y], g.neighbours, force, g.centres)
           for y in years}
    stats["modern"] = koeppen.modern(g, pcfg, paleobiome.hex_codes, shift)
    stats["lapse"] = shift is not None
    stats["legacy"] = leg["koeppen"][max(leg["koeppen"])].astype(int)
    stats["terrain"] = terrain
    return out, prov, stats


def main():
    ap = argparse.ArgumentParser(prog="python -m pipeline")
    ap.add_argument("command", choices=["build", "settlements", "biome", "cultures-check"])
    ap.add_argument("--config", default="pipeline/config.toml")
    ap.add_argument("--step", type=int)
    ap.add_argument("--out")
    a = ap.parse_args()
    with open(a.config, "rb") as f:
        cfg = tomllib.load(f)
    if a.command == "biome":
        b = cfg["paleobiome"]
        paleobiome.subset(b["source"], b["data"], b["box"], b["bp_min"], b["bp_max"],
                          [n for n, _ in b.get("calibrate", {}).get("features", [])],
                          b.get("monthly_vars", []))
    elif a.command == "cultures-check":
        import os
        from . import cultures
        cc = cfg["settlements"]["cultures"]
        cultures.check(cc["table"], cc["wikipedia_cache"], os.path.join(cc["out_dir"], "wikipedia.json"))
    elif a.command == "settlements":
        from . import settlements
        settlements.build(cfg, gridmod.load(cfg["grid"]["source"]))
    else:
        build(cfg, a.step, a.out)


if __name__ == "__main__":
    main()
