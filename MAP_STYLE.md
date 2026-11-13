# Map Style Brief

*How the Neolith map should feel. Drawn from Paradox, Creative Assembly and Firaxis dev diaries and interviews (research pass 2026-11-13). Sources at the end.*

## The one-line version

**A calm, readable, living land that the player keeps wanting to look at. It is the stage and the UI sits on top of it, so it shouldn't shout.**

## What the three studios agree on

1. **The map is the game's main screen, so it has to work as a tool.** CK3's art team wanted a map that is "useful as well as moody and pretty", so players have a reason to visit it. For example, terrain type should read at a glance without switching map modes. Firaxis made the map "more important" in Civ VI and built the whole art style around that.
2. **Soothing beats spectacular.** Victoria 3's art director wanted the map "very interesting yet soothing enough not to compete in complexity with the interface". The UI palette is chosen to sit on top of the map, not to match it.
3. **Hierarchy comes from scale and complexity, not saturation.** Vic3 directs the eye by balancing how detailed and how large each asset is. CK3 #177 says "important interactable objects should pop more". Everything else steps back.
4. **Each zoom level shows its own layer of detail.** Creative Assembly (*Three Kingdoms*): "We always layer the details". Zoomed out, fog and depth blur "bring it all together". In Paradox games the paper map *is* the zoomed-out terrain map, with small illustrations added. CK3 #177 put a lot of effort into blending between zoom levels and removing pop-in.
5. **Readability holds at the default zoom.** Firaxis designed for the zoomed-out view players actually use ("you want to see the world as a whole"). Things are told apart by **silhouette and shape**, not fine texture.
6. **The map records what happened.** Vic3's "living map" shows farms, mines and forestry as marks on the land, and war damage builds up where battles repeat. In Civ VI, a war-damaged sphinx stays visible on the map. The map should show the history of the game being played.
7. **The look comes from period art.** Civ VI uses Age-of-Exploration cartography. In the fog, sketched hand-drawn trees "melt" into real ones. *Three Kingdoms* uses ink wash and Chinese landscape painting. CK3's *All Under Heaven* paper map uses shan shui brushwork. Each era gets the drawing style of its own world.
8. **Plausibility is part of the fantasy.** Civ VII's map team: "when the maps don't feel plausibly Earth-like, it detracts from the experience." Straight edges and repetitive shapes were the problems they worked hardest to remove. CA built *Thrones of Britannia* on real height data.
9. **Historical accuracy is guarded down to small details.** CK3 repainted sunflowers out of a loading screen after testers pointed out they were anachronistic.
10. **Atmosphere stays secondary and can be turned off.** Cloud shadows, weather, day/night and waves add life. CK3 makes them toggleable, and none of them is allowed to hide information. Map text should "feel less digital and easier on the eyes".

## Rules for Neolith

**Feel.** Quiet, earthy, a little hopeful: a world getting greener and fuller. Think of a naturalist's survey plate, not a satellite photo or a board game.

**Palette.**
- Use muted, natural biome colours: steppe ochres, forest greens, wetland olive, cold grey-blue ice. Keep saturation for things that are interactive or that changed recently (a newly founded site, a drowning coast, a new spread of farming).
- Political and cultural overlays are translucent washes over the terrain, never opaque fills. The land should always show through.
- Water is dark and calm so coastlines read strongly. Coastlines matter a great deal in this period: Doggerland, the Black Sea, the Persian Gulf.

**Hierarchy, from loudest to quietest:**
1. Selection and anything the player can click
2. Famous sites and their labels
3. Changes happening now (sea-level rise, farming fronts, new settlements)
4. Rivers and coastlines
5. Biome texture
6. Atmosphere (clouds, weather)

If a lower layer is louder than a higher one, that's a bug.

**Zoom levels.**
- *Far:* the globe on its table. The board is a painted atlas laid on a sphere: biome washes, major rivers, sea, region names in a spaced-out serif face, a few illustrated icons (megaliths, tells, lake villages). No hex lines.
- *Mid:* the default play view. Terrain reads at a glance, site pieces appear, and hex edges show faintly or only on hover.
- *Near:* detail fills in, such as individual houses, fields, livestock and boats. Give the player a reason to zoom in on Çatalhöyük.
- Blend smoothly between levels. Nothing should pop in at a hard threshold.
- **Crisp at every distance.** Like a printed survey plate, borders are sharp edges at any zoom, never soft gradients: a coast or a forest edge is a clean curved line, not a blur. Smooth means the line's shape, not its edge.

**The hex grid is scaffolding.** Players should see a landscape, not cells. At every zoom, coasts and biome boundaries must cut across hexes, not trace their edges: hiding the grid lines while the coast stays stepped is not a pass. Relief is one continuous surface, not raised tiles with cliffs. Rivers follow the real geography. The crisp hex board is for the editor (and the "edge blending" switch off). **Straight lines and grid-shaped edges are the most obvious sign of a fake world.** Civ VII and our own terrain-critic and smooth-critic all point at the same problem.

