# Isostyle surfaces: methods note

*Run of 2026-11-12. Regenerate with `.venv/bin/python -m isostyle build`. Numbers below are in
`summary.json`; per-cell values in `surfaces.csv.gz`; isolines in `contours.geojson`.*

## What was built, and what was not

Presence and evidence surfaces for five material classes on the game's hex grid, at the eight map
keyframes. **Style surfaces (correspondence analysis, attribute shares, edge strength) were not
built**: the Phase 1 audit found no open attribute-level data that covers more than isolated
patches, and the request for this phase was presence and evidence only.

| Material | Occupations with known status | Known absences | Presence surface |
|---|---|---|---|
| Pottery | 9,475 | 1,901 from labels, 196 recorded (North Africa) | Informative. 60–95% of the weight is label-derived, by slice |
| Ground stone | 7,065 | 308 (all from labels) | Weak: 84–99% label-derived, few absences |
| Flaked stone | 1,386 | none | Constant at 100%: shows only where finds are recorded |
| Bone and antler | 231 | none | Constant at 100%; acid soils masked |
| Ornaments | 627 | none | Constant at 100% |

For the last three, no source records an absence and no culture label implies one, so the
"presence" map is a map of recording. Their maps say so, and the overlay draws them as dotted
extents, not as boundaries.

## Inputs

- **Grid:** `build/combined_map.geojson`, 26,410 lon/lat hexagons (about 0.58° × 0.5°). They are
  not equal-area: a cell at 60°N covers half the ground of one at the equator. Distances are
  great-circle, so the kernel is unaffected, but cell counts are not areas. Sea and ice per slice
  come from the grid's own `terrain` (Water, Ice).
- **Slices:** 10,000 to 3,000 BCE every 1,000 years, each ±500 years.
- **Dates:** XRONOS dumps, p3k14c 2025.07, NeoNet Med v2 and Atl v1 as cached by `make settlements`,
  with no site types dropped. 116,588 distinct dates in the grid's box; 72,913 calibrate inside
  the working range.
- **Presence datasets** (fetched to `build/isostyle/sources/`, hashes in `provenance.json`):

| Dataset | Used for | Records | Dating |
|---|---|---|---|
| Evershed et al. 2022, lipid residue table (MIT) | pottery | 313 | published date range |
| Rigaud, Manen & García-Martínez de Lagrán 2018, S1 (CC BY) | pottery, ornaments | 39 + 49 | published date range |
| Dolbunova et al. 2023 (CC BY 4.0) | pottery | 156 sites | **one span for the whole dataset, 6000–4000 BCE** |
| Windler 2019, Spondylus (CC BY 4.0) | ornaments | 417 sites | by culture, 100-year bins |
| Tsirintoulaki, Matzig & Riede 2023 | bone/antler | 50 points | direct radiocarbon dates |
| BDA, Perrin 2021 (CC BY 4.0) | all but ornaments | 1,463 occupation flags | TPQ/TAQ |
| MedAfriCarbon v1.0.3, Lucarini et al. 2020 (CC BY 4.0) | pottery present **and absent**; flaked stone and ground stone (polished axes) present | 341 phases | the phase's radiocarbon dates |
| Rotunno & Crema 2025 (MIT) | pottery present **and absent**, Sahara and Sahel | 278 site × state groups, 855 dates | radiocarbon |
| DEFC, Aspöck et al. (CC BY 4.0) | all five, presence only; Greece and Anatolia | 759 areas, 1,366 records | period start and end years |
| DObsiSS v2.0, Batist (CC BY-SA 4.0) | flaked stone (sourced obsidian), SW Asia | 177 site contexts | ASPRO period |
| Jordan et al. 2016, earliest-pottery table, African rows (no licence stated; hand-extracted to `inputs/`) | pottery present | 83 sites, about 50 on the grid | median cal BP ± 200 years |
| SoilGrids 2.0 pH(H2O), 5 km (CC BY 4.0) | bone/antler mask | | |

Africa, searched separately: nothing open records ornaments, bone tools or harpoons, or ground stone
north of 6°N. Tixier's (1963) Maghreb flaked-stone typology (doi:10.5281/zenodo.11099349) has type
counts for about 300 assemblages but no coordinates or dates; it suits later style work, not
presence. Phelps et al. 2019 (PANGAEA 904942) dates about 160 African faunal assemblages but
records none of the five classes. West Africa and the Horn have almost no dated sites in any open
compilation. Searched for outside Europe and found nothing open and georeferenced: ornaments, ground stone and bone
tools for the Levant, Mesopotamia, Iran, the Caucasus, Arabia and Central Asia; pottery outside North
Africa and Anatolia (TAY, ASPRO and CANeW have no open download). Jordan et al. 2016 lists earliest
pottery across Afro-Eurasia but only as a PDF. Found in the audit but not used: Jensen et al. 2020 bone points (table layout needs hand
parsing), Rigaud et al. 2015 ornaments (sites carry a culture name but no dates), the CLIOARCH
lithics (almost all before 10,000 BCE), PaMELA and the British implement petrology database (undated).

## Method

1. **Calibration.** IntCal20, full distribution on a 10-year grid. No marine reservoir correction.
2. **Occupation episodes.** Within a site, dates are chained while their 95% ranges overlap or lie
   within 200 years (`episode_gap`). 21,085 episodes at 16,091 sites; 14,944 overlap the slices.
   An episode's pᵢ(t) is the mean of its dates' distributions.
