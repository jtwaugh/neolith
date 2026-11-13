> **Historical.** This describes the 2023 Django/Leaflet prototype, which was removed on 2026-11-13 (`game/`, `neolithic_deities/`, `manage.py`, `scripts/*.py`). It is kept because the pipeline and `neolith-rs` still cite its formats (§3, §5) and defect numbers. The current project is described in `README.md`; the grid and the per-epoch properties the pipeline still reads now live in `data/legacy/`.

# Neolith (Neolithic Deities): Reverse-Engineered Spec

*Reconstructed from the code, data and git history as of `1e36e62` on `develop` plus the uncommitted working-tree changes (2026-11-11). Development ran from 2023-05-01 to 2023-05-21, 34 commits.*

This spec describes what the code **does**. Where that differs from what it seems **meant** to do, the gap is flagged with ⚠️. Section 9 lists every known defect in one place.

---

## 1. What it is

The README calls it "a Paradox map-staring game but set in the Neolithic era". It's a browser map of Europe, North Africa and Western Asia covered in about 26k hexagons. Each hex has paleo-environmental properties (terrain/biome, Köppen climate, population density) that change over time, from 10,000 BCE to 3,000 BCE. A game clock moves the year forward, and the map re-colours as each hex's properties change. One visible example is the drowning of Doggerland. Known Neolithic settlements appear on the map once they're founded.

Right now it's a **historical visualizer plus a map-data editor**, not a game. There are no players, agents, decisions or simulation rules. Cultures, a tech tree and ancient-DNA samples exist as data files but nothing in the code reads them.

Internal project name: `neolithic_deities`. App name: `game`.

---

## 2. Architecture

```
Browser (single page: /game/)
  Leaflet 1.7.1 map + d3 v6 colour scales + Ace 1.4.13 JSON editor
  main.js keeps the client state: hex layer, update cache, settlements, clock
        │  fetch (JSON)
        ▼
Django 4.2 (neolithic_deities project, "game" app)
  views.py: thin JSON endpoints
  hex_processing.py: loading, diffing, adjacency
  State lives ONLY in LocMemCache (in-process memory). No DB models.
        │  reads once
        ▼
game/static/game/assets/combined_map.geojson (27.7 MB, every hex × every epoch)
```

- **Backend:** Django 4.2, Python 3.8 (Elastic Beanstalk platform). SQLite is configured but holds only Django's built-in auth/session tables. `game/models.py` is empty.
- **Server state:** `django.core.cache` with the `LocMemCache` backend. It's per-process and lost on restart.
- **Frontend:** one Django template (`game.html`), one script (`main.js`, about 600 lines, no build step) and `styles.css`. Libraries are loaded from CDNs.
- **Deployment:** AWS Elastic Beanstalk. The app is `neolith`, the env `neolith-test` is mapped to the `develop` branch, region `us-west-2`, and the WSGI path is `neolithic_deities.wsgi:application`.

---

## 3. Data model

### 3.1 Hex grid

- **Geometry:** flat-topped hexagons in WGS84 lon/lat degrees. Each is about 0.577° wide and 0.5° tall. Coordinates are not equal-area, so hexes shrink on the ground as latitude rises.
- **Extent:** longitude −16.5° to 66.0°, latitude 6.1° to 75.9°. That covers Iceland's latitude band and Iberia east to Central Asia, and the Sahel north to the Arctic.
- **Count:** 26,410 features, with ids 1 to N.
- **Origin:** made with QGIS "Create Grid" (hexagon). The `left/top/right/bottom` attributes and the `*_majority` zonal-statistics fields are QGIS output.

### 3.2 `combined_map.geojson` (the canonical dataset)

This is a GeoJSON `FeatureCollection`. Each feature looks like this:

```jsonc
{
  "type": "Feature",
  "geometry": { "type": "Polygon", "coordinates": [[[lon, lat], ...7 points]] },
  "properties": {
    "id": 1,
    "left": -16.46, "top": 75.86, "right": -15.89, "bottom": 75.36,   // bbox, used for adjacency
    "terrain":            { "-10000": "Water", "-9000": "Water", ..., "-3000": "Water" },
    "climate":            { "-10000": "Ocean", ... },                  // Köppen code string
    "koeppen":            { "-10000": 0.0, ... },                      // Köppen index 0–30
    "population_density": { "-10000": 0.0, ... }                       // people/km² (rough)
  }
}
```

