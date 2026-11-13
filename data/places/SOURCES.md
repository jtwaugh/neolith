# Exotic places: sources and reasoning

`places.toml` lists places where someone looking at the map expects something
to be going on: straits, river mouths, islands, oases, passes, drowned plains.
`python -m pipeline places` measures how empty each is in our data
(`build/critic/places/`). The exotic critic (`.claude/agents/exotic-critic.md`)
then asks why, and writes a plan per place in `plans/<key>.toml`: research to do,
or speculation to add beside the recorded data, or a reason to leave it alone.
`python -m pipeline places-check` validates the plans.

## How the catalogue was made

- The list was chosen by hand. It is a list of places to look at, not a finding,
  and it is not complete: the critic may nominate more.
- Each `box` was set by eye and checked against the built map's coastline on the
  place's `sheet.png`. A box is a frame for counting hexes and sites. It is
  generous (a hex is about 0.58° by 0.5°) and is not a measurement of the place.
- Each `why` is plain present-day geography. Where it mentions a different
  shoreline, that comes from the board itself: the pipeline's sea-level curve
  (after Lambeck et al. 2014) applied to ETOPO1, as written up in
  `pipeline/README.md` and `data/coasts/SOURCES.md`. No `why` claims anything
  about what has been found at a place.
- Nothing in the build reads the catalogue, the dossiers or the plans. The
  emptiness ranking counts known sites, so it must never feed the expected
  population density.

## Places

| Kind | Places |
|---|---|
| Straits | Bab-el-Mandeb, Strait of Hormuz, Bosphorus, Dardanelles, Strait of Gibraltar, Strait of Messina, Strait of Sicily, Strait of Otranto, Kerch Strait, Danish straits, Strait of Dover |
| Deltas | Nile delta, Shatt al-Arab, Danube delta, Volga delta, Amu Darya delta, Rhône delta, Ebro delta, Po delta, Rhine mouth |
| River mouths | Don mouth, Dnieper mouth, Kura mouth, Senegal mouth, White Sea Karelia (Vyg mouth and Onega Bay) |
| Confluences | Khartoum confluence, Samara Bend and Middle Volga steppe |
| Islands | Cyprus, Crete, Cyclades, Malta, Sardinia, Balearic Islands, Canary Islands, Socotra, Dahlak archipelago, Farasan Islands, Bahrain, Orkney, Gotland |
| Oases and inland deltas | Fayum, Siwa, Kharga and Dakhla, Fezzan, Azraq, Palmyra and El Kowm, Tayma, Al-Hasa, Merv oasis, Sistan |
| Lake shores | Lake Abbe, Lake Tana, Lake Van, Lake Onega, Upper Volga - Oka interfluve lakes and bogs, Kama basin and Middle Urals peat bogs, Kargopol lakes (Lacha and Kubenskoye), Lake Megachad |
| Passes and gates | Darial Gorge, Derbent pass, Cilician Gates, Zagros Gates, Iron Gates, Brenner Pass |
| Isthmuses and land bridges | Isthmus of Suez, North Sinai coast, Isthmus of Corinth, Isthmus of Perekop, Lake Ladoga and the Karelian Isthmus, Kuma-Manych depression |
| Drowned plains | Persian Gulf floor, Doggerland, Northern Adriatic plain, North-west Black Sea shelf, North Caspian lowland |
| Headlands | Ras al-Hadd, Cape Guardafui |
| Horn of Africa (added 2026-11-13 from the Horn plans) | Gulf of Zula, Danakil coast and Nabro, Middle Awash, Main Ethiopian Rift lakes, Dire Dawa and Harar caves, Hargeisa and Laas Geel |

## Plans

A plan's claims about the past carry their own citations in the plan file
(`cite`, `url`, and `checked`: whether the critic opened the source and it says
what the plan claims). Every link in a plan is also listed below, under the
place's name, so the reading list survives outside the conversation that
produced it. `pipeline/tests/test_sources.py` enforces this.

## References

- Lambeck, K., Rouby, H., Purcell, A., Sun, Y. & Sambridge, M. 2014. Sea level
  and global ice volumes from the Last Glacial Maximum to the Holocene. *PNAS*
  111:15296–15303. https://doi.org/10.1073/pnas.1411762111

**Gibraltar, Dardanelles and Bosporus** (`[[sea.channel]]` in
pipeline/config.toml). All three are narrower than a hex, so the hex medians
closed them: the hex over the Gibraltar narrows has a median of +4 m and the
Atlantic and Mediterranean never met on the board; the Dardanelles and
Marmara were cut off, so the Marmara basin (to −340 m) was drawn as land in
some key frames. Gibraltar (14 km, Camarinal sill about −280 m) and the
Dardanelles (Marmara marine from 12.55 ± 0.35 cal ka, before the board
starts) are open in every year; the Bosporus from −7050, when the Black Sea
lake ends (data/lakes/SOURCES.md).

- Camarinal Sill (sill about 280 m deep; narrows about 14 km).
  https://en.wikipedia.org/wiki/Camarinal_Sill
- Çağatay, M.N. et al. The tephra record from the Sea of Marmara for the
  last ca. 70 ka (marine transgression of the Marmara 12.55 ± 0.35 cal ka;
  Dardanelles sill about −65 m today).
  https://research.itu.edu.tr/tr/publications/the-tephra-record-from-the-sea-of-marmara-for-the-last-ca-70-ka-a/
- The Sea of Marmara during marine isotope stages 5 and 6 (Termination I
  reconnection sill about −84 m). https://research.itu.edu.tr/en/publications/the-sea-of-marmara-during-marine-isotope-stages-5-and-6/

**Bab-el-Mandeb**

