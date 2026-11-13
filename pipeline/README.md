# Hex-map pipeline

Rebuilds the Rust app's world file, `neolith-rs/assets/world.bin`, from
`raw/` and `pipeline/config.toml`. It goes via an intermediate
`build/combined_map.geojson` (SPEC §3.2 format), which `neolith-convert`
turns into `world.bin`. It replaces the QGIS zonal-statistics step and the
one-off `scripts/*.py`. The old Django app's `combined_map.geojson` is left
alone.

```sh
make test     # unit tests on synthetic grids/rasters
make maps     # venv + ETOPO and BIOME4 downloads (once) + build + convert -> neolith-rs/assets/world.bin
.venv/bin/python -m pipeline build --step 1000 --out build/try.geojson   # GeoJSON only
```

Settlements in `world.bin` come from `data/settlements/settlements.geojson`
(`make settlements`) when it exists, else the original
`game/static/game/assets/settlements.geojson`.

Outputs in `build/`: `report.md`, which has agreement with the committed
terrain, unmatched colours, mountain changes, sea-level flips, watched regions and class counts.
Also `preview/{N}_bce.png` and `provenance.json`, which says which keyframe
each year's value came from.

## Stages

1. **Grid**: geometry, ids and bboxes from `[grid] source`. Adjacency uses
   the SPEC §5 formula, checked in the report: every neighbour pair is one
   hex apart.
2. **Terrain**: each `[[terrain.sources]]` PNG and `.pgw` pair is
   classified per pixel against the palette (exact match, else nearest
   within `tolerance`, else no vote). Each hex takes the majority class
   over the pixel centres inside its polygon.
2b. **Land gaps**: the drawn maps have no biome (grey, `Land`) over
   Arabia, Russia east of the Volga, Central Asia and the Iranian and
   Levantine uplands. Those hexes take the modelled biome for the same year
   from Beyer, Krapp & Manica 2020 (HadCM3 + BIOME4, 0.5°, 1000-year
   slices, CC BY 4.0). Each hex takes the majority code of the cells inside
   it, or the nearest cell, and `[paleobiome.classes]` maps the code to
   our terrain classes; BIOME4's five tundra types become `Tundra`.
   The model is drier than the drawn maps, so by default the gaps are
   **calibrated** (`[paleobiome.calibrate]`): a k-nearest-neighbour
   classifier learns the drawn biome from the model's own climate (BIO1,
   BIO6, BIO10, log BIO12, log BIO18) on the hexes both cover, and
   predicts the gaps from the same model climate, so the model's dry bias
   cancels out. Years with no drawn map use the nearest drawn map's
   classifier on their own climate. A gap hex whose climate is unlike any
   drawn hex (cold deserts in Turan, the far north-east) keeps the model's
   biome. A gap
   hex the model has as water takes its neighbours' majority. The years in
   `extend_keyframes` (−10000, −4000, −3000) get keyframes too: the nearest
   drawn map, with its gaps taken from that year's model slice. This runs
   before the landform stage. The drawn Mountains are gaps too, so every
   mountain hex gets a real biome. `make build/biome.npz` downloads the 1.3 GB NetCDF once and
   cuts it to our box and years with `python -m pipeline biome`.
3. **Landform and mountain biomes** (`data/terrain/SOURCES.md`): mountains
   are a static `landform` (0 flat, 1 hills, 2 mountains, 3 high mountains),
   not a terrain class. A raster cell is mountain by the `[mountains]` bands
   (Kapos et al. 2000: high ground outright, lower ground only where steep
   or with over 300 m of relief within 7 km). A hex is mountains when at least
   `min_fraction` of its cells are, high mountains when its median is also
   at least `high_elevation`, and hills from `hills_fraction`. The drawn maps'
   Mountains are biome gaps (`[paleobiome] gaps`), filled in stage 2b like
   Land. For both the calibration and the treeline, model temperatures are
   moved to each hex's median elevation (`[paleobiome.lapse]`, 6.5 °C/km
   from the mean land elevation of the model cells). Mountain hexes that fail
   the Paulsen & Körner (2014) treeline rule (`[mountains.treeline]`) become
   `Alpine`. Ice and Water stay as they are.
