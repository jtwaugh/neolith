# Legacy hex grid and per-epoch properties

These are the parts of the 2023 prototype's per-epoch maps
(`game/static/game/assets/maps/*.geojson`, about 245 MB, removed on
2026-11-13) that the pipeline still reads:

- `grid.geojson`: the canonical hex geometry, ids and bounding boxes
  (`pipeline/config.toml` `[grid] source`), from the 5000 BCE file.
- `<N>_bce.geojson`: per hex, the hand-classified `terrain`, `climate`,
  `koeppen` and `population_density` (+ `_index`) of each 2023 key frame,
  with no geometry (`[legacy] dir`). `population_density` still comes only
  from here; terrain and Köppen are kept for the comparisons in
  `build/report.md`.

Extracted unchanged (same floats, same order); `compose.legacy()` and
`grid.load()` give byte-identical arrays from these and from the originals.
3000 and 4000 BCE were identical in the originals and still are.
