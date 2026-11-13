# Isostyle surfaces: methods note

*Run of 2026-11-12. Regenerate with `.venv/bin/python -m isostyle build`. Numbers below are in
`summary.json`; per-cell values in `surfaces.csv.gz`; isolines in `contours.geojson`.*

## What was built, and what was not

*Since this section was written, the atlas has grown beyond artefact classes; see "Layers beyond
artefact classes" below.*

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
| SoilGrids 2.0 pH(H2O), 5 km (CC BY 4.0) | bone/antler mask | | |

Africa, searched separately: nothing open records ornaments, bone tools or harpoons, or ground stone
north of 6°N. Tixier's (1963) Maghreb flaked-stone typology (doi:10.5281/zenodo.11099349) has type
counts for about 300 assemblages but no coordinates or dates; it suits later style work, not
presence. Phelps et al. 2019 (PANGAEA 904942) dates about 160 African faunal assemblages but
records none of the five classes. West Africa and the Horn have almost no dated sites in any open
compilation. Searched for outside Europe and found nothing open and georeferenced: ornaments, ground stone and bone
tools for the Levant, Mesopotamia, Iran, the Caucasus, Arabia and Central Asia; pottery outside North
Africa and Anatolia (TAY, ASPRO and CANeW have no open download). Jordan et al. 2016 lists earliest
pottery across Afro-Eurasia but only as an all-rights-reserved PDF supplement; it was used until
2026-11-13 and dropped (see `inputs/README.md` for the sites that went with it). Found in the audit but not used: Jensen et al. 2020 bone points (table layout needs hand
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

## Layers beyond artefact classes (added 2026-11-12)

The surfaces are now driven by a layer registry, `data/isostyle/layers.toml`. Each layer names its
kind, its unit of evidence, its kernel-width rule, its isoline levels, its licence and a note. There
are three kinds of evidence point:

| Unit | What one is | Source | Weight per slice |
|---|---|---|---|
| Occupation | One episode of a radiocarbon-dated site, or an external record that matched none | XRONOS, p3k14c, NeoNet, plus the presence datasets | Calibrated date distribution, or a uniform published range |
| Core | One pollen core in one slice in which it has counted levels | Neotoma, including the European Pollen Database | 1 in that slice |
| Sample | One ancient genome that passes AADR's quality assessment | AADR v66.p1 | Normal distribution from AADR's date mean and SD |

| Group | Layer | Kind | Evidence | Source and licence |
|---|---|---|---|---|
| Subsistence | Cereal grain | presence and absence | dated sampled phases | EUROEVOL archaeobotany (Colledge 2016; licence field unfilled, UCL record says copyright waived); Arranz-Otaegui & Roe 2023 SW Asian flora (CC0); directly dated grain in XRONOS |
| Subsistence | Domestic livestock | presence and absence | faunal assemblages | EUROEVOL fauna (Manning 2016, CC0); ADEMNES via Arranz-Otaegui & Roe (CC0); Open Context Anatolia (CC BY); Phelps et al. 2019 Africa (CC BY) |
| Environment | Cereal pollen in cores | presence and absence | pollen cores | Neotoma / EPD (CC BY 4.0) |
| Environment | Dung-fungus spores in cores | presence and absence | cores that count non-pollen palynomorphs | Neotoma / EPD |
| Environment | Open land | gridded value, % | 1° REVEALS cells | LandClimII, Fyfe et al. 2021 (CC BY) |
| Structures & organics | Enclosures, megalithic tombs, pile dwellings, houses, mines, metallurgy, waterlogged organics | presence only | dated occupations | XRONOS site types and dated materials (CC BY); rondel enclosures (CC BY) |
| People | Ancient genomes; Y clades I2, G2a, R1b, R1a, C, J2, H2, other; mt clades U5, U4, H, K, J, T2, N1a, other | presence only (genomes); share | samples | AADR v66.p1 (CC0) |

### Rules

- **Cereal grain.** A phase is present if charred wheat or barley is recorded, and absent if at least five plant taxa are recorded but no wheat or barley. In SW Asia before about 8500 BCE this includes wild-type grain.
- **EUROEVOL.** The files are downloaded by hand, because UCL Discovery refuses scripted downloads; `fetch` records their checksums. Sites and the plant taxa list come from the SQL dump, because the CommonSites CSV has unquoted commas. A phase is dated by its own radiocarbon samples. A phase without its own samples takes only its site's dates that carry the same EUROEVOL period label (EN, MN, LN, LM ...); a phase without a period, or without such dates, is dropped. An earlier version took all of a site's dates and put livestock in France at 7,000 BCE through Mesolithic dates at multi-period sites. The two earliest French livestock phases left, Gazel and Font-des-Pigeons (Châteauneuf-les-Martigues), are the contested "Mesolithic sheep" caves; they are kept as recorded. Cereals are wheat, barley and rye of cultivated or wild/cultivated status, plus indeterminate cereal; oats count only where explicitly domestic. For livestock the taxa list's WildDomesticStatus decides; unspecified *Ovis* counts as domestic (Neolithic Europe had no wild sheep), and mixed-status *Bos*, *Sus* and *Capra* count as uncertain. EUROEVOL is built around Neolithic sites, so it adds many presences but few absences.
- **Domestic livestock.** Present if domestic cattle, sheep, goat or pig is recorded. Absent only if at least 50 identified specimens (or 8 taxa) include no livestock genus of domestic *or uncertain* status. Unspecified sheep/goat, *Bos* or *Sus* count as uncertain.
- **Pollen cores.** A level counts if it has a pollen sum. A core-slice is absent only if it has counted levels and none holds the type. Dung spores are unknown, not absent, in cores that do not count non-pollen palynomorphs. Ages come from the dataset's default chronology; cores with only uncalibrated ages are left out.
- **Open land.** Each hex takes the 1° cell containing its centre. A slice averages the REVEALS windows that are at least half inside it. Firmness is the probability from the reconstruction's standard error that open land is 50% or more.
- **Structures.** These are regex rules on XRONOS's free-text site type and dated material (`layers.toml`). Paulsson's 2019 megalith dates (CC BY-NC-ND) were joined by lab number until 2026-11-13 and are no longer used, because their licence forbids derivatives.
- **Haplogroups.** Clades are matched by prefix on AADR's manual Y call (else its ISOGG call) and its mt call; mt H excludes HV. Each clade's share is computed among samples with a call of that kind, and Y only among males. The two smallest mt clades (U2, X) are folded into "other" so the set fits the 8-colour palette.
- **Kernel widths.** These are cross-validated per layer where it has at least 20 presences and absences. Dung spores borrow from cereal pollen, the Y clades from Y I2, the mt clades from mt U5, and the structure layers from pottery.

### Not built, and why

- **Wool:** no open spindle-whorl, loom-weight or textile compilation before 2200 BCE, and no open kill-off (mortality profile) compilation.
- **Isotopes and strontium mobility:** IsoArcH has no bulk download. MAIA's licence and download need checking, and calling a person non-local needs a strontium baseline (Hoogewerff et al. 2019, CC BY-NC). These are left for a later pass.
- **Ancestry proportions:** AADR has none. Computing them (qpAdm or ADMIXTURE on the genotypes) is a separate job; haplogroup shares stand in.
- **Lanting's logboat dates:** these exist only in a PDF and still need extracting.
- **Metal lead isotopes:** too sparse before 3000 BCE.

### Biases specific to these layers

- **Cereal grain** depends on flotation, which became routine only from the 1970s and unevenly by country.
- **Livestock absences** are rare: most identified assemblages after 6000 BCE have some domestic animal. With EUROEVOL in, the kernel width cross-validates to 200 km, which still smooths heavily.
- **Pollen** samples vegetation a few kilometres around a lake or bog. Cores are dense in northern and central Europe and sparse in the Mediterranean and SW Asia. Large wild grasses put about 6% of pre-farming European levels in the cereal type.
- **REVEALS** covers only 30–75°N, 25°W–50°E, and only 1° cells that have pollen records. Natural steppe and alpine land count as open.
- **Structures** rest on how XRONOS's sources typed their sites. Houses and pile dwellings are badly undercounted: most houses are filed as plain settlements, and most pile dwellings are dated by tree rings, which no open table lists.
- **Ancient genomes** come mostly from burials and from projects in a few countries. A clade's share is a share of sampled individuals, not of the population.

## Fixes prompted by the gap critic (2026-11-12)

The gap critic (`.claude/agents/gap-critic.md`) found these problems while reading the dossiers; all are fixed:

- **Arabian pottery.** A bare "Neolithic" label in Arabia counted as pottery-bearing, but the Arabian Neolithic made none; it now counts as absent. Ubaid-labelled Gulf sites still count as present, and so does the Bronze Age.
- **Eastern European pottery.** Dolbunova's 156 forager-pottery sites all had one 6000–4000 BC span, so the Baltic, Belarus and the Russian forest switched on together at 6,000 BCE. Each site now starts at the modelled start of its nearest modelled site (5540–6000 BC; `inputs/dolbunova2023_starts.csv`).
- **Structures on older phases.** A site's type applies to all its dates, which put megaliths in Iberia at 7,000 BCE and enclosures in Britain at 6,000 BCE. Structure layers now have an earliest plausible date (`not_before` in `layers.toml`).
- **Open land.** REVEALS lists every cell in every window, with all-zero rows where there is no reconstruction; these were read as 0% open land and halved the means. They are now dropped.
- **Anatolian livestock dates.** The Open Context summary's "Start BCE" column holds cal BP, which had put Anatolian assemblages about 1,950 years too early.
- **Cereal absences.** These now need at least five plant taxa in the phase.

## Speculative layers (for the game)

`python -m isostyle speculative` fills every layer's masked land cells, writing
`data/isostyle/speculative/`. **These are not evidence.**

For each layer, slice and land cell (ice and sea stay empty):

1. **Observed:** the evidence surface's value where it has enough evidence.
2. **Judged:** else the expected value of the gap critic's judgement for the cell's region and slice (`data/isostyle/intuitions/`). Several judgements average, weighted by confidence. For haplogroup sets, a clade the judgement omits gets 0 and "other" gets the remainder.
3. **Blended:** judged cells within three hex steps of observed ones move toward the observed values (weights 0.75, 0.5, 0.25).
4. **Extrapolated:** cells no judgement covers take the mean of the nearest observed values, spread ring by ring, with confidence "none".

Acid-soil masks are filled: the game wants use, not survival.

Judged regions are groups of modern countries (Russia split at 56°N), so judged values change at modern borders.

The critics' free-text fill rules were then translated into machine-readable `adjust` entries in the intuition files, by one agent per theme instructed to encode only what each rule says. The schema is in `isostyle/intuitions.py`, and the builder applies the entries in order before blending:

| Kind | What it does |
|---|---|
| `gradient` | Linear change along latitude or longitude |
| `area` | A value inside a box |
| `coast` | A value within some distance of the sea of that slice, in steps of about 55 km |
| `near` | A value within some radius of a point |
| `elevation` | A value above or below a height, from ETOPO1 at the cell centre |
| `river` | A value within some distance of water. Water can be named traced rivers (the map pipeline's HydroRIVERS courses, counted only in slices where the river flowed), named lakes at that slice's shoreline, or any HydroRIVERS reach above a catchment size, optionally within a box |
| `polygon` | A value inside an outline |
| `slice_value` | A value for particular slices |

Any entry may be limited to some slices, may add to the value instead of replacing it, or may withdraw a sub-area as "unknown", which leaves it to extrapolation.

350 of 808 judgements carry rules; the rest are flat fills because their rules say no more. Of the rules, 182 are polygons and 32 rivers; these replaced most box and point approximations of rivers, deltas, basins, deserts and ranges. `speculative/rules.md` marks which rules are encoded.

Known approximations:
- Some broad zones are still boxes: loess, chalk, the Pontic steppe and the Paris basin.
- River strip widths the rules didn't state were set by the translating agents (30–50 km).
- A coastal strip narrower than one hex is one hex wide.
- An elevation rule applies to all high ground in its region, not just the named range.
- Rules that give no numbers, and habitat rules (peat shores, shell-midden coasts), stay flat.

The viewer's Speculative view colours each cell by value and hatches judged cells: sparse hatching for high confidence, dense for low, crosshatch for extrapolated. Hovering a judged cell shows the judgement behind it.

### Smoothing and its evals (added 2026-11-12)

After the fill, speculative cells are smoothed; **observed cells never move**. Three settings in
`isostyle/config.toml` `[speculative]` control it:

| Setting | Value | What it does |
|---|---|---|
| `blend_rings` | 12 | Judged cells within this many hex rings of observed cells lean toward the observed values (weight falls linearly with distance). It was 3. |
| `time_smooth` | 0.4 | Each speculative cell moves this share of the way toward the mean of its own value in the slices before and after. |
| `smooth_iters` | 16 | Passes in which each speculative cell moves halfway to the mean of its neighbours. |
| `bridge` | 0.75 | A speculative cell observed in both neighbouring slices moves this share of the way toward the mean of those two values (less for firmer judgements; not where the judgement names a value for that slice). |

`python -m isostyle evals` measures the result (`data/isostyle/evals/report.md`), and `--search` chose these
settings: the smoothest of 60 grid points that pass every guard (`evals/search.json`). Against the unsmoothed fill:

| Measure | Unsmoothed | Now |
|---|---|---|
| Mean step, observed cell to speculative neighbour (share of the layer's range) | 0.072 | 0.031 |
| Mean step between speculative neighbours | 0.0056 | 0.0037 |
| Speculative neighbour pairs more than 0.4 apart, per 1,000 | 1.75 | 0 |
| Speculative cell-slices that reverse by more than 0.15 each way, per 1,000 | 2.7 | 0.7 |
| Hold-out error: hide a tenth of observed cells in blocks, refill, compare | 0.095 | 0.029 |
| Mean move of speculative cells away from the unsmoothed fill (limit 0.03) | 0 | 0.021 |

Limits to keep in mind:
- The chosen settings sit at the corner of the grid searched, so the search did not find an optimum; it stopped
  where the grid did. The 0.03 limit on drift is a judgement call, not a derived number.
- The hold-out test hides blocks two rings deep, so it rewards blending close to evidence. It says nothing about
  the fill hundreds of km from any evidence; only the drift limit protects the critics' judgements there.
- Time smoothing softens real arrivals as well as flicker. The check that farming still arrives in order
  (Anatolia, Balkans, central Europe, British Isles) passes with the same slice for each region as before, but arrivals in speculative
  cells are more gradual than the judgements state.

A second critic, `.claude/agents/smooth-critic.md`, looks at the maps for artefacts the numbers miss. Its claims
are tested with `python -m isostyle evals --check claims.json`; confirmed ones become permanent cases in
`data/isostyle/evals/regressions.toml`.

**Critic round (2026-11-12).** The smooth-critic reviewed all 34 layers and made 18 claims; the numbers confirmed
16: 13 artefacts (6 flicker, 4 rings round small observed patches, 3 seams) and 3 real patterns. The 13 are cases in
`evals/regressions.toml`. Its four proposed changes to the fill were added as switches and searched (64
combinations, `evals/search.json`; the first search is `search_stage1.json`):

| Switch | Result |
|---|---|
| `bridge`: a speculative cell observed in both neighbouring slices leans toward those values | Kept (0.75). Score 0.344 to 0.341. |
| `blend_conf`: firmer judgements resist the blend | Rejected: hold-out error rises from 0.030 to 0.048. |
| `kernel_cap`: blend no further than the layer's kernel | Rejected: hold-out error rises to 0.037, observed-edge steps grow. |
| `hold_rings`: keep the ring nearest evidence fixed while smoothing | Rejected: no gain alone; fails the hold-out guard with `blend_conf`. |
| `time_from_observed` off: do not pull evidence into the slice before it | Rejected: flicker rises from 0.7 to 0.9 per 1,000. |

**None of the 13 cases passes under any combination.** Two causes lie outside the fill settings:
- In the sparse presence-only layers (mines, pile dwellings, metallurgy, enclosures, megalithic tombs, waterlogged
  organics) an observed cell reads 1.0 ("recorded here") while the critics' judgements for the same layer run
  0 to 0.4 ("share of land with one"). Every observed patch is an island whatever the fill does. Nine of the 13
  cases are in these layers.
- The cases measure how steep a step is. A shorter blend, which the critic asked for to remove rings, makes the
  step steeper, so the ring cases cannot pass by that route.
One judgement was edited: `open_land.toml` Caucasus, whose elevation rule now ramps over 300 to 1,200 m (new
optional `ramp_m` on elevation rules). Its case still fails (0.228 against 0.1).

**Confidence lines.** `conf_edges` in the report counts speculative neighbour pairs in different confidence
classes: 17 per 1,000, and 84% of them have a value step under 0.02. The game draws each class at a different
strength, so region borders (for example 56°N across Russia) show as straight lines over a smooth value. No fill
setting changes this; it needs confidence exported as a number and smoothed, or drawn differently.

**Coasts and time in the game.** A slice now carries values for every cell that is land at any time from the slice
before to the slice after (column `land` = 0 marks cells that are not land in the slice year itself; the maps and
viewer leave them out). The game interpolates each hex linearly between slices, takes the weaker of the two
confidence levels, and hides hexes that are sea or ice in the current year.

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
