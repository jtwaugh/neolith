# Rivers: sources and reasoning

`rivers.toml` lists the rivers and their histories. `python -m pipeline build`
turns it into `build/rivers.geojson` (polylines with a `state` step function) and
a per-hex `river` class (0 none, 1 minor or seasonal, 2 major perennial).
Years are BCE as negative numbers. Calibrated ka BP converts as BCE = BP − 1950.

## How courses are made

- **The GEOGLOWS v2 stream network** (CC BY 4.0; a subset of NGA's TDX-Hydro,
  CC BY-SA 4.0; https://data.geoglows.org) supplies most courses. It is
  derived from the TanDEM-X DEM, so it includes dry Saharan channels wherever
  the topography still shows them. A river is traced downstream from its
  `from` point. A tributary stops where it meets a river already drawn.
  Until 2026-11-13 the courses were traced on HydroRIVERS v1.0 (Lehner &
  Grill 2013), whose licence can't be passed on under CC BY-SA. Remaining
  mentions of HydroRIVERS in the table below describe that earlier tracing. On the swap,
  every traced course was compared with its HydroRIVERS version: most lie
  within a hex. Four needed new `from`, `to` or waypoints: the Danube (start
  moved to Sigmaringen), the Uzen (stopped at Kamysh-Samar), Wadi Howar (the
  upper wadi turns into a dune sink at 25.4°E) and the Kura (the lower course
  runs south through the Mughan lowland). The Syr Darya southern course,
  Akchadarya and Irharhar, all low confidence, reach the Aral or the chotts
  by slightly different lines (up to 1.6°).
- **Waypoints** cover channels the stream network can't follow (buried under sand
  seas, ending in DEM sinks, or flowing the "wrong" way for today's
  topography). They are read by eye off published figures, are approximate to
  a few tenths of a degree, and are meant to be redrawn in QGIS from the
  georeferenced figures.
- **Shelf extensions** are automatic. From each sea mouth the pipeline follows
  the lowest spill path in ETOPO1 down to the sea at the run's lowest sea level
  (the `[sea] curve`, about −60 m at −10000). Each year a river ends where the
  run of Water hexes at its mouth begins, so its lower course drowns as the
  board's sea rises. Each drowned stretch is a separate segment with its own
  "absent from" year. The Doggerland Rhine–Thames–Elbe system, the Ur-Schatt
  across the Persian Gulf, the Po across the northern Adriatic and the
  Don–Azov all come from this rule, with no dates entered by hand.

## Was there a river running north from Lake Megachad?

**No outflow to the north is documented.** The evidence:

1. **The outlet was to the south.** At highstand (about 325–330 m) Megachad
   spilled through the **Mayo Kébbi** into the Benue, then the Niger, then the
   Atlantic.
   - Armitage, S.J., Bristow, C.S. & Drake, N.A., 2015. West African monsoon
     dynamics inferred from abrupt fluctuations of Lake Mega-Chad. *PNAS* 112:
     8543. https://www.pnas.org/doi/10.1073/pnas.1417655112
   - Marine geochemistry suggests the lake overflowed to the Niger catchment
     almost continuously after about 11 ka:
     https://www.sciencedirect.com/science/article/abs/pii/S0012821X26003031
2. **The "northern" channel is the Bahr el Ghazal, and it stayed inside the
   Chad basin.** It runs northeast from the southern (Lake Chad) basin over a
   sill at about 285–288 m into the Bodélé depression.
   - At full highstand both basins were one lake, so the Bahr el Ghazal was
     a strait, not a river. In the app it is drawn only where the board shows
     land. With the drawn Megachad it is submerged through the humid period,
     which is the right outcome.
   - The Bodélé dried abruptly after the last highstand, about 5 ka.
   - Sources: Bristow, Drake & Armitage 2009, Deflation in the dustiest place
     on Earth: the Bodélé Depression, Chad. *Geomorphology* 105:50. Drake &
     Bristow 2006, Shorelines in the Sahara: geomorphological evidence for an
     enhanced monsoon from palaeolake Megachad. *The Holocene* 16:901.
3. **The Tibesti was the watershed.**
   - **South side:** it drained into Megachad. The Angamma delta lies at the
     lake's northern tip, and seasonal flow from the Tibesti ended about
     4.3 ka (Bristow et al. 2018, *Quaternary Science Reviews*).
   - **North-east side:** it fed the **Kufrah River**, which flowed **north**
     through Kufra. This is about 900 km of channel mapped with ALOS PALSAR
     radar. Its link to the Gulf of Sirte via Wadi Sahabi is "likely" but not
     proven, because the Calanscio sand sea blocks the radar.
     - Paillou, P. et al. 2009. Mapping of a major paleodrainage system in
       eastern Libya using orbital imaging radar: The Kufrah River. *EPSL*
       277:327. https://hal.archives-ouvertes.fr/hal-00405365
     - Paillou, P. et al. 2012. The Kufrah paleodrainage system in Libya: a
       past connection to the Mediterranean Sea? *C. R. Geoscience* 344:406.
       https://hal.archives-ouvertes.fr/hal-00833333
