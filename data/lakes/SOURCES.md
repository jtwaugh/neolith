# Lakes: sources and reasoning

`lakes.toml` gives each lake a seed point, a window and a water-level curve.
`python -m pipeline build` (`pipeline/lakes.py`) turns these into:

- **Extent:** the ETOPO1 cells the lake reaches from its seed at that year's
  level (a priority flood). A hex with half or more of its cells under water
  becomes Water. Hexes the drawn maps have as Water inside the lake's basin
  become land when the lake doesn't reach them that year.
- **Outlet:** where the flood first leaves the window. A curve above the
  outlet is held just under it, so an overflowing lake doesn't pour down the
  valley beyond. Computed outlets come close to the literature: Megachad at
  327 m through the Mayo Kébbi gap (325 m in Armitage et al. 2015); the
  Caspian at 18 m (the Manych); Sarykamysh at 55 m southwards (the Uzboy
  head); the Aral at 57 m towards Sarykamysh.
- **Shorelines:** a new shape whenever the level moves 2 m
  (`build/lakes.geojson`), drawn as a thin line over the hexes.
- **Levels** for spillway rivers. In `data/rivers/rivers.toml`,
  `spill = { lake, above }` makes a river flow only while the lake is that
  high, and `lake = "..."` extends a river's mouth to that lake at its
  lowest level.

Years are BCE as negative numbers (BCE = cal ka BP × 1000 − 1950).

## Lake Megachad (medium confidence)

Armitage, S.J., Bristow, C.S. & Drake, N.A., 2015. West African monsoon
dynamics inferred from abrupt fluctuations of Lake Mega-Chad. *PNAS* 112:8543.
https://pmc.ncbi.nlm.nih.gov/articles/PMC4507243