**Time shows on the land.** Over the game's 7,000 years the map should visibly:
- open clearings around farming villages
- spread fields and pasture
- grow tells in height
- add worn routes between sites
- drown coasts

Leave scars: abandoned sites fade to ruins instead of disappearing. This is our version of the "living map", and it is what keeps a map-staring game interesting.

**Evidence and speculation look different, quietly.** This is specific to Neolith. Data map modes are a wash over the terrain, never an opaque fill, and the sea stays sea. Recorded values get the strongest wash; judged and extrapolated values keep the same hue at a fainter wash, so a guess reads as a lighter hand, not a different colour. They should be visibly the cartographer's guess without looking broken, and never so loud that the gaps dominate the map.

**One mark, one meaning.** Hatching means only "thinly surveyed: an absence of sites here says little". Nothing else uses it, so it never gets confused with speculation.

**Period art.** The globe and its table stay: there is no way to make the frame contemporary with the Neolithic, and it reads honestly as an instrument for looking back at the past. Inside the board, base the drawing style on the period's own visual world, not on later cartography:
- earth pigments: ochre, haematite, charcoal, kaolin
- motifs from painted pottery, like Halaf, Samarra, Cucuteni and Linear Pottery bands
- textures of rock art and incised bone

Use this for map illustrations and icons on the board.

**Accuracy pass.** Don't draw anachronistic flora, fauna, crops or technology: no maize, no horses as mounts before their time, no wheeled carts before about 3500 BCE. Apply the CK3 sunflower rule. It covers what is drawn, not names: archaeology names sites after modern places ("Ugarit", "Prague"), and those are the names the evidence uses. Where a period-neutral form exists, prefer it ("Ras Shamra"). Names must be spelled right: no letters or apostrophes lost in import.

**Atmosphere.** Slow cloud shadows, seasonal tint and drifting smoke from settlements are good additions. All of them can be toggled, and none may lower the contrast of rule 1 or 2 in the hierarchy. None exists yet, so it isn't on the checklist.

## Checklist for critics and PRs

- [ ] Can you identify the terrain at the default zoom without opening a map mode?
- [ ] Is anything louder than its place in the hierarchy?
- [ ] Are there any straight lines or hex-shaped edges in natural features (coasts, biome borders, relief)?
- [ ] Do overlays let the terrain show through?
- [ ] Does each zoom step add detail, without anything popping in?
- [ ] Could a player tell, without a tooltip, what changed in the last few centuries (coasts, sites, farming)? Biomes drift slower than that.
- [ ] Can you tell speculation from evidence, without the speculation looking broken?
- [ ] Is anything on the map anachronistic?

## Sources

- Paradox, *Victoria 3* Dev Diary #49, Graphics Overview: https://www.paradoxinteractive.com/games/victoria-3/news/dev-diary-49-graphic-overview
- Paradox, *Victoria 3* Dev Diary #50, Living Map: https://forum.paradoxplaza.com/forum/developer-diary/victoria-3-dev-diary-50-living-map.1531318/ (via secondary coverage: https://www.altchar.com/game-news/victoria-3-map-changes-and-interactive-elements-arHA17n8bMtb)
- Paradox, *CK3* Dev Diary #28, Art Focus: https://forum.paradoxplaza.com/forum/threads/ckiii-dev-diary-28-art-focus.1393627/
- Paradox, *CK3* Dev Diary #177, A Fresh Coat of Paint: https://devtrackers.gg/crusader-kings/p/3c2f2816-dev-diary-177-a-fresh-coat-of-paint
- Paradox, *EU5* Tinto Talks #64 (terrain map mode, heightmap): https://forum.paradoxplaza.com/forum/developer-diary/tinto-talks-64-21st-of-may-2025.1756210/
- Creative Assembly, *Total War: Three Kingdoms* art (Pawel Wojs): https://gamesbeat.com/how-creative-assembly-conceived-the-art-for-total-war-three-kingdoms/
- Creative Assembly, *Thrones of Britannia* map from real height data: https://pcgamer.com/total-war-saga-thrones-of-britannia-unveils-map-23-times-bigger-than-attilas
- Firaxis, *Civ VI*, Making it both playable and beautiful (Brian Busatti): https://gamedeveloper.com/art/making-i-civilization-vi-i-both-playable-and-beautiful
- Firaxis, *Civ VI* art and cartographic fog of war: https://digitaltrends.com/gaming/art-civilization-vi
- Firaxis, *Civ VI* Gamescom interview (Darney, Busatti): https://wccftech.com/civilization-vi-interview-with-sarah-darney-and-brian-busatti/
- Firaxis, *Civ VII* From the Devs, Map Generation: https://civilization.2k.com/en-GB/civ-vii/from-the-devs/map-generation/

*Caveat: the Paradox forum pages returned errors or browser-check pages when fetched. For Vic3 #50, CK3 #28 and EU5 Tinto Talks #64, the points above come from search excerpts and secondary coverage rather than the full diary text.*