4. **Drake et al. 2011** connect the Fezzan, Serir Tibesti and Kufra basins
   only by alluvial fans and lake overflow, not by a channel out of Megachad.
   They map these as linked catchments for about 11–8 ka.
   - Drake, N.A., Blench, R.M., Armitage, S.J., Bristow, C.S. & White, K.H.,
     2011. Ancient watercourses and biogeography of the Sahara explain the
     peopling of the desert. *PNAS* 108:458.
     https://pmc.ncbi.nlm.nih.gov/articles/PMC3021035

**So the map shows:**
- the Chari and Logone flowing into Megachad
- the Mayo Kébbi spilling south to the Benue
- the Bahr el Ghazal linking the lake to the Bodélé, inside the basin
- the Tibesti wadis feeding the Angamma delta
- a separate north-flowing Kufrah/Sahabi system rising on the far side of
  the Tibesti
- the Wadi Howar ("Yellow Nile") running east from the Ennedi to the Nile

**Still open:** read the Drake 2011 SI §3 and Ghoneim & El-Baz 2007 (*Int. J.
Remote Sensing* 28:5001, on a radar-mapped mega-paleodrainage in the eastern
Sahara) for any argued spillway north. Neither is reported as one in the
secondary sources checked here.

## River by river

Confidence: **high** means a modern river whose course is not in doubt;
only its lower course changes, with sea level. **Medium** means the timing is
from regional humid-period chronologies. **Low** means the course and/or
timing is a reasonable reading of sparse evidence.