4. **Sea level**: the median ETOPO1 elevation per hex is compared with
   `[sea] curve`. A hex is sea when it's below sea level *and* connected to
   open ocean (the grid edge or deeper than `seed_depth`), so closed
   basins like Qattara and the Caspian don't flood. Modern sea floor that
   was dry takes its neighbours' majority land class.
5. **Köppen** (`[koeppen]`, `pipeline/koeppen.py`): for each key frame
   (−10000 … −3000), the Beyer et al. 2020 monthly temperature and
   precipitation (`monthly_vars`, in `build/biome.npz`) are classified with
   the Beck et al. 2018 rules (Sci. Data 5:180214, Table 1) into the 0–30 index; `climate` is its code
   string. Each frame is the modern (0 BP) climatology plus the model
   anomaly smoothed over 3 months and ±1 ka (`[koeppen.smooth]`), which stops
   single-month noise from making boreal hexes summer-dry (Ds). With
   `lapse = true`, each hex's own mean monthly climate is classified, with
   its temperatures moved to the hex's median elevation as in stage 3
   (`[paleobiome.lapse]`). Without it, each 0.5° cell is classified and the
   hex takes the majority. Hexes whose
   terrain is wetter than their climate step up BW → BS → non-arid
   (`[koeppen.nudge]`), so the green Sahara and Arabia aren't desert.
   Each year's Water is Ocean, Ice is EF, and exposed shelf takes its land
   neighbours' class. The report validates the 0 BP slice against the
   committed modern Köppen. `source = "legacy"` restores the old copy.
   Population still comes from the committed epoch files (`[legacy]`); the
   population lookup has the 199/215 swap fixed.
6. **Fill**: years between keyframes use `[time] fill`. With `fronts`
   (the default), each hex that changes A→B between two keyframes switches
   at a year set by how far it is from where B already was, so biomes
   advance as fronts. Years outside the keyframe range hold the nearest
   keyframe. With `hold`, every year takes the latest earlier keyframe.
5b. **Coasts**: `data/coasts/coasts.toml` gives dated polygons of former sea
   inland of today's coast (the Gulf head, the Po plain, the northern Nile
   delta), which ETOPO1's modern surface can't show. Hexes mostly inside a
   stage's polygon become Water for its years, right after the sea step;
   `build/coasts.geojson` has the polygons for checking.
6a. **Lakes**: each lake in `data/lakes/lakes.toml` has a level curve, or
   an area curve (km²) for lakes the literature gives by area; a `dam` line
   can stand in for a barrier the modern DEM no longer has.
   - **Extent:** a priority flood of ETOPO1 from the lake's seed point
     gives the level needed to cover each cell. The lake can't rise above
     its outlet, where the flood first leaves its window.
   - **Hexes:** those mostly under water become Water. Drawn Water inside
     the lake's basin that the lake doesn't reach that year takes
     neighbouring land.
   - **Shorelines:** written to `build/lakes.geojson` for drawing over the
     hexes (`neolith-convert --lakes`; `world.bin` version 3).
   - **Levels** drive spillway rivers (`spill` in `rivers.toml`).
   - Sources: `data/lakes/SOURCES.md`.
5c. **Edge sea** (`[edge_sea]`, `pipeline/edge_sea.py`): the app measures a
   hex's distance to water from the map's own Water hexes, so a coast that
   lies off the map (the Gulf of Guinea, the Atlantic off Senegal) would
   read as deep inland. For each key frame, each hex gets `edge_sea_km`: the
   distance from its centre to the nearest open-sea cell outside the grid's
   box, at that year's `[sea] curve` level, from a wider 6 arc-min ETOPO1
   window (`make build/etopo_wide.asc`, 4.5 MB). 65535 means none within
   `max_km`. The app takes the nearer of this and the on-map distance
   (`world.bin` version 12). Lakes off the map are not counted.
6a′. **Elevation**: each hex's median ETOPO1 elevation (metres, present-day
   datum) is written as a static scalar `elevation` property, not year-keyed,
   for the app's elevation map mode (`world.bin` version 4). `landform` is
   written the same way (`world.bin` version 5). The app draws peaks and hills
   from it over the biome.
