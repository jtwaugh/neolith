# Terrain: landform, mountain biomes and the treeline

How the pipeline turns elevation and model climate into the `landform`
property and the biome on mountain hexes (`pipeline/elevation.py`,
`pipeline/paleobiome.py`, `pipeline/compose.py`; settings in
`pipeline/config.toml` under `[mountains]`, `[mountains.treeline]`,
`[paleobiome]` and `[paleobiome.lapse]`).

## Decisions

| Question | Choice | Why |
|---|---|---|
| Is "Mountains" a biome? | No. It's a static `landform` (0 flat, 1 hills, 2 mountains, 3 high mountains), and every land hex has a biome in `terrain`. | A mountain range carries forest, steppe or tundra depending on climate. The drawn maps' grey Mountains hid that, e.g. 63% of the Iranian plateau had no biome. |
| What makes a hex mountains? | At least 40% of its ETOPO1 cells pass the Kapos et al. (2000) bands; high mountains also have a median of at least 2000 m; hills have at least 15%. | The Kapos bands are the UNEP-WCMC mountain definition. The 2000 m and 15% cut-offs are this project's own. |
| What biome goes under the drawn Mountains? | They are biome gaps, like `Land`: the calibrated kNN predicts them from model climate (Beyer et al. 2020), moved to each hex's own elevation. | That's the same method the Land gaps already used, and it was validated there (74–80% held-out agreement). |
| Moving climate to the hex's elevation | Temperatures shift by −6.5 °C per km of difference between the hex's median elevation and the mean land elevation of the 0.5° model cells it samples. | Beyer et al. bias-correct the model to 0.5° modern observations, so a cell's climate stands for roughly that cell's mean elevation. 6.5 °C/km is the standard environmental lapse rate. Precipitation is left alone. |
| Köppen on mountains | Each hex's own mean monthly climate is classified with the same temperature shift, rather than the majority class of its model cells. | That keeps climate consistent with the Alpine biome: 85–94% of Alpine hexes come out ET/EF, depending on the key frame. |
| Which mountain hexes are Alpine? | Those whose lapse-corrected monthly climate fails the Paulsen & Körner (2014) treeline rule: a season of months above 0.9 °C must last at least 94 days and average at least 6.4 °C. | That rule is fitted to 376 treelines worldwide. Monthly means stand in for the daily values it was fitted on. |

## Checks (build of 2026-11-12, −6000)

- The Alps' highest hexes (median 2270–2370 m) come out Alpine. The present-day Alpine treeline is about 2000–2300 m.
- The highest Caucasus hexes (median 2400–2700 m) have season means of 7–10 °C and stay forest. The present-day treeline there is about 2500–2800 m, so a hex median sits at or below it.
- Central Afghanistan (2700–2900 m) stays semi-desert or steppe. Dry continental interiors have treelines above 3300 m.
- Alpine hexes number 141 at −9000, 98 at −6000 and 111 at −3000, tracking the early-to-mid Holocene warmth.

## Known limits

- The hex median decides the class, so the alpine fringe of a range whose median is below the treeline doesn't show.
- The climate model's own 0.5° biomes (`kept model` in the report) are not lapse-corrected.
- Köppen uses the same correction (`[koeppen] lapse`). It raises agreement with the modern Köppen map from 67% to 70% on mountain hexes and from 57% to 61% on high mountains (84% to 85% overall). Precipitation isn't corrected, so orographic rain and rain shadows still come from the 0.5° model.

## References

- Beyer, R.M., Krapp, M. & Manica, A. (2020). High-resolution terrestrial climate, bioclimate and vegetation for the last 120,000 years. *Scientific Data* 7, 236. https://doi.org/10.1038/s41597-020-0552-1
- Paulsen, J. & Körner, C. (2014). A climate-based model to predict potential treeline position around the globe. *Alpine Botany* 124, 1–12. https://doi.org/10.1007/s00035-014-0124-0
- Kapos, V., Rhind, J., Edwards, M., Price, M.F. & Ravilious, C. (2000). Developing a map of the world's mountain forests. In Price, M.F. & Butt, N. (eds), *Forests in Sustainable Mountain Development: a State of Knowledge Report for 2000*, CABI, pp. 4–9. No DOI. The map is described in Kapos, V. (2000), UNEP-WCMC web site: mountains and mountain forests, *Mountain Research and Development* 20(4), 378. https://doi.org/10.1659/0276-4741(2000)020[0378:UWWSMA]2.0.CO;2 , and the dataset is at https://wesr-search.unep.org/ckan/dataset/unep-wcmc-rsrc-geospatial-dataset-mountains-of-the--world---2000
- Amante, C. & Eakins, B.W. (2009). ETOPO1 1 Arc-Minute Global Relief Model: Procedures, Data Sources and Analysis. NOAA Technical Memorandum NESDIS NGDC-24. https://doi.org/10.7289/V5C8276M