- Lambeck, K., Purcell, A., Flemming, N.C., Vita-Finzi, C., Alsharekh, A.M. &
  Bailey, G.N. 2011. Sea level and shoreline reconstructions for the Red Sea:
  isostatic and tectonic considerations and implications for hominin migration
  out of Africa. *Quaternary Science Reviews* 30:3542–3574 (read in full; the
  strait never closed, channels under 4 km wide at lowstand).
  https://disperse-project.org/sites/disperse-project.org/files/uploads/2011_Lambeck_etal._QSR_RedSea.pdf
- Meredith-Williams, M.G., Hausmann, N., Bailey, G.N., King, G.C.P., Alsharekh,
  A., Al Ghamdi, S. & Inglis, R.H. 2014. 4200 new shell mound sites in the
  southern Red Sea. *Internet Archaeology* 37, section 2 (read; seven Tihama
  midden sites of 8–5 ka cal BP after Tosi 1986; author list from memory).
  https://intarch.ac.uk/journal/issue37/2/2.html
- Hausmann, N., Kokkinaki, O. & Leng, M.J. 2019. Red Sea palaeoclimate: stable
  isotope and element-ratio analysis of marine mollusc shells. In *Geological
  Setting, Palaeoenvironment and Archaeology of the Red Sea*, Springer (read;
  few middens dated, mainland ones dune-covered or eroded).
  https://nora.nerc.ac.uk/id/eprint/521853/1/Hausmann%20et%20al.%202019.%20Res%20Sea%20book%20chapter.pdf
- Bailey, G.N., Meredith-Williams, M., Alsharekh, A. & Hausmann, N. 2019. The
  archaeology of Pleistocene coastal environments and human dispersals in the
  Red Sea: insights from the Farasan Islands. Same volume, chapter 26 (read).
  https://disperse-project.org/sites/disperse-project.org/files/uploads/2019_Chap26_Bailey_etal.pdf
- Lee, R. 2023. Crossing the Red Sea: a Yemen and Ethiopian interchange
  circuit. *The British Yemeni Society Journal*, 18–26 (read; Tihama obsidian
  from Nabro, al-Salif c. 5000 BC).
  https://eprints.whiterose.ac.uk/id/eprint/206498/1/Yemen_Ethiopia_Lee_.pdf
- Roselló, E., Morales, A. & Popov, S. 2005. Preliminary survey of the Late
  Stone Age faunas from Gihayu (Khor Umayra lagoon, Republic of Yemen).
  *Archaeofauna* 14:253–265 (not opened: the site blocks automated readers;
  known from a search summary).
  https://revistas.uam.es/archaeofauna/article/view/7448
- Durrani, N. 2005. *The Tihamah Coastal Plain of South-West Arabia in its
  Regional Context c. 6000 BC – AD 600*. BAR International Series 1456
  (catalogue page read, book not). https://www.barpublishing.com/?p=31436
- Khalidi, L. 2005. The prehistoric and early historic settlement patterns on
  the Tihāmah coastal plain (Yemen): preliminary findings of the Tihāmah
  Coastal Survey 2003. *Proceedings of the Seminar for Arabian Studies*
  35:115–127 (not opened: access refused).
  https://hal.archives-ouvertes.fr/halshs-00484011
- Hardt, J., Smidt, W., Pfeiffer, K., Abdoulkader, M., Ali, I.O. & Umlauf, A.
  2026. Routes of interaction in the historical Sultanate of Tadjoura
  (Djibouti): results of two geoarchaeological and ethnohistorical research
  seasons in 2023 and 2024. In *Entangled Africa*, DAI, 131–152 (read in
  full 2026-11-12, for the plan's research item: every radiocarbon age, at
  Loubatanlé, the crater and Boli, falls between 51 BCE and the present; the
  Boli tumuli are compared with 3rd-millennium BCE ones but are undated, and
  some pottery is "possibly Neolithic" and undated. Nothing to ingest for
  10,000–3,000 BCE). https://doi.org/10.34780/wwt5ah24 and
  https://publications.dainst.org/books/dai/catalog/book/2167/chapter/7964
- Wikipedia, "Asa Koma" (read; Gobaad plain, Djibouti, early 2nd millennium
  BCE). https://en.wikipedia.org/wiki/Asa_Koma

**Socotra**

- Jansen van Rensburg, J. 2018. The rock art of Dahaisi cave, Soqotra, Yemen.
  *Rock Art Research* 35(2):180–187 (read).
  https://rockartresearch.com/index.php/rock/article/download/185/180
- Naumkin, V.V. & Sedov, A.V. 1993. Monuments of Socotra. *Topoi* 3(2):569–623
  (first page only). https://doi.org/10.3406/topoi.1993.1486
- Sirak, K. et al. 2024. Medieval DNA from Soqotra points to Eurasian origins
  of an isolated population at the crossroads of Africa and Arabia. *Nature
  Ecology & Evolution* (not opened: login wall; title and authors from
  memory). https://doi.org/10.1038/s41559-024-02322-x

**Amu Darya delta**

- Brunet, F., Hudžanazarov, M. & Szymczak, K. 2013. Le site d'Ajakagytma et le
  complexe culturel de Kel'teminar au sein des processus de néolithisation en
  Asie centrale. *Cahiers d'Asie centrale* 21/22:191–205 (abstract read).
  https://journals.openedition.org/asiecentrale/1814
- Wikipedia, "Kelteminar culture" (read; 5500–3500 BCE, dwellings).
  https://en.wikipedia.org/wiki/Kelteminar_culture
- Vinogradov, A.V. 1957. K voprosu o yuzhnykh svyazyakh kel'teminarskoi
  kul'tury. *Sovetskaya etnografiya* 1957(1):25–45 (not opened; known from a
  search summary; title from memory).
  https://eo.iea.ras.ru/wp-content/uploads/1957/01/eoarchive_1957_1_025_vinogradov.pdf
- XRONOS, record RUL-241, site "Akcha" (read). https://xronos.ch/c14s/73010

**Nile delta**