6b. **Rivers**: the rivers in `data/rivers/rivers.toml` become polylines
   with a `state` step function (perennial, seasonal or absent), written to
   `build/rivers.geojson`. Hexes are not turned into water. Each hex gets a
   derived `river` class per year (0 none, 1 minor or seasonal, 2 large
   perennial).
   - **Courses** are traced downstream along HydroRIVERS (`make maps`
     downloads about 270 MB to `build/hydrorivers/`), or entered as
     waypoints for buried channels.
   - **Sea mouths** are extended across the shelf along the lowest ETOPO1
     spill path to the sea at the run's lowest level.
   - **Each year** a river ends where the run of Water hexes at its mouth
     begins, so shelf reaches drown with the sea curve.
   - `neolith-convert --rivers build/rivers.geojson` puts the rivers into
     `world.bin` (format version 2; version 1 files still load).
   - Sources, dates and the Lake Megachad question are in
     `data/rivers/SOURCES.md`.
7. **Output**: with `[output] sparse = true`, a year key is written only
   when a hex's value changes. That means the same under §3.2's
   step-function rule and the backend's "latest key ≤ year" lookup. At a
   100-year step it's 16 MB, against 28 MB for the old 8 dense epochs.

## Checking the terrain

```sh
.venv/bin/python -m pipeline suspects     # build/critic/terrain/suspects.md
.venv/bin/python -m pipeline look --name balkans --box 10 36 32 50 --years -9000 -8500 -8000 -7500 -7000
```

`pipeline/look.py`, settings in `[critic]`. Both read the built map and
change nothing.

- **`suspects`** screens the whole map for likely artefacts: biome edges
  that keep to one hex row or column, thin bands, a biome whose share of a
  5° tile jumps between keyframes or jumps and comes straight back, biomes
  under a Köppen class `[critic.climate]` doesn't allow them, floodplains
  that vanish while their river still runs, and lone hexes. Each row is a
  box and years to look at, with the `look` command for it. The screens are
  loose: real zonal boundaries (the Sahel) show up too.
- **`look`** draws one box: `years.png` (each year, in a palette where every
  class is distinct, with rivers and numbered pollen anchors),
  `stages_<N>_bce.png` for each keyframe year asked for (drawn map, BIOME4,
  calibrated model, gaps filled, after cleanup, final), and `look.md` (class
  shares, changes, which stage set each class, Köppen under each class,
  terrain on big-river hexes, anchors against the map).
- The stage maps come from `build/stages.npz`, which `pipeline build` writes
  with the main output.

The `terrain-critic` agent (`.claude/agents/terrain-critic.md`) works through
these and writes a report under `build/critic/terrain/`.

## Checking exotic places

```sh
.venv/bin/python -m pipeline places                       # build/critic/places/index.md
.venv/bin/python -m pipeline places --name bab_el_mandeb  # one place
.venv/bin/python -m pipeline places --name tihama --box 42.2 13.5 43.6 17.0
.venv/bin/python -m pipeline places-check                 # validate data/places/plans/
```

`pipeline/places.py`, settings in `[places]`. `data/places/places.toml` lists
straits, river mouths, deltas, islands, oases, passes and drowned plains:
places where someone looking at the map expects something to be going on.
Nothing in the build reads the catalogue or anything made from it.

- **`places`** writes a dossier and a sheet of maps per place, and an index
  ranked by emptiness (the share of epochs with no site in the box, plus the
  distance to the nearest site). A dossier holds, per epoch, land and water
  in the box, hexes that drown later, sites in the box and within 100 km and
  the missing-sites residuals; then the sites, likely duplicates, doubtful
  coordinates, survey intensity, rivers, lakes and coast changes on record,
  and what the speculative evidence layers hold there. The ranking says
  where to look. It counts known sites, so it must never feed the expected
  density.
- The **exotic critic** (`.claude/agents/exotic-critic.md`) takes named
  places or the top of the index and asks of each: is it really empty, why,
  what does the literature know that we lack, and should we research,
  speculate or leave it? It writes `data/places/plans/<key>.toml`: sites
  known to the literature (with citation, link, and whether it opened the
  source), datasets to ingest, and speculation to add beside the record,
  as settlements marked inferred or as isostyle adjust rules. It lists its
  links in `data/places/SOURCES.md`. It only plans; applying a plan is a
  separate step.
- **`places-check`** validates the catalogue and the plans (verdict, causes
  from `isostyle/intuitions.py`, sites within reach of their place, layer
  ids, links listed in `SOURCES.md`).

## Adding data

