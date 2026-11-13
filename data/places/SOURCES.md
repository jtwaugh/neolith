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
| River mouths | Don mouth, Dnieper mouth, Kura mouth, Senegal mouth |
| Confluences | Khartoum confluence |
| Islands | Cyprus, Crete, Cyclades, Malta, Sardinia, Balearic Islands, Canary Islands, Socotra, Dahlak archipelago, Farasan Islands, Bahrain, Orkney, Gotland |
| Oases and inland deltas | Fayum, Siwa, Kharga and Dakhla, Fezzan, Azraq, Palmyra and El Kowm, Tayma, Al-Hasa, Merv oasis, Sistan |
| Lake shores | Lake Abbe, Lake Tana, Lake Van |
| Passes and gates | Darial Gorge, Derbent pass, Cilician Gates, Zagros Gates, Iron Gates, Brenner Pass |
| Isthmuses and land bridges | Isthmus of Suez, North Sinai coast, Isthmus of Corinth, Isthmus of Perekop |
| Drowned plains | Persian Gulf floor, Doggerland, Northern Adriatic plain, North-west Black Sea shelf |
| Headlands | Ras al-Hadd, Cape Guardafui |

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