- Zhao, X., Kaniewski, D., Wang, Y., Marriner, N., Salem, A. et al. 2025. On the
  long and winding road: unravelling the late emergence of Neolithic
  agriculture in the Nile Delta. *Quaternary Science Reviews* 359:109368
  (abstract read, on the ECNU repository page).
  https://doi.org/10.1016/j.quascirev.2025.109368 and
  https://pure.ecnu.edu.cn/en/publications/on-the-long-and-winding-road-unravelling-the-late-emergence-of-ne/
- Egypt Exploration Society, Delta Survey (read; 783 sites, public map);
  Spencer, J. 2024. *Archaeological Sites of the Nile Delta of Egypt: A
  Gazetteer*. EES Excavation Memoir 119. https://www.ees.ac.uk/delta-survey
- Felbinger, U., The Neolithic in the Nile Delta, TOPOI project A-2-4 (read).
  https://topoi.org/feature/the-neolithic-in-the-nile-delta/
- Heath, J. 2023. Tell el-Farkha: an exceptional predynastic site in the Nile
  Delta. *Ancient Egypt* 137 (read). https://the-past.com/?p=49261
- Wikipedia, "Tell el-Farkha" (read; coordinates and phases).
  https://en.wikipedia.org/wiki/Tell_el-Farkha
- Guyot, F. et al. 2022. Investigating the Nile Delta's first settlements:
  excavations at Tell el-Samara 2016–2019. *BIFAO* 122 (not opened: access
  refused). https://hal.archives-ouvertes.fr/hal-03812307

**North-west Russia: Lake Onega, Lake Ladoga and the Karelian Isthmus, White Sea Karelia**

- Tarasov, A., Nordqvist, K., Mökkönen, T. & Khoroshun, T. 2017. Radiocarbon
  chronology of the Neolithic–Eneolithic period in the Karelian Republic
  (Russia). *Documenta Praehistorica* 44:98–121, doi:10.4312/dp.44.7 (read;
  194 dates from 77 sites, 6th–2nd millennium cal BC; sites on a map, no
  coordinates in the tables).
  https://journals.uni-lj.si/DocumentaPraehistorica/article/view/44.7 and
  https://journals.uni-lj.si/DocumentaPraehistorica/article/download/44.7/7341
- Zaitseva, G.I., Timofeev, V.I., Zagorska, I. & Kovaliukh, N.N. 2000.
  Radiocarbon dates of the Mesolithic sites of Eastern Europe. *Radiocarbon
  and Archaeology* 1:33–52 (read; 211 dates with site coordinates to the
  minute, Karelia, Vologda, Komi, Upper Volga, Baltic states).
  https://old.archeo.ru/izdaniya-1/vagnejshije-izdanija/pdf/2000Radiocarbon.pdf
- Zaitseva, G.I., Timofeev, V.I., Dergachev, V.A. & Sementsov, A.A. 1997. Some
  aspects on the distribution of radiocarbon dates from the Mesolithic and
  Neolithic of European Russia. *Iskos* 11 (abstract page read).
  https://journal.fi/iskos/article/view/110428
- Schulting, R.J., Mannermaa, K., Tarasov, P.E. et al. 2022. Radiocarbon dating
  from Yuzhniy Oleniy Ostrov cemetery reveals complex human responses to
  socio-ecological stress during the 8.2 ka cooling event. *Nature Ecology &
  Evolution*, doi:10.1038/s41559-021-01628-4 (read: abstract and
  introduction; 177 burials, main use 8250–8000 cal BP after reservoir
  correction).
  https://baikalproject.artsrn.ualberta.ca/wp-content/uploads/2022/01/Schulting-et-al_2022_Radiocarbon-dating-from-Yuzhniy-Oleniy-Ostrov_NatEcolEvol.pdf
- Lobanova, N.V. 2019. On the chronology of rock art in Karelia (Russia).
  *Fennoscandia archaeologica* XXXVI (read; tables of the Onega and
  White Sea carving groups and of the dated sites around them, with
  elevations).
  https://journal.fi/fennoscandiaarchaeologica/article/download/126571/76389/265733
- Seitsonen, O., Nordqvist, K., Gerasimov, D. & Lisitsyn, S. 2012. "The good,
  the bad, the weird": Stone Age and Early Metal Period radiocarbon dates and
  chronology from the Karelian Isthmus, North-West Russia. *Geochronometria*
  39(2):101–121, doi:10.2478/s13386-012-0001-9 (read; all Isthmus dates,
  8600 cal BC – AD 300, 81 judged usable).
  https://geochronometria.com/-The-good-the-bad-the-weird-Stone-Age-and-Early-Metal-Period-radiocarbon-dates-and,184394,0,2.html
- Miettinen, A., Sarmaja-Korjonen, K., Sonninen, E. et al. 2008. The
  palaeoenvironment of the 'Antrea Net Find'. *Iskos* 16 (abstract page read).
  https://journal.fi/iskos/article/view/110409
- *Iskos* 16 (2008), Karelian Isthmus – Stone Age Studies in 1998–2003 (issue
  page; contents known from a search summary, not opened).
  https://journal.fi/iskos/issue/view/7830
- Dolukhanov, P.M., Shukurov, A.M., Arslanov, Kh.A. et al. 2007. Evolution of
  waterways and early human settlements in the eastern Baltic area:
  radiocarbon-based chronology. *Radiocarbon* 49(2):527–542 (read).
  https://doi.org/10.1017/S0033822200042442
- Kulkova, M., Gusentsova, T., Nesterov, E., Sorokin, P. & Sapelko, T. 2012
  (authors as given in a search summary). Chronology of Neolithic–Early Metal
  Age sites at the Okhta River mouth (Saint Petersburg, Russia).
  *Radiocarbon* (not opened: access refused).
  https://repository.arizona.edu/handle/10150/654758