- **Time-keyed properties.** Every property in `HEX_PROPERTIES = ["terrain", "climate", "koeppen", "population_density"]` is a map from **year to value**. Year keys are strings of **negative integers** (BCE as negative numbers): `-10000, -9000, -8000, -7000, -6000, -5000, -4000, -3000`.
- **Value semantics:** a value holds from its key-year until the next key-year (a step function). There's no interpolation.
- **Terrain vocabulary** (as found in the data): Water, Plains, Mountains, Land, Boreal Forest, Grassland, Savannah, Temperate Forest, Semi-Desert, Extreme Desert, Chaparral, Woodlands, Ice, Steppe-Forest, Tropical Forest, Unknown. The categories match published paleovegetation map legends.
- **Köppen index:** 0 = Ocean, 1 to 30 = Af … EF, 31 = "missingno". The mapping is in `scripts/koeppen_to_terrain.py` and `pipeline/koeppen.py` (`CODES`). The pipeline classifies it per key frame from Beyer et al. 2020 paleoclimate (see `pipeline/README.md`); the committed epoch files hold only modern Köppen.
- **Population density buckets:** 0.0, 0.1, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 5.0. These come from raster grey levels via a hand-written lookup. The commit message calls them "extremely speculative".

⚠️ **Data quality by epoch.** Only **−9000 through −5000** carry detailed biome terrain, digitised from `raw/maps/composite/*`. The **−10000, −4000 and −3000** layers hold placeholder terrain (just Plains, Water, Mountains and Ice). `4000_bce.geojson` and `3000_bce.geojson` are byte-identical. So at −4000 the map goes from detailed biomes back to generic "Plains". "Land" (about 16k hex-epochs) and "Unknown" (203) are leftover categories from the RGB conversion.

### 3.3 Per-epoch source maps: `assets/maps/{N}_bce.geojson`

These are the same grid, with one file per epoch and scalar properties plus intermediate fields (`red_majority`, `green_majority`, `blue_majority`, `population_density_index`). They're the inputs to `create_hex_history.py` and the client never fetches them. Together they're about 250 MB in git.

### 3.4 Settlements: `assets/settlements.geojson`

Despite the extension, this is a **JSON array** of feature-like objects, not a FeatureCollection:

```jsonc
{ "id": 2,
  "properties": { "name": "Çatalhöyük", "founding": -7400, "type": "settlement",
                  "population": { "-7400": 3000, "-7300": 3500, ... } },
  "geometry": { "type": "Point", "coordinates": [lon, lat] } }
```

There are 12 entries: Çatalhöyük, Jericho, Göbekli Tepe, Ain Ghazal, Tell Sabi Abyad and Beidha, plus six generic "Hunter-Gatherer Settlements". Ids 7 and 8 are duplicates at the same point. Population is a sparse year-to-count map, usually every 100 years.

`settlements.json` is the older source. It uses positive BCE years and puts `population` at the top level. `scripts/fix_settlements.py` moved `population` into `properties`. The sign flip of the years was done some other way.

### 3.5 Unused data

| File | Contents | Status |
|---|---|---|
| `cultures.json` | 6 archaeological cultures (Cardium, LBK, Vinča, TRB, Cucuteni-Trypillia, Yamnaya), each with an ancestry `gene_pool` (EEF/WHG/EHG/CHG/ANF/SP fractions) and `material_practices` | Not referenced. ⚠️ Not valid JSON (trailing commas). |
| `tech_tree.json` | 17 tech nodes, each with `dependencies` and `unlocks`, e.g. basic_tools → agriculture → animal_husbandry → horse_domestication → wheeled_vehicles | Not referenced. ⚠️ Not valid JSON. ⚠️ Not consistent: `unlocks` names culture pottery types and `metallurgy` that don't match the `dependencies` edges. |
| `dna_artifacts.csv` | 16,388 ancient-DNA samples (id, age BP, death date, lat/lon, Y and mtDNA haplogroups). Looks like an AADR export. | Not loaded. The template has a placeholder `.dna-info` panel. |
| `chad icons.jpg` | Image | Not referenced. |
| `raw/maps/**` | Source paleo-terrain rasters (Europe GIFs for 12k–5k BCE, Africa, composite PNGs georeferenced with `.pgw`/`.aux.xml`) | Untracked, offline inputs only. |

