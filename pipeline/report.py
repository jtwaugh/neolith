"""build/report.md and build/preview/{year}.png."""
import ast
import os
from collections import Counter

import numpy as np
from PIL import Image

from .paleobiome import NON_BIOME
from .raster import Affine, hex_pixels


def terrain_colours(settings_path="neolithic_deities/settings.py", scheme="terrain"):
    """A colour scheme ({value: colour}) from settings.COLOR_SCHEMES, without Django."""
    tree = ast.parse(open(settings_path).read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "COLOR_SCHEMES":
            for k, v in zip(node.value.keys, node.value.values):
                if ast.literal_eval(k) == scheme:
                    # Values may be expressions (the Köppen domain is
                    # list(range(0, 31))): read "range" and default the
                    # domain to its indices.
                    s = {ast.literal_eval(kk): vv for kk, vv in zip(v.keys, v.values)}
                    colours = ast.literal_eval(s["range"])
                    try:
                        domain = ast.literal_eval(s["domain"])
                    except ValueError:
                        domain = range(len(colours))
                    return dict(zip(domain, colours))
    return {}


# Classes the Django colour scheme doesn't have; same colours as neolith-rs palette.rs.
EXTRA_COLOURS = {"Tundra": "#8f9c8a", "Land": "#b39b73", "Alpine": "#b2a6d3", "Floodplain": "#4fc26b"}



def _rgb(hexstr):
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def preview(path, grid, terrain, colours, res=0.1):
    left, top = grid.bbox[:, 0].min(), grid.bbox[:, 1].max()
    w = int((grid.bbox[:, 2].max() - left) / res) + 1
    h = int((top - grid.bbox[:, 3].min()) / res) + 1
    tf = Affine(res, -res, left + res / 2, top - res / 2)
    img = np.full((h, w, 3), 255, np.uint8)
    for i, (ring, bbox) in enumerate(zip(grid.rings, grid.bbox)):
        rr, cc = hex_pixels(ring, bbox, tf, (h, w))
        img[rr, cc] = _rgb(colours.get(terrain[i], "#ff00ff"))
    Image.fromarray(img).save(path)


def in_bbox(grid, box):
    c = grid.centres
    lon0, lat0, lon1, lat1 = box
    return (c[:, 0] >= lon0) & (c[:, 0] <= lon1) & (c[:, 1] >= lat0) & (c[:, 1] <= lat1)


def islands_section(grid, terrain, stats, watch):
    """Report lines: island hexes added ([islands]) and the watched islands'
    land hexes every 1000 years."""
    years = sorted(terrain)
    ys = [y for y in years if y % 1000 == 0] or years
    added = sum(r[4] for v in stats.values() for r in v)
    L = ["", "## Islands", "",
         f"[islands]: {added} hex-frames made land on small landmasses that had fewer land hexes "
         "than their area; most in one frame: "
         f"{max((sum(r[4] for r in v) for v in stats.values()), default=0)}.", ""]
    if watch:
        c = grid.centres
        L += ["Land hexes centred on each island:", "",
              "| island | hexes | " + " | ".join(map(str, ys)) + " |", "|---" * (len(ys) + 2) + "|"]
        for name, (lon0, lat0, lon1, lat1) in watch:
            m = (c[:, 0] >= lon0) & (c[:, 0] <= lon1) & (c[:, 1] >= lat0) & (c[:, 1] <= lat1)
            L.append(f"| {name} | {int(m.sum())} | " +
                     " | ".join(str(int((terrain[y][m] != "Water").sum())) for y in ys) + " |")
    return L


def settlement_water_section(grid, terrain, settlements, top=15):
    """Report lines: settlements whose own hex is Water in a frame they are
    occupied (their `occupation` phases, as the game reads them). "Coastal"
    means a neighbour hex is land that frame, so the shore is drawn a hex
    off; "offshore" means none is, so the site's coordinates or the sea
    itself are wrong."""
    from .compose import alive_frames, phases
    years = sorted(terrain)
    index = {h: i for i, h in enumerate(grid.ids)}
    water = {y: terrain[y] == "Water" for y in years}
    per_year, rows = Counter(), []
    for f in settlements:
        p = f["properties"]
        i = index.get(p.get("hex"))
        if i is None:
            continue
        alive = alive_frames(phases(p, years), years)
        wet = [y for y in alive if water[y][i]]
        if not wet:
            continue
        per_year.update(wet)
        offshore = sum(all(water[y][j] for j in grid.neighbours[i]) for y in wet)
        lon, lat = f["geometry"]["coordinates"][:2]
        rows.append((p.get("name", "?"), lon, lat, len(wet), len(alive), wet[0], wet[-1], offshore))
    L = ["", "## Settlements on Water", "",
         f"{len(rows)} of {len(settlements)} settlements have their own hex as Water in at least one "
         f"frame they are occupied; for {sum(r[3] == r[4] for r in rows)} it is every such frame. "
         "Coastal: a neighbour hex is land that frame (the shore is drawn a hex off). "
         "Offshore: no neighbour is (the coordinates, or the drawn sea, are wrong).", ""]
    if not rows:
        return L
    ys = [y for y in years if y % 500 == 0] or years
    L += ["| year | " + " | ".join(map(str, ys)) + " |", "|---" * (len(ys) + 1) + "|",
          "| on Water | " + " | ".join(str(per_year[y]) for y in ys) + " |", "",
          f"Longest on Water (top {top}):", "",
          "| settlement | lon, lat | years on Water / occupied | first…last | offshore |", "|---|---|---|---|---|"]
    step = years[1] - years[0] if len(years) > 1 else 1
    for name, lon, lat, n, a, y0, y1, off in sorted(rows, key=lambda r: (-r[3], -r[7], r[0]))[:top]:
        L.append(f"| {name} | {lon:.2f}, {lat:.2f} | {n * step} / {a * step} | {y0}…{y1} | {off * step} |")
    return L


def write(build_dir, grid, terrain, raw_terrain, legacy_terrain, prov, sea_stats,
          unmatched, mountains, watch, land=None, regions=(), koeppen=None, clean=None,
          settlements=None, islands_watch=()):
    os.makedirs(os.path.join(build_dir, "preview"), exist_ok=True)
    colours = {**EXTRA_COLOURS, **terrain_colours()}
    years = sorted(terrain)
    L = ["# Hex map build report", ""]

    deg = Counter(len(n) for n in grid.neighbours)
    c, h = grid.centres, abs(grid.bbox[0, 1] - grid.bbox[0, 3])
    pairs = [(i, j) for i, ns in enumerate(grid.neighbours) for j in ns]
    touching = sum(np.hypot(*(c[i] - c[j])) < 1.05 * h for i, j in pairs)
    L += [f"Grid: {len(grid)} hexes. Neighbour counts: "
          + ", ".join(f"{k}: {deg[k]}" for k in sorted(deg))
          + f". Neighbour pairs one hex apart: {touching}/{len(pairs)}.", ""]

    L += ["## Years", "", "| year | terrain | sea level (m) | flooded | exposed |",
          "|---|---|---|---|---|"]
    for y in years:
        s = sea_stats[y]
        L.append(f"| {y} | {prov[y]} | {s['sea_level']:.1f} | {s['flooded']} | {s['exposed']} |")

    L += ["", "## Raster vs committed terrain (keyframes, before sea overlay)", "",
          "| year | agree | of | % |", "|---|---|---|---|"]
    for y in sorted(raw_terrain):
        if y in legacy_terrain:
            a = int((raw_terrain[y] == legacy_terrain[y]).sum())
            L.append(f"| {y} | {a} | {len(grid)} | {100 * a / len(grid):.1f} |")

    L += ["", "## Unmatched raster colours (top 8 per keyframe)", ""]
    for y in sorted(unmatched):
        top = ", ".join(f"{c}: {n}" for c, n in unmatched[y].most_common(8)) or "none"
        L.append(f"- {y}: {top}")

    L += ["", "## Mountains (landform from elevation; biome from climate)", "",
          "Mountains are a static landform (`landform` >= 2), not a terrain class. "
          "*Drawn* counts the keyframe's hand-drawn Mountains, which are biome gaps; "
          "*kept/removed/added* compare them with the landform. *Alpine* is mountain "
          "hexes above the treeline; *neighbours* is drawn Mountains no model "
          "biome reached.", "",
          "| year | mountain hexes | drawn | kept | removed | added | under water/ice "
          "| alpine | neighbours | biomes on mountain hexes |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for y in sorted(mountains):
        m = mountains[y]
        mix = ", ".join(f"{b} {n}" for b, n in m.get("biomes", []))
        L.append(f"| {y} | {m['mountain']} | {m.get('drawn', '')} | {m.get('kept', '')} "
                 f"| {m.get('removed', '')} | {m.get('added', '')} | {m['covered']} "
                 f"| {m['alpine']} | {m['neighbours']} | {mix} |")

    land_stats, biome_bp, model, cal = land or ({}, {}, {}, {})
    if land_stats:
        L += ["", "## Land gaps (no biome drawn) filled from BIOME4 (Beyer et al. 2020)", ""]
        if cal:
            L += ["Gap biomes are calibrated: the drawn maps' biome is predicted from the "
                  "model's climate (kNN), trained where both cover. *Raw* is how often the "
                  "model's own biome matches the drawn one; *calibrated* is the same for the "
                  "kNN, holding out each 10° tile in turn. *Kept model* counts gap hexes whose "
                  "climate is unlike any drawn hex, which keep the model's biome.", "",
                  "| keyframe | model slice (BP) | trained on | gap hexes | kept model "
                  "| from neighbours | raw agreement | calibrated (held out) |",
                  "|---|---|---|---|---|---|---|---|"]
            for y in sorted(land_stats):
                s, c = land_stats[y], cal[y]
                gap = (raw_terrain.get(y, raw_terrain[c["trained_on"]]) == "Land")
                kept = int((gap & (c["pred"] == "")).sum())
                L.append(f"| {y} | {biome_bp[y]} | {c['trained_on']} | {s['gap']} | {kept} "
                         f"| {s['neighbours']} | {100 * c['raw']:.0f}% | {100 * c['cv']:.0f}% |")
        else:
            L += ["| keyframe | model slice (BP) | gap hexes | from model | from neighbours |",
                  "|---|---|---|---|---|"]
            for y in sorted(land_stats):
                s = land_stats[y]
                L.append(f"| {y} | {biome_bp[y]} | {s['gap']} | {s['model']} "
                         f"| {s['neighbours']} |")

    if regions:
        L += ["", "## Regions: top terrain classes (share of non-water hexes)", ""]
        for r in regions:
            m = in_bbox(grid, r["bbox"])
            L += [f"**{r['name']}**", ""]
            for y in years:
                if y % 1000:
                    continue
                c = Counter(v for v in terrain[y][m] if v != "Water")
                n = sum(c.values()) or 1
                L.append(f"- {y}: " + ", ".join(f"{k} {100 * v / n:.0f}%"
                                                for k, v in c.most_common(4)))
            L.append("")

    if clean:
        L += ["", "## Biome cleanup", "",
              "*Warped*: model-filled hexes whose biome changed when sampled at a displaced "
              "position ([biome.edges]). *Bridged*: hexes changed to break up a forbidden "
              "pair of neighbours ([biome.adjacency]). *Floodplain*: hexes made Floodplain "
              "([rivers.floodplain]).", "",
              "| year | warped | bridged | floodplain |", "|---|---|---|---|"]
        for y in years:
            row = [clean.get(k, {}).get(y) for k in ("warped", "adjacency", "floodplain")]
            if any(row):
                L.append(f"| {y} | " + " | ".join("" if v is None else str(v) for v in row) + " |")
        L += ["", f"Population cleared on Water: {clean.get('water_population', 0)} hex-years."]

    L += ["", "## Watched regions: Water hexes / total", ""]
    for w in watch:
        m = in_bbox(grid, w["bbox"])
        L.append(f"- {w['name']}: " + ", ".join(
            f"{y}: {int((terrain[y][m] == 'Water').sum())}/{int(m.sum())}"
            for y in years if y % 500 == 0))

    rt = (clean or {}).get("reinterpreted")
    if rt:
        rules = clean.get("reinterpret_rules", [])
        L += ["", "## Reinterpreted drawn classes ([[terrain.reinterpret]])", "",
              "| key frame | " + " | ".join(f"{r['from']} → {r['to']}" for r in rules) + " |",
              "|---" * (len(rules) + 1) + "|"]
        for y in sorted(rt):
            L.append(f"| {y} | " + " | ".join(str(rt[y].get(k, 0)) for k in range(len(rules))) + " |")

    md = (clean or {}).get("misdated")
    if md:
        rules = clean.get("misdated_rules", [])
        L += ["", "## Mis-dated drawn regions ([[terrain.misdated]])", "",
              "Drawn hexes made biome gaps because the drawing there copies a source map of another time.", ""]
        for k, r in enumerate(rules):
            got = ", ".join(f"{y}: {md[y][k]}" for y in sorted(md) if k in md[y])
            L.append(f"- {r['name']}: {got or 'none'} hexes"
                     + (f"; gaps trained on the {r['train_from']} drawing too" if "train_from" in r else ""))

    up = (clean or {}).get("upland")
    if up:
        L += ["", "## Upland rule ([biome.upland])", "",
              "Gap-filled upland hexes given woodland, forest-steppe or grassland by precipitation and date: "
              + ", ".join(f"{y}: {n}" for y, n in sorted(up.items())) + "."]

    hw = (clean or {}).get("high_water")
    if hw and hw[0]:
        hexes, elev = hw
        L += ["", "## High drawn water ([terrain.high_water])", "",
              "Drawn Water above the elevation limit outside every lake box, made a biome gap. "
              "A real palaeolake among these belongs in data/lakes/lakes.toml.", "",
              "| key frame | hexes | highest (lon, lat, m) |", "|---|---|---|"]
        c = grid.centres
        for y in sorted(hexes):
            idx = hexes[y]
            top = sorted(idx, key=lambda i: -elev[i])[:3]
            L.append(f"| {y} | {len(idx)} | " + "; ".join(
                f"{c[i, 0]:.2f}, {c[i, 1]:.2f}, {elev[i]:.0f}" for i in top) + " |")

    isl = (clean or {}).get("islands")
    if isl is not None:
        L += islands_section(grid, terrain, isl, islands_watch)
        maj = (clean or {}).get("majority_land") or {}
        L += ["", f"Drawn Water on hexes that are mostly land at the frame's water level, outside every "
              f"lake, made land: {sum(maj.values())} hex-frames, at most {max(maj.values(), default=0)} "
              "in a frame."]

    if settlements is not None:
        L += settlement_water_section(grid, terrain, settlements)
        fixes, aud = (clean or {}).get("coord_fixes"), (clean or {}).get("coord_audit")
        if fixes is not None or aud is not None:
            why = Counter(r for a in (aud or []) for r in a["reasons"].split(";"))
            L += ["", f"Coordinates: {len(fixes or [])} corrections applied (data/settlements/corrections.toml: "
                  + ", ".join(f"{n} {k}" for k, n in Counter(a for _, a in fixes or []).most_common())
                  + f"); the audit lists {len(aud or [])} suspect sites ("
                  + ", ".join(f"{n} {k}" for k, n in why.most_common())
                  + ") in data/settlements/coordinate_audit.csv."]
        sl = (clean or {}).get("settled_land")
        if sl:
            drowned = [f for f in settlements if f["properties"].get("drowned") is not None]
            L += ["", f"[settled_land]: {sum(sl['kept'].values())} hex-frames kept as land under sites above the "
                  f"water; {sl['drowned']} occupation phases of {len(drowned)} settlements ended by the water "
                  "(site ground below sea or lake level).",
                  "", "| drowned by | settlements |", "|---|---|"]
            by = Counter((f["properties"]["drowned"] // 1000) * 1000 for f in drowned)
            for y in sorted(by):
                L.append(f"| {y}…{y + 999} | {by[y]} |")
            cuts = sl.get("cuts", [])
            if cuts:
                L += ["", "Every phase ended by the water (depth: metres over the site's ground; "
                      "at the start it is the model's own error there):", "",
                      "| settlement | drowned | water | depth at start | depth then |", "|---|---|---|---|---|"]
                for name, y, body, d0, d in sorted(cuts, key=lambda c: (c[2], c[1], c[0])):
                    L.append(f"| {name} | {y} | {body} | {d0} | {d} |")
            wet = sl.get("wet_starts", [])
            if wet:
                bodies = Counter(w[2] for w in wet)
                L += ["", f"Phases starting under the modelled water ({len(wet)}: "
                      + ", ".join(f"{n} {b}" for b, n in bodies.most_common()) + "). A dated site was dry "
                      "then, so either that water level or the site's coordinates are wrong. Lake cases "
                      "are evidence against the lake curve in data/lakes/lakes.toml.", "",
                      "| settlement | start frame | water | depth (m) |", "|---|---|---|---|"]
                for name, y, body, d in sorted(wet, key=lambda w: (w[2] == "sea", w[2], -w[3]))[:40]:
                    L.append(f"| {name} | {y} | {body} | {d} |")
                if len(wet) > 40:
                    L.append(f"| … {len(wet) - 40} more | | | |")

    L += ["", "## Terrain class counts (every 1000 years)", ""]
    classes = sorted({v for y in years for v in terrain[y]})
    years = [y for y in years if y % 1000 == 0] or years
    L += ["| class | " + " | ".join(map(str, years)) + " |", "|---" * (len(years) + 1) + "|"]
    counts = {y: Counter(terrain[y]) for y in years}
    for c in classes:
        L.append(f"| {c} | " + " | ".join(str(counts[y][c]) for y in years) + " |")
    missing = [c for c in classes if c not in colours]
    if missing:
        L += ["", f"Not in the terrain colour scheme (drawn magenta in previews): {missing}"]

    kprops, kstats = koeppen or (None, None)
    if kstats:
        L += koeppen_section(grid, kprops, kstats, regions)
        source = ("Köppen is classified from Beyer et al. 2020 monthly climate "
                  "(Beck et al. 2018 rules); population is copied from the committed epoch files.")
    else:
        source = "climate/koeppen/population are copied from the committed epoch files."
    L += ["", "Caveats: sea level is an approximate eustatic curve with no isostatic "
          f"rebound; {source}"]
    with open(os.path.join(build_dir, "report.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    for y in sorted(terrain):
        preview(os.path.join(build_dir, "preview", f"{-y}_bce.png"), grid, terrain[y], colours)
    if kstats:
        kc = terrain_colours(scheme="koeppen")
        kc[31] = "#ff00ff"
        for y in kstats["bp"]:
            preview(os.path.join(build_dir, "preview", f"koeppen_{-y}_bce.png"),
                    grid, kprops[y], kc)


def koeppen_section(grid, kprops, kstats, regions=()):
    """Report lines: modern-slice validation, per-key-frame counts, nudges."""
    from .koeppen import CODES, OCEAN, MISSING
    names = CODES + ["missingno"]
    ky = sorted(kstats["bp"])
    L = ["", "## Köppen per key frame", ""]
    m, leg = kstats.get("modern"), kstats["legacy"]
    if m is not None:
        both = (m > 0) & (leg > 0) & (leg < MISSING)
        if both.any():
            exact = (m[both] == leg[both]).mean()
            first = np.array([names[a][0] == names[b][0] for a, b in zip(m[both], leg[both])]).mean()
            how = ("each hex's mean climate, lapse-corrected to its median elevation"
                   if kstats.get("lapse") else "majority class of the 0.5° model cells")
            L += [f"Validation: the 0 BP model slice ({how}) matches the committed modern "
                  f"Köppen on {exact:.0%} of {int(both.sum())} land hexes ({first:.0%} on the "
                  "main letter A-E).", ""]
            groups = sorted({names[v][0] for v in leg[both]})
            L += ["| main class (modern) | hexes | model agrees |", "|---|---|---|"]
            for gname in groups:
                sel = both & np.array([names[v][0] == gname for v in leg])
                agree = np.mean([names[v][0] == gname for v in m[sel]])
                L.append(f"| {gname} | {int(sel.sum())} | {agree:.0%} |")
            L.append("")
    else:
        L += ["No 0 BP slice in build/biome.npz for validation; rerun `python -m pipeline biome`.", ""]
    L += ["| key frame | BP slice | changed vs modern | nudged | water mismatch | missing |",
          "|---|---|---|---|---|---|"]
    for y in ky:
        k, t = kprops[y], kstats["terrain"][y]
        land = (k != OCEAN) & (leg != OCEAN)
        mismatch = int(((t == "Water") != (k == OCEAN)).sum())
        nudged = kstats["nudged"].get(y)
        L.append(f"| {y} | {kstats['bp'][y]} | {int((land & (k != leg)).sum())} | "
                 f"{int(nudged.sum()) if nudged is not None else '-'} | {mismatch} | "
                 f"{int((k == MISSING).sum())} |")
    alp = [(y, kstats["terrain"][y] == "Alpine") for y in ky]
    if any(a.any() for _, a in alp):
        L += ["", "Alpine hexes classed polar (ET/EF): " + ", ".join(
            f"{y}: {int(np.isin(kprops[y][a], [CODES.index('ET'), CODES.index('EF')]).sum())}"
            f"/{int(a.sum())}" for y, a in alp)]
    if regions and kstats["nudged"]:
        L += ["", "Nudged hexes by region:", "",
              "| region | " + " | ".join(map(str, ky)) + " |", "|---" * (len(ky) + 1) + "|"]
        for r in regions:
            sel = in_bbox(grid, r["bbox"])
            L.append(f"| {r['name']} | " + " | ".join(
                str(int((kstats["nudged"][y] & sel).sum())) for y in ky) + " |")
    L += ["", "Class counts:", "", "| class | " + " | ".join(map(str, ky)) + " |",
          "|---" * (len(ky) + 1) + "|"]
    counts = {y: Counter(np.asarray(kprops[y], int).tolist()) for y in ky}
    for c in sorted({c for y in ky for c in counts[y]}):
        L.append(f"| {names[c]} | " + " | ".join(str(counts[y][c]) for y in ky) + " |")
    return L