- Kolka, V.V., Korsakova, O.P., Shelekhova, T.S. & Tolstobrova, A.N. 2015.
  Reconstruction of the relative level of the White Sea during the
  Lateglacial–Holocene ... in the area of the Chupa settlement (North
  Karelia). *Vestnik MGTU* 18(2):255–268 (read; in Russian).
  https://vestnik.mauniver.ru/v18_2_n61/12_kolka_255-268.pdf
- Tolstobrov, D.S., Tolstobrova, A.N., Korsakova, O.P. & Vashkov, A.A. 2024.
  New data on changes in the White Sea level on the Karelian coast in the
  Holocene. *Limnology and Freshwater Biology* 2024(4) (abstract read).
  https://limnolfwbiol.com/index.php/LFWB/article/view/1118
- Lunkka, J.P., Putkinen, N. & Miettinen, A. 2012. Shoreline displacement in
  the Belomorsk area, NW Russia during the Younger Dryas stadial. *Quaternary
  Science Reviews* 37:26–37 (not opened; citation from Kolka et al. 2015).
  https://doi.org/10.1016/j.quascirev.2012.01.023
- Rybalko, A.E., Subetto, D.A. et al. 2022. Limnogenesis of large lakes in the
  North-West of the Russian Plain. *Limnology and Freshwater Biology*
  2022(4):1559–1561 (abstract read).
  https://journals.rcsi.science/2658-3518/article/view/289231
- UNESCO World Heritage Centre, Petroglyphs of Lake Onega and the White Sea
  (1654), inscribed 2021 (not opened: access refused; component coordinates
  from a search summary).
  https://whc.unesco.org/en/list/1654
- Wikipedia, "Lake Onega" (read; area 9,891 km², surface 33 m).
  https://en.wikipedia.org/wiki/Lake_Onega
- Wikipedia, "Butovo culture" (read; c. 9600–6000 BC, Upper Volga lake
  shores). https://en.wikipedia.org/wiki/Butovo_culture

**Upper Volga - Oka interfluve lakes and bogs** (proposed place `upper_volga_lakes`)

- Zaretskaya, N.E., Zhilin, M.G., Karmanov, V.N. & Uspenskaya, O.N. 2005.
  Radiocarbon dating of wetland Meso-Neolithic archaeological sites within
  the Upper Volga and Middle Vychegda. *Geochronometria* 24:117–131 (read in
  full; site positions in the text, dates in tables 3–7).
  http://www.geochronometria.pl/pdf/geo_24/Geo24_16.pdf
- Meadows, J., Lozovski, V.M., Lozovskaya, O.V., Chirkova, S.S., Craig, O.,
  Lucquin, A. & Spataro, M. 2015. Absolute chronology of Upper Volga-type
  pottery: more evidence from Zamostje 2. *Samara Journal of Science*
  4(3):113–121 (abstract read). https://snv63.ru/2309-4370/article/view/22296
- Alexandrovskiy, A.L., Voronin, K.V., Dolgikh, A.V., Kovalukh, N.N., Skripkin,
  V.V. & Glavatskaya, E.V. 2012. Radiocarbon age for the cultural layer of the
  Neolithic–Bronze Age settlement Pesochnoe-1 (Lake Nero, Russia).
  *Radiocarbon* 54(3–4):589–597 (read).
  https://cambridge.org/core/services/aop-cambridge-core/content/view/45D33FB54F44C9A5CCADF0C85C747413/S0033822200047275a.pdf/radiocarbon_age_for_the_cultural_layer_of_the_neolithicbronze_age_settlement_pesochnoe1_lake_nero_russia.pdf
- Wikipedia, "Butovo culture" (read; Ozerki, Stanovoje-4 and Sakhtysh-14
  after Zhilin). https://en.wikipedia.org/wiki/Butovo_culture
- Zaitseva, G.I., Timofeev, V.I., Dergachev, V.A. & Sementsov, A.A. 1997. Some
  aspects on the distribution of radiocarbon dates from the Mesolithic and
  Neolithic of European Russia. *Iskos* 11 (abstract read; the IHMC
  database). https://journal.fi/iskos/article/view/110428
- Sorokin, A.N. 2018 (author and year from a search summary). The terminal
  Palaeolithic and Mesolithic of the Meshchera lowlands: the contemporary view
  (not opened: the page redirected to a 404).
  https://readera.org/finalnyj-paleolit-i-mezolit-meshherskoj-nizmennostisovremennyj-vzgljad-143164022-en
- Sadokov, D., Kostromina, N., Mazei, N., Bobrov, N. et al. 2024. Allerød
  interstadial vegetation and lacustrine palaeoenvironment of the central
  Mologa-Sheksna Lowland. EGU24-12877 (abstract read; Allerød peat at
  96.5–102.5 m, palaeolakes drained in the early Holocene).
  https://meetingorganizer.copernicus.org/EGU24/EGU24-12877.html
- Wohlfarth, B., Tarasov, P., Bennike, O., Lacourse, T., Subetto, D.,
  Torssander, P. & Romanenko, F. 2006. Late glacial and Holocene
  palaeoenvironmental changes in the Rostov-Yaroslavl' area, West Central
  Russia. *Journal of Paleolimnology* 35:543–569 (abstract read; Nero levels
  lower from c. 13,000 cal BP). https://doi.org/10.1007/s10933-005-3240-4
- Borisova, O., Konstantinov, E., Utkina, A., Baranov, D. & Panin, A. 2022. On
  the existence of a large proglacial lake in the Rostov-Kostroma lowland,
  north-central European Russia. *Journal of Quaternary Science* 37(8)
  (abstract seen through a search summary only; no MIS 2 large lake).

**Kama basin and Middle Urals peat bogs** (proposed place `kama_middle_urals`)