| Paper | Map |
|---|---|
| Arid 12.9–11.5 ka; no elevation given | 295 m at −10000 (assumed) |
| Highstand at the 329 m shoreline by 11.5 ka | 329 m from −9550 |
| Beach-ridge clusters 11.5–10.4, 9.4–8.1 and 6.6–5.4 ka; lower in between, no elevations | 320 m for −8300…−7600 and −6000…−4800 (assumed) |
| 308 m shoreline at 6.0 ± 0.3 ka, "a brief fall" | 308 m at −4000 |
| Regressive Goz Kerki shoreline at 325–330 m, 5.4–5.0 ka | 326 m at −3050 |
| Fall of >100 m in the Bodélé and >34 m in Lake Chad by 4.7 ka | 285 m at −2750 (after the map's end) |
| Bahr el Ghazal sill 287 m (288 m in one figure caption); Mayo Kébbi overflow 325 m | Sill used for the Bahr el Ghazal spillway; the outlet comes from ETOPO1 (327 m) |

- Dated settlements the curve puts under water when they start (the map
  build's report, "Phases starting under the modelled water"; build of
  2026-11-12): Borkou 121 m, Beurkia 48 m, Mandi 41 m, Faya-Largeau 10 m.
  Borkou's depth means its record is placed at a regional centroid in the
  Bodélé, not at the site, so it says nothing about the curve. Faya-Largeau
  (317 m, from about −4000) sits under the 329 m stand of −3900…−3450, the
  6.6–5.4 ka beach-ridge cluster; either its date or the length of that
  stand is off, and it is the case to check first. The 308 m fall at −4000
  is Armitage et al.'s dated "brief fall" and stays.
- One lake fills both the Chad and Bodélé basins whenever it is above the
  sill. That is true for the whole map period, so no separate Bodélé lake is
  needed. Its separation, about 4.7 ka, and final drying, about 1 ka, fall
  after −3000.
- The Mayo Kébbi flows only while the lake is at its outlet, which gives four
  overflow phases. The Bahr el Ghazal flows at −10000 (295 m, above the
  287 m sill). It is under the lake from about −9700, where the board shows
  Water.

## Caspian Sea (low confidence)

The published curves disagree on both depth and timing.
- Late Khvalynian stand near 0 m ending about 12 ka, then a fast fall into
  the Mangyshlak regression. Its minimum is about 9 cal ka, at −50 to −113 m
  depending on the author; **−80 m used**.
- The New Caspian rise began about 8 ka, to about −25 m (peaks near −20 m).
- References: Bezrodnykh et al. 2015; Kroonenberg et al.; the GSA 2021
  abstract "The Caspian Sea level changes during the second part of the Late
  Pleistocene"
  (https://gsa.confex.com/gsa/2021AM/webprogram/Paper370289.html).
- A palynological study of the central and southern basin argues for a
  highstand from 10.55 to 4.11 cal ka BP instead
  (https://core.ac.uk/download/29139334.pdf).
- With −80 m, the northern Caspian is dry around −7000, and the Volga, Ural
  and Uzboy run out across it.
- **Minimum moved to 10.5 ka (−8550).** Sorokin et al. 2021 date the
  Mangyshlak regression to 11.9–10.5 ka BP, and Bezrodnykh & Sorokin 2016
  date the freshwater Mangyshlak deposits of the northern Caspian to 12–9 ka.
  With the minimum at 9 ka the North Caspian floor (about −35 m) stayed dry
  until about −5500; now the curve is −45 m at −7050, −30 m at −6050, and the
  northern Caspian refloods about −6600 (data/places/plans/volga_delta.toml).

## Aral Sea (low confidence)

- Holocene transgressions reached about 53–56 m. Regressions (to 30–45 m)
  happened when the Amu Darya turned to Sarykamysh, and are not dated well
  enough to place. Krivonogov et al. 2014,
  https://cawater-info.net/aral/pdf/krivonogov-et-al-en.pdf.
- **53 m** (the pre-1960 level) is used throughout.

## Sarykamysh Lake (low confidence)

- Kes' (1979), cited by Krivonogov et al., has the Amu Darya filling
  Sarykamysh and overflowing down the Uzboy for most of the Holocene. It is
  held full throughout, at its computed 55 m outlet.
- Létolle et al. 2007 (Quaternary International) report repeated
  reactivations instead
  (https://zin.ru/labs/brackish/pdfs/2007/Uzboy_and_the_Aral_regressions_A_hydrological_approach.pdf).
  Dated phases would go here.

## Dead Sea (medium confidence)

- Holocene levels ranged between about −430 and −370 m (Bookman (Ken-Tor) et
  al. 2004; Migowski et al. 2006, *Quaternary Research* 66:421). The wet
  phases at 10–8.6 and 5.6–3.5 cal ka BP are the highs.
- The values between are interpolated from those ranges. The lake is
  narrower than a hex, so it shows only as a shoreline.

## Baltic (low confidence)

**The problem.** The land around the Baltic has risen since the ice sheet
melted, up to about 290 m at the uplift centre, so a past water surface is
tilted against today's elevations and no single level works. The board also
had a worse problem: at hex scale the Danish straits read as land, so the
sea step never reached the Baltic. It drained the basin and filled it with
neighbouring land types until about −6500.

**The model.**
- *Uplift* (`pipeline/isostasy.py`, `[isostasy]` in the config). Today's
  uplift rate is an elliptical dome centred on the Gulf of Bothnia (peak
  9.5 mm/yr, long axis to the NE), and the rate grows exponentially into
  the past. Uplift still to come after age *t* is
  scale × rate × τ × (e^{t/τ} − 1). The scale (0.85), τ (4.8 kyr) and the
  dome's axes were fitted by least squares to the calibration points below.
  Each year's surface is ETOPO1 minus that uplift.
- *Water level* (`level = "sea-or-outlet"`). Each year the basin is flooded
  from the Gotland Deep on that surface. If the global sea level is above
  its lowest outlet to the open ocean, it is sea at the global level;
  otherwise it is a lake held at that outlet. Only window-edge cells in
  today's open sea count as outlets.
- *Ice.* Before the Baltic Ice Lake drained, an ice dam along the ice margin
  of the time (the Middle Swedish end moraines and Salpausselkä) closes
  central Sweden, and the board's Ice hexes block the water. Ice hexes never
  become Water.

**What comes out** (no stage dates are imposed):

| Stage | Model | Literature |
|---|---|---|
| Baltic Ice Lake | to −9700, at −20 m (40 m above the sea) | drained 11.7–11.6 cal ka (≈ −9700), a drop of about 25 m |
| Yoldia Sea | −9700 to −9100 (open through central Sweden) | 11.7–10.7 cal ka (−9750 to −8750) |
| Ancylus Lake (lake at its outlet) | −9100 to −6500, rising −51 → −19.5 m, then held at the Danish straits | 10.7–9.8 cal ka; transition to marine 9.8–8.5 ka (Blekinge) |
| Littorina Sea | from −6500, at the global level | SW Baltic transgression about 8–7.5 cal ka (Mecklenburg Bay 8 ka, Arkona 7.2 ka) |

The Yoldia–Ancylus switch comes about 350 years early, and the Ancylus
outflow ends about 1,200 years later than the Mastogloia transition in
Blekinge. The early outlet heights are the least certain part: the
Baltic Ice Lake drop is 37 m in the model against 25 m in the literature.

**Calibration** (uplift since then = shoreline elevation today − water level
then; the water level is the global curve for marine shorelines and about
−20 m for the Ancylus transgression):

| Point | Age (cal ka) | Observed (m) | Model (m) | Source |
|---|---|---|---|---|
| Skuleberget, highest shoreline 286 m | 10.4 | 306 | 297 | Rosentau et al. 2021 (Berglund 2004) |
| Gästrikland, highest shoreline about 200 m | 10.7 | 247 | 253 | Rosentau et al. 2021 (Berglund 2005) |
| Tallinn, Ancylus transgression 34–36 m | 10.3 | 55 | 68 | Rosentau et al. 2021 (Veski 1998) |
| Saaremaa, Ancylus shoreline 25–35 m | 10.3 | 50 | 27 | Rosentau et al. 2021 |
| Kõpu, Ancylus transgression 47 m | 10.3 | 67 | 78 | Rosentau et al. 2021 |
| Tallinn, Littorina maximum 21–22 m | 7.4 | 29 | 33 | Rosentau et al. 2021 |
| Narva-Luga, Littorina shoreline 14 m (north) | 7.5 | 22 | 0 | Rosentau et al. 2021 |
| Mecklenburg Bay, sea −27 m at 9.0 ka | 9.0 | 0 | 0 | Rosentau et al. 2021 |

Misfits reach about 23 m, mostly on the dome's southeastern edge (Saaremaa,
Narva). The ages of the highest shorelines and the Ancylus level (−20 m)
are approximate. `pipeline/tests/test_isostasy.py` checks every point is
within 25 m.

**Limits.**
- One dome with one time constant. Real uplift has more structure (a
  second centre over the Barents Sea, a forebulge to the south).
- The sea step itself ignores uplift, so the Norwegian and Swedish west
  coasts (Oslofjord, Trøndelag) don't show their higher past sea levels.
- The board's drawn ice is used only until −9700 (it covers central Sweden
  until about −8500, when the area was in fact ice-free).
- Marine stages draw no shoreline line, like the open sea elsewhere.
- **Karelian Isthmus (`clear`).** The drawn maps put Water over the whole
  western isthmus (hexes 20–80 m above sea level today) for the whole
  period. Run without that drawn Water, the model on its own wets only a
  scattered few hexes there (Vyborg Bay, the Vuoksi lowland). The strait is
  real until Ladoga was cut off from the Baltic, about 10.2 cal ka
  (Ludikova et al. 2024, see data/rivers/SOURCES.md), so the drawn Water
  stays until −8250. From then on, drawn Water the model doesn't reach in
  28.2–33.6°E, 59.7–62.0°N becomes land (modern sea floor excepted). Ladoga's
  outflow then runs through the Heinjoki Strait (rivers.toml).

**Baltic outflow (`outflow`).** In its lake stages the Baltic is held at its
lowest outlet, so it overflowed somewhere; the board draws that river. Each
year the flood that finds the spill level also records its way out, and the
saddle is the highest cell on it (pipeline/lakes.py, `minimax` with
`route`). From the saddle the river takes the least-cost way down to that
year's sea, over ground no higher than the spill and not along the lake's
own shore, preferring low ground (`outflow_path`). One river per saddle,
flowing in the years the lake drained over it; it shortens where the sea
covers its lower course, like the other rivers.

| Stage | Model outlet | Literature |
|---|---|---|
| Baltic Ice Lake (to −9700) | Darss sill, Mecklenburg Bay, Fehmarn Belt, Great Belt, Kattegat | Mostly through Öresund before the Billingen drainage (Björck 1995, 2008). The model has no forebulge, so it can't tell the two routes apart |
| Early Ancylus Lake (−9100 to −8000) | West of Vänern: briefly to the Glomma (−9100 to −8800), then to the Göta älv (−8700 to −8000) | Initial Ancylus outlet in south-central Sweden through the Vänern basin and Göta älv (Björck 2008) |
| Late Ancylus Lake (−7900 to −6600) | Darss sill, Fehmarn Belt, Great Belt (the "Dana River") | Outlet moves to the Danish straits after about 10.3–10.2 cal ka, with a 200–300 year fluvial stage in the Great Belt (Björck 2008). Lemke and colleagues find a valley cut into the Darss sill to −23/−24 m about 10.3 ka but no Dana River there; Feldens & Schwarzer 2012 put the threshold west of the Fehmarn Belt. The Great Belt was marine by about 8.9 cal ka, before Öresund (Bennike et al.) |

The late switch to the Danish straits comes about 300 years after the
literature's 10.2 ka; the Glomma episode isn't in the literature and comes
from the uplift model letting the lake reach Värmland. Low confidence.

## Lake Ladoga (low confidence)

The board had no Ladoga. The drawn maps leave its basin as land, ETOPO1
records it as a flat surface at 1 m (no bathymetry; the real surface is
about 5 m asl). From the isolation (−8250) a dam along the isthmus divide
(Neva lowland, Heinjoki threshold, Salpausselkä) keeps the Baltic model out
of its catchment: ETOPO1's lake surface counts as ground, the uplift
correction sinks the north-west shore by up to 50 m, and without the dam the
Baltic flooded the skerry coast (three or four hexes outside the shoreline)
over the Heinjoki threshold. It is now a lake of its own, held at its present
extent all period: 1.5 m on the ETOPO datum floods about 16,700 km² from the
seed, against a real area of about 17,700 km². Its lowest exit in the window
is at 21 m, so nothing leaks. `basin_margin = 0` keeps it from clearing the
Baltic's water around it.

| Literature | Model |
|---|---|
| Joined to the Baltic (Baltic Ice Lake, Yoldia, Ancylus) until about 10.2 cal ka; some put the isolation at about 11.5 cal ka (Ludikova et al. 2024; Dolukhanov et al.) | the lake, plus the drawn Water over the isthmus until −8250 |
| Early-Holocene lowstand: submerged coastal bars at 13, 21 and 41 m below today's level (*Limnology and Freshwater Biology*, 2024–25) | not shown: no bathymetry |
| Ladoga transgression in the south: rise from about 5 cal ka (Dolukhanov et al.) or 3.7–3.6 ka (Taipale Bay study) to about 14 m, then the Neva breakthrough at 3.5–3.2 cal ka | after −3000 for the most part; not shown |

The Ancylus-stage maximum is given as 17–18 m (about 8.1 ka) or about 20 m
in the southern shallows (Subetto's excursion guide). The sources disagree,
and some are field-trip guides or abstracts.

## Lake Onega (medium confidence)

The board had no Onega: all 49 hexes of its basin were forest. It is now a
lake through the whole window at about today's outline. The basin was free
of ice by about 13–12 ka, and the large proglacial Onega stages (southern
basin at about 80–85 m) are older, about 14.5–13.3 ka (Rybalko et al. 2022).
Levels were a few metres above today's around −5000 (Lobanova 2019, citing
Devyatova 1986): 35 m from −6000 to −4000 tapering back, 33 m otherwise.
ETOPO1 has partial bathymetry (23–34 m); 33 m floods about 10,800 km² from
the seed, against a real area of 9,891 km². The computed outlet is 77 m. The
Svir (data/rivers/) drains it to Ladoga.

## Mologa-Sheksna lake (low confidence)

A proglacial and early Holocene lake in the lowland now under the Rybinsk
Reservoir. Sadokov et al. 2024 found Allerød peat (13.4–12.1 cal ka BP) at
96.5–102.5 m over 100 km² of the central lowland, which bounds the Allerød
level, and say the basins held lakes "for several millennia until their
ultimate drainage in the early Holocene". The final drainage date, about
10.9–10.7 cal ka BP (−8950 to −8750), is from search summaries of the same
group, not a paper read. Held at 100 m until −8950, then drained by −8750.
ETOPO1 has the reservoir's surface (97–102 m), not the old valley floor, so
the extent (about 3,900 km²) is roughly the reservoir's.

## White Sea (low confidence)

The sea step lowers today's White Sea by the global curve and ignores
uplift, so its shallow bays dried out and the Karelian coast was all land at
−8000, when it should have been higher than today's. The coast was
depressed by the ice: at Chupa the marine limit is 104–142 m at 13–11.5 ka
and the shore 33–40 m at about 6.35 ka (Kolka et al. 2015); a lake at 34 m
was isolated about 5.8 ka (Tolstobrov et al. 2024); at Belomorsk the
settlement Yerpin Pudas I (21.5–23.7 m) is dated 5570–5360 cal BC (Lobanova
2019). It is now a `sea-or-outlet` basin flooded on the uplift-corrected
surface (pipeline/isostasy.py), open to the Barents Sea through the Gorlo
in every year.

Uplift. The Fennoscandian dome, fitted on the Baltic, already fits the
Chupa isolation-basin curve (Kolka et al. 2015, table 2: basins at 81.5,
61, 53 and 33-40 m isolated at 11.23, 10.22, 9.06 and 6.36 cal ka BP)
within about 12 m; these are now calibration checks in `[isostasy]`. It
gives no uplift east of about 36°E, so Onega Bay stayed too dry early and
the box's water grew through the period instead of shrinking. A second,
small dome (`[[isostasy.dome]]`, centre 38.5°E 64.5°N, 200 km, 1.75 mm/yr
today, same scale and tau) is grid-fitted to three eastern points: on the
Onega Peninsula a Late Glacial shore about 15 m above today's at 13-11.5 ka
and a fall of 1.7-1.8 mm/yr over the last 4 ka (Kublitskiy et al. 2023;
Onega Peninsula lake studies), and in southern Onega Bay relative sea level
above 4-5 m until 10.1-9.5 cal ka BP (Kolka et al. 2025, Lake Pertozero).
Misfits are within 7 m.

Limits. The eastern points are from abstracts, and their positions are to
the region, not the basin. The Middle Holocene (Tapes) transgression on the
Onega Peninsula and in the Gulf of Dvina, where relative sea level rose in
the Boreal and early Atlantic, can't be shown by a smooth exponential.

## Black Sea lake (low confidence)

The sea step seeds its flood fill from deep hexes, so on its own the board
gives the Black Sea the global curve (−60 m at −10000). Until it reconnected
to the Mediterranean it was a lake with its own level. The lake layer now
applies that level until the reconnection (`until`): hexes the lake covers
are Water, and sea-step Water it doesn't reach becomes land. From the
reconnection year the sea step's terrain stands.

| Source | Claim | Used |
|---|---|---|
| Soulet et al. 2011 | Reconnection about 9.0 cal ka BP | `until = −7050` |
| Giosan et al. 2009 | Lake about −30 m just before reconnection, from delta and shelf stratigraphy; no catastrophic flood | −30 m at −7100 |
| NW Black Sea shelf studies | Late Neoeuxinian lake about −40 m, not −100 m | −40 m at −10000 |
| Ryan, Pitman and colleagues | Lake at −90 m or lower, catastrophic flood (about 9.1 cal ka) | Not used; to try it, set the level to −95 m |

- At reconnection the board's global sea is at −25 m, so the switch is a
  rise of about 5 m. That is a modest flood, in line with Giosan et al.
- Before about −7700 the lake is higher than the global curve, so less of
  the NW shelf is dry than the board showed before. The Sea of Azov is dry
  throughout the lake stage.
- The Don, Dnieper and Danube (St George branch) now run out to the lake at
  its lowest level (−40 m) and shorten as it rises and at the reconnection.
- The Bosporus is narrower than ETOPO1's 2′ cells, so the computed outlet
  (+5 m, at the window edge) doesn't bind. Outflow through the Bosporus
  (Aksu, Hiscott and colleagues) isn't drawn as a river.
- The Bosporus opens with the lake's end: a `[[sea.channel]]` in
  pipeline/config.toml from −7050, so the hexes on the strait are Water from
  the reconnection and land (a bridge between Thrace and Anatolia) before.
  Soulet et al. 2011 (QSR) put the lake below the old Bosporus sill at
  reconnection, which is why no outflow is drawn before it.

## Saharan lakes, by area (low confidence)

The literature gives these by area, not level, so `area = [[year, km²]]`
sets each year's level to the one at which the flood from the seed covers
that much. Flat floors flood in big steps on ETOPO1's whole metres (Darfur
goes from 1,137 km² at 554 m to 13,190 km² at 555 m), so cells tied on a
metre fill in flood order, ring by ring, to hit the area.

Drake, N.A. et al. 2022. Sedimentary and geomorphic evidence of Saharan
megalakes: a synthesis. *Quaternary Science Reviews* 276:107318. Of the
Saharan basins only Chad and the Niger (Timbuktu) held megalakes in the
AHP; the others held smaller lakes.

- **West Nubian Palaeolake (Darfur):** about 5330 km² (Pachur & Hoelzmann
  1991; Hoelzmann et al. 2000, 2001), mapped from settlements at 555 m. The
  flood reaches 5330 km² at 555.3 m, and the computed outlet (574 m)
  matches the 573 ± 3 m spillway of the older megalake (Ghoneim & El-Baz
  2007). Timing from Pachur & Altmann 2006 (via the Lake Ptolemy summary):
  freshwater by 9.2 ¹⁴C ka, low stands about 8.1 and 7.5 ¹⁴C ka, highstand
  6.7–6.8 ¹⁴C ka, wadis flowing until 3.3–2.4 ¹⁴C ka. Areas between are
  assumed, within Hoelzmann et al.'s 1100–7000 km².
- **Megalake Timbuktu:** 27,352 km² at a 264 m shoreline, median depth 2 m
  (Drake et al. 2022, from the ALOS DEM). No direct dates; formed about
  9.5 ka, gone by the mid-Holocene. Dunes blocked the Niger at the Tossaye
  gorge (Beaudet et al. 1977). ETOPO1 has the gorge cut, so a `dam` line
  (280 m) stands in for the dunes. On ETOPO1 the area is reached at 268.6 m.
- **Wadi Shati palaeolake (Fezzan):** the largest Holocene Fezzan lake, 660 km²;
  perennial 7.75–6.6 ka, shrinking (gypsum) from 6.5 ka, dry just before
  5 ka (Drake et al. 2014, EGU abstract EGU2014-1298; Drake et al. 2018,
  *QSR* 200:376). The seed is the lowest point in Wadi Shati on ETOPO1 and
  is approximate. Smaller than a hex, so a shoreline only.

## Not yet modelled

- **Saharan megalakes** in the Chotts, Ahnet-Mouydir and Fezzan basins date
  to MIS 5 or earlier, with no evidence of AHP megalakes (Drake et al. 2022).
  The White Nile flood lake (4690 km², late Pleistocene to early Holocene;
  Williams et al. 2006) is a backwater on a flowing river, which the
  seed-and-flood model can't represent.
- **Lake Lisan**, Faiyum (Moeris), Van, Urmia: still as the drawn maps have
  them.

## References

- Björck, S. 2008. The late Quaternary development of the Baltic Sea basin.
  In *Assessment of Climate Change for the Baltic Sea Basin*; and Björck et
  al. 2008, An attempt to resolve the partly conflicting data and ideas on
  the Ancylus–Littorina transition, *Polish Geological Institute Special
  Papers* 23:21–26 (Ancylus outlet history; Dana River as a 200–300 year
  fluvial stage after about 10 ka).
  https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-article-BUS6-0020-0020/c/Bjorck_S_An_attempt_PGISP_23_2008.pdf
- Lemke, W. et al. (Darss sill valley at −23/−24 m about 10.3 ka; no Dana
  River at the Darss sill). https://www.io-warnemuende.de/files/forschung/meereswissenschaftliche-berichte/mebe67_2006-roessler.pdf
- Bennike, O. et al. (Great Belt marine before Öresund; oldest marine shells
  about 8.9 cal ka in the northern Great Belt). https://oceanrep.geomar.de/id/eprint/19565
- Soulet, G., Ménot, G., Lericolais, G. & Bard, E. 2011. A revised calendar
  age for the last reconnection of the Black Sea to the global ocean.
  *Quaternary Science Reviews* 30:1019–1026 (about 9000 cal BP; lake below
  the Bosporus sill at reconnection). https://archimer.ifremer.fr/doc/00038/14909

Everything cited above, with links where one exists. Add to this list
whenever a source is used.

- Kolka, V.V. et al. 2025. Relative sea-level changes in the southern part
  of the Onega Bay of the White Sea in the Late Glacial and the Holocene.
  *Doklady Earth Sciences* (abstract read via a search summary).
  https://link.springer.com/article/10.1134/S1028334X25605814
- Kublitskiy, Yu. et al. 2023. Reconstruction of relative sea-level changes
  based on a multiproxy study of isolated basins on the Onega Peninsula (the
  White Sea, northwestern Russia). *Quaternary International* (abstract
  read). https://www.sciencedirect.com/science/article/abs/pii/S1040618222001574
- Bottom sediments of the eastern part of the Onega Peninsula lakes in the
  context of the White Sea relative level changes. *Limnology and
  Freshwater Biology* (abstract read via a search summary).
  https://journals.rcsi.science/2658-3518/article/view/289394
- Bezrodnykh, Y.P. & Sorokin, V.M. 2016. On the age of the Mangyshlakian
  deposits of the northern Caspian Sea. *Quaternary Research* 85(2):245–254.
  https://doi.org/10.1016/j.yqres.2016.01.004
- Sorokin, V. et al. 2021. Late Quaternary regressions in the Caspian Sea.
  GSA Connects 2021, paper 17-4.
  https://gsa.confex.com/gsa/2021AM/webprogram/Paper364725.html
- Rybalko, A.E., Subetto, D.A. et al. 2022. Limnogenesis of large lakes in
  the North-West of the Russian Plain. *Limnology and Freshwater Biology*
  2022(4):1559–1561. https://journals.rcsi.science/2658-3518/article/view/289231
- Lobanova, N.V. 2019. On the chronology of rock art in Karelia (Russia).
  *Fennoscandia archaeologica* XXXVI.
- Lake Onega (area, surface). https://en.wikipedia.org/wiki/Lake_Onega
- Sadokov, D. et al. 2024. Allerød interstadial vegetation and lacustrine
  palaeoenvironment of the central Mologa-Sheksna Lowland. EGU24-12877.
  https://meetingorganizer.copernicus.org/EGU24/EGU24-12877.html
- Kolka, V.V., Korsakova, O.P., Shelekhova, T.S. & Tolstobrova, A.N. 2015.
  Reconstruction of the relative level of the White Sea ... in the area of
  the Chupa settlement (North Karelia). *Vestnik MGTU* 18(2):255–268.
  https://vestnik.mauniver.ru/v18_2_n61/12_kolka_255-268.pdf
- Tolstobrov, D.S. et al. 2024. New data on changes in the White Sea level on
  the Karelian coast in the Holocene. *Limnology and Freshwater Biology*
  2024(4). https://limnolfwbiol.com/index.php/LFWB/article/view/1118
- Armitage, S.J., Bristow, C.S. & Drake, N.A., 2015. West African monsoon
  dynamics inferred from abrupt fluctuations of Lake Mega-Chad. *PNAS*
  112:8543. https://pmc.ncbi.nlm.nih.gov/articles/PMC4507243
- The Caspian Sea level changes during the second part of the Late
  Pleistocene. GSA Annual Meeting 2021.
  https://gsa.confex.com/gsa/2021AM/webprogram/Paper370289.html
- Connection of the Aral and Caspian seas in the Late Pleistocene – early
  Holocene. GSA Annual Meeting 2021.
  https://gsa.confex.com/gsa/2021AM/webprogram/Paper363494.html
- Palynological record of the central and southern Caspian (highstand
  10.55–4.11 cal ka BP). https://core.ac.uk/download/29139334.pdf
- Bezrodnykh et al. 2015; Kroonenberg et al. (Caspian curves; via the
  above).
- Krivonogov, S.K. et al. 2014. The fluctuating Aral Sea. *Gondwana
  Research* 26:284. https://www.cawater-info.net/aral/pdf/krivonogov-et-al-en.pdf
- Létolle, R. et al., 2007. Uzboy and the Aral regressions: a hydrological
  approach. *Quaternary International* 173–174:125.
  https://zin.ru/labs/brackish/pdfs/2007/Uzboy_and_the_Aral_regressions_A_hydrological_approach.pdf
- Migowski, C. et al., 2006. Holocene climate variability and cultural
  evolution in the Near East from the Dead Sea sedimentary record.
  *Quaternary Research* 66:421.
  https://resolve.cambridge.org/core/journals/quaternary-research/article/abs/holocene-climate-variability-and-cultural-evolution-in-the-near-east-from-the-dead-sea-sedimentary-record/CF8DE672C625B2A12CFED45E19B83F7C
- Bookman (Ken-Tor), R. et al., 2004 (Dead Sea levels). Review: Quaternary
  lake levels in the Dead Sea basin: two centuries of research.
  https://cris.haifa.ac.il/en/publications/quaternary-lake-levels-in-the-dead-sea-basin-two-centuries-of-res/
- Drake, N.A., Candy, I., Breeze, P., Armitage, S.J., Gasmi, N.,
  Schwenninger, J.L., Peat, D. & Manning, K., 2022. Sedimentary and
  geomorphic evidence of Saharan megalakes: a synthesis. *Quaternary
  Science Reviews* 276:107318.
  https://pure.royalholloway.ac.uk/files/54133996/Accepted_Manuscript.pdf
- Drake, N.A., Lem, R.E., Armitage, S.J. et al., 2014. The palaeoclimate of
  Wadi Shati, Libyan Sahara: the last 130 ka. EGU General Assembly,
  EGU2014-1298. https://meetingorganizer.copernicus.org/EGU2014/EGU2014-1298-1.pdf
- Drake, N.A. et al., 2018. Reconstructing palaeoclimate and hydrological
  fluctuations in the Fezzan Basin since 130 ka. *QSR* 200:376.
  https://eprints.lancs.ac.uk/id/eprint/128081
- Hoelzmann, P., Kruse, H.-J. & Rottinger, F., 2000; Hoelzmann, P., Keding,
  B., Berke, H., Kröpelin, S. & Kruse, H.-J., 2001. Environmental change and
  archaeology: lake evolution and human occupation in the Eastern Sahara
  during the Holocene. *Palaeogeography, Palaeoclimatology, Palaeoecology*
  169:193. https://doi.org/10.1016/S0031-0182(01)00211-5
- Pachur, H.-J. & Altmann, N., 2006. *Die Ostsahara im Spätquartär*.
  Springer. https://doi.org/10.1007/978-3-540-47625-2 (timing via the
  summary at https://en.wikipedia.org/wiki/Lake_Ptolemy)
- Ghoneim, E. & El-Baz, F., 2007. *Int. J. Remote Sensing* 28:5001.
  https://doi.org/10.1080/01431160701266818
- Beaudet, G. et al., 1977; Petit-Maire, N. & Riser, J., 1983 (Niger dune dam
  and the Araouane; via Drake et al. 2022).
- Williams, M.A.J. et al., 2003, 2006 (White Nile lake; via Drake et al.
  2022).
- Soulet, G., Ménot, G., Lericolais, G. & Bard, E., 2011. A revised calendar
  age for the last reconnection of the Black Sea to the global ocean.
  *Quaternary Science Reviews*.
  https://www.researchgate.net/publication/228824154_A_revised_calendar_age_for_the_last_reconnection_of_the_Black_Sea_to_the_global_ocean
- Soulet, G. et al., 2011. Black Sea "Lake" reservoir age evolution since the
  Last Glacial: hydrologic and climatic implications. *EPSL*.
  https://www.researchgate.net/publication/233920081_Black_Sea_Lake_reservoir_age_evolution_since_the_Last_Glacial_-_Hydrologic_and_climatic_implications
- Giosan, L., Filip, F. & Constatinescu, S., 2009. Was the Black Sea
  catastrophically flooded in the early Holocene? *Quaternary Science
  Reviews*.
  https://www.researchfactory.ro/data/_uploaded/publications/2008-08%20Was%20the%20Black%20Sea%20catastrophically%20flooded%20in%20the%20early%20Holocene.pdf;
  summary: https://www.ancientportsantiques.com/wp-content/uploads/Documents/ETUDESarchivees/BlackSeaInfill/BlackSeaLevel-Giosan2009.pdf
- Holocene marine transgression in the Black Sea: new evidence from the
  northwestern Black Sea shelf (late Neoeuxinian about −40 m).
  https://www.researchgate.net/publication/266320122_Holocene_marine_transgression_in_the_Black_Sea_New_evidence_from_the_northwestern_Black_Sea_shelf
- Compilation of evidence for a rapid Mediterranean-derived submergence of
  the Black Sea shelf (lake surface about −30 m).
  https://www.researchgate.net/publication/310048685_Compilation_of_geophysical_geochronological_and_geochemical_evidence_indicates_a_rapid_Mediterranean-derived_submergence_of_the_Black_Sea's_shelf_and_subsequent_substantial_salinification_in_the_early
- Ryan, W.B.F., Pitman, W.C. et al., 1997, 2003 (deep lake, catastrophic
  flood; via the above).
- Rosentau, A. et al., 2021. A Holocene relative sea-level database for the
  Baltic Sea. *Quaternary Science Reviews*. Data and country-wise
  description: https://doi.org/10.5880/GFZ.1.3.2020.003;
  https://datapub.gfz-potsdam.de/download/10.5880.GFZ.1.3.2020.003vEGWF/2020-003_Rosentau-et-al_Supplement_2_country-wise_data_description.pdf
- Berglund, M., 2004. Holocene shore displacement and chronology in
  Ångermanland, eastern Sweden, the Scandinavian glacio-isostatic uplift
  centre; Berglund 2005, 2010; Veski 1998 (via Rosentau et al. 2021).
- Yoldia Sea (11.7–10.7 cal ka; Baltic Ice Lake final drainage 11,620 cal
  BP): https://en.wikipedia.org/wiki/Yoldia_Sea
- Mastogloia Sea / transition: https://en.wikipedia.org/wiki/Mastogloia_Sea
- Early Holocene history of the Baltic Sea, as reflected in coastal
  sediments in Blekinge (Ancylus 10.7–9.8 cal ka; transition 9.8–8.5 ka).
  https://www.researchgate.net/publication/223181129_Early_Holocene_history_of_the_Baltic_Sea_as_reflected_in_coastal_sediments_in_Blekinge_southeastern_Sweden
- Lemke, W. et al. Early Holocene history of the southwestern Baltic Sea:
  the Ancylus Lake stage.
  https://www.researchgate.net/publication/240525437_Early_Holocene_history_of_the_southwestern_Baltic_Sea_The_Ancylus_Lake_stage
- The eastern shores of the Baltic Sea in the Early Holocene.
  https://rgs-ibg.onlinelibrary.wiley.com/doi/10.1002/geo2.87
- Ludikova, A.V. et al., 2024. *Quaternary* 7(3):31 (the Heinjoki
  paleo-outlet of Lake Ladoga). https://www.mdpi.com/2571-550X/7/3/31
- Dolukhanov, P.M. et al. Evolution of waterways and early human
  settlements in the eastern Baltic area: radiocarbon-based chronology.
  *Radiocarbon*. https://www.cambridge.org/core/product/50D0CE873BE05527714BCCC5D66B8A07
- Lake Ladoga water levels and the Ladoga transgression (Taipale Bay
  coast; Ancylus maximum 17–18 m). https://core.ac.uk/download/226292428.pdf;
  https://journal.fi/iskos/article/view/110412/64904
- Submerged early-Holocene coastal bars in Lake Ladoga. *Limnology and
  Freshwater Biology*. https://journals.rcsi.science/2658-3518/article/view/288500
- Lake Ladoga Holocene history (EGU 2008 and 2009 abstracts).
  https://meetingorganizer.copernicus.org/EGU2009/EGU2009-9406.pdf;
  https://meetings.copernicus.org/www.cosis.net/abstracts/EGU2008/03592/EGU2008-A-03592.pdf
