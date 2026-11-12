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

Everything cited above, with links where one exists. Add to this list
whenever a source is used.

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