Taken together, these show where the game was headed: cultures with genetic make-up spreading across hexes, with techs gating their practices.

---

## 4. Offline data pipeline (`scripts/`)

The scripts are run by hand from the repo root, and most were later superseded. In order:

1. **QGIS (manual):** georeference the source rasters, build the hex grid, and run zonal-statistics "majority" per RGB band for terrain, plus Köppen and population rasters.
2. `koeppen_to_terrain.py`: reads `hex_pop.geojson`, sets `climate` = the Köppen code string, sets placeholder `terrain` 0/1 (water/land), and writes `maps/5000_bce.geojson`. *(Early bootstrap.)*
3. `get_pop_indices.py`: prints the distinct `population_density_index` values (used to build the lookup).
4. `convert_population_density.py`: maps grey-level index to people/km² for all 8 epoch files, in place.
5. `convert_terrain.py`: maps `(r,g,b)` majority to terrain name for epochs 9000–5000 only, in place. Prints any unmatched RGB values, which become "Unknown".
6. `create_hex_history.py`: merges the 8 epoch files into `combined_map.geojson` with year-keyed properties (see §3.2). **This is the only step whose output the app reads.**
7. `fix_settlements.py`: settlements.json → settlements.geojson.
8. `add_cultures.py` / `add_resources.py`: identical scripts that write **random** resources, terrain and climate into a now-missing `hex.geojson`. These are from the prototype stage and are obsolete.

⚠️ None of these scripts is wired into the app, and the intermediate inputs (`hex_pop.geojson`, `hex.geojson`) aren't in the repo, so the pipeline can't be reproduced from what's committed.

---

## 5. Backend API

Every route is under `/game/`. Responses are JSON unless noted. "Requires cache" means the route returns HTTP 400 *"Hexagon data not cached. Call cache_hexagon_data first."* unless `cache_hexagon_data/` has run in the same process.

| Method | Path | Behaviour |
|---|---|---|
| GET | `/game/` | Renders `game.html` and injects `HEX_PROPERTIES` and `COLOR_SCHEMES` from settings as JS globals `hexProperties` and `colorSchemesData`. |
| GET | `cache_hexagon_data/` | Loads `combined_map.geojson` into cache key `hexagon_data` if absent. Returns `{success, message}`. |
| GET | `prepare_hex_updates/` | Requires cache. Computes the **change log** (below), stores it as `hex_updates` and returns the whole log. |
| GET | `get_current_hexes/<int:Y>/` | Requires cache. `Y` is a **positive BCE year**. Returns a JSON array of features whose properties are flattened to their values at year `−Y` (latest key ≤ −Y). The bbox fields are dropped, and a property with no key ≤ −Y is left out. |
| GET | `get_hex_updates/<int:year>/` | Requires cache. Returns `hex_updates[year]` or `{}`. ⚠️ Unused by the client, and the URL converter can't take negative years. |
| GET | `get_hex_updates_range/<int:start>/<int:end>/` | Requires cache (returns 404 if missing) and requires `hex_updates` (400). Returns `{year: updates}` for every integer year in `range(−start, −end)`, so empty years come back as `{}`. |
| GET | `get_hexagon_data/` | Returns the whole raw dataset, loading it if needed. ⚠️ Unused. It's 27 MB. |
| GET | `get_hex_by_id/<int:id>/` | Requires cache. Returns the raw (time-keyed) feature, or `{"error": ...}` with HTTP 200 if not found. |
| POST | `update_hex_by_id/<int:id>/` | `csrf_exempt`, no auth. The body is a full feature JSON. Forces `properties.id = id`, replaces the feature in the cached dataset and returns plain text. ⚠️ Doesn't rebuild `hex_updates`, so playback ignores the edit. Edits are never saved to disk. |
| GET | `generate_adjacency_map/` | Requires cache. Returns `{hexId: [neighbourIds…]}` (see below). |
| — | `/admin/` | Default Django admin (no models registered). |