3. **Range-dated records.** A dataset record with a date range gets a uniform distribution over
   it; these units are marked `dating = range` in `units.csv.gz`. A record within 2 km of a dated
   site and overlapping one of its episodes marks that episode instead (923 of 2,472 did).
4. **Temporal weight.** wᵢⱼ is the share of pᵢ(t) inside slice j.
5. **Presence yᵢ** per material: 1 if a dataset records it there or a dated sample is of it
   (`basis = recorded`); otherwise 1 or 0 if the episode's culture or stage label implies it
   (`basis = label`, rules in `label_presence.toml`); otherwise unknown and left out. A culture
   label counts only if the episode's median falls in the culture's range ± 200 years.
6. **Kernel.** K(d) = exp(−d²/2σ²) for d ≤ 2.5σ. E = Σ wK; f = (Σ wKy + αf₀)/(E + α), α = 1,
   f₀ the slice's mean presence.
7. **σ by leave-one-place-out cross-validation** (log loss, all slices together):

| σ (km) | 50 | 75 | 100 | 150 | 200 | 300 |
|---|---|---|---|---|---|---|
| Pottery | 0.2307 | 0.2296 | 0.2292 | **0.2291** | 0.2294 | 0.2319 |
| Ground stone | 0.0859 | 0.0827 | 0.0810 | 0.0795 | 0.0792 | **0.0791** |

   Pottery: σ = 150 km, but the curve is nearly flat from 75 to 200 km. Ground stone: σ = 300 km,
   the largest value tried and still improving, which mostly reflects how few absences it has.
   The three materials without absences cannot be cross-validated and use pottery's 150 km.
8. **Masking.** A cell is masked when E < 1.2 (two fully dated sites one σ away, 2·e^(−½)), when
   it is ice, or, for bone and antler, when its mean topsoil pH is below 5.5 (2,892 land cells).
   Masked cells are grey, lilac or sand on every map and are blank in `surfaces.csv.gz`.
9. **Isolines.** Delaunay triangulation of cell centres, `tricontour` at 25%, 50% and 75%.
   Triangles touching a masked or sea cell, or spanning a gap in the grid, are removed first.
10. **Uncertainty.** 200 bootstrap runs: units resampled with replacement, one slice drawn from
    each unit's weights. Each cell gets the share of runs with f ≥ 50% among runs where it has
    enough evidence (`uncertainty_*.png`, and two columns in `surfaces.csv.gz`).
11. **Graves** are kept and flagged (`grave` in `units.csv.gz`): 1,560 of 16,992 units.

## Reading the new non-European datasets

- **MedAfriCarbon** codes each phase yes / low frequency / no for pottery and four lithic tool
  classes. "No" is used as an absence for pottery only: a phase without backed tools still has
  flaked stone, and one without polished axes may still have grinding stones.
- **Rotunno & Crema** flag each date's layer as with or without pottery. The dates of one site
  with the same flag are one record.
- **DEFC**'s CSV export joins multi-valued fields with unquoted commas, so fields are found by
  pattern. Small-find types decide the class: axes, adzes, grindstones, pestles, mortars and mace
  heads count as ground stone; jewellery and beads as ornaments; a tool record whose materials
  include bone or antler, or an awl, spatula, needle or point with no stone or metal material, as
  bone and antler. That last rule is an inference.
- **DObsiSS** records sourced obsidian only; it stands for flaked stone presence.
- A record within 2 km of a dated site, overlapping one of its episodes, marks that episode; a
  recorded presence beats a recorded absence, and both beat a label.

## Known biases

- **Outside Europe, North Africa and Anatolia, presence still rests on labels.** The Levant,
  Mesopotamia, Iran, the Caucasus, Arabia and Central Asia have dated sites but almost no recorded
  material classes.
- **The pottery surface is mostly a map of labels.** Its absences are "Mesolithic", "Epipalaeolithic"
  and aceramic culture names; its presences are mostly "Neolithic" and later names. The 6,000 BCE
  boundary from Iberia to the Baltic is the label boundary between those.
- **Labels are stamped per site.** Many sources give every date at a site all of the site's
  labels. An early date at a site filed as "Neolithic" therefore counts as pottery-bearing. The
  7,000 BCE panel shows this: pottery above 50% in the Carpathian basin and patches of Iberia,
  earlier than any accepted pottery there. Treat that panel's highs outside the Near East as artefacts.
- **`label_presence.toml` is hand-coded** from general knowledge, not from a cited source.
  "Mesolithic = no pottery" is wrong for forager pottery filed under that stage; the Dolbunova
  sites correct this in the east only where they exist.
- **Dolbunova's sites share one 2,000-year span**, so they spread evenly over the 6,000, 5,000 and
  4,000 BCE slices whatever their real dates.
- **Recording bias dominates the three presence-only materials.** Flaked stone and bone follow
  BDA's coverage (France, Iberia, the Maghreb); ornaments follow Windler's Spondylus zone.
- **Research intensity.** Russia, Belarus, Ukraine, the Baltic states and most of the grid outside
  Europe are masked in most slices. See `audit/AUDIT.md`.
- **Soil pH is modern topsoil.** Bogs and lake beds preserve bone inside acid regions (Denmark's
  Maglemose points are from such places), so the mask is too harsh there.
- **Wrong coordinates** in the sources are not screened.
- **1,000-year slices** blur any change faster than that; the 6,000 BCE slice spans 6,500–5,500 BCE.
- **Ice** in the keyframes lasts until 8,000 BCE over all of Scandinavia, which is too long.
