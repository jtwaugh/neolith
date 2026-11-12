# Grand-strategy look & feel rubric

The critic agent (`.claude/agents/gsg-critic.md`) scores Neolith against this
rubric, using screenshots from the running app (`harness/neolith.py shot`)
next to reference screenshots of shipped games (`harness/neolith.py refs`,
saved under `build/critic/refs/<game>/`).

Score each category **0–5** against the anchors. Every score must cite at least one
Neolith screenshot and, where it helps, one reference image by path, plus what
the state readout (`neolith.py state`) showed at that moment.

| Score | Meaning |
|---|---|
| 0 | Missing entirely |
| 1 | Present but reads as a debug tool or data viewer |
| 2 | Functional; clearly a prototype |
| 3 | Competent indie strategy game |
| 4 | Close to a mid-budget shipped title |
| 5 | Matches the Victoria 3 / CK3 bar |

## 1. The map as the hero (weight 3)

The map should fill the screen and be the thing you want to stare at.
- **Victoria 3** (the main benchmark): the map is a full-bleed living diorama.
  Zoomed in, it shows terrain, cities and moving traffic ("living map"). Zoomed
  out, it becomes a stylized paper map with painted labels. UI panels float over
  the map, which runs to all four screen edges.
- **CK3**: three zoom levels, and the far zoom turns into a hand-drawn paper map
  with sea monsters.
- Check: does the board run edge to edge, or does it sit in a grey studio void?
  Is there a far-zoom "overview" style, separate from the close terrain? Can you
  see what each tile is without a legend? Does the camera always end up somewhere
  sensible, or can it get lost?

## 2. Map labels & typography (weight 2)

- Paradox games print region and realm names *on the map*, curved and letter-spaced
  along the shape of the region, and sized to the region. Seas are named in italics.
- Check: are geography, seas, rivers and cultures named on the map? Are settlement
  labels readable over every terrain? Is the UI font characterful, or is it
  egui's default?

## 3. Map modes & legibility of information (weight 2)

- EU4, HOI4 and Victoria 3 offer one-click map modes, and each has a legend or
  tooltip that explains the colours. Borders separate political units, and
  terrain shows through the political colours.
- Check: is there a legend for every mode? Are the colour ramps perceptually
  ordered (population, elevation)? Does the Köppen mode explain its codes? Is
  there a political/cultural mode? (There's no data for one yet, so call it a gap.)

## 4. Time & pacing controls (weight 2)

- The industry standard is a date readout plus 5 speed steps plus pause, in a
  fixed corner (top right in Victoria 3 and HOI4, bottom right in CK3), with
  keyboard 1–5 and Space.
- Check: is the clock readable at a glance? Do speed steps mean something? Does
  something *happen* when time passes (events, notifications, an outliner)?

## 5. Information architecture: panels, tooltips, outliner (weight 2)

- Victoria 3 uses a left panel for the selected object, a right-hand outliner
  (journal, pinned items) and a top bar of national stats with nested tooltips.
- Check: does the inspector feel like an in-world dossier, or like a property
  sheet? Is there an outliner? Are there any top-bar resources or stats? Do the
  tooltips explain things?

## 6. Art direction & UI skin (weight 2)

- Paradox UIs carry period-themed frames (Victoria 3 brass and velvet, CK3
  parchment, and so on). **Old World** and **Civ VI** show a coherent stylized
  look on a hex/tile map, and are the closest precedent for a hex board.
- Check: does the UI share the map's visual language (a Neolithic theme: stone,
  ochre, fibre, bone), or is it stock dark-mode egui? Are the terrain art,
  palette and lighting consistent?

## 7. Playability: is there a game here? (weight 3)

Actually try to play. Look for a player entity, goals, decisions, feedback and
consequences.
- Check: what can the player *do* besides watch and inspect? Is there an
  objective? Does any input change the simulation? Report honestly. A beautiful
  map viewer with no verbs scores 0–1 here, whatever the art looks like.

## 8. Feel: camera, interaction & feedback (weight 1)

- Check: zoom-to-cursor, smooth pans, a hover highlight and click feedback.
  Does double-click glide? Do pieces and labels reflow sensibly when zoomed? Are
  there dead clicks?

## 9. Biome map aesthetics (weight 3)

This one is about the terrain map *as a picture*: does the land read as a
believable, beautiful landscape, or as a spreadsheet coloured in? Judge it at
three zooms (far ≈ 1.2–1.6, mid ≈ 0.35, close ≈ 0.1), and in at least four
transition zones:
- Sahara to Sahel (desert, semi-desert, savannah);
- the Pontic steppe to forest (grassland, steppe-forest, temperate and boreal forest);
- the Mediterranean rim (chaparral, woodlands, mountains);
- the Fertile Crescent into the Zagros (grassland, semi-desert, mountains);
- the far north (boreal forest, tundra, ice), if visible.

