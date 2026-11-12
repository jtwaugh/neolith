# Isostyle pipeline

Kernel-smoothed presence and evidence surfaces for material classes on a hex
grid, per time slice, with masks and bootstrap uncertainty.

```sh
.venv/bin/pip install -r isostyle/requirements.txt
make settlements                      # once: caches the radiocarbon dumps in build/settlements/
.venv/bin/python -m isostyle build    # fetches the other datasets, writes data/isostyle/
.venv/bin/python -m isostyle audit    # Phase 1 data audit, writes data/isostyle/audit/
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
| `maps/presence_<material>.png` | Presence per slice with 25/50/75% isolines |
| `maps/evidence_<material>.png` | Evidence E per slice; the mask layer |
| `maps/uncertainty_<material>.png` | Bootstrap firmness of the 50% line (materials with absences) |
| `maps/overlay_boundaries.png` | 50% lines of all materials per slice |
| `surfaces.csv.gz` | Per land cell, slice and material: evidence, presence, mask and reason, label share, bootstrap shares |
| `contours.geojson` | The isolines, with material, slice and level |
| `summary.json` | Counts, chosen σ, cross-validation scores |
| `METHODS.md` | Methods note and known biases |
| `label_presence.toml` | Hand-coded label rules (input) |

## Modules

`fetch` downloads; `sources` reads the presence datasets; `dates` calibrates
and splits sites into occupation episodes; `observe` decides what each unit
says about each material; `surface` does the kernel, cross-validation and
bootstrap; `maps` draws; `build` ties them together. `audit`, `context` and
`plots` belong to the Phase 1 audit.