- Zaretskaya, N.E., Hartz, S., Terberger, T., Savchenko, S.N. & Zhilin, M.G.
  2012. Radiocarbon chronology of the Shigir and Gorbunovo archaeological bog
  sites, Middle Urals, Russia. *Radiocarbon* 54(3–4):783–794 (read in full;
  61 dates, table 1).
  https://resolve.cambridge.org/core/services/aop-cambridge-core/content/view/F3D2E5D73C3850C8E41225E739698432/S0033822200047433a.pdf/radiocarbon-chronology-of-the-shigir-and-gorbunovo-archaeological-bog-sites-middle-urals-russia.pdf
- Lychagina, E.L. & Vybornov, A.A. 2017. Chronology of Kama Neolithic culture.
  *Documenta Praehistorica* 44:152–161, https://doi.org/10.4312/dp.44.9 (read
  in full; table 1, about 50 dates, no coordinates).
  https://revije.ff.uni-lj.si/DocumentaPraehistorica/article/download/44.9/7343
- Archaeology magazine, 25 April 2018. New dates obtained for Russia's Shigir
  idol (read; c. 11,600 years, after Zhilin et al. 2018, *Antiquity*
  92(362):334–350, not opened).
  https://archaeology.org/news/2018/04/25/180425-russia-shigir-idol/
- Wikipedia, "Shigir Idol" (read; find-spot coordinates 57.3809 N, 60.1407 E).
  https://en.wikipedia.org/wiki/Shigir_Idol
- Chairkina, N., Kuzmin, Y. & Hodgins, G. 2017. Radiocarbon chronology of the
  Trans-Urals Mesolithic to Bronze Age (title paraphrased from a search
  summary). *Radiocarbon* 59(2) (not opened; 153 dates).
- Piezonka, H., Kosinskaya, L., Dubovtseva, E., Chemyakin, Y., Enshin, D. et
  al. 2020. The emergence of hunter-gatherer pottery in the Urals and West
  Siberia: new dating and stable isotope evidence. *Journal of Archaeological
  Science* 116:105100 (not opened).

**Volga delta, Don mouth, Samara Bend, Manych and North Caspian lowland**

- Allen Ancient DNA Resource v66.p1, 1240K annotation file (Mallick, S. et
  al. 2024, *Scientific Data*; CC0). Read from the copy downloaded for the
  isostyle aDNA layer: localities, coordinates and direct dates for southern
  Russia. https://dataverse.harvard.edu/api/access/datafile/13994515
- Dolbunova, E., Lucquin, A., McLaughlin, T.R. et al. 2023. The transmission
  of pottery technology among prehistoric European hunter-gatherers. *Nature
  Human Behaviour* 7:171–183. Data deposit (CC BY 4.0), SI_ORA.xlsx read for
  site coordinates. https://zenodo.org/records/6619101 ; paper (not
  reopened): https://eprints.whiterose.ac.uk/194827
- Tsybrij, A., Tsybrij, V., Dolbunova, E., Mazurkevich, A., Kulkova, M. &
  Zaitseva, G. 2017. Radiocarbon chronology of Neolithic in the Lower Don and
  North-eastern Azov Sea. *Documenta Praehistorica* 44:204–223 (read, with
  Table 1). https://journals.uni-lj.si/DocumentaPraehistorica/article/view/44.13
  https://doi.org/10.4312/dp.44.13
- Kulkova, M.A., Vybornov, A.A., Yudin, A., Doga, N. & Popov, A. 2019. New
  interdisciplinary research on Neolithic-Eneolithic sites in the Low Volga
  River region. *Documenta Praehistorica* 46:376–387 (read, with Table 1).
  https://journals.uni-lj.si/DocumentaPraehistorica/article/view/46.23
  https://doi.org/10.4312/dp.46.23
- Courel, B., Meadows, J., González Carretero, L. et al. 2021. The use of
  early pottery by hunter-gatherers of the Eastern European forest-steppe.
  *Quaternary Science Reviews* 269:107143 (read).
  https://eprints.whiterose.ac.uk/177764/
  https://doi.org/10.1016/j.quascirev.2021.107143
- Vybornov, A., Kulkova, M., Kosintsev, P. et al. 2018. Diet and chronology
  of Neolithic-Eneolithic cultures (from 6500 to 4700 cal BC) in the Lower
  Volga basin. *Radiocarbon* 60(5):1597–1610 (abstract read).
  https://doi.org/10.1017/RDC.2018.95
- Vybornov, A.A., Kulkova, M., Andreev, K. & Nesterov, E. 2017. Radiocarbon
  chronology of the Neolithic in the Povolzhye (Russian eastern Europe).
  *Documenta Praehistorica* 44:224–239 (record only; text not read).
  https://dlib.si/stream/URN:NBN:SI:DOC-OO2ZWENB/f7d624c3-476d-4e35-ad9b-6dafdad30f80/PDF
- Vybornov, A.A., Kulkova, M., Goslar, T. & Possnert, G. 2013. The problem of
  the neolithisation process chronology in Povolzhye. *Documenta
  Praehistorica* 40:13–20 (abstract read).
  https://dlib.si/stream/URN:NBN:SI:DOC-7VGJMG9T/91a7600f-9ad8-4cca-9ae0-a146c209e014/PDF
- Dolukhanov, P.M., Shukurov, A., Davison, K. et al. 2009. The spread of the
  Neolithic in the South East European Plain: radiocarbon chronology,
  subsistence, and environment. *Radiocarbon* 51(2):783–793 (abstract read).
  https://doi.org/10.1017/S0033822200056095
- Yudin, A.I. Article on the Varfolomeevskaya site (Maly Uzen, Varfolomeevskoye
  reservoir; 36 radiocarbon dates); access refused, known only from a search
  summary. https://journals.eco-vector.com/2658-4816/article/download/569138/134519