- **New terrain keyframe:** georeference it to WGS84 with a `.pgw`, add a
  `[[terrain.sources]]` entry, and add its colours to `palette` if needed.
- **New river:** add a `[[river]]` to `data/rivers/rivers.toml` (a `from`
  point on HydroRIVERS, or `points` waypoints) and a row in its SOURCES.md.
  Main rivers go before their tributaries: a tributary stops where it meets
  a river already drawn. A river whose course changed is split: the shared
  upper course (with `to` at the fork) and one entry per branch, each with
  its own `state` (`before` waypoints link a branch to its parent).
- **Finer time step:** change `[time] step` (100 by default).

## `fronts` fill

For consecutive keyframes t0 < t1, take each target value B in turn and
the hexes that change into it. Run a BFS from hexes that are already B at
t0, through the changing hexes. A hex d hops out switches at
t0 + (t1−t0)·(d+1)/(D+1), where D is the furthest hop in its connected
patch. A patch with no B next to it (a new biome appearing) grows out from
its middle. This is deterministic. Water is overridden afterwards by the
sea-level stage.

## Known limits

- The sea-level curve is approximate (read off Lambeck et al. 2014) and has
  no isostatic rebound, so the Baltic and Scandinavia are wrong.
- A coastal hex is sea when more than half of it is below sea level.
  Even at −3000 that disagrees with the raster on about 300 coastal hexes.
- Mountain biomes come from model climate moved to the hex's median
  elevation, so a range whose median is below the treeline shows no alpine
  fringe.
- The Land-gap biomes come from model climate, at 0.5° (one to two cells
  per hex), so southern Arabia looks blocky. On their own, the model's
  biomes match the drawn maps on only 22–45% of hexes: it has desert where
  the drawn Sahara is grassland or savannah, because HadCM3 underplays the
  Holocene monsoon. Calibrated, the match is 74–80% with each 10° tile held
  out, and the report's "Land gaps" table tracks both figures. Calibration
  carries over the drawn maps' class names, including "Savannah" for the
  Pontic steppe band, which extends it east of the Volga and into Turan.
- In Europe the −9000 and −8000 drawings copy Late Glacial maps (Allerød and
  Younger Dryas; `[[terrain.misdated]]`, `data/terrain/SOURCES.md`). There,
  those years are filled from the model, calibrated on the −7000 drawing, so
  −10000 (inside the Younger Dryas) still looks more Holocene than it was:
  the anchors agree there in only 44% of European slices.
- −4000 and −3000 apply the −5000 classifier to later model climate. The
  model barely dries Arabia by then, so Arabia stays largely grassland and
  semi-desert, though the humid period ended around 4000–3000 BCE.
- Köppen is 0.5° model climate (HadCM3, bias-corrected), so it is blocky
  and smooth across coasts. Lapse-corrected, its 0 BP slice matches the
  modern Köppen on 85% of land hexes (93% on the main letter), up from 84%;
  on mountain hexes the figure rises from 67% to 70%, and on high mountains
  from 57% to 61%. Most of the remaining mountain mismatches are aridity
  boundaries (BW/BS/Cs/Ds), which the rainfall drives and the lapse
  correction doesn't touch. Most E (polar) misses are Arctic lowland that the
  model has as Dfc. Mountain hexes
  have biomes now, so they are nudged like any other (the Hoggar and
  Tibesti are BSh grassland at −6000). The nudge follows terrain, so Arabia stays steppe at −3000 (see above).
- Slope and relief come from 2 arc-minute cells (about 3.7 km), coarser than
  the 1 km data the Kapos bands were set for, so slopes read low.

## Settlements

```sh
make settlements   # writes data/settlements/
```

| File in `data/settlements/` | Contents |
|---|---|
| `settlements.geojson` | One point feature per site; `neolith-convert` reads it directly |
| `dates.csv.gz` | Every radiocarbon date behind every site, with lab number and the references its record gives |
| `SOURCES.md` | What to cite: each dataset's citation, licence and retrieval date, and the most-used original references |
| `provenance.json` | Every downloaded file: URL, date, size, SHA-256 |
| `curated.geojson` | Hand entries (input, not generated) |

### Sources

