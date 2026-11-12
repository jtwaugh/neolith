"""Export the speculative layers for the game's world file.

`python -m isostyle export` writes data/isostyle/speculative/evidence_layers.json
for `neolith-convert --evidence`. The game's hexes are the grid's features in
file order (build/combined_map.geojson), so codes are indexed by that order.

Per layer: id, name, group, set, kind, units, vmin, vmax, the slice years,
and `codes`: base64 of one byte per (slice, hex), slice-major:
  code = confidence * 50 + bin, bin = value scaled to 0..49 over vmin..vmax,
  confidence 0 observed, 1 judged high, 2 judged medium, 3 judged low,
  4 extrapolated; 255 = no value (sea, ice, or nothing to fill from).
The game reads a slice's codes as holding from that year until the next
slice (the same step-function rule as the map's year keys).
"""
import base64
import json
import os

import numpy as np
import pandas as pd

from . import grid as gridmod, layers as layermod

CONF = {"observed": 0, "high": 1, "medium": 2, "low": 3, "none": 4}
BINS = 50


def run(cfg, log=print):
    out_dir = cfg["output"]["out_dir"]
    sdir = os.path.join(out_dir, "speculative")
    spec = pd.read_csv(os.path.join(sdir, "speculative.csv.gz"))
    registry = layermod.Registry.load(cfg["presence"]["layers"])
    years = [int(y) for y in cfg["time"]["slices"]]
    grid, _ = gridmod.load_game(cfg["grid"]["file"], np.array(years))
    n = len(grid)
    ix = pd.Series(np.arange(n), index=grid["cell"].values)
    layers = []
    for L in registry:
        s = spec[spec["layer"] == L["id"]]
        if s.empty:
            continue
        lo, hi = (L["vmin"], L["vmax"]) if L["kind"] in ("continuous", "grid") else (0.0, 1.0)
        codes = np.full((len(years), n), 255, dtype=np.uint8)
        ci = ix.reindex(s["cell"].values).values.astype(int)
        sk = s["slice"].map({y: k for k, y in enumerate(years)}).values.astype(int)
        v = s["value"].values.astype(float)
        ok = ~np.isnan(v)
        b = np.clip(np.floor((v - lo) / (hi - lo) * BINS), 0, BINS - 1)
        c = s["confidence"].map(CONF).fillna(4).values
        codes[sk[ok], ci[ok]] = (c[ok] * BINS + b[ok]).astype(np.uint8)
        layers.append({"id": L["id"], "name": L["name"], "group": L["group"], "set": L["set"], "kind": L["kind"],
                       "units": L.get("units_label") or ("share" if L["kind"] != "presence_only" else "share recorded"),
                       "vmin": lo, "vmax": hi, "note": L["note"],
                       "codes": base64.b64encode(codes.tobytes()).decode()})
    doc = {"format": "neolith-evidence-1", "hexes": n, "slices": years, "bins": BINS,
           "confidence": ["observed", "judged, high confidence", "judged, medium confidence",
                          "judged, low confidence", "extrapolated"],
           "source": "isostyle speculative layers (data/isostyle/METHODS.md): not evidence where confidence > 0",
           "layers": layers}
    path = os.path.join(sdir, "evidence_layers.json")
    json.dump(doc, open(path, "w"), separators=(",", ":"))
    log(f"export: {len(layers)} layers × {len(years)} slices × {n} hexes -> {path} ({os.path.getsize(path) / 1e6:.1f} MB)")
    return path