- Bezrodnykh, Y.P. & Sorokin, V.M. 2016. On the age of the Mangyshlakian
  deposits of the northern Caspian Sea. *Quaternary Research* 85(2):245–254
  (abstract read: 18 radiocarbon ages, 12–9 ka, freshwater basins likened to
  the delta's ilmeni). https://doi.org/10.1016/j.yqres.2016.01.004
  https://cambridge.org/core/journals/quaternary-research/article/on-the-age-of-the-mangyshlakian-deposits-of-the-northern-caspian-sea/B794F1CED32E1CA370E7FE01F38364CB
- Sorokin, V., Yanina, T., Bolikhovskaya, N., Berdnikova, A. & Tkach, N. 2021.
  Late Quaternary regressions in the Caspian Sea. GSA Connects 2021, paper
  17-4 (abstract read: Mangyshlak regression 11.9–10.5 ka BP).
  https://gsa.confex.com/gsa/2021AM/webprogram/Paper364725.html
- Lavrentyev, N.V. 2022. Paleohydrological events and ancient man in the
  valley of the Western Manych River (the Ponto-Caspian region, Russia).
  *Limnology and Freshwater Biology* 2022(4):1459–1461 (read: early Khvalynian
  Manych strait 17.7–14.9 ka by OSL; 'few Mesolithic sites were known').
  https://journals.rcsi.science/2658-3518/article/view/289402
  https://doi.org/10.31951/2658-3518-2022-A-4-1459

**Lake Megachad**

- Breunig, P., Neumann, K. & Van Neer, W. 1996. New research on the Holocene
  settlement and environment of the Chad Basin in Nigeria. *African
  Archaeological Review* 13:111–145 (metadata read via Crossref; text not
  opened). https://doi.org/10.1007/BF01956304
- Thiemeyer, H. 2006 (deposited). From Megachad to Microchad: environmental
  changes during the Holocene. Frankfurt SFB 268 (abstract read via CORE; PDF
  behind a bot wall). https://core.ac.uk/download/14501739.pdf
  http://publikationen.ub.uni-frankfurt.de/frontdoor/index/index/docId/1775
- MacEachern, S. 2012. The Holocene history of the southern Lake Chad Basin:
  archaeological, linguistic and genetic evidence. *African Archaeological
  Review* 29:253–271 (metadata and search summaries only).
  https://doi.org/10.1007/s10437-012-9110-3
- Sereno, P.C. et al. 2008. Lakeside cemeteries in the Sahara: 5000 years of
  Holocene population and environmental change. *PLoS ONE* 3(8):e2995
  (abstract read). https://doi.org/10.1371/journal.pone.0002995
- Armitage, S.J., Bristow, C.S. & Drake, N.A. 2015. West African monsoon
  dynamics inferred from abrupt fluctuations of Lake Mega-Chad. *PNAS*
  112:8543–8548 (abstract read). https://doi.org/10.1073/pnas.1417655112
- Bristow, C., Holmes, J., Mattey, D., Salzmann, U. & Sloane, H. 2018. A late
  Holocene palaeoenvironmental 'snapshot' of the Angamma Delta, Lake Megachad
  at the end of the African Humid Period. *Quaternary Science Reviews*
  202:182–196 (abstract read on the Northumbria portal).
  https://doi.org/10.1016/j.quascirev.2018.04.025
  https://researchportal.northumbria.ac.uk/en/publications/a-late-holocene-palaeoenvironmental-snapshot-of-the-angamma-delta/
- Gabriel, B. 1977. *Zum ökologischen Wandel im Neolithikum der östlichen
  Zentralsahara*. Berliner Geographische Abhandlungen 27 (read: Steinplätze,
  their distribution, and the bibliography citing Courtin 1966, Coppens
  1967–69, Huard & Massip 1964, Servant 1970).
  https://e-docs.geo-leo.de/server/api/core/bitstreams/eeb31ca5-7f20-42f2-9ce7-c24b6f125cc8/content
- Abanga, A. 2018. *L'Acheuléen dans la région des lacs d'Ounianga, nord du
  Tchad*. Master's thesis, Université Toulouse Jean Jaurès (read: history of
  research in northern Chad, the ArRéLaT project, the Lebeuf 1969/1981
  citation).
  https://dante.univ-tlse2.fr/files/original/3e3a16e5e04e332ebe9364b6927775a384386489.pdf
- Encyclopædia Universalis. Yves Coppens (1934–2022): du Tchad à l'Éthiopie
  (read: 1960–66 missions, "plusieurs centaines de gisements
  archéologiques"). https://www.universalis.fr/encyclopedie/yves-coppens/2-du-tchad-a-l-ethiopie/
- Quéchon, G. & Roset, J.-P. 1974. Prospection archéologique du massif de
  Termit (Niger). *Cahiers ORSTOM, sér. Sci. Hum.* 11(1):85–104 (not read: the
  IRD server was in maintenance; details from a search summary).
  https://horizon.documentation.ird.fr/exl-doc/pleins_textes/pleins_textes_5/b_fdi_12-13/14238.pdf
- Brauneck, J. 2010. Würzburger Geographische Arbeiten 103 (Zoo Baba section
  with radiocarbon dates; not read: blocked to scripts and too large to fetch).
  https://opus.bibliothek.uni-wuerzburg.de/files/23514/WGA_103.pdf
- Wikipedia. Dufuna canoe (read: discovery in 1987, 8.4 m, Khaya, between
  Potiskum and Gashua, two dates cited to Breunig et al. 1996).
  https://en.wikipedia.org/wiki/Dufuna_canoe
- XRONOS records for the Chad-basin dates the build drops or doubts: Konduga
  Kn-4300 (read), Nedeley Gif-1094 (read), Koro Toro Gif-1095 (not read),
  Mandi "44Gif" (read), Beurkia T-642 (read). https://xronos.ch/c14s/275610
  https://xronos.ch/c14s/64813 https://xronos.ch/c14s/64794
  https://xronos.ch/c14s/64809 https://xronos.ch/c14s/64718
- Seidensticker, D., Hubau, W. & Jungnickel, K. aDRAC, Archive des datations
  radiocarbone d'Afrique centrale (data read; nothing in window near the
  box). https://github.com/dirkseidensticker/aDRAC