`views.save_hex_data` is dead code with no route.

**Change log (`process_hex_updates`):** for each hex and property, walk the year keys in file order (−10000 to −3000) and record `hex_updates[year][hexId][property] = value` whenever the value differs from that hex's previous value. The −10000 entry is always recorded, so the first year's log holds the full initial state. Year keys are Python ints. In practice the log has entries only at the 8 epoch years.

**Adjacency (`process_adjacency_map`):** grid column = `round((left − minLeft) / (0.75·width))`. Grid row = `round((top − minTop + offset) / height)`, where even columns are shifted by −½·height. Neighbours use the "even-q / odd-q" offset tables for flat-topped hexes. This was fixed in `f9ba47e`.

---

## 6. Frontend behaviour

### 6.1 Screens and layout

1. **Start screen:** title "Neolithic Deities", a numeric *Start Year* input (default **−7500**, negative = BCE) and a **Start Game** button.
2. **Game screen** (shown after Start):
   - Leaflet map in an 800×600 container, centred at (39.07, 21.82) with zoom 4. There are **no base tiles**, only hexes over a light-blue background.
   - A **map-mode selector** (Leaflet control, top-left): *Koeppen*, *Terrain* or *Population_density*. Changing it restyles every hex and rebuilds the palette.
   - A **Year display** ("Year: −7500").
   - A **hex info panel** (fixed, top-right) showing Terrain, Climate Code, Koeppen Index, Resources, Agriculture Adoption, Trade Route Quality, Caloric Surplus and People/km², plus an **Edit JSON** button. ⚠️ Resources, agriculture, trade and caloric fields don't exist in the data and always show blank.
   - A **settlement info panel** (name and population), shown when a settlement marker is clicked.
   - A **control panel**. *Uncommitted change:* a toggle switch flips between **Game Mode** and **Editor Mode**:
     - *Game controls:* Pause/Play button, a speed slider from 1 to 100 years/second, and a years/sec readout.
     - *Editor controls:* colour palette, tool buttons (pencil, paint bucket, lasso, select-all, deselect-all), Undo, Redo, Download JSON, a file input and Upload JSON. Turning on Editor Mode pauses the clock if it's running.
   - A **JSON editor** (Ace, JSON mode) docked at the bottom with Save and Cancel.

### 6.2 Load sequence (on Start)

1. `startYear = currentYear = input value`.
2. `loadData()`, run in order:
   1. `GET /game/cache_hexagon_data/`
   2. `GET /game/prepare_hex_updates/` (⚠️ the response is the full change log, about the size of the dataset, and the client throws it away)
   3. `GET generate_adjacency_map/` → `adjacencyMap`
   4. Add the map-mode control.
   5. `GET get_current_hexes/{−startYear}/` → for each hex, `hexIdMap[id] = feature`, and wrap it in its own `L.geoJSON` layer inside `hexLayer` (an `L.layerGroup`). That's about 26k layers. Fill comes from the d3 ordinal scale for the current mode, with a grey 0.3px stroke and opacity 1.
   6. Build the colour palette.
   7. Fetch `settlements.geojson`. Show markers for settlements already founded, and index the rest into `settlementUpdates[foundingYear]`.

Relative URLs in steps 3 and 5 only resolve because the page is served at `/game/` with a trailing slash.

### 6.3 Clock and playback

