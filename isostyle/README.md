# Isostyle pipeline

Kernel-smoothed evidence surfaces on a hex grid, per time slice, with masks
and bootstrap uncertainty: material culture, crops and herds, pollen-based
land cover, structures and organics, and ancient DNA. What each layer is and
how it is built lives in the layer registry, `data/isostyle/layers.toml`.

```sh
.venv/bin/pip install -r isostyle/requirements.txt
make settlements                       # once: caches the radiocarbon dumps in build/settlements/
.venv/bin/python -m isostyle pollen    # once, ~30 min: Neotoma pollen cores (resumes; reruns retry failures)
.venv/bin/python -m isostyle build     # fetches the other datasets, builds, writes data/isostyle/ and the viewer
.venv/bin/python -m isostyle viewer    # just the viewer, from the last build
.venv/bin/python -m isostyle audit     # Phase 1 data audit, writes data/isostyle/audit/
.venv/bin/python -m isostyle gaps      # gap dossiers per layer (build/isostyle/gaps/)
.venv/bin/python -m isostyle intuitions  # validate the gap critic's notes
.venv/bin/python -m isostyle speculative # fill the gaps from the critic's notes (for the game), then rerun `viewer`
.venv/bin/python -m isostyle export      # speculative layers -> data/isostyle/speculative/evidence_layers.json
.venv/bin/python -m unittest discover -s isostyle/tests -t .
```

`build` reads `isostyle/config.toml`; `audit` reads `isostyle/audit.toml`
(its own 50 km equal-area grid and 250-year slices).

## Inputs

- **Grid file** (`[grid] file`): the hex-map pipeline's GeoJSON. Each feature
  needs `id`, `left/top/right/bottom` and a year-keyed `terrain`.
- **Site table.** By default it is built from the cached radiocarbon dumps,
  the datasets under `[[sources]]` and `data/isostyle/label_presence.toml`,
  and saved as `build/isostyle/units.csv.gz`. To use your own, set
  `[presence] units_file` to a CSV with `lon`, `lat`, and for each material
  `y_<material>` (1, 0 or empty) and `basis_<material>` (`recorded`, `label`
  or empty), plus one `w_<year>` column per slice.

## Outputs in `data/isostyle/`

| File | Contents |
|---|---|
| `maps/presence_<layer>.png` | Presence or value per slice, with isolines |
| `maps/evidence_<layer>.png` | Evidence E per slice; the mask layer |
| `maps/uncertainty_<layer>.png` | Firmness of the middle isoline (layers with absences or values) |
| `maps/overlay_<group>.png` | Boundaries of every layer in a group, per slice |
| `maps/dominant_<y|mt>.png` | Most common haplogroup clade per cell |
| `surfaces.csv.gz` | Per land cell, slice and layer: evidence, presence, mask and reason, label share, bootstrap shares |
| `contours.geojson` | The isolines, with material, slice and level |
| `summary.json` | Counts, chosen σ, cross-validation scores |
| `METHODS.md` | Methods note and known biases |
| `label_presence.toml` | Hand-coded label rules (input) |
| `layers.toml` | The layer registry (input) |
| `inputs/` | Hand-extracted tables (input) |

## Into the game

`python -m isostyle export` writes `data/isostyle/speculative/evidence_layers.json`. It holds one byte per
layer, slice and game hex, packing a 50-step value with a confidence level (format in `isostyle/export.py`).
`neolith-convert --evidence` puts it into `world.bin` (world format version 10), and `make maps` passes it when
the file exists. The game shows it as the Evidence map mode, with a layer picker.

The isostyle build reads the hex-map pipeline's `build/combined_map.geojson`. The pipeline now takes an
exclusive lock on `build/` while it writes. If `make maps` may be running, wrap isostyle commands:
`python -m pipeline.lock build -- .venv/bin/python -m isostyle build`.

## Gap critic

`python -m isostyle gaps [--layer ID]` writes a dossier per layer to
`build/isostyle/gaps/<layer>/`:
- the share of land cells with evidence, by region and slice
- every gap (a connected run of masked land in one region and slice), with
  its edge values and what other layers show inside it
- map crops of the largest gaps

The `gap-critic` agent (`.claude/agents/gap-critic.md`) reads a dossier,
asks why each region is empty and what it would expect there, and writes
`data/isostyle/intuitions/<layer>.toml` in the schema in
`isostyle/intuitions.py`. Each judgement records the causes (from a fixed
list), an expected value with confidence, the reasoning, the literature it
checked, what would settle it, and a rule for filling the gap in a
speculative layer. `python -m isostyle intuitions` validates the files.
These are judgements, not data, and stay separate from the surfaces.

## Adding a layer

Add a `[[layer]]` to `data/isostyle/layers.toml`. For occupation layers,
either give `site_type` / `dated_material` patterns, or write a reader in
`sources.py` that returns rows with `layer` set to the new id (and `present`
1 or 0) and list it in `sources.load`. Core and sample layers are filled by
`pollen.units` and `people.units`; grid layers by a function in
`build.GRID_LAYERS`.

## Modules

| Module | Job |
|---|---|
| `layers` | Loads the layer registry |
| `fetch` | Downloads `[[sources]]`, with provenance |
| `sources` | Reads datasets into presence/absence records |
| `dates` | Calibrates dates and splits sites into occupation episodes |
| `observe` | Decides what each occupation says about each occupation layer |
| `pollen` | Neotoma cores into core units |
| `people` | AADR genomes into sample units |
| `landcover` | REVEALS open land per cell |
| `surface` | Kernel, cross-validation and bootstrap |
| `maps` | Draws the PNGs |
| `build` | Ties them together |
| `viewer` | Writes the HTML viewer |
| `gaps` | Gap dossiers for the critic |
| `intuitions` | Schema and validator for the critic's notes |
| `speculative` | Fills each layer's gaps from the critic's notes, for the game |

`audit`, `context` and `plots` belong to the Phase 1 audit.
