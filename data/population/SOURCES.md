# Population: methods and visibility inventory

Phase 1 of the expected-vs-observed work. The catalogue is `inventory.toml`; this file is its
write-up. Nothing here is built yet.

## The question

We have a site list (`data/settlements/`). We want to say where it under-represents people: where
we would expect more sites than we see, and why. So expected occupation must use **no site or date
counts**, and the observed record is what it is compared against:

    observed site intensity = expected occupation × detection

Ecologists fit the same structure to museum and sighting records (see "Presence-only models with
sampling bias" below).

## Decisions

| Question | Choice | Why |
|---|---|---|
| Can site or date density feed the population layer? | No. | It is the observed side. Using it would make the comparison circular. |
| Where does farming's arrival come from? | A dispersal-front model with published parameters. | The isostyle cereal and livestock surfaces come from finds at sites. They are kept as a check. |
| How is research effort measured? | Density of out-of-period dates per hex. | It shows where archaeologists dig, independent of where Neolithic people lived. |
| What are published regional densities for? | Hold-out anchors. | A well-surveyed area should come out with a small residual. |

## Methods

### Usable for expected occupation

**Forager density from environment.** Tallavaara et al. (2018) fit ethnographic hunter-gatherer
densities to net primary productivity, biodiversity and pathogen stress. Productivity matters
everywhere, biodiversity mainly where productivity is low, and pathogens mainly where it is high.
Their data and R scripts are open (CC BY 4.0). Tallavaara et al. (2015) applied the same idea to
palaeoclimate for Europe at 30,000–13,000 years ago, and concluded that the archaeological record
there is incomplete: the same expected-versus-observed reading we want. Binford's (2001)
ethnographic table of 339 groups is available as the `binford` R package.

**Farming dispersal front.** Pinhasi et al. (2005) place the origin in the northern Levant and
Mesopotamia and give a spread rate of 0.6–1.3 km/yr across Europe. Fort (2012) attributes about 40%
of that rate to cultural diffusion. Silva & Steele (2014) show how to let terrain speed up or slow
down the front. These speeds were fitted to dated sites, so the front is not fully independent of
the record at continental scale. We take the published parameters as given and do not refit them
to our site list.

### Sanity checks

**Gridded back-casts.** HYDE 3.2 (Klein Goldewijk et al. 2017) allocates regional population totals
to a grid from 10,000 BCE. Its world total at 10,000 BCE is 4.4 million with a range of under 0.01
to 8.9 million, or 0.03 people/km² (0–0.07). Kaplan et al. (2011) build a second land-use scenario
from a population-to-land-use relationship. Still to read: HYDE's allocation rules for the early
Holocene, which are in the paper's methods section and were not checked here.

**Pollen land cover.** Fyfe et al. (2015) classify 982 European pollen records into land-cover
types from 9000 BP. Neolithic land use shows from about 6000 BP. Europe only.

### The observed side: compare, never feed in

**Dates as data.** Summed or kernel-density curves of radiocarbon dates (Shennan et al. 2013;
Bevan et al. 2017; reviewed by Crema 2022). They track relative change in dated occupations.

**Site counts scaled from key areas.** Zimmermann et al. (2009) scale house and site counts in the
Rhineland up through a hierarchy of map scales. Their figures for non-state societies come out
lower than the usual literature values.

**Cemetery age structure.** Bocquet-Appel (2011) reads a rise in the share of juvenile skeletons
as a rise in fertility at the transition to farming. It gives rates, not densities.

### Framework

**Presence-only models with sampling bias.** Phillips et al. (2009) correct for uneven collecting
by drawing background points with the same bias as the records ("target-group background").
Fithian et al. (2015) estimate the bias jointly across many species. Renner et al. (2015) set the
whole problem up as a point process. Verhagen & Whitley (2012) review the archaeological
equivalent, predictive modelling.

## Visibility factors

| Factor | What it does | Covariate | Do we have it? | Reference |
|---|---|---|---|---|
| Submergence | Drowned coasts and plains are almost unsampled | Land at the epoch, Water today | Yes | Bailey & Flemming 2008 |
| Alluvial burial | Floodplains and deltas bury early sites | Floodplain and delta share of the hex | Partly: valley floors, no sediment thickness | Wilkinson 2000; Contreras 2023 |
| Age-dependent loss | Older deposits are more often destroyed | Epoch age with a published loss curve | Yes | Surovell et al. 2009 |
| Research effort | Dates pile up where archaeologists work | Out-of-period dates per hex | Partly: see below | Phillips et al. 2009; Crema 2022 |
| Soil acidity | Acid soils destroy bone | Topsoil pH | Yes, from isostyle | SoilGrids |
| Desert deflation | Surface scatters can't be dated; dunes bury sites | Aridity, sand seas | Partly | **none yet** |
| Modern ground cover | Forest and built-up land hide finds | Modern land-cover shares | No | **none yet** |
| Access barriers | Conflict and closed zones stop fieldwork | None chosen | No | **none yet** |

The three unsourced factors need a reference before their covariates go into the detection model.

## Layers on the map

| Layer | Where it lives | Source | Notes |
|---|---|---|---|
| Net primary productivity | Hex property `npp`, g dry matter/m²/yr, at the 8 key frames | Miami model (Lieth 1973, constants as in Tallavaara et al.'s script) from annual mean temperature and precipitation (BIO1, BIO12) of Beyer et al. (2020), the model run the biomes and Köppen classes already use | `pipeline/productivity.py`, `[productivity]` in `pipeline/config.toml`. Temperature is moved to the hex's elevation first. Rounded to 10. Shelf hexes with no model land cell take their neighbours' mean, up to 3 rings out. The app shows none on a hex that is Water that year. |
| Biodiversity | Derived in the app from `npp`; not stored | `B = 0.0644 + 0.00018032 × NPP`, a line fitted to Tallavaara et al.'s present-day productivity and biodiversity rasters over the map's box, weighted by cell area (R² 0.82, RMSE 0.045) | `neolith-rs/crates/core/src/forager.rs`. It adds nothing productivity doesn't already say: it is on the map so the model's inputs can be seen. |
| Farming front | Hex property `farming`: the year farming reaches the hex; absent if not by 3000 BCE | Pinhasi et al. (2005): one origin, one speed, shortest path over land | `pipeline/farming.py`, `[farming]` in `pipeline/config.toml`. Static. Says when farming could first be present, not whether the land can be farmed. |
| Expected population | Derived in the app from `npp`, climate, rivers and `farming`; the "Expected population" map mode and the hex inspector | Foragers by the equation below; farmers as set out under "The farming side" | `neolith-rs/crates/core/src/forager.rs`, `farming.rs` and `World::expected_at`. Nobody on Ice; nothing on Water. |

### Choices made in applying the model

| Question | Choice | Why |
|---|---|---|
| Which productivity do hexes carry? | The Miami value, not the climate model's own `npp`. | It is the scale the equation was fitted on; `npp` runs about 2.3 times lower. One number per hex, and it is the one the function uses. |
| Pathogen stress | A function of productivity: −0.808 + 0.0000712 × NPP, plus 0.0005244 × (NPP − 1,349) above 1,349. Until 2026-11-12 it was one constant, −0.8194. | It is the authors' own piecewise fit of pathogen stress on productivity for their 300 forager groups (in their script). Their mapped surface describes historical farming societies and over this map lies mostly above the fitted range. See "Pathogen and biodiversity revisited". |
| Biodiversity | A straight line in productivity. | No reconstruction of richness exists for 10,000–3,000 BCE. A quadratic or cubic fits barely better (R² 0.84). |
| Very productive hexes | The prediction is held inside the fitted groups' range, 0.2 to 270.75 per 100 km². | With pathogens following productivity nothing reaches the top any more; the bottom still binds on bare ground far inland. |

With these choices, 190 km from water (where the coastal factor is 1): 0.5 per 100 km² at zero
productivity, 3.6 at 500, 19 at 1,000, 60 at 1,500, 67 at 1,700, 60 at 2,000 and 4 at 3,000.

On the map as first built on 2026-11-12, before the coastal term and with pathogens constant
(superseded; kept for the record), over land hexes (not Water or Ice):

| Year | Productivity, 5th / median / 95th percentile | Expected foragers per 100 km², 5th / median / 95th | Hexes held at the top of the range |
|---|---|---|---|
| −10,000 | 50 / 510 / 1,780 | 0.6 / 3.7 / 189 | 459 of 17,395 |
| −6,000 | 70 / 630 / 1,850 | 0.6 / 5.8 / 223 | 659 of 17,579 |
| −3,000 | 50 / 640 / 1,740 | 0.6 / 6.0 / 172 | 433 of 17,370 |

The top few percent are the wet tropics along the map's southern edge. Their densities are the
least trustworthy on the map: they are where the fixed pathogen level matters most.

## The farming side

**When farming arrives.** Pinhasi et al. (2005) fitted `arrival = origin date + shortest-path
distance / speed` to 735 dated early Neolithic sites. We run that model with their numbers and do
not refit it:

| Parameter | Value | From |
|---|---|---|
| Origin | Çayönü (39.73°E, 38.22°N) | Their best-correlated origin for shortest-path distances |
| Start | 8800 BCE | Midpoint of their origin date, 10,000–11,500 cal BP |
| Speed | 0.9 km/yr | Midpoint of their calibrated shortest-path range, 0.7–1.1 |
| Sea crossings | Land hexes within 100 km are linked | They allow "some sea travel" to near islands and no long voyages, without a distance. **100 km is this project's choice.** |

The front does not enter Water or Ice; it waits at the edge until the hex opens. It is not slowed
by mountains, deserts or latitude.

**Check against conventional dates.** The dates in the third column are the round figures in
general use for the first farming in each area, from memory and not individually sourced; they are
here only to show the size and direction of the misfit.

| Place | Model (BCE) | Conventional (BCE) | Model is |
|---|---|---|---|
| Cyprus | 7920 | 8500 | 580 late |
| Çatalhöyük | 8110 | 7400 | 710 early |
| Thessaly | 6980 | 6500 | 480 early |
| Thrace (Karanovo) | 7340 | 6000 | 1340 early |
| Southern Italy | 6490 | 6000 | 490 early |
| Valencia | 4530 | 5500 | 970 late |
| Portugal | 3880 | 5400 | 1520 late |
| Rhineland | 5370 | 5300 | 70 early |
| Paris basin | 5110 | 5100 | 10 early |
| Kyiv | 6900 | 4800 | 2100 early |
| England | 4780 | 4000 | 780 early |
| Denmark | 5230 | 3950 | 1280 early |
| Ireland | 4090 | 3750 | 340 early |
| Fayum | 7290 | 5200 | 2090 early |
| Jeitun | 6850 | 6000 | 850 early |
| Central Zagros | 7870 | 8000 | 130 late |
| Tunisia | 4830 | 5000 | 170 late |

The median misfit is about 700 years. The pattern is the known one for a single-speed front: it
has no pause in Anatolia or on the North European Plain, no fast coastal spread along the western
Mediterranean, and Egypt takes up farming two thousand years after the front passes. Where the
model is early, the map expects farmers before there were any; a shortfall of sites there is the
model's error, not a visibility bias.

**Davison et al.'s model, tried and not adopted (2026-11-12).** Their "Model 2" adds faster
spread along coasts (10 km/yr) and the Danube and Rhine (5 km/yr), slower spread northward, and
no farming above 1000 m. It is a population simulation (growth plus diffusion), not a front, so it
was solved as they describe on a 0.1° mesh (`pipeline/davison.py`; theirs was 1/12°). The paper
gives no calendar date for the start; the same 8800 BCE was used, from Jericho, their origin.

| | Pinhasi front (on the map) | Davison Model 2 |
|---|---|---|
| Median misfit against the 17 conventional dates | 710 years | 1,590 years |
| Typical direction | 480 years early | 1,590 years early |
| Scatter left after removing that offset, all places | 610 years | 440 years |
| The same, Europe only | 460 years | 330 years |
| Places never reached | none | Central Zagros; 8,683 hexes in all, most above 1000 m |

- Its pattern across Europe is better: Iberia and the coasts no longer lag. But everything arrives
  earlier, so with the same start date the dates are worse. It would fit Europe with a start
  about 1,600 years later, which is no longer a start in the Levant. No start date was fitted.
- The 1000 m limit empties the Anatolian and Iranian plateaus and the Zagros, where early farming
  sites are.
- **The replication is only partly verified.** Without the fast strips (their Model 1) the solver
  matches the timings the paper reports: the Alps and Morocco in about 4,700–4,900 years against
  their "approximately 4,000" and "a similar time" to 5,000–5,500, and Britain not yet reached at
  5,800 against their 5,500. With the strips it runs faster than theirs: Gibraltar in 1,710 years
  against their 3,000, England in 2,750 against 3,500. The paper does not say how the fast strips
  were differenced, and the result depends on it.
- The module and its tests are in the repo but the build does not call it.

**Whether the hex can be farmed** is decided per year from its Köppen class, productivity and
rivers. All three conditions must hold:

| Condition | Rule | Basis |
|---|---|---|
| Warm enough | Not polar (E), and not a class ending c or d (fewer than four months at 10 °C) | The Köppen definitions |
| Not tropical | Not an A class | Wheat and barley are winter-rain crops. **No reference yet.** |
| Wet enough | Productivity of at least 460 g/m²/yr, or a river crosses the hex | 460 is the Miami value for 250 mm of rain a year, a commonly given lower limit for rain-fed cereals (the 10-inch isohyet in Bennett 1960, seen in a search summary and not read in full). Rivers stand for the Nile and Mesopotamia. |

Dryness is judged from productivity because the map's climate layer cannot do it: it has steppe
(BSh) on every hex of the Sahara at −5000 and −3000 and no desert class at all. A first version
that trusted the arid classes put farmers at the full ceiling across the Sahara and Arabia.

**These rules are this project's own. No published model is behind them.**

**How many farmers** ("Farmer ceiling and growth" in the inventory). From Davison et al. (2006):

| Parameter | Value | From |
|---|---|---|
| Ceiling | 3.5 people/km² | 50 times Dolukhanov's 7 hunter-gatherers per 100 km² of temperate forest, the ratio being Ammerman & Cavalli-Sforza's |
| Northward thinning | × 1 at 38°N and south, × 0.5 at 56°N, on the same line to 0 at 74°N | "A factor of approximately 2 across the distance from Greece to Denmark", linear in latitude. The two anchor latitudes and the clamp at 1 are this project's reading. |
| Growth | Logistic at 0.02 a year from the hex's forager density to the ceiling | Their intrinsic growth rate. Half the ceiling is reached about 200 years after arrival. |

Farming never lowers the figure: where the forager density already exceeds the ceiling, it stands.
Unlike the forager side, the farmers' ceiling does not depend on productivity.

**Limits of the farming side**

- The ceiling is one number for all farmable land. Zimmermann et al. (2009) give site-based
  densities for the Rhineland's early farmers to hold it against (compare only, never an input);
  that comparison has not been made yet.
- A band along the Sahel, south of the Sahara, passes all three farmability tests and fills with
  farmers at the full ceiling once the front arrives. Nothing in the record supports wheat and
  barley farmers there; the band is an artefact of the rules.
- The Köppen layer's missing desert class is a fault in the map, not in this model, and is not
  fixed here.
- Desert hexes with a river are farmed from the moment the front arrives. Irrigation farming on
  the Mesopotamian alluvium and the Nile came later than that.
- The mountains of Davison et al.'s model (no farming above 1000 m) are not used: it would empty
  the Anatolian and Iranian plateaus, where early farming sites are.

## Residuals rebuilt around effort and coast (2026-11-12; the current maps)

Expected population by productivity never predicted where sites are, so the residual step no
longer uses it. What a hex should have now rests only on what the evidence supports.

    sites known ~ Poisson(area × presence × detection)

| Part | Term | Value |
|---|---|---|
| Presence | Epoch (8 levels) | fitted: −13.08 at −10,000 rising to −11.09 at −3,000 |
| Presence | Near water, foragers only: the model's own coastal factor, `exp(2.1279 − 0.4024 ln(km + 10))` | **fixed**, from ethnographic groups, not from these sites |
| Presence | Farmed (the front has arrived and the land is farmable) | fitted: +0.72 ± 0.02, about twice the sites of unfarmed land |
| Detection | ln(1 + later dates per 10,000 km²) | fitted: +0.69 ± 0.004 |
| Detection | Drowned | fitted: −0.47 ± 0.05 |
| Detection | Acid soil | fitted: −0.43 ± 0.02 |

**Checks**

| Model | Deviance (lower is better) |
|---|---|
| The old design, expected people as the offset (last run) | 80,482 |
| No presence pattern beyond epoch and farmed | 67,906 |
| **With the coastal factor fixed from ethnography (the model used)** | **67,122** |
| With the coastal slope fitted to the sites instead | 66,208 |
| The model used, plus expected population by productivity | 67,062 |

- The sites' own coastal slope for foragers is −0.37 ± 0.01 against the −0.40 used.
- Farmed hexes also thin out away from water (−0.30 ± 0.01). The model gives farmers no coastal
  term, so the maps under-expect farmed coasts a little.
- Adding expected population on top gives an exponent of −0.06 ± 0.01: it adds nothing.

**What the maps show** (139,753 hex-epochs of land with people on it)

| Outcome | Hex-epochs | Where |
|---|---|---|
| As expected | 126,243 | |
| Little dated archaeology nearby | 7,223 | From −5,000 on: the coasts of Africa and Arabia, the Sahel band, Anatolia to Iran, the Pontic steppe, the Maghreb |
| Unexplained shortfall | 3,536 | Ireland and western Britain throughout; central Europe, Iberia, southern Scandinavia and the Levant once farmed |
| More sites than expected | 2,735 | Scattered through well-studied Europe and the Levant |
| Acid soil | 13 | |
| Drowned | 3 | |

Sites if nothing hid them, against sites known: 1,354 against 436 at −10,000; 15,482 against
5,132 at −4,000. On this reading the list holds about a third of what full visibility would show,
at every epoch.

**How to read them**

- A hex is flagged only when at least one whole site is missing. Before −5,000 so few sites are
  known that almost no hex outside Britain and Ireland reaches that, which is why the early
  panels are nearly empty. They are not saying the early record is complete.
- "Farmed" still comes from the dispersal front and the farmability rules, with their known
  faults. The Sahel band and the square-edged block on the Pontic steppe are those faults showing
  through, not findings.
- Ireland before about 8000 BCE is still flagged: near water and well studied, but not yet settled.
- The coastal bands round Africa and Arabia are the new result: shores where foragers should have
  been commonest and almost nothing has been dated.
- Whole hexes now under water cannot appear at all, so the largest loss the coastal term implies
  is not on the map.

The files on disk are from a re-run later the same day, after the world file was rebuilt with
evidence layers (version 10). It changed 38 of 142,414 expected densities and 19 hex-epochs of
ice; the coefficients are the same to three places and the counts differ by a handful (7,231
little dated archaeology nearby, 126,254 as expected, deviance 67,124).

The limits listed under the first design below still apply (overdispersion, effort not being
independent of past population, nothing for burial or ground cover, a site counting as one site).

## Residuals: the first design, expected people against the site list (superseded)

`make residuals` (`pipeline/residuals.py`, `[residuals]` in `pipeline/config.toml`) writes
`residuals.csv.gz` (one row per land hex per epoch), `residuals.json` (the fit) and two maps in
`maps/`. Run of 2026-11-12. **The tables in this section are from the run before the coastal
term was added; the files on disk are from the run after it. See "After the coastal term".**

**The model.** For each land hex at each of the 8 epochs:

    sites known ~ Poisson(expected people × exp(epoch + farmed + effort + drowned + acid soil))

| Term | What it is | Fitted |
|---|---|---|
| Expected people | Density from the app's model (`neolith-convert --expected`) × hex area. Entered as an offset: one more person, proportionally one more site. | fixed at 1 |
| Sites known | Sites in `build/settlements.geojson` occupied within 500 years of the epoch. 19,996 site-epochs. | |
| Epoch | One level per epoch: sites per person, which also absorbs older deposits being lost. | −12.19 at −10,000 rising to −10.31 at −3,000 |
| Farmed | Farmers leave fewer sites per person than foragers. A nuisance term, not a visibility reason. | −1.50 ± 0.02 |
| Effort | ln(1 + dated records younger than 4,200 BP per 10,000 km², smoothed over 100 km). 102,718 of the 206,875 dated records on the map. Later than the period, so it shows where archaeologists work without counting the sites being judged. | +0.80 ± 0.004 |
| Drowned | Land at the epoch, Water at −3,000. | −0.13 ± 0.05 |
| Acid soil | Topsoil pH below 5.5 (SoilGrids). | −0.14 ± 0.02 |

"Nothing hiding the sites" sets effort to at least the 90th percentile of land hexes (62 later
dates per 10,000 km²), not drowned, not acid. A hex-epoch is short when at least one site is
missing against that and it has no more than half the sites expected.

**The main finding: expected population does not predict where sites are.**

| Check | Result |
|---|---|
| Deviance with no population term at all | 68,192 |
| Deviance with expected people as the offset (the model above) | 87,414: worse than leaving population out |
| Exponent on expected people when it is left free (1 would be proportional) | 0.003 ± 0.007 |
| The same without the farmed term | 0.12 ± 0.004 |
| Foragers only | −0.02 ± 0.01 |
| Farmed hexes only | 0.56 ± 0.03 |
| Best-studied quarter of hex-epochs, foragers only | 0.10 ± 0.01 |
| Best-studied quarter, farmed only | 0.41 ± 0.03 |

Research effort explains most of where sites are known. Among foragers, the productivity-based
density explains nothing: twice the expected people does not mean more known sites, even in the
best-studied quarter. Among farmed hexes there is a real but weak relation (the ceiling's
northward thinning and the growth after arrival), well short of proportional.

So the maps below rest on an assumption the data rejects. They show where the *model* and the
list disagree; they are not yet evidence of where sites are hidden.

**What the maps show** (139,753 hex-epochs):

| Outcome | Hex-epochs | Where |
|---|---|---|
| As expected | 117,991 | |
| Little dated archaeology nearby | 15,883 | The Sahel band, Anatolia to Iran and the Caucasus, the Pontic steppe, the Maghreb, the Nile and Mesopotamian rivers |
| Unexplained shortfall | 3,146 | Ireland and western Britain before farming; central Europe, Iberia and the Levant once farmed |
| More sites than expected | 2,733 | Scattered through the best-studied parts of Europe |
| Drowned | 0 | Never the largest reason: its effect is small |
| Acid soil | 0 | The same |

Reading them with what is already known to be wrong:

- The Sahel band is the farmability artefact, and the model's most confident "missing sites".
- Ireland before about 8000 BCE is flagged because the model puts foragers on any productive
  land; the island was not yet settled. "Unexplained" there means the land was empty.
- Farmed central Europe is short because every farmed hex sits at one ceiling, and where the
  front arrives early (Denmark, Kyiv, Thrace) farmers are expected before there were any.
- Anatolia, Iran and the Caucasus are the most plausible real finding: farmed early, by the
  model and by the record, with little dated archaeology of any period.

**Limits**

- Counts are overdispersed; the standard errors above are too small.
- Effort is not independent of past population: places lived in later were mostly liveable
  earlier. That is the standard weakness of a target-group background.
- Nothing stands for alluvial burial, desert deflation or modern ground cover.
- "Drowned" only sees hexes wholly under water by −3,000. Sites cannot be recorded on a hex with
  no land, so the list has nothing there to fit against.
- A site is one site, whether a flint scatter or a tell.

## After the coastal term (2026-11-12)

Forager density is now the published equation times a factor for distance to the sea or a lake:

    × exp(2.1279 − 0.4024 ln(km to the water's edge + 10))

about ×3.3 on the shore, ×1.6 at 50 km, ×1 at 190 km, ×0.5 at 1,000 km, flat beyond 2,000 km.

| | |
|---|---|
| Fitted to | What the published equation misses for the 338 Binford groups with all three layers (the equation itself is left as published) |
| Fit | Intercept 2.128 ± 0.253, slope −0.402 ± 0.048; R² 0.175 on the misses. The equation's R² on these densities goes from 0.42 to 0.53 |
| Held-out check | Leaving each of the 27 D-PLACE regions out in turn, the mean squared miss falls from 1.50 to 1.32 |
| Distance in the fit | To the nearest sea cell of Tallavaara's 1/6° land mask, less half a cell |
| Distance on the map | From the hex centre to the nearest Water hex that year, less half a hex, in whole km (`World::shore_km`). Sea and lakes both count; rivers do not |
| Where | `neolith-rs/crates/core/src/forager.rs` (`shore_factor`). **This project's own fit, not a published model** |

At that point the prediction's cap bound on productive coasts as well as in the wet tropics:
1,887 of 113,952 forager hex-epochs sat at the top. (No longer: see "Pathogen and biodiversity
revisited".)

**Residuals re-run with it**

| Check (exponent on expected people; 1 would be proportional) | Before | After |
|---|---|---|
| All hex-epochs, with the farmed term | 0.003 ± 0.007 | 0.037 ± 0.007 |
| Foragers only | −0.02 ± 0.01 | 0.02 ± 0.01 |
| Best-studied quarter, foragers only | 0.10 ± 0.01 | 0.16 ± 0.01 |
| Farmed only | 0.56 ± 0.03 | 0.59 ± 0.03 |
| Deviance with expected people as the offset (68,192 with no population term) | 87,414 | 86,344 |

Fitted terms after: farmed −1.34 ± 0.02, effort +0.72 ± 0.004, drowned −0.37 ± 0.05 (was −0.13),
acid soil −0.18 ± 0.02. Outcomes: 120,329 as expected, 13,297 little dated archaeology nearby,
3,433 unexplained shortfall, 2,694 more sites than expected; drowned and acid soil are still never
the largest reason.

So the coastal term helps a little and does not fix it. Splitting forager density into its two
parts shows why:

| Part of forager density | Its exponent against known sites, all foragers | Best-studied quarter |
|---|---|---|
| Distance to water (as ln(km + 10); the model uses −0.40) | −0.37 ± 0.01 | −0.42 ± 0.01 |
| Productivity (the published equation; 1 would be proportional) | −0.06 ± 0.01 | 0.07 ± 0.01 |

- **The coastal term is confirmed by the sites.** Known forager sites thin out with distance from
  water at almost exactly the rate fitted to the ethnographic groups, which the sites played no
  part in. In the best-studied quarter there are 3.1 sites per 10,000 km² within 30 km of water
  and 0.45 beyond 300 km.
- **The productivity part is what fails.** Across the best-studied quarter, the equation's
  density runs from under 2 to over 50 per 100 km², and known sites per area barely double.

The second point is about our use of the equation as much as the equation: biodiversity is tied
to productivity and pathogen stress is a constant, so every term pushes the same way and nothing
holds productive land back.

## Pathogen and biodiversity revisited (2026-11-12)

The question: can the productivity part of forager density be made to agree with known sites
by changing how biodiversity and pathogen stress are supplied, without using site data in the
model? Six ways of supplying them were scored against the sites. **The sites were used to judge
the options, not to fit anything; but they did inform which option was kept.**

| Option | Density at 1,300 against 300 g/m²/yr | 95th percentile, per 100 km² | Exponent of the productivity part against sites, all foragers | Best-studied quarter |
|---|---|---|---|---|
| 0. As it was: biodiversity a line in productivity, pathogens constant | ×32 | 245 | −0.06 ± 0.01 | 0.07 ± 0.01 |
| 1. Pathogens rise with productivity (the authors' fit) | ×26 | 63 | −0.05 ± 0.01 | 0.10 ± 0.01 |
| 2. The authors' modern biodiversity raster, pathogens constant | | 207 | −0.05 ± 0.01 | 0.08 ± 0.01 |
| 3. Both 1 and 2 | | 52 | −0.03 ± 0.01 | 0.11 ± 0.01 |
| 4. The authors' productivity-only model (their piecewise fit; no biodiversity or pathogens) | ×17.5 | 41 | −0.04 ± 0.01 | 0.13 ± 0.01 |
| 5. The authors' modern rasters for both | | 11 | 0.23 ± 0.02 | 0.39 ± 0.02 |

(An exponent of 1 would mean sites proportional to expected people. Distance to water was left
free in each fit.)

**Kept: option 1.** Pathogen stress now follows productivity by the relation the authors fitted
to their own forager groups. It is published, it is about foragers, and it removes the need for
the cap: density peaks at about 67 per 100 km² near 1,700 g/m²/yr and falls in the wet tropics,
which is what the paper reports.

**Not kept**

- Option 2: almost no gain, for a stored present-day layer with no value on 2,705 hex-epochs of
  land that is now sea.
- Option 4 scores slightly better than option 1 and is simpler, but drops biodiversity from the
  model altogether; and the choice between them would then rest on the sites.
- Option 5 is the only one that moves the exponent much, and it is the one ruled out before: the
  modern pathogen surface records the disease of historical farming societies, so part of what it
  "explains" is where farming later made people dense. It is not independent of the record.

**Residuals re-run with option 1**

| Check (exponent on expected people) | Before the coast | With the coast | With the coast and option 1 |
|---|---|---|---|
| All hex-epochs, with the farmed term | 0.003 | 0.037 | 0.069 ± 0.008 |
| Foragers only | −0.02 | 0.02 | 0.06 ± 0.01 |
| Best-studied quarter, foragers only | 0.10 | 0.16 | 0.24 ± 0.01 |
| Farmed only | 0.56 | 0.59 | 0.58 ± 0.03 |
| Deviance with expected people as the offset (68,192 with no population term) | 87,414 | 86,344 | 80,482 |

Fitted terms: farmed −1.92 ± 0.02, effort +0.63 ± 0.004, drowned −0.48 ± 0.05, acid soil
−0.19 ± 0.02. Outcomes: 123,390 as expected, 10,013 little dated archaeology nearby, 3,643
unexplained shortfall, 2,703 more sites than expected, 4 drowned. Forager density on the map now
runs from 0.4 (5th percentile) through 2.9 (median) to 48 (95th) per 100 km², with a maximum of
140.

Each step has helped and none has fixed it: expected people still fit the sites worse than no
population term at all. Within the published equation there is no further choice of inputs that
is both independent of the record and flat enough. What is left is the equation's own
productivity slope, which the sites say is several times too steep for this region.

## Coastal foraging: research pass (2026-11-12)

Prompted by the residuals: among foragers, expected density does not predict where sites are.
The forager model has no coasts, lakes or rivers.

**What the published models do with fishing**

| Model | Aquatic resources | Read |
|---|---|---|
| Tallavaara et al. 2018 (ours) | Left out; the authors say coasts may be under-predicted | Script and data |
| Zhu et al. 2021 (FORGE, a process model) | "Fishing is not implemented in the current land-only model"; they attribute part of their misfit to it | Full text |
| Ordonez & Riede 2022 (Europe, 21,000–8,000 BP) | Groups taking more than 30% of their protein from water were removed before fitting. Mean early Holocene density 1.78 per 100 km² of inhabited area, which the authors think is high | Full text |
| Kavanagh et al. 2018 (hindcast 21,000–4,000 BP) | **Distance to the nearest coast is a predictor**, with productivity, environmental stability, mobility and land ownership; 220 societies, about 77% of variation explained | Abstract and press release only: the paper is behind a login, so its coefficients are not in hand |

So three of the four leave the coast out by construction, and the one that includes it is the
one we could not read.

**What the archaeology says, for context** (not inputs)

- Bailey & Milner (2002) argue coasts were a primary focus of settlement and population growth,
  and look marginal mainly because early shorelines are drowned.
- Lundström et al. (2021) estimate early Holocene pioneer coastal Norway at 0.4–1.2 per 100 km²
  overall and 3–10 per 100 km² in core areas, from sites (compare only).
- Jørgensen et al. (2022) find coastal forager populations in northern Norway and western Finland
  rising and falling together with marine and climate proxies.

**A check on the open data** (this project's own analysis, not a published result)

Binford's 339 groups are open through D-PLACE (CC BY-NC 4.0), with density, percentage of
subsistence from fishing, and coordinates. For the 338 with all three of Tallavaara's layers,
the published equation was applied and its misses compared with fishing and with distance to the
sea. Distance is to the nearest sea cell of Tallavaara's own 1/6° land mask, thinned to 1/3°, so
it is coarse and counts inland seas and the largest lakes as sea.

| Distance to the sea | Groups | Median density per 100 km² | Mean share of subsistence from fishing | Mean miss of the equation (ln units; + means denser than predicted) |
|---|---|---|---|---|
| Under 25 km | 7 | 6.6 | 65% | +1.12 |
| 25–100 km | 120 | 36.1 | 52% | +0.57 |
| 100–300 km | 73 | 13.4 | 30% | +0.24 |
| Over 300 km | 138 | 3.1 | 15% | −0.55 |

| Model of ln density | R² |
|---|---|
| Tallavaara's five terms, refitted to these densities | 0.50 |
| + percentage from fishing | 0.59 |
| + ln(distance to sea + 10 km) | 0.67 |

- The coefficient on ln(distance + 10 km) is −0.71 ± 0.06: other things equal, a group 20 km from
  the sea is about seven times as dense as one 300 km inland.
- Distance to the sea does better than fishing dependence and absorbs it (with both in, fishing
  adds nothing). The two are correlated at −0.62.
- It holds outside the tropics: for the 231 groups beyond 30° of latitude, distance alone explains
  a quarter of what the equation misses.

Not done: no allowance for neighbouring groups being alike, no hold-out test, nothing for rivers
or lakes below the mask's resolution, and the pathogen term is still the modern surface. The
7-group nearest band is too small to read.

**What it means for the map**

- Distance to the sea can be computed per hex per epoch from the terrain already on the map, so
  the Doggerland coast and the Black Sea lake would each carry their own shoreline.
- The densest foragers would then sit on early Holocene shores, most of which are under water
  now. The residual fit found drowning unimportant, but it could only see hexes wholly drowned
  and expected little there; with a coastal term that changes.
- Kavanagh et al.'s published coefficient would be a better source than our own fit. It needs
  the paper. Until then the term is in the model with our fit ("After the coastal term").

## The Tallavaara model as published

Read from the authors' script and data (Zenodo, CC BY 4.0; retrieved 2026-11-12): the R script as a
PDF, three global rasters at 1/6° and the table of ethnographic groups.

**Inputs**

| Input | How the authors built it | Range in the fitting sample |
|---|---|---|
| Density | Binford (2001) and Kelly (2013), averaged where both list a group; people per 100 km²; "non-normal" groups and densities of 300 or more dropped. 300 groups remain. | 0.2 to 271 |
| Productivity | **Not a vegetation model.** The Miami model (Lieth 1973) from WorldClim annual mean temperature T (°C) and precipitation P (mm): the lower of `3000 / (1 + exp(1.315 − 0.119 T))` and `3000 (1 − exp(−0.000664 P))`, in g dry matter/m²/yr. | 0 to 2580 |
| Biodiversity | Mean of two richness maps each scaled 0–1: mammals plus birds (BiodiversityMapping.org, 10 km) and vascular plants (Kreft & Jetz 2007, interpolated). Present-day. | 0 to 0.61 |
| Pathogen stress | Mean z-score of the prevalence of 10 pathogens in the 186 societies of the Standard Cross-Cultural Sample (variable v2178, from Low's coding), kriged to a global surface, with five invented low-stress points in the Arctic. | −0.98 to 0.65 |

**The prediction equation.** The authors' maps average an ordinary regression and a support-vector
regression of the same form. The script prints only rounded, centred coefficients, so the
regression was refitted here from their table and rasters. It reproduces their fit exactly (300
groups, R² 0.546):

    ln(density per 100 km²) = −0.4298 + 0.0010875·NPP + 8.9814·B + 1.0967·S
                              − 0.0022175·NPP·S − 0.0030029·NPP·B

with NPP the Miami value, B biodiversity and S pathogen stress. Residual standard deviation 1.16
in ln units, so a single hex is good to within a factor of about three either way. The authors'
own cross-validation, leaving out everything within 500 km, gives R² 0.46.

**What this means for the map** (computed over the map's box from the authors' rasters):

- **Productivity scale.** The climate model's own `npp` (Beyer et al., grams of carbon) is not the
  model's input. At the 13,000 BP slice the Miami value from the same model's temperature and
  rainfall has a median of 431 against 174 for `npp`, a ratio of about 2.3, with a correlation of
  0.85. So the hexes carry the Miami value.
- **Biodiversity** follows productivity closely here: productivity and its square explain 80% of
  it. Holding it at the box median changes predicted ln density by a standard deviation of 0.66.
- **Pathogen stress** is the problem layer. Productivity explains only 28% of it in the box. The
  box median is 0.03 and the upper quartile 0.40, while three quarters of the fitting sample sit
  below −0.47: most of Europe, North Africa and Western Asia lies outside the range the model was
  fitted on. The surface is also kriged from historically recorded disease in societies that were
  mostly farmers and herders, so it describes the agrarian Old World, not 10,000 BCE.
- **Predicted densities** in the box with all three present-day layers: median 3.9 per 100 km²
  (0.04/km²), 5th to 95th percentile 1.0 to 12.3 per 100 km².
- The model leaves out aquatic resources, as the authors note, so coasts, lakes and rivers are
  under-predicted.

## Known limits

- **Research-effort data.** The committed `data/settlements/dates.csv.gz` has 53,191 dates, of
  which only 9,540 are later than 2500 BCE. The isostyle run counted 116,588 dates in the grid's
  box with 72,913 in the working range, so about 43,000 out-of-range dates exist in the cached raw
  dumps. The background has to be built from those dumps.
- **Nile delta.** A search found site-level coring reports (Buto, Sais) but no delta-wide measure
  of burial depth. The alluvial-burial reference covers Mesopotamia, and Contreras (2023) is a
  North American case study.
- **Wilkinson 2000.** The DOI resolves to an abstract matching the article; the title was not
  confirmed on the publisher's page.
- **Forager model inputs.** Biodiversity is a function of productivity and pathogen stress a
  constant ("Choices made in applying the model"), so expected forager density is, in effect, a
  curve in productivity alone.
- **One copy of the equations.** The forager coefficients and the farming rules live in the Rust
  core. The pipeline reads their results through `neolith-convert --expected` and has no copy.
- **Climate smoothing.** Köppen classes use a smoothed anomaly on the modern climatology
  (`[koeppen.smooth]`); productivity uses the raw model slice.

## References

- Bailey, G. & Milner, N., 2002. Coastal hunter-gatherers and social evolution: marginal or central? Before Farming 2002(3–4), article 1. https://eprints.whiterose.ac.uk/926/
- Binford hunter-gatherer data in D-PLACE (CC BY-NC 4.0; after Binford 2001). https://github.com/D-PLACE/dplace-dataset-binford
- Jørgensen, E.K., Pesonen, P. & Tallavaara, M., 2022. Climatic changes cause synchronous population dynamics and adaptive strategies among coastal hunter-gatherers in Holocene northern Europe. Quaternary Research 108: 107–122. https://doi.org/10.1017/qua.2019.86
- Kavanagh, P.H., Vilela, B., Haynie, H.J., Tuff, T., Lima-Ribeiro, M., Gray, R.D., Botero, C.A. & Gavin, M.C., 2018. Hindcasting global population densities reveals forces enabling the origin of agriculture. Nature Human Behaviour 2: 478–484. https://doi.org/10.1038/s41562-018-0358-8
- Lundström, V., Peters, R. & Riede, F., 2021. Demographic estimates from the Palaeolithic–Mesolithic boundary in Scandinavia: comparative benchmarks and novel insights. Philosophical Transactions of the Royal Society B 376: 20200037. https://doi.org/10.1098/rstb.2020.0037
- Ordonez, A. & Riede, F., 2022. Changes in limiting factors for forager population dynamics in Europe across the last glacial-interglacial transition. Nature Communications 13: 5140. https://doi.org/10.1038/s41467-022-32750-x
- Zhu, D., Galbraith, E.D., Reyes-García, V. & Ciais, P., 2021. Global hunter-gatherer population densities constrained by influence of seasonality on diet composition. Nature Ecology & Evolution 5: 1536–1545. https://doi.org/10.1038/s41559-021-01548-3
- Bailey, G.N. & Flemming, N.C., 2008. Archaeology of the continental shelf: marine resources, submerged landscapes and underwater archaeology. Quaternary Science Reviews 27: 2153–2165. https://doi.org/10.1016/j.quascirev.2008.08.012
- Bennett, M.K., 1960. A world map of food crop climates. Food Research Institute Studies 1(3): 285–295. https://ageconsearch.umn.edu/record/136582
- Bevan, A., Colledge, S., Fuller, D., Fyfe, R., Shennan, S. & Stevens, C., 2017. Holocene fluctuations in human population demonstrate repeated links to food production and climate. PNAS 114(49): E10524–E10531. https://doi.org/10.1073/pnas.1709190114
- Beyer, R.M., Krapp, M. & Manica, A., 2020. High-resolution terrestrial climate, bioclimate and vegetation for the last 120,000 years. Scientific Data 7: 236. https://doi.org/10.1038/s41597-020-0552-1
- Binford, L.R., 2001. Constructing Frames of Reference. Berkeley: University of California Press. Data as the `binford` R package: https://github.com/benmarwick/binford
- Bocquet-Appel, J.-P., 2011. When the world's population took off: the springboard of the Neolithic Demographic Transition. Science 333(6042): 560–561. https://doi.org/10.1126/science.1208880
- Contreras, D.A., 2023. Landscape taphonomy predictably complicates demographic reconstruction. Journal of Archaeological Method and Theory. https://doi.org/10.1007/s10816-023-09634-5
- Crema, E.R., 2022. Statistical inference of prehistoric demography from frequency distributions of radiocarbon dates: a review and a guide for the perplexed. Journal of Archaeological Method and Theory 29(4): 1387–1418. https://doi.org/10.1007/s10816-022-09559-5
- Davison, K., Dolukhanov, P., Sarson, G.R. & Shukurov, A., 2006. The role of waterways in the spread of the Neolithic. Journal of Archaeological Science 33(5): 641–652. https://doi.org/10.1016/j.jas.2005.09.017 (preprint, read here: https://arxiv.org/abs/q-bio/0505013)
- Fithian, W., Elith, J., Hastie, T. & Keith, D.A., 2015. Bias correction in species distribution models: pooling survey and collection data for multiple species. Methods in Ecology and Evolution 6(4): 424–438. https://doi.org/10.1111/2041-210X.12242
- Fort, J., 2012. Synthesis between demic and cultural diffusion in the Neolithic transition in Europe. PNAS 109(46): 18669–18673. https://doi.org/10.1073/pnas.1200662109
- Fyfe, R.M., Woodbridge, J. & Roberts, N., 2015. From forest to farmland: pollen-inferred land cover change across Europe using the pseudobiomization approach. Global Change Biology 21(3): 1197–1212. https://doi.org/10.1111/gcb.12776
- Kaplan, J.O., Krumhardt, K.M., Ellis, E.C., Ruddiman, W.F., Lemmen, C. & Klein Goldewijk, K., 2011. Holocene carbon emissions as a result of anthropogenic land cover change. The Holocene 21(5): 775–791. https://doi.org/10.1177/0959683610386983
- Klein Goldewijk, K., Beusen, A., Doelman, J. & Stehfest, E., 2017. Anthropogenic land use estimates for the Holocene – HYDE 3.2. Earth System Science Data 9: 927–953. https://doi.org/10.5194/essd-9-927-2017
- Lieth, H., 1973. Primary production: terrestrial ecosystems. Human Ecology 1: 303–332. https://doi.org/10.1007/BF01536729
- Phillips, S.J., Dudík, M., Elith, J., Graham, C.H., Lehmann, A., Leathwick, J. & Ferrier, S., 2009. Sample selection bias and presence-only distribution models: implications for background and pseudo-absence data. Ecological Applications 19(1): 181–197. https://doi.org/10.1890/07-2153.1
- Pinhasi, R., Fort, J. & Ammerman, A.J., 2005. Tracing the origin and spread of agriculture in Europe. PLoS Biology 3(12): e410. https://doi.org/10.1371/journal.pbio.0030410
- Renner, I.W., Elith, J., Baddeley, A., Fithian, W., Hastie, T., Phillips, S.J., Popovic, G. & Warton, D.I., 2015. Point process models for presence-only analysis. Methods in Ecology and Evolution 6: 366–379. https://doi.org/10.1111/2041-210X.12352
- Shennan, S. et al., 2013. Regional population collapse followed initial agriculture booms in mid-Holocene Europe. Nature Communications 4: 2486. https://doi.org/10.1038/ncomms3486
- Silva, F. & Steele, J., 2014. New methods for reconstructing geographical effects on dispersal rates and routes from large-scale radiocarbon databases. Journal of Archaeological Science 52: 609–620. https://doi.org/10.1016/j.jas.2014.04.021
- SoilGrids 2.0, pH(H2O) 0–5 cm, 5 km aggregate (CC BY 4.0). https://files.isric.org/soilgrids/latest/data_aggregated/5000m/phh2o/phh2o_0-5cm_mean_5000.tif
- Surovell, T.A., Finley, J.B., Smith, G.M., Brantingham, P.J. & Kelly, R., 2009. Correcting temporal frequency distributions for taphonomic bias. Journal of Archaeological Science 36(8): 1715–1724. https://doi.org/10.1016/j.jas.2009.03.029
- Tallavaara, M., Eronen, J.T. & Luoto, M., 2018. Supporting data and script for "Productivity, biodiversity, and pathogens influence the global hunter-gatherer population density" (CC BY 4.0). Zenodo. https://doi.org/10.5281/zenodo.1167852
- Tallavaara, M., Eronen, J.T. & Luoto, M., 2018. Productivity, biodiversity, and pathogens influence the global hunter-gatherer population density. PNAS 115(6): 1232–1237. https://doi.org/10.1073/pnas.1715638115
- Tallavaara, M., Luoto, M., Korhonen, N., Järvinen, H. & Seppä, H., 2015. Human population dynamics in Europe over the Last Glacial Maximum. PNAS 112(27): 8232–8237. https://doi.org/10.1073/pnas.1503784112
- Verhagen, P. & Whitley, T.G., 2012. Integrating archaeological theory and predictive modeling: a live report from the scene. Journal of Archaeological Method and Theory 19: 49–100. https://doi.org/10.1007/s10816-011-9102-7
- Wilkinson, T.J., 2000. Regional approaches to Mesopotamian archaeology: the contribution of archaeological surveys. Journal of Archaeological Research 8(3): 219–267. https://doi.org/10.1023/a:1009487620969
- Zimmermann, A., Hilpert, J. & Wendt, K.P., 2009. Estimations of population density for selected periods between the Neolithic and AD 1800. Human Biology 81(2–3): 357–380. https://doi.org/10.3378/027.081.0313