- **Borders between biomes.**
  - *Abrupt or unnatural:* hard single-hex steps; long straight runs or perfect
    staircases along the hex grid; rectangular blocks; edges that follow the
    keyframe maps' digitising rather than geography (a ruler-straight edge across
    a plain).
  - *Implausible neighbours:* biomes that meet without the ecotone you'd expect,
    such as Extreme Desert next to Temperate Forest, or Ice next to Grassland.
  - *Noise:* checkerboards, salt-and-pepper speckle and lone single hexes that
    read as noise.
  - Use `pick`/`hex` on both sides of a border to name the biomes, and say where
    (lon/lat).
  - **Reference:** CK3's terrain map, where biomes blend over soft painted edges
    and the province borders sit on top as a separate layer, and Old World's
    tile art, which blends across tile edges.
- **Palette harmony.**
  - Do neighbouring biome colours clash (two similar yellows, such as Grassland
    and Savannah; or a lurid green next to a muddy one)?
  - Is the saturation consistent?
  - Does water read as water against the land?
  - Is there a clear value hierarchy, with water darkest or lightest
    consistently, deserts warm and forests cool?
- **Layer clashes.** The board stacks these layers:
  - flat tile colour;
  - grout lines between hexes;
  - bevel;
  - region borders;
  - hillshade;
  - relief steps (cliffs between raised tiles);
  - printed terrain art (2D) or raised props (3D);
  - biome-edge blending and shore foam;
  - rivers and lake shorelines;
  - settlement pieces;
  - map labels;
  - the legend.

  Which of them fight each other? For example:
  - grout plus region borders double up into a heavy hex mesh;
  - hillshade muddies the biome colours;
  - relief cliffs read as walls between biomes;
  - the 2D art pattern moirés at mid zoom;
  - 3D props hide the colour;
  - river lines are lost against forest green;
  - labels sit on busy art.

  **Isolate each layer with `set`** (`--hillshade 0`, `--borders 0`,
  `--grout 0`, `--art off|2d|3d`, `--art-blend false`, `--relief false`,
  `--flat-lighting true`, `--rivers false`). Compare screenshots of the same
  view with the layer on and off, and say which layers earn their place at
  which zoom.
- **Scale and level of detail.**
  - Does the hex grid dominate when zoomed out (a visible honeycomb texture at
    far zoom is a smell), and does it disappear or stay readable close in?
  - Does the art density suit each zoom?
- **Change over time.**
  - Play across a few keyframes and watch a border. Do biomes jump in blocks?
  - Does a change read as a natural front or as a recolouring?

Score anchors for this category:
- **1:** the land reads as coloured hexes;
- **3:** pleasant, with visible grid artefacts and some clashing layers;
- **5:** reads as one painted landscape at every zoom, like CK3's terrain map.

**Overall** = the weighted mean, rounded to 0.1, of all nine categories
(weights 3, 2, 2, 2, 2, 2, 3, 1, 3, summing to 20).

## Report format

Write `build/critic/<YYYYMMDD-HHMM>/report.md` with:
1. A one-paragraph verdict, then the overall score.
2. A table: category, score, one-line justification.
3. A section per category: what you saw (with screenshot paths), the matching
   reference (with path), and the **top 1–3 concrete changes**. The biome
   aesthetics section also gets a list of named problem spots (lon/lat, the
   biomes on each side, a crop path) and a layer table (layer, keep / tone down /
   drop, at which zoom, and why). Name the code
   where the state readout or your reading points to it (for example
   `neolith-rs/crates/app/src/panels.rs`).
4. A play log: the actions you took, in order, with what the state readout
   reported after each.
5. A prioritized backlog: the 5 changes that would most raise the score per unit
   of effort.

## References

The rubric uses these sources. Reference screenshots come from each game's
Steam store page via the Steam `appdetails` API (`neolith.py refs`), go to
`build/critic/refs/` and are never committed.

- Victoria 3 Dev Diary #49, Graphics Overview: https://forum.paradoxplaza.com/forum/developer-diary/victoria-3-dev-diary-49-graphics-overview.1530190/
- Victoria 3 Dev Diary #50, Living Map: https://forum.paradoxplaza.com/forum/developer-diary/victoria-3-dev-diary-50-living-map.1531318/
- Victoria 3 Dev Diary #121, Maps Maps Maps: https://forum.paradoxplaza.com/forum/developer-diary/victoria-3-dev-diary-121-maps-maps-maps.1687572/
- CK3 Dev Diary #2, The Medieval Map (three zoom levels, paper map at far zoom): https://forum.paradoxplaza.com/forum/developer-diary/ck3-dev-diary-2-the-medieval-map.1274052/
- CK3 Dev Diary #25, Map Features and Map Modes: https://forum.paradoxplaza.com/forum/threads/ckiii-dev-diary-25-map-features-and-map-modes.1388210/
- CK3 Dev Diary #28, Art Focus: https://forum.paradoxplaza.com/forum/developer-diary/ckiii-dev-diary-28-art-focus.1393627/
- Steam store pages: Victoria 3 https://store.steampowered.com/app/529340/ ·
  Crusader Kings III https://store.steampowered.com/app/1158310/ ·
  Europa Universalis IV https://store.steampowered.com/app/236850/ ·
  Hearts of Iron IV https://store.steampowered.com/app/394360/ ·
  Old World https://store.steampowered.com/app/597180/ ·
  Civilization VI https://store.steampowered.com/app/289070/