**Lake Tana**

- Sahle, Y., Firew, G.A., Pearson, O.M., Stynder, D.D. & Beyin, A. 2024. MIS 3
  innovative behavior and highland occupation during a stable wet episode in
  the Lake Tana paleoclimate record, Ethiopia. *Scientific Reports* 14:17038
  (read, full text via Europe PMC PMC11269595: Gorgora rock shelter 1 km from
  the north shore, MSA over 42 ka cal BP, LSA and 'ceramic Neolithic' levels
  undated). https://doi.org/10.1038/s41598-024-67743-x
- Firew, G.A. 2014. *Archaeological fieldwork around Lake Tana area of
  northwest Ethiopia and the implication for an understanding of aquatic
  adaptation*. PhD thesis, University of Bergen (abstract only, read through
  the NVA search API; the PDF returned HTTP 403: Kurtiye rock shelter,
  occupation from the sixth millennium BP, fish, pottery, late domesticates).
  https://hdl.handle.net/1956/8931
- Barnett, T. 1999. *The Emergence of Food Production in Ethiopia*. BAR
  International Series (not read; cited by Sahle et al. 2024).
- Dombrowski, J. 1970. Preliminary report on excavations in Lalibela and
  Natchabiet caves, Begemeder. *Annales d'Éthiopie* 8 (not read; known from a
  search result).

**Cape Guardafui**

- Chittick, N. 1976. An archaeological reconnaissance in the Horn: the
  British-Somali expedition, 1975. *Azania* 11:117–133 (read: Damo 5 km west
  of the cape and Hafun, Graeco-Roman coastal sites; stone artefacts collected
  at localities and rock-shelters, unpublished).
  https://www.ancientportsantiques.com/wp-content/uploads/Documents/PLACES/IndOc-Gulf/Somalia-Chittick1976.pdf
- Ali, M.Y. & Ibrahim, I. 2012. Rock art in Somaliland: discovery of two new
  rock painting sites. *Adumatu* 25:7–24 (read: Laas Geel at 44°26.611'E
  9°46.881'N with a test-pit charcoal date of 4810–4760 BP after Gutherz et al.
  2010; Karin Heegan at 48°38'E 11°03'N with LSA microliths, pottery and dates
  of 1,600–2,100 BP; Dhambalin at 45°26.039'E 10°21.913'N).
  https://alsudairy.org.sa/wp-content/uploads/2024/06/Issue25-E_P007-024.pdf

**Horn of Africa without a place entry** (Main Ethiopian Rift lakes, Dire Dawa
caves, Hargeisa and Laas Geel, Lake Turkana and the Omo, Juba–Shabelle)

- Tribolo, C., Asrat, A., Bahain, J.-J. et al. 2017. Across the gap:
  geochronological and sedimentological analyses from the Late
  Pleistocene–Holocene sequence of Goda Buticha, southeastern Ethiopia. *PLoS
  ONE* 12:e0169418 (read: cave about 15 km west of Dire Dawa, Holocene layers
  IIc–IIb dated 7791 ± 126 to 4676 ± 144 cal BP, Complex I 4060 ± 90 cal BP).
  https://doi.org/10.1371/journal.pone.0169418
- Brandt, S., Hildebrand, E., Vogelsang, R., Wolfhagen, J. & Wang, H. 2017. A
  new MIS 3 radiocarbon chronology for Mochena Borago Rockshelter, SW Ethiopia.
  *Journal of Archaeological Science: Reports* 11:352–369 (read: Holocene
  deposits excavated by Gutherz 2000–2002, published in Gutherz et al. 2002).
  https://crc806db.uni-koeln.de/data/A/A1/Brandt%20et%20al.%202017.pdf
- Gutherz, X., Diaz, A., Ménard, C. et al. 2014. The Hargeisan revisited: lithic
  industries from shelter 7 of Laas Geel, Somaliland. *Quaternary
  International* 343:69–84 (record page read; full text closed).
  https://archive-ouverte.unige.ch/unige:105883
- Ministère de la Culture. Laas Geel: the African Lascaux (read: occupation in
  the 3rd millennium BCE; mission led by Gutherz 2001–2013 and Cauliez since).
  https://archeologie.culture.gouv.fr/en/laas-geel-african-lascaux
- Ménard, C., Bon, F., Dessie, A. et al. 2014. Late Stone Age variability in the
  Main Ethiopian Rift: new data from the Bulbula River, Ziway–Shala basin.
  *Quaternary International* 343:53–68 (not read: HAL refused the request;
  occupations at about 34–33 ka and 14–11 ka cal BP per a search summary).
  https://hal.archives-ouvertes.fr/hal-01964659
- Lesur, J., Hildebrand, E.A., Abawa, G. & Gutherz, X. 2014. The advent of
  herding in the Horn of Africa: new data from Ethiopia, Djibouti and
  Somaliland. *Quaternary International* 343:148–158 (not read).
  https://doi.org/10.1016/j.quaint.2013.11.024
- Mustaphi, C.J.C. & Marchant, R. 2016. A database of radiocarbon dates for
  palaeoenvironmental research in eastern Africa. *Open Quaternary* 2:2 (read:
  793 dates, 23 archaeological; covers Ethiopia and the Gulf of Aden).
  https://eprints.whiterose.ac.uk/100183/1/22_348_1_PB.pdf

**Dahlak archipelago**

- Beyin, A. & Bar-Yosef Mayer, D.E. 2018. Prehistoric settlements on the Red
  Sea coast of Eritrea: implications for assessing early human dispersals
  across the Red Sea basin. In A. Sarathi (ed.), *Early Maritime Cultures in
  East Africa and the Western Indian Ocean*, Archaeopress Access Archaeology,
  pp. 1–32 (read in the publisher's open sample: the survey, the sites and the
  Fig. 4 date table for Misse East, Gelalo NW and Asfet Unit F).
  https://www.archaeopress.com/Archaeopress/DMS/EF8E85A7FCEC4ED5B414B15060004654/9781784917128-sample.pdf