- **Intended model:** the year advances by 1 each tick. Each tick runs `updateVisibleSettlements()` (adds markers founded this exact year) and `updateVisibleHexes()` (applies this year's change-log entries).
- **Speed slider (`adjustGameSpeed`):** replaces the interval with one of `1000 / yearsPerSecond` ms (1 to 100 years/s) that runs both updaters. **This is the only code path that drives map updates.**
- **Hex update fetching:** updates are fetched in 10,000-year batches via `get_hex_updates_range`, cached client-side in `updatesCache[year]` and applied by walking `hexLayer.toGeoJSON()` and re-rendering each changed hex.
- ⚠️ **The clock doesn't start on its own.** `startGame` never starts an interval, but the button reads "Pause". The first click on Pause/Play starts a 1 s/year interval that **only increments the year counter**. It doesn't update hexes or settlements, and it ignores the speed slider. The simulation only runs after the slider is moved, and pausing and resuming with the button falls back to the counter-only timer.

### 6.4 Settlements

A settlement gets a marker (`settlement-icon.png`, 32×32, z-offset 1000) once `founding ≤ currentYear`. Clicking it shows the name and the population at the latest population key ≤ currentYear. Settlements never disappear. `populationUpdates` is computed but not used.

### 6.5 Hex interaction (depends on `editingMode`)

- **`select`** (default): show the info panel, remember `selectedHexData`, and outline the hex in red (`selectedHexLayer`).
- **`pencil`**: set the current map-mode property to the selected palette value and re-render that hex.
- **`paintbucket`**: flood-fill from the clicked hex across neighbours (via `adjacencyMap`) that share its value for the current mode.
- **Palette:** one swatch per value in the mode's colour-scheme domain. Clicking a swatch sets `selectedProperty`, which is read from a `data-` attribute and so is always a **string**.
- Tool buttons turn red when active, but nothing resets the other button or offers a way back to `select` mode.
- Lasso, select-all, deselect-all, undo, redo and upload have **no handlers**. Their icons point at `game/icons/*.png`, and that folder doesn't exist.

### 6.6 JSON editing and export

- **Edit JSON:** fetches the raw time-keyed feature (`get_hex_by_id`), loads it into Ace and hides the info panel.
- **Save:** parses the JSON, POSTs it to `update_hex_by_id`, then shows an `alert()` with the result. Changes only reach the server's in-memory cache. The map on screen isn't re-rendered.
- **Download JSON:** downloads `hexLayer.toGeoJSON()` as `map.geojson`. That's the **current-year flattened snapshot**, so it's not round-trippable into `combined_map.geojson`.

### 6.7 Colour schemes (`settings.COLOR_SCHEMES`)

These are d3 `scaleOrdinal` with explicit domain and range:

- **koeppen:** domain 0 to 30, using the standard Köppen–Geiger palette (ocean = `#184a85`).
- **terrain:** 15 named biomes with hand-picked colours.
- **population_density:** 9 buckets on a black-to-white greyscale.

---

## 7. Configuration and running

- Run: `python manage.py runserver`, then open `http://127.0.0.1:8000/game/`. ⚠️ The README says `python settings.py runserver`, which is wrong.
- Only Django is really needed. `requirements.txt` also lists dev tools (snakeviz, virtualenv, tornado), and ⚠️ `six` is pinned to a local macOS `file:///AppleInternal/...` wheel, so `pip install -r` fails anywhere else, Elastic Beanstalk included.
- Settings: `DEBUG=True`, the `SECRET_KEY` is committed, and `ALLOWED_HOSTS=[]`.

---

## 8. Git workflow

Work happens on `develop` and gets merged into `main` through PRs #1–#16. The Elastic Beanstalk test env tracks `develop`. The working tree has uncommitted changes (the game/editor mode toggle and `.ebextensions/`) and untracked `raw/`, `.gitignore` and `requirements.txt`. `.DS_Store` files and `db.sqlite3` are committed.

---

## 9. Known defects and gaps

**Correctness: playback**
1. The clock only drives map updates after the speed slider is moved. Pause/Play starts a timer that only counts (§6.3).
2. `applyUpdates` skips falsy values (`if (update[prop])`), so any change **to** `0`/`0.0` never shows. That includes koeppen=0 (Ocean) and density=0, which is exactly the Doggerland-flooding case for those modes.
3. `updateSingleHex` calls `hexLayer.removeLayer(feature)` with a plain feature object, not the layer. Nothing gets removed, and each update **stacks a new layer** on top of the old one. Memory and render cost grow with every epoch change and every edit, and Download JSON exports duplicates.
4. `applyUpdates` serialises the whole 26k-hex layer (`toGeoJSON()`) on every epoch year, and re-renders a hex once per changed property.
5. Year −1 is never inside any fetched batch, so it's refetched on every tick.
6. Ticks can fire before `hexLayer` exists if the slider moves during loading, and then they throw.

**Correctness: editor**

7. The flood fill **loops forever** when the selected value equals the clicked hex's value. The guard only logs and doesn't return. This is the "doesn't *always* crash the browser" from the commit log.
8. The palette value is a string, so painting numeric modes (koeppen, population) writes `"4"` instead of `4`. d3's ordinal scale then **extends its domain implicitly** and picks the wrong colour.
9. `openJSONEditor`'s pause check is inverted (`if (!intervalID) toggleGamePause()`), so it **un-pauses** a paused game.
10. On an id mismatch, `saveJSON` alerts and then saves anyway. Cancel isn't wired.
11. Server-side edits don't rebuild `hex_updates`, don't refresh the client map and vanish on restart.
12. There's no way to go back to select mode after choosing pencil or bucket. The tools' active highlighting never clears.
13. Two elements share `id="download-json"`, and Upload does nothing.

**Data**

14. "Land" and "Unknown" terrain aren't in the colour domain, so d3 assigns them recycled colours. "Land" probably renders in the Ice colour.
15. Population-density domain order is `…0.8, 1.5, 1.0, 2.0…`, so 1.0 renders **lighter** than 1.5. The lookup in `convert_population_density.py` (199→1.5, 215→1.0) looks wrong at the source.
16. The −10000, −4000 and −3000 epochs are placeholders (§3.2). 4000 and 3000 are identical.
17. `settlements.geojson` isn't valid GeoJSON. Settlements 7 and 8 are duplicates.
18. `cultures.json` and `tech_tree.json` aren't valid JSON.
19. Info-panel fields (resources, agriculture, trade, caloric surplus) have no data behind them.

**Architecture and ops**

20. LocMemCache is per worker process. Under Elastic Beanstalk with multiple workers, `cache_hexagon_data` on one worker and `get_current_hexes` on another gives "not cached" errors.
21. LocMemCache pickles on every `get`, so each request, even `get_hex_by_id`, deserialises the full 27 MB dataset.
22. `prepare_hex_updates` sends the whole change log to a client that discards it.
23. Deploy blockers: `ALLOWED_HOSTS=[]`, `DEBUG=True`, a committed secret key, a broken `requirements.txt`, and no `STATIC_ROOT` collection step.
24. `update_hex_by_id` is CSRF-exempt and unauthenticated (fine locally, not on a public host).
25. About 250 MB of per-epoch GeoJSON is committed to git, but the app only needs `combined_map.geojson`.
26. Minor: `console("…")` (not a function) in `startGame`. Implicit globals (`selectedColor`, `modeLabel`, `data`). Nested `<head>` in the template. A deprecated `initMouseEvent` call. `try/catch` around un-awaited async calls.
27. There are no tests (`game/tests.py` is empty).

---

## 10. Implied roadmap (from data and stubs, not built)

- **Editor completion:** lasso and multi-select, undo/redo, upload a GeoJSON to replace the dataset, and saving edits back into the time-keyed format and to disk.
- **Cultures layer:** hexes or settlements owned by cultures from `cultures.json`, with ancestry mixes that change through migration and admixture. Ancient-DNA samples (`dna_artifacts.csv`) shown as clickable points with haplogroups (the `.dna-info` panel is already in the template).
- **Tech tree:** `tech_tree.json` gating each culture's material practices (pottery styles, megaliths, horse domestication, wheeled vehicles).
- **Hex economy:** resources, agriculture adoption, trade-route quality and caloric surplus per hex (the info panel already has slots for them), likely driving population density and settlement growth.
- **"Deities":** the project name suggests the player acts as a god influencing cultures. Nothing in the code implements this yet.