- **[XRONOS](https://xronos.ch)** supplies nearly all dates. It already
  compiles p3k14c, CalPal, RADON, EUROEVOL, NERD, AIDA, 14SEA,
  MedAfriCarbon and others, and each record names where it came from.
  There is one API download per entry in `[settlements.xronos] countries`
  and `site_types`. The country list covers Europe, the Near East and
  Africa north of 6°N.
- **`[[settlements.tables]]`** are extra CSV/TSV tables read after XRONOS:
  p3k14c 2025.07 and the two NeoNet datasets. A date whose lab number is
  already in hand is skipped, so they only add what XRONOS lacks. To add a
  table, add an entry with its column mapping and a
  `[settlements.citations.<name>]` block.
- **Wikidata** (off by default) supplies `wikidata`, `wikipedia` and
  `culture` for sites it classes as archaeological sites with an English
  Wikipedia article. The query runs per 10° tile, one request at a time.
  The query service refused this client without contact details, so set
  `contact` and `enabled = true` under `[settlements.wikidata]` to use it.
  This step has unit tests but has not yet run against the live service.

Downloads are cached in `build/settlements/` (about 660 MB). Delete a
cached file to refetch it.

### Steps

1. **Read**: a date returned by several XRONOS queries is used once. Site
   types are lower-cased and folded through `type_aliases`; an empty type
   becomes `site`. Dates at `exclude_types` (graves, hoards, non-site
   samples), dates with an error above `max_std` and dates off the grid's
   extent are ignored.
   Site names in XRONOS and p3k14c are sometimes UTF-8 that was read as
   Windows-1252 or Mac Roman, once or twice over (`GraviÃ¨re`,
   `Sundfj√¶ra`). Each run of non-ASCII characters is re-read as UTF-8 if
   the result is shorter and in Latin script. What will not decode becomes
   U+FFFD, a lost letter. A name with lost letters takes the one clean
   spelling within `same_name_km` that matches it (`G�bekli Tepe` →
   `Göbekli Tepe`); about 30 sites with no clean twin keep the `�`.
2. **Calibrate**: each date's median calibrated age against IntCal20, on a
   10-year grid. Marine and shell dates get no reservoir correction, so
   they come out a few centuries too old.
3. **Group**: dates sharing a site name and coordinates form one entry.
   Entries are folded into one site when they are within `same_km` and one
   name's words all appear in the other's, or within `same_name_km` with
   the same words. The shortest name is kept and the rest go in `aliases`.
   Compiled sources hold one date once per database, so within a site,
   rows with the same lab number, or the same age and error, count as one
   date and pool their references. A site is kept if at least one date
   falls inside `[time] start..end`.
4. **Date the site**: `founding` and `abandoned` are the `trim` and
   `1 - trim` quantiles of its dates, which is the earliest and latest date
   for sites with fewer than `1/trim` dates. `founding` is a "no later
   than" bound: it reflects what was sampled.
   `occupation` lists phases `[start, abandoned_by]` from the dates
   between those two: dates more than `abandon_after` years apart start a
   new phase, and each phase is assumed to end `abandon_after` years after
   its last date (no evidence for that long is read as abandonment). The
   app hides a site outside its phases. `abandoned_by` is an upper bound
   and the last date a lower one; under-sampled sites will show false gaps.
5. **Wikidata**: an item matches the nearest site within `match_km` whose
   name shares its distinctive words. Items that match nothing and have an
   inception date inside the time window become sites with
   `sources = ["wikidata"]` and no `abandoned` or `occupation` (they never end).
6. **Curated entries**: each one overrides, key by key, the dated site
   whose name or alias equals its `match` property, or else the nearest
   within `merge_km`. With a null geometry it takes that site's point.
   Entries with no dated site are added as they are.
7. **Hex**: each site gets the id of the hex containing it. Sites off the
   grid are dropped.

### Site properties

`name`, `founding`, `abandoned` (last date), `occupation`, `type`,
`population` (empty unless curated), `n_dates`, `importance`, `evidence`, `periods` (the sources' most common period labels,
unnormalised), `hex`, `key`, and where known `aliases`, `wikidata`,
`wikipedia`, `wikidata_culture`, `culture`, `stage` and `features`.

For citation: `sources` lists the datasets the site rests on (the keys of
`[settlements.citations]`, described in `SOURCES.md`), and `references`
lists the original publications and databases its dates cite, most used
first. `dates.csv.gz` joins to sites on `site_id`.

Ids are the curated id, or a CRC32 of `key`, so they stay the same across
rebuilds unless a site's kept name or point changes.

### Piece size and visibility bias

Almost no site has a population figure, so the board sizes pieces from
`importance` (0–3) instead (`score_sites`, `[settlements.importance]`):

- the base is the class of the site type: tells, enclosures, hillforts and
  pile dwellings 3; settlements and houses 2; caves, camps and plain
  "site" 1; pits, hearths, kilns and find-spots 0.
- there is +1 for a long total occupation and +1 for many dates. Both are
  judged against sites within 150 km, not against the whole map, because
  occupation span and date counts grow with research effort. A
  well-dated site in Ireland competes with Irish sites; one in Ukraine
  competes with Ukrainian sites.
- `references` and `sources` are never used, because they measure only
  how much a site has been studied.

A recorded population, where there is one, overrides `importance` in the
app. `evidence` (0–2: one date or none, 2–4, 5+) makes single-date sites
look tentative (pale) rather than smaller.

**Survey intensity** (`survey_intensity`, `[settlements.survey]`,
`data/settlements/survey.csv.gz`) is a detection layer, built with the
"target-group background" idea from species-distribution modelling:

- every dated record of any period and any site type in the cached dumps
  (graves, medieval kilns, Bronze Age hillforts) counts as fieldwork.
- the records are smoothed with a 100 km Gaussian and cut into levels 0/1/2.
- where there are few records of any age, few early sites says little
  about early people. The board hatches those hexes, and `make maps`
  writes the level as a static `survey` hex property.

Limits:
- the layer is time-independent.
- modern borders show through it (national dating programmes).
- it is never an input to expected population density, so the comparison
  between expected and observed sites stays independent.

## Cultures

```sh
make cultures-check   # fetch the cited Wikipedia revisions, record what they support
make settlements      # assigns cultures and stages, writes data/cultures/
```

`data/cultures/cultures.toml` (hand-written) lists archaeological cultures
and broad stages (Mesolithic, Neolithic…). Each entry has a pattern for
the period labels sources put on dates, a few traits from a controlled
vocabulary (economy, pottery, houses, burial, monuments, metal,
domesticates, other), the English Wikipedia article they are cited to,
and, where the article gives one, a date range with the article's own
words for it in `quotes`.

**Citation check.** `make cultures-check` fetches each article and records
its revision id, Wikidata id and permanent URL in
`data/cultures/wikipedia.json`. It lists every trait and range quote the
article text doesn't contain. When the article is broader than the entry
(*Prehistoric Egypt* for Faiyum A), only paragraphs naming the entry
count. The table currently passes with no unsupported traits: traits the
articles didn't back were removed, and cultures with no article were
folded into their stage.

**Assignment.** Many sources label every date at a site with all of the
site's periods (true of 55% of XRONOS sites), so labels say which cultures
were at a site, not which date belongs to which. A date counts toward a
culture only if the site carries its label and the date falls in the
culture's range, ± `range_margin`. A culture without a cited range uses
the central 80% of its labelled dates instead, marked `observed`. A date
two cultures fit counts for neither. Stages work the same way, and a stage
and its `parent` together count as the parent.

**Per site** (`settlements.geojson`), when evidence allows:

- `culture`: `{"-9230": "ppna", "-8510": "ppnb"}`, a step function keyed
  by start year, like the map's year keys
- `stage`: the same for stages
- `culture_dates`: how many dates back each culture
- `culture_inferred`, `stage_inferred`: guesses for dates whose own labels
  give none, from labelled sites nearby (`[settlements.cultures.infer]`:
  at least 2 sites within 50 km attesting it within 250 years, two-thirds
  of the votes, no tie, and the date inside its range). Never merged into
  `culture` / `stage`; prefer those and fall back to these.
- `culture_inferred_support`, `stage_inferred_support`: per inferred id,
  the most sites that agreed and the nearest one's distance in km

A holdout test (each labelled date voted on by the other sites) runs on
every build; its rates are in `data/cultures/SOURCES.md`.

**Outputs in `data/cultures/`:**

- `cultures.json`: every entry with its traits, range (each end marked
  `cited` or `observed`), citation, `unverified` traits, and what the
  dated sites show (site count, start-year spread, centre, extent)
- `SOURCES.md`: the citation table

`build/cultures/unmapped_labels.tsv` lists labels nothing matched, most
sites first, for growing the table.