- Meredith-Williams, M.G., Hausmann, N., Inglis, R.H. & Bailey, G.N. 2014.
  4200 new shell mound sites in the southern Red Sea. *Internet Archaeology*
  37 (read: about 1,200 remote-sensed mounds on the Dahlak islands, 19
  doubtful candidates at Massawa, crossing distances, the Fig. 7 coordinate).
  https://intarch.ac.uk/journal/issue37/2/ia.37.2.pdf
  https://intarch.ac.uk/journal/issue37/2/2.html
- Zazzaro, C. 2013. *The Ancient Red Sea Port of Adulis and the Eritrean
  Coastal Region*. BAR S2569 (read: Blanc 1952 on Dahlak Kebir obsidian
  microliths and undated middens; Roubet 1970 and Trucca 1971 at Gurgussum,
  Massawa). https://unora.unior.it/bitstream/11574/50291/1/Zazzaro2013.pdf
- Beyin, A. 2011. Early to Middle Holocene human adaptations on the Buri
  Peninsula and Gulf of Zula, coastal lowlands of Eritrea. *Azania* 46:123–140
  (metadata only; not opened). https://doi.org/10.1080/0067270X.2011.580139
- Bar-Yosef Mayer, D.E. & Beyin, A. 2009. Late Stone Age shell middens on the
  Red Sea coast of Eritrea. *Journal of Island and Coastal Archaeology*
  4:108–124 (metadata only; not opened).
  https://doi.org/10.1080/15564890802662171
- Beyin, A. & Shea, J.J. 2007. Reconnaissance of prehistoric sites on the Red
  Sea coast of Eritrea, NE Africa. *Journal of Field Archaeology* 32:1–16
  (metadata only; not opened). https://doi.org/10.1179/009346907791071764
- Oppenheimer, C., Khalidi, L., Gratuze, B. et al. 2019. Risk and reward:
  explosive eruptions and obsidian lithic resource at Nabro volcano
  (Eritrea). *Quaternary Science Reviews* 226:105995 (metadata only; not
  opened). https://doi.org/10.1016/j.quascirev.2019.105995

**Lake Abbe**

- Khalidi, L., Mologni, C., Ménard, C. et al. 2020. 9000 years of human
  lakeside adaptation in the Ethiopian Afar: fisher-foragers and the first
  pastoralists in the Lake Abhe basin during the African Humid Period.
  *Quaternary Science Reviews* 243:106459 (abstract read via the Semantic
  Scholar API; the open manuscript on HAL and ScienceDirect refused automated
  access). https://doi.org/10.1016/j.quascirev.2020.106459
  https://hal.science/hal-02911601v1
- CEPAM (CNRS / Université Côte d'Azur). News item on Khalidi et al. 2020
  (read: Raso-02 at about 10,000 BP, the Gamarri and Afambo lakes, a lake area
  swing of over 5,000 km²).
  https://www.cepam.cnrs.fr/actualite/article-levolution-des-paleorivages-du-lac-abhe-en-afar-ethiopien-revele-9000-ans-de-resilience-humaine-face-aux-changements-climatiques
- Mologni, C., Bruxelles, L., Schuster, M. et al. 2021. Holocene East African
  monsoonal variations recorded in wave-dominated clastic paleo-shorelines of
  Lake Abhe, Central Afar region (Ethiopia & Djibouti). *Geomorphology*
  391:107896 (not opened; the highstand and lake-fall ages are from a search
  summary). https://doi.org/10.1016/j.geomorph.2021.107896
- Ministère de la Culture (France), Grands sites archéologiques. 'Extremely
  rare human bone remains in East Africa' (read: Hara Idé 3, phases of
  16,000–11,500 and 9500–8700 BCE).
  https://archeologie.culture.gouv.fr/en/extremely-rare-human-bone-remains-east-africa
- Ministère de la Culture (France). 'The banks of Lake Abbe: fertile ground'
  (read: over 100 sites, a lake of about 6,000 km² more than 10,000 years ago,
  Ali Dabba, Antakari 3, the mission's history).
  https://archeologie.culture.gouv.fr/en/banks-lake-abbe-fertile-ground
- Ministère de la Culture (France). 'On the banks of Lake Abbe' (read: Asa
  Koma, 2500–1800 BCE). https://archeologie.culture.gouv.fr/en/banks-lake-abbe
- Dupuy, C. 2019. Review of Gutherz, X. (dir.) 2017, *Asa Koma. Site
  néolithique dans le bassin du Gobaad (République de Djibouti)*. *Journal des
  Africanistes* 89-1:187–191 (read: setting, fauna, the six charcoal dates in
  outline, Wakrita UBA-20229, about 30 tombs from the 4th millennium BC).
  https://journals.openedition.org/africanistes/7945
  https://doi.org/10.4000/africanistes.7945
- Cauliez, J., Gutherz, X. & Pène, J.-M. 2008. Première caractérisation des
  faciès céramiques néolithiques de la région du Gobaad en République de
  Djibouti: les sites d'Hara-Idé 2 et d'Asa-Koma. *L'Anthropologie*
  112:691–715 (metadata only; not opened).
  https://doi.org/10.1016/j.anthro.2008.06.003
- Gutherz, X., Lesur, J., Cauliez, J. et al. 2015. New insights on the first
  Neolithic societies in the Horn of Africa: the site of Wakrita, Djibouti.
  *Journal of Field Archaeology* 40:55–68 (metadata only; not opened).
  https://doi.org/10.1179/0093469014Z.000000000110
- XRONOS record Gif-7404, Asa Koma, filed under Somalia at 44.69 E, 9.72 N
  (read in the raw download build/settlements/xronos_country_SO.json).
  https://xronos.ch/c14s/249361