| River | Course | State | Confidence | Basis |
|---|---|---|---|---|
| Nile, Blue Nile | Stream network (the Nile stopped at the delta head near Cairo) | perennial | high | Modern river. Nile flow was higher in the African Humid Period (AHP) but never stopped. |
| Atbara | Stream network | perennial, seasonal from −3500 | medium | Seasonal today. Assumed perennial during the AHP, which ended about 5.5 ka (deMenocal et al. 2000, *QSR* 19:347). |
| Wadi Howar | Stream network to 27.4°E, then waypoints to the Nile | seasonal; perennial −8500; seasonal −3300 | medium | Kröpelin & Pachur 1987, *Science* 237:298; Kuper & Kröpelin 2006, *Science* 313:803 (monsoon arrives in the eastern Sahara about 8500 BCE, retreats from Egypt about 5300 BCE). HydroRIVERS loses the channel in a DEM sink. Ennedi headwaters west of 24.4°E not yet drawn. |
| Niger, Benue, Senegal | Stream network | perennial | high | Modern rivers. |
| Tilemsi, Azawagh | Stream network | seasonal until −3500 | low | Fossil valleys draining the Adrar des Ifoghas and Aïr to the Niger. Dated to the AHP generally (Drake et al. 2011). |
| Chari, Logone | Stream network | perennial | high | Modern rivers feeding Lake Chad. |
| Mayo Kébbi (the Megachad spillway) | Stream network | flows while Megachad is at its outlet (lakes.toml) | medium | Megachad overflow from about 11 ka to the end of the highstand about 5 ka (Armitage et al. 2015). The modern Logone still spills into it in big floods. |
| Bahr el Ghazal (Chad) | waypoints | flows while Megachad is above the 287 m sill; under the lake above about 300 m | medium | See above. Submerged on the board while Megachad is drawn. Intermittent late-Holocene flow (last in the 1870s). |
| Tibesti wadis | Stream network | seasonal | low | Angamma delta; flow ended about 4.3 ka, after the map's end. |
| Kufrah River, and its Uweinat branch from the Gilf Kebir–Uweinat side | waypoints | seasonal −8500 to −5300 | low | Paillou et al. 2009, 2012 for the course and the eastern branch (read by eye off their radar maps). Timing follows the eastern-Sahara humid window (Kuper & Kröpelin 2006). Not shown to have reached the sea in the Holocene. |
| Irharhar | Stream network to 27.4°N, then waypoints to Chott Melrhir | seasonal until −3500 | low | Drake et al. 2011; Coulthard et al. 2013, *PLoS ONE* 8:e74834 (mainly a last-interglacial river; Holocene flow weaker). |
| Saoura | Stream network, then waypoints along the Oued Messaoud | seasonal | medium | It still floods today. |
| Tamanrasett (lower course) | waypoints | seasonal until −3500 | low | Skonieczny, C. et al. 2015. African humid periods triggered the reactivation of a large river system in Western Sahara. *Nature Communications* 6:8751. Only the radar-mapped Mauritanian stretch is drawn. The upper course from the Hoggar is conjectural. |
| Tigris | Stream network + shelf (from Diyarbakır) | perennial | medium | Present course past Baghdad, Kut and Amarah. Before this change the `from` point snapped to a Euphrates headwater, so the "Tigris" line followed the Euphrates. Uruk-period joint channel belts (Morozova 2005, *Geoarchaeology* 20:401) and a Gharraf course past Girsu and Lagash are argued but not placeable. The Ur-Schatt across the dry Gulf comes from the shelf rule. Caveat: the mid-Holocene transgression. Bogemans et al. (2016, 2017) date it from about 7.8 ka, estuarine but confined to the channels, with progradation from about 4.9 ka. Its inland limit is put at Kut, Samawah, or Nasiriyah and Amarah by different authors (summarised by Jotheri et al. 2017). ETOPO's modern, sediment-filled plain can't show it. |
| Euphrates (upper) | Stream network, stopped near Sippar | perennial | high | |
| Euphrates (old course) | waypoints: Sippar, Kish, Nippur, Shuruppak, Uruk, Larsa, Ur, then the marshes to the Tigris | perennial | low | The 4th-millennium cities sit on this levee (Adams 1981, *Heartland of Cities*). Uruk had a freshwater channel from the 8th millennium BCE, and its first avulsion cycle ran from the Neolithic to the Uruk period (Jotheri et al. 2017, *Quaternary International*, doi:10.1016/j.quaint.2017.11.037). The present western course (Hilla–Samawah–Nasiriyah) is later and not drawn. |
| Nile delta: Canopic, Pelusiac | waypoints via the branch towns + shelf | perennial | medium | The modern delta began forming 8–7 ka (Stanley & Warne 1993, 1994). The Canopic was active for "thousands of years" before 1000 BC (Stanley, Warne & Schnepp 2004, *J. Coastal Research* 20:920; Wilson 2012, *Water History*). Before about −6000 the branches crossed a wider exposed delta plain, and the shelf rule extends them. |
| Nile delta: Sebennytic | waypoints + shelf | perennial from −5050 | low | Channel deposits from about 7 ka cal BP (Stanley 2021, *Quaternary* 4:39). |
| Nile delta: Rosetta, Damietta | — | not drawn | medium | The Bolbitine–Rosetta branch began about 1000 BC (Wilson 2012); the Damietta (Phatnitic) is later. |
| Jordan | Stream network | perennial | high | |
| Amu Darya, Syr Darya (upper courses) | Stream network, stopped at the delta heads | perennial | high | Courses enter the grid at 66°E. The deltas are below. |
| Amu Darya (Daudan) | Stream network (dry channel past Khiva and Dashoguz into the Sarykamysh depression) | perennial | low | Kes' (1979) has the Amu feeding Sarykamysh and the Uzboy for most of the Holocene. Krivonogov et al. 2014 (*Gondwana Research* 26:284): Sarykamysh full about 5–4 ka cal BP (Kelteminar settlement on the upper Uzboy). |
| Akchadarya | Stream network, linked to the Amu by two waypoints | perennial from −5000 | low | Krivonogov et al. 2014: channel fill 6490–6940 cal BP at 42.06°N 61.46°E; sites 5–3 ka cal BP. "Functioned at least since the middle Holocene"; earlier activity unknown, so absent before −5000. |
| Amu Darya modern lower course (Aral sub-delta) | — | not drawn | low | Dated from antiquity on (Krivonogov et al. 2014; Tolstov 1962), after the map's end. |
| Syr Darya (southern course) | Stream network, linked by one waypoint | perennial | low | Krivonogov et al.'s Daryalyk: shells 10,770–11,190 cal BP at 44.61°N 65.21°E. "Courses south of the Kuvandarya functioned in the middle–early Holocene"; the delta shifted north over time. |
| Karadarya | Stream network | seasonal | low | Potamogeton fruit in the bed, 6170–6290 cal BP at 44.29°N 65.10°E. Assumed a secondary branch for the whole period. |
| Syr Darya northern courses | — | not drawn | medium | Inkardarya 4–3 ka; Janadarya and Kuvandarya from 2.7–2.5 ka; the modern Kerderi/Small Aral course late medieval (Krivonogov et al. 2014). All after −3000. |
| Uzboy | waypoints, from the Sarykamysh outlet to the Caspian (extended to its lowest level) | seasonal while Sarykamysh overflows | low | Flow phases are disputed. Kes' (1979) has the Amu flowing via Sarykamysh and the Uzboy to the Caspian for most of the Holocene; Létolle et al. 2007 (*Quaternary International* 173:125) report repeated reactivations. HydroRIVERS drains into the Sarykamysh sink, so waypoints. |
| Volga, Ural | Stream network, extended to the Caspian at its lowest level | perennial | high | Lower courses drown as the Caspian rises (lakes.toml). |
| Don, Dnieper, Danube (upper) | Stream network + shelf; the Danube stopped at the Chilia fork above Tulcea | perennial | high | The Don, Dnieper and Danube (St George branch) run out to the Black Sea lake at its lowest level (−40 m) until the reconnection at −7050, and shorten as it rises (`data/lakes/`). |
| Danube (St George branch) | waypoints past Mahmudia to Sfântu Gheorghe + shelf | perennial to −5250 | low | The St George I lobe, 8900–7200 BP (Vespremeanu-Stroe et al. 2017, *Marine Geology*, AMS ¹⁴C and OSL). Earlier, the same outlet crossed the exposed shelf. Giosan et al. 2006 (*Geology* 34:757) instead date St George I to about 5.5–3.6 ka; the newer chronology is used. The channel probably kept some flow after the switch; drawn as absent. |
| Danube (Sulina branch) | waypoints past Crişan to Sulina + shelf | perennial from −5250 | low | The Sulina lobe, 7200–2000 BP (Vespremeanu-Stroe et al. 2017; Giosan et al. 2006 give 3.6–2.0 ka). |
| Danube Chilia and St George II lobes | — | not drawn | medium | After 2000 BP; the Chilia lobes from about 1.5–0.9 ka (Filip & Giosan 2014, *Anthropocene*; Vespremeanu-Stroe et al. 2017). |
| Rhine (upper), Thames, Elbe, Seine | Stream network + shelf; the Rhine stopped at Wijk bij Duurstede | perennial | high | Doggerland and Channel River drainage from the shelf rule. |
| Rhine (valley course) | waypoints along the Late Weichselian valley to its mouth near Rotterdam + shelf | perennial to −5450 | medium | Berendsen & Stouthamer 2002: early Holocene flow in a few large incised channels in the valley (infills dated 9800–8000 ¹⁴C BP). The Benschop system (from 7600 ¹⁴C BP) stayed in the valley until it avulsed near Gouda about 6500 ¹⁴C BP (≈7.4 cal ka, −5450). |
| Rhine (Benschop course) | waypoints: IJsselstein, Benschop, Gouda, to the tidal area between Den Haag and Leiden + shelf | perennial −5450 to −4350 | medium | Same source (their Fig. 7). Abandoned at the Wijk bij Duurstede avulsion about 5500 ¹⁴C BP (≈6.3 cal ka, −4350). |
| Rhine (Oude Rijn) | waypoints: Utrecht, Woerden, Leiden, Katwijk + shelf | perennial from −4350 | medium | The Utrecht river system: the main Rhine course from about 5500 ¹⁴C BP until it was dammed in AD 1122 (Berendsen & Stouthamer 2002, Fig. 8). The avulsion node sits on the Peel Boundary Fault zone. Smaller SW-flowing distributaries existed throughout but aren't drawn. From −4200 the board turns the strip west of Woerden to Water, so the line stops there. ETOPO has the drained polders below sea level; that roughly matches the real tidal and peat back-barrier area, which the Oude Rijn crossed to the sea at Katwijk. |
| Meuse | Stream network + shelf | perennial | medium | Followed the southern edge of the Late Weichselian valley to the Rotterdam estuary. Channel belts older than 6000 ¹⁴C BP survive only in fragments, so the modern course stands in down to the Biesbosch, then waypoints to the Rotterdam estuary. |
| Rhône (upper) | Stream network, stopped at Arles | perennial | high | |
| Rhône (Saint-Ferréol branch) | waypoints south from Arles to the Beauduc–Faraman coast + shelf | perennial | low | Vella et al. 2005 (*Marine Geology* 222–223:235): the delta plain builds from about 7000 ¹⁴C BP; the first fluvial input followed a palaeothalweg south of Arles to the centre of the plain; the Saint-Ferréol lobe grew 6500–6000 BP (after L'Homer) and stayed active to about 2000 BP. Before 7000 BP the shelf rule carries the river across the exposed shelf. |
| Rhône (Ulmet branch) | waypoints towards Saintes-Maries + shelf | perennial from −4650 | low | Oldest dated Ulmet channel 5780 ± 40 ¹⁴C BP (≈6.6 cal ka); contemporaneous with Saint-Ferréol to about 2000 BP (Vella et al. 2005). |
| Rhône (Peccaïs branch) | waypoints towards Aigues-Mortes + shelf | perennial from −4900 | low | Distributaries multiplied west of the Peccaïs Rhône from about 6000 ¹⁴C BP (≈6.85 cal ka); the Peccaïs lobe built 5400–4350 BP (Vella et al. 2005, after L'Homer 1975). |
| Grand Rhône, Petit Rhône | — | not drawn | medium | Later courses (Vella et al. 2005). The whole Rhône delta is about one hex across, so its branches are sub-hex detail with approximate waypoints. |
| Po | Stream network, stopped short of the modern delta at about 12.25°E, + shelf | perennial | medium | The modern course below Ficarolo dates from the AD 1152 avulsion; no main course downstream of it is attested before the Po di Adria (about 4.0–2.5 ka) and the Po di Spina (1st millennium BCE), so the modern line stands in. Bruno et al. 2017 (*Sedimentology* 64:1792): an estuary migrated landward 11.5–7.0 kyr BP; the Po split into three branches around 10 ka (within a few km); the shoreline reached its furthest inland position about 7.7 cal kyr BP, roughly 30 km inland of today. The board's coast (ETOPO1 and the sea curve) can't show that transgression. |
| Vistula | Stream network (`shelf = false`) | perennial | high | The Baltic stages (Baltic Ice Lake, Yoldia, Ancylus, Littorina) are modelled in `data/lakes/` on an uplift-corrected surface; an extension across today's sea floor wouldn't follow them, so the Vistula ends at its modern mouth. |
| Kura, Terek, Sulak | Stream network, extended to the Caspian at its lowest level | perennial | high | Modern rivers. Their lower courses drown as the Caspian rises (lakes.toml), as for the Volga and Ural. Holocene Kura and Terek delta branches aren't dated well enough to time (Kura delta Caspian-level work: INTAS project 2005-1000008-8078; Terek avulsions are historical, Magritsky et al. 2018). |
| Aras | Stream network from the Bingöl highlands, stopped at the Kura near Sabirabad | perennial | high | Historical accounts of a separate Caspian mouth aren't dated, so it is drawn as a Kura tributary throughout. |
| Kuban | Stream network to its modern mouth at Temryuk + the Black Sea lake extension (joins the Don's path across the dry Azov) | perennial | medium | Giaime et al. 2016: the Taman peninsula was an archipelago about 6 ka and the delta prograded after that; the 2019 *Geomorfologiya* paper dates the Bugaz stage of the transgression 9.5–7.9 ka. The ancient Hypanis branch to the Kiziltash liman (Black Sea) isn't dated, so the modern Azov course stands in. |
| Rioni | Stream network + Black Sea lake extension | perennial | medium | Laermanns et al. 2018 (*Quaternary International* 465:85): a barrier–lagoon coast until about 5000 BC, delta progradation mostly 3500–1500 BC. ETOPO's modern Colchis plain can't show the inland coast. |
| Inguri, Çoruh | Stream network + Black Sea lake extension | perennial | high | Modern rivers on a steep, narrow shelf. |
| Douro | Stream network + shelf | perennial | high | Naughton et al. 2007 (*J. Coastal Research*): estuarine infill as the sea rose 11.5–6 cal ka; the main channel had moved north to about its present line by 6530 cal BP. |
| Guadalquivir | Stream network to Sanlúcar + shelf | perennial | medium | Dabrio et al. 2000 (*Marine Geology* 162:381): marine influence in the Gulf of Cádiz estuaries from about 10 ka; maximum flooding about 6500 BP, then infilling by lateral progradation. At its maximum the estuary (later the Roman Lacus Ligustinus) reached towards Seville (2007 Seville cores, *El registro holoceno del estuario del Guadalquivir*); the board's coast can't show it. |
| Neva | — | not drawn | medium | Formed about 3500–3200 cal BP (≈ −1400), when the Ladoga transgression broke through the Neva threshold (Ludikova et al. 2024, *Quaternary* 7:31; Dolukhanov et al., *Radiocarbon*). After the map's end. |
| Heinjoki Strait (Ladoga outlet) | waypoints from the modelled Ladoga shore (today's, near Taipale Bay) through the Vuoksi lowland past the Vetokallio threshold at Heinjoki (Veshchevo) to Vyborg Bay | perennial from −8250 | low | Ladoga's outlet to the Baltic before the Neva: from about 10.2 cal ka (MDPI review in Ludikova et al. 2024; Dolukhanov et al. date the waterway from about 11.5 cal ka), flow falling from about 4.1 cal ka and ending 3.5–3.2 cal ka. Waypoints are approximate. Drawn from −8250, when the Baltic entry stops keeping the drawn strait over the isthmus (data/lakes/SOURCES.md); its western end drowns in Vyborg Bay when the Baltic model floods it. |
| Vuoksi | Stream network from Imatra down the lake corridor to the Heinjoki Strait | perennial from −3750 | low | Saimaa broke through the Salpausselkä at Imatra about 5.7 cal ka (Saarnisto 1970). Whether its water then went east to Ladoga or west through Heinjoki is unclear; it is drawn into the strait. |
| Svir | Stream network from Lake Onega, stopped at the Ladoga shore | perennial | high | Onega's outlet to Ladoga through the window (both lakes in `data/lakes/`). HydroRIVERS carries it on down the Neva, which formed only about −1400, so it is stopped at the Svir mouth. |
| Oka, Kama | Stream network to the Volga | perennial | high | Modern courses. Added for the Upper Volga–Oka bog sites and the Kama Neolithic (data/places/plans/upper_volga_lakes.toml, kama_middle_urals.toml). |
| Samara | Stream network to the Volga | perennial | high | Modern course; the Samara Bend sites (data/places/plans/samara_bend.toml). |
| Uzen | Stream network to the Kamysh-Samar sink | seasonal | medium | HydroRIVERS joins the Bolshoi and Maly Uzen into one channel. Snow-fed steppe rivers that shrink to pools in summer; Varfolomeevka (Orlovka culture) is on the Maly Uzen (data/places/plans/north_caspian_lowland.toml). |
| Manych | Stream network from the Manych-Gudilo chain to the Don | seasonal | medium | The Caspian–Black Sea spillway through the trough is early Khvalynian, 17.7–14.9 ka by OSL, and "ceased to exist" afterwards; the board's Caspian outlet there (+18 m) is above its level all period (data/places/plans/manych.toml). Drawn as a minor intermittent river. |

## Known gaps

- **Lake levels:** Megachad, the Caspian, Aral, Sarykamysh and the Dead Sea
  are modelled (`data/lakes/`), and the Mayo Kébbi, Bahr el Ghazal and Uzboy
  follow them as spillways. The Volga, Ural and Uzboy extend to the Caspian
  at its lowest level. The Black Sea lake stage (to −7050) and the Saharan
  palaeolakes and the Baltic stages are modelled too.
- **Course changes** are drawn for the Amu Darya and Syr Darya deltas, the
  Euphrates, the Nile delta and the Rhine–Meuse delta. The Rhine–Meuse
  courses follow the main channel in Berendsen & Stouthamer's maps. Their
  full dated channel-belt GIS (Cohen et al. 2012, DANS) is restricted
  access; with it, every belt could be imported with its own dates.
  The Danube delta follows the 2017 lobe chronology, and the Rhône delta
  Vella et al. 2005. The Po has no attested course change downstream of
  Ficarolo within the period.
- **Inland transgressions** at the Gulf head, in the Po plain and in the
  Nile delta can't be shown: ETOPO1 is today's sediment-filled surface. A
  per-region "coast override" (Water hexes from a dated shoreline map)
  would be the way to add them. The Tigris's
  early course and the Euphrates's westward shifts within the period are not
  dated well enough to time.
- **River size is fixed**, so the Nile's larger humid-period discharge isn't
  shown.
- **Ladoga's level** is held at its present extent (data/lakes/), so the
  start of the Ladoga transgression before −3000 isn't shown.
- **Inland coasts at the Guadalquivir and Rioni:** the mid-Holocene
  Guadalquivir estuary up towards Seville and the Colchis coast before the
  Rioni delta built out want dated shorelines in `data/coasts/`.
- **Not yet catalogued:** Loire, Garonne, Ebro, Tagus, Oder, Northern
  Dvina, Helmand, Karun, Orontes, and other Saharan fossil rivers
  (Wadi Sahel, the Chotts' Oued Djedi, the Fezzan wadis).

## References

Everything cited above, with links where one exists. Add to this list
whenever a source is used. A river or lake isn't finished until its row
above and its references here are in place.

### Data
- GEOGloWS ECMWF Streamflow Service, Hydrological Model Version 2.0: stream
  network (`global_streams_simplified.gpkg`) and attribute table
  (`v2-model-table.parquet`), CC BY 4.0. https://data.geoglows.org ,
  https://geoglows-v2.s3.amazonaws.com . Its streams are a subset of NGA's
  TDX-Hydro (2023, from the TanDEM-X DEM; CC BY-SA 4.0). Courses have been
  traced along it since 2026-11-13 (`pipeline/geoglows.py`); the files are
  downloaded at build time, not committed. Upstream area is `DSContArea`, so
  the `min_upland` values in `rivers.toml` mean what they did. GEOGLOWS has
  no endorheic flag: a network counts as reaching the sea when ETOPO cells
  below 0 m within 0.25° of its mouth are today's sea (open ocean on the hex
  grid, or the Baltic, Black Sea or White Sea boxes in `data/lakes/lakes.toml`).
- Lehner, B. & Grill, G., 2013. Global river hydrography and network
  routing: HydroSHEDS/HydroRIVERS. *Hydrological Processes* 27:2171.
  https://www.hydrosheds.org/products/hydrorivers . Used until 2026-11-13,
  then replaced by GEOGLOWS v2, because its WWF licence can't be passed on
  under the project's CC BY-SA data licence.
- Cohen, K.M., Stouthamer, E., Pierik, H.J. & Geurts, A.H., 2012.
  Rhine-Meuse Delta Studies' Digital Basemap for Delta Evolution and
  Palaeogeography. Utrecht University / DANS (restricted access).
  https://doi.org/10.17026/dans-x7g-sjtw. Report:
  https://dspace.library.uu.nl/bitstream/handle/1874/319441/2012.pdf

### Chad basin and the Sahara
- Armitage, Bristow & Drake 2015, *PNAS* 112:8543.
  https://www.pnas.org/doi/10.1073/pnas.1417655112
- Megachad overflow to the Niger after 11 ka (marine geochemistry).
  https://www.sciencedirect.com/science/article/abs/pii/S0012821X26003031
- Drake, Blench, Armitage, Bristow & White 2011, *PNAS* 108:458.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC3021035
- Paillou et al. 2009, *EPSL* 277:327. https://hal.archives-ouvertes.fr/hal-00405365
- Paillou et al. 2012, *C. R. Geoscience* 344:406.
  https://hal.archives-ouvertes.fr/hal-00833333
- Bristow, Drake & Armitage 2009, *Geomorphology* 105:50; Drake & Bristow
  2006, *The Holocene* 16:901; Bristow et al. 2018, *QSR*.
- Kröpelin & Pachur 1987, *Science* 237:298 (Wadi Howar); Kuper & Kröpelin
  2006, *Science* 313:803.
- Skonieczny et al. 2015, *Nature Communications* 6:8751 (Tamanrasett).
- Coulthard et al. 2013, *PLoS ONE* 8:e74834 (Irharhar).
- deMenocal et al. 2000, *QSR* 19:347 (end of the African Humid Period).
- Ghoneim & El-Baz 2007, *Int. J. Remote Sensing* 28:5001.

### Central Asia
- Krivonogov, S.K. et al. 2014. The fluctuating Aral Sea: a multidisciplinary
  study of its history during the last 2000 years. *Gondwana Research*
  26:284. https://www.cawater-info.net/aral/pdf/krivonogov-et-al-en.pdf
- Létolle, R., Micklin, P., Aladin, N. & Plotnikov, I., 2007. Uzboy and the
  Aral regressions: a hydrological approach. *Quaternary International*
  173–174:125.
  http://www.cawater-info.net/bk/water_land_resources_use/english/english_ver/pdf/uzboy.pdf
- Kes', A.S., 1979, 1983, 1991; Tolstov, S.P., 1962 (cited via Krivonogov
  et al. 2014).

### Mesopotamia
- Jotheri, J., Altaweel, M., Tuji, A., Anma, R., Pennington, B., Rost, S. &
  Watanabe, C., 2017. Holocene fluvial and anthropogenic processes in the
  region of Uruk in southern Mesopotamia. *Quaternary International*.
  https://doi.org/10.1016/j.quaint.2017.11.037;
  https://www.ancientportsantiques.com/wp-content/uploads/Documents/PLACES/IndOc-Gulf/Uruk-Jotheri2018.pdf
- Holocene avulsion history of the Euphrates and Tigris rivers in the
  Mesopotamian floodplain (11 avulsions).
  https://www.researchgate.net/publication/340502784_Holocene_avulsion_history_of_the_Euphrates_and_Tigris_rivers_in_the_Mesopotamian_floodplain
- Morozova, G.S., 2005. A review of Holocene avulsions of the Tigris and
  Euphrates rivers. *Geoarchaeology* 20:401.
  https://www.researchgate.net/publication/230035623_A_review_of_Holocene_avulsions_of_the_Tigris_and_Euphrates_Rivers_and_possible_effects_on_the_evolution_of_civilizations_in_Lower_Mesopotamia
- Adams, R.McC., 1981. *Heartland of Cities*. University of Chicago Press.
- Bogemans et al. 2016, 2017 (Gulf-head transgression; cited via Jotheri et
  al. 2017).

### Nile delta
- Stanley, J.-D., Warne, A.G. & Schnepp, G., 2004. Geoarchaeological
  interpretation of the Canopic, largest of the relict Nile delta
  distributaries. *J. Coastal Research* 20:920.
  https://repository.si.edu/items/a8989891-9ea0-4682-a628-afe033f90504
- Stanley, J.-D., 2021. Holocene aridity-induced interruptions of human
  activity along a fluvial channel in Egypt's northern delta. *Quaternary*
  4:39. https://doi.org/10.3390/quat4040039
- Wilson, P., 2012. Waterways, settlements and shifting power in the
  north-western Nile delta. *Water History*.
  https://www.ancientportsantiques.com/wp-content/uploads/Documents/PLACES/Egypt-Libya/NileDelta/NileDelta-Wilson2012.pdf
- Stanley, J.-D. & Warne, A.G., 1993 (*Science* 260:628), 1994 (*Science*
  265:228): initiation of Holocene deltas.

### Danube delta
- Vespremeanu-Stroe, A., Preoteasa, L., Zăinescu, F. et al., 2017. Holocene
  evolution of the Danube delta: an integral reconstruction and a revised
  chronology. *Marine Geology*.
  https://www.sciencedirect.com/science/article/abs/pii/S0025322717301445
- Giosan, L., Donnelly, J.P., Constantinescu, S., Filip, F., Ovejanu, I.,
  Vespremeanu-Stroe, A., Vespremeanu, E. & Duller, G.A.T., 2006. Young
  Danube delta documents stable Black Sea level since the middle Holocene:
  morphodynamic, paleogeographic, and archaeological implications.
  *Geology* 34:757.
- Filip, F. & Giosan, L., 2014. Evolution of Chilia lobes of the Danube
  delta: reorganization of deltaic processes under cultural pressures.
  *Anthropocene*.
  https://www.sciencedirect.com/science/article/abs/pii/S2213305414000368
- Giosan, L. et al. Black Sea catastrophically flooded in the early
  Holocene (the reconnection; see data/lakes/SOURCES.md for the lake stage). https://www.whoi.edu/cms/files/Giosan_et_al-all_46963.pdf

### Rhône and Po deltas
- Vella, C., Fleury, T.-J., Raccasi, G., Provansal, M., Sabatier, F. &
  Bourcier, M., 2005. Evolution of the Rhône delta plain in the Holocene.
  *Marine Geology* 222–223:235. https://doi.org/10.1016/j.margeo.2005.06.028;
  https://www.sciencedirect.com/science/article/abs/pii/S0025322705002136
- L'Homer, A., 1975. Notice de la Carte géologique des Saintes-Maries-de-la-Mer
  au 1/50,000 (via Vella et al. 2005).
- Bruno, L., Bohacs, K.M., Campo, B., Drexler, T.M., Rossi, V., Sammartino,
  I., Scarponi, D., Hong, W. & Amorosi, A., 2017. Early Holocene
  transgressive palaeogeography in the Po coastal plain (northern Italy).
  *Sedimentology* 64:1792. https://doi.org/10.1111/sed.12374;
  https://iris.unimore.it/bitstream/11380/1169644/3/sed.12374.pdf
- Po di Adria (about 4.0–2.5 ka) and Po di Spina: Water matters.
  Geoarchaeology of the city of Adria (Po Delta).
  https://www.researchgate.net/publication/307946897_Water_matters_Geoarchaeology_of_the_city_of_Adria_and_palaeohydrographic_variations_Po_Delta_Northern_Italy;
  Chrono-spatial modelling of deltaic progradation (Spina lobe).
  https://www.vliz.be/imisdocs/publications/422094.pdf

### Rhine–Meuse delta
- Berendsen, H.J.A. & Stouthamer, E., 2002. Paleogeographic evolution and
  avulsion history of the Holocene Rhine-Meuse delta, The Netherlands.
  *Netherlands Journal of Geosciences* 81:97.
  https://doi.org/10.1017/S0016774600020606
- Stouthamer, E. & Berendsen, H.J.A., 2000. Factors controlling the Holocene
  avulsion history of the Rhine-Meuse delta. *J. Sedimentary Research*
  70:1051.
- Berendsen, H.J.A. & Stouthamer, E., 2001. *Palaeogeographic development of
  the Rhine-Meuse delta, The Netherlands*. Van Gorcum, Assen.

### Caucasus
- Giaime, M., Avnaim-Katav, S., Morhange, C., Marriner, N. et al., 2016.
  Evolution of Taman peninsula's ancient Bosphorus channels (south-west
  Russia): deltaic progradation and Greek colonisation. *J. Coastal Research*.
  https://www.ancientportsantiques.com/wp-content/uploads/Documents/PLACES/Bosphorus-BlackSea/Taman-Giaime2016.pdf;
  https://kups.ub.uni-koeln.de/28640
- 2019. Evolution of the main geomorphological
  structure of the Holocene Kuban river delta. *Geomorfologiya* 2019(4):77.
  https://doi.org/10.31857/s0435-42812019477-87;
  https://journals.eco-vector.com/0435-4281/article/view/17660
- Laermanns, H., Kelterbaum, D., May, S.M., Elashvili, M., Opitz, S.,
  Hülle, D., Rölkens, J., Verheul, J., Riedesel, S. & Brückner, H., 2018.
  Mid- to Late Holocene landscape changes in the Rioni Delta area (Kolkheti
  lowlands, W Georgia). *Quaternary International* 465:85.
  https://research.aber.ac.uk/en/publications/mid-to-late-holocene-landscape-changes-in-the-rioni-delta-area-ko/
- INTAS project 2005-1000008-8078: Caspian sea-level highstands and
  lowstands from the Kura delta. https://cordis.europa.eu/project/id/INTAS2005-1000008-8078
- Magritsky, D.V. et al., 2018. Terek and Sulak mouth changes in the
  geological past and modern period.
  https://istina.msu.ru/conferences/presentations/117321148
- ISRSE 2005 proceedings: satellite monitoring of
  the Ural, Terek, Sulak and Kura deltas.
  https://www.isprs.org/proceedings/2005/isrse/html/papers/265.pdf

### Iberia
- Dabrio, C.J., Zazo, C., Goy, J.L., Sierro, F.J., Borja, F., Lario, J.,
  González, J.A. & Flores, J.A., 2000. Depositional history of estuarine
  infill during the last postglacial transgression (Gulf of Cadiz, Southern
  Spain). *Marine Geology* 162:381. https://doi.org/10.1016/S0025-3227(99)00069-9;
  https://eprints.ucm.es/id/eprint/11355/1/2000_1_margeo.pdf
- 2007. El registro holoceno del estuario del
  Guadalquivir en el área de Sevilla: aproximación geoarqueológica.
  https://investiga.upo.es/documentos/5ec8591729995265802be156
- Naughton, F., Sánchez Goñi, M.F., Drago, T. et al., 2007. Holocene
  changes in the Douro estuary (northwestern Iberia). *J. Coastal Research*
  23(3). https://bioone.org/journals/journal-of-coastal-research/volume-2007/issue-233/05-0462.1/Holocene-Changes-in-the-Douro-Estuary-Northwestern-Iberia/10.2112/05-0462.1.full

### Ladoga and the Neva
- Ludikova, A.V. et al., 2024. Diatom evidence for the Heinjoki paleo-outlet
  of Lake Ladoga, northern Karelian Isthmus. *Quaternary* 7(3):31.
  https://www.mdpi.com/2571-550X/7/3/31;
  https://doaj.org/article/6d06f6de11d34ecbb83f266b34eaee25
- Dolukhanov, P.M. et al. Evolution
  of waterways and early human settlements in the eastern Baltic area:
  radiocarbon-based chronology. *Radiocarbon*.
  https://www.cambridge.org/core/product/50D0CE873BE05527714BCCC5D66B8A07
- Malachovskij, D. et al., 1996. Evidence from the Neva River valley,
  Russia, of the Holocene history of Lake Ladoga. *Fennia*.
  https://fennia.journal.fi/article/view/8912
- To the history of the Baltic–Ladoga connection (bifurcation into the
  pre-Neva and the Heinjoki Strait). *Limnology and Freshwater Biology*.
  https://limnolfwbiol.com/index.php/LFWB/article/view/481
- Saarnisto, M., 1970. The Late Weichselian and Flandrian history of the
  Saimaa lake complex. *Commentationes Physico-Mathematicae* 37 (Societas
  Scientiarum Fennica).
