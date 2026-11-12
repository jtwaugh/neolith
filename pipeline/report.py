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
EXTRA_COLOURS = {"Tundra": "#9fa89a", "Land": "#cfc29b", "Alpine": "#bcb3c6"}



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


def write(build_dir, grid, terrain, raw_terrain, legacy_terrain, prov, sea_stats,
          unmatched, mountains, watch, land=None, regions=(), koeppen=None):
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

    L += ["", "## Watched regions: Water hexes / total", ""]
    for w in watch:
        m = in_bbox(grid, w["bbox"])
        L.append(f"- {w['name']}: " + ", ".join(
            f"{y}: {int((terrain[y][m] == 'Water').sum())}/{int(m.sum())}"
            for y in years if y % 500 == 0))

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
