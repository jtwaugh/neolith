# Sources for `data/renown/`

`neolith-rs/crates/app/assets/renown.json` lists the prehistoric sites a player is most likely to look for by name, so the map names them first and at far zoom (`neolith-rs/crates/app/src/renown.rs`). It is a hand-made list, written on 2026-11-12 after the greatest-hits critic's review (`build/critic/20261112-2227-hits/report.md`) found that famous sites were labelled after catalogue entries.

## How it's made

- **renown** is an editorial judgement of how well known a site is to a general reader, not an archaeological measure: 3 for the sites in every popular account of the period, 2 for sites well known to anyone who reads about it, 1 for sites a specialist would look for. It never changes a piece's size or a recorded value; it only orders and shows labels.
- **lon / lat** are the site coordinates given by the Wikipedia article below (rounded). An entry is matched to every settlement record whose name contains the entry's name or an alias as whole words (ignoring accents and case) within `radius_km` (default 15 km). The radius is wider where the entry is a district or its records sit off the article's point (Fayum, Tell Aswad, Nevalı Çori, Nabta Playa). Jarmo, Franchthi, Ali Kosh and Tell Ramad had wide radii to catch a second, misplaced record of the site; those records are now joined to the site (`data/settlements/records.toml`, `[[same]]`), so the radii are back to the default.
- All the records an entry matches are labelled with the entry's name, once, so duplicate records of one site (Çatalhöyük ×4, Aswad / Tell Aswad, Varna / Varna Cemetery …) show one name.
- **parts** (optional) names records that are separate parts of one site and are meant to stay separate: `Çatalhöyük West` (the Chalcolithic mound, 300 m from the East mound) and `Çatalhöyük Environmental` (off-mound samples the compilations file on their own, 2.5 km away); `Fayum A80` (the Fayum entry is a district, and its records are localities up to 19 km apart). They are matched like aliases. The state check (`pipeline/state.py`, `famous_sites`) does not count a part as a stray duplicate, and takes it as the site's main record only when nothing else matches. The app ignores the field.
- **known_for** is a one-line summary of the article.
- **piece** (optional) picks the game piece from what the article describes: `town` for a settlement of houses (Jericho, Çatalhöyük, Skara Brae), `monument` for a ring of stones or pillars (Göbekli Tepe, Stonehenge), `cave` for a cave site (Franchthi). It is a drawing choice only; without it the piece follows the record's kind and population.

## Sites

| Site | Renown | Reference | In the settlement data |
|---|---|---|---|
| Jericho | 3 | https://en.wikipedia.org/wiki/Jericho | yes |
| Çatalhöyük | 3 | https://en.wikipedia.org/wiki/%C3%87atalh%C3%B6y%C3%BCk | yes |
| Göbekli Tepe | 3 | https://en.wikipedia.org/wiki/G%C3%B6bekli_Tepe | yes |
| Stonehenge | 3 | https://en.wikipedia.org/wiki/Stonehenge | yes |
| Skara Brae | 3 | https://en.wikipedia.org/wiki/Skara_Brae | yes |
| Newgrange | 3 | https://en.wikipedia.org/wiki/Newgrange | yes (its own XRONOS dates and two literature dates) |
| Carnac | 3 | https://en.wikipedia.org/wiki/Carnac_stones | yes |
| Knossos | 3 | https://en.wikipedia.org/wiki/Knossos | yes |
| Tell Aswad | 2 | https://en.wikipedia.org/wiki/Tell_Aswad | yes |
| Tell Ramad | 1 | https://en.wikipedia.org/wiki/Tell_Ramad | yes |
| Ain Ghazal | 2 | https://en.wikipedia.org/wiki/%27Ain_Ghazal | yes |
| Abu Hureyra | 2 | https://en.wikipedia.org/wiki/Tell_Abu_Hureyra | yes |
| Jarmo | 2 | https://en.wikipedia.org/wiki/Jarmo | yes |
| Ganj Dareh | 2 | https://en.wikipedia.org/wiki/Ganj_Dareh | yes |
| Ali Kosh | 2 | https://en.wikipedia.org/wiki/Ali_Kosh | yes |
| Nevalı Çori | 2 | https://en.wikipedia.org/wiki/Neval%C4%B1_%C3%87ori | yes |
| Çayönü | 2 | https://en.wikipedia.org/wiki/%C3%87ay%C3%B6n%C3%BC | yes |
| Aşıklı Höyük | 2 | https://en.wikipedia.org/wiki/A%C5%9F%C4%B1kl%C4%B1_H%C3%B6y%C3%BCk | yes |
| Hacılar | 1 | https://en.wikipedia.org/wiki/Hac%C4%B1lar | yes |
| Mureybet | 1 | https://en.wikipedia.org/wiki/Mureybet | yes |
| Tell Halaf | 2 | https://en.wikipedia.org/wiki/Tell_Halaf | yes |
| Tell Brak | 1 | https://en.wikipedia.org/wiki/Tell_Brak | yes |
| Uruk | 3 | https://en.wikipedia.org/wiki/Uruk | yes |
| Eridu | 2 | https://en.wikipedia.org/wiki/Eridu | yes (hand entry; no date of the occupation published) |
| Ur | 2 | https://en.wikipedia.org/wiki/Ur | yes (hand entry; no date of the Ubaid levels published) |
| Byblos | 2 | https://en.wikipedia.org/wiki/Byblos | yes |
| Ugarit | 2 | https://en.wikipedia.org/wiki/Ugarit | yes |
| Beidha | 1 | https://en.wikipedia.org/wiki/Beidha_(archaeological_site) | yes |
| Ain Mallaha | 1 | https://en.wikipedia.org/wiki/Ain_Mallaha | yes |
| Tell Sabi Abyad | 1 | https://en.wikipedia.org/wiki/Tell_Sabi_Abyad | yes |
| Khirokitia | 2 | https://en.wikipedia.org/wiki/Khirokitia | yes |
| Merimde Beni Salame | 2 | https://en.wikipedia.org/wiki/Merimde | yes |
| Fayum | 2 | https://en.wikipedia.org/wiki/Faiyum_A_culture | yes |
| Nabta Playa | 2 | https://en.wikipedia.org/wiki/Nabta_Playa | yes |
| Franchthi | 2 | https://en.wikipedia.org/wiki/Franchthi_Cave | yes |
| Sesklo | 2 | https://en.wikipedia.org/wiki/Sesklo | yes |
| Dimini | 1 | https://en.wikipedia.org/wiki/Dimini | yes (located, 2026-11-13) |
| Lepenski Vir | 2 | https://en.wikipedia.org/wiki/Lepenski_Vir | yes |
| Vinča | 2 | https://en.wikipedia.org/wiki/Vin%C4%8Da-Belo_Brdo | yes |
| Starčevo | 1 | https://en.wikipedia.org/wiki/Star%C4%8Devo_culture | yes |
| Karanovo | 1 | https://en.wikipedia.org/wiki/Karanovo_culture | yes |
| Varna | 2 | https://en.wikipedia.org/wiki/Varna_Necropolis | yes |
| Talianki | 2 | https://en.wikipedia.org/wiki/Talianki | yes |
| Maidanetske | 1 | https://en.wikipedia.org/wiki/Maidanetske | yes |
| Ġgantija | 2 | https://en.wikipedia.org/wiki/%C4%A0gantija | yes (hand entry; its two dates are after 3000 BCE) |
| Ötzi | 2 | https://en.wikipedia.org/wiki/%C3%96tzi | yes |
| Los Millares | 1 | https://en.wikipedia.org/wiki/Los_Millares | yes (its own XRONOS dates, 2026-11-13) |
| Avebury | 2 | https://en.wikipedia.org/wiki/Avebury | yes |
| Durrington Walls | 1 | https://en.wikipedia.org/wiki/Durrington_Walls | yes (as 'Woodhenge'; restored 2026-11-13) |
| Ness of Brodgar | 2 | https://en.wikipedia.org/wiki/Ness_of_Brodgar | yes (literature dates, 2026-11-13) |

Every site in the list has a record on the map (`make state`, "famous sites missing").

## Removed

- **Mehrgarh** (renown 3, https://en.wikipedia.org/wiki/Mehrgarh), removed 2026-11-13: it lies at about 67.6°E, east of the board, which ends at about 65°E, so no record of it can be shown. It is the case for widening the box: the first farmers of South Asia are the one renown-3 site the map cannot hold. Put it back if the box is widened.

## Restored

- **Durrington Walls** (renown 1, https://en.wikipedia.org/wiki/Durrington_Walls; 51.1925, -1.7875) was removed on 2026-11-13 as after the period: the henge and the settlement inside it date to about 2500 BCE, and the compilations' dates filed under Durrington Walls are 4400 ± 150 BP (NPL-191) and younger. One older date, Gro-901 (4584 ± 80 BP, charcoal), is filed under it, and the build groups it and the other 'Durrington Walls' records with the neighbouring 'Woodhenge' (the article: Woodhenge lies immediately south). Restored the same day by decision 0.3 of `docs/plans/research/2026-11-13-2026.md`, with `aliases = ["Woodhenge"]`, so that record, the one on the map at about 3310 BCE, carries the famous name. Nothing recorded was changed.

## Karahan Tepe (not added)

The greatest-hits critic named Karahan Tepe (`hits-2026-11-12-11`). It is not in the list because no radiocarbon date of the site is published, so it has no record to label: Karul 2021 (Buried Buildings at Pre-Pottery Neolithic Karahantepe, Türk Arkeoloji ve Etnografya Dergisi 82:21–31, https://dergipark.org.tr/en/download/article-file/1683122) dates its three excavated structures only as Late PPNA and Early PPNB, and Wikipedia's 9750–9400 BCE (https://en.wikipedia.org/wiki/Karahan_Tepe) rests on a news report. Add it, with a dated record, when the excavators publish dates.

## How the missing sites were added (2026-11-13)

Seven sites of the list had no record. Nothing recorded was replaced; each was added by the mechanism that fits why it was missing.

| Site | Why it was missing | What was added | Source |
|---|---|---|---|
| Dimini | XRONOS files its one date (nd-133, 5630 ± 150 BP) with no position | `[[locate]]` in `data/settlements/records.toml` | https://en.wikipedia.org/wiki/Dimini |
| Newgrange | the compilations' 126 XRONOS records are typed "Boyne Passage Grave", which the build drops with the tombs (`exclude_types`) | two direct dates on people buried in the chamber, OxA-36079 (4473 ± 29 BP) and OxA-36080 (4421 ± 30 BP), in `data/settlements/literature_dates.csv` | Cassidy et al. 2020, https://doi.org/10.1038/s41586-020-2378-6, as listed in AADR v66.p1, https://dataverse.harvard.edu/api/access/datafile/13994515 |
| Ness of Brodgar | the compilations' five dates (4320–4185 BP) calibrate after 3000 BCE | the eleven dates of 4300 BP and older from Table 1 of the excavators' dating paper, in `literature_dates.csv`; five are samples the authors treat as possibly residual (marked in the `period` column). The six Trench J dates, which the authors leave out of their model as residual, are not entered | Card et al. 2018, https://doi.org/10.1017/eaa.2016.29 (accepted manuscript, https://storre.stir.ac.uk/handle/1893/24423) |
| Eridu | not in the compilations | hand entry in `data/settlements/curated.geojson`: c. 5400–600 BCE | https://en.wikipedia.org/wiki/Eridu |
| Ur | the compilations' 15 dates are all after 3000 BCE | hand entry: c. 3800–500 BCE | https://en.wikipedia.org/wiki/Ur |
| Ġgantija | not in the compilations | hand entry: c. 3600–2500 BCE | https://en.wikipedia.org/wiki/%C4%A0gantija |
| Los Millares | the 99 XRONOS records are typed "Settlement with megalithic necropolis", dropped with the tombs | hand entry: 3200–2300 BCE | https://en.wikipedia.org/wiki/Los_Millares |

The hand entries carry archaeological phase dates from the Wikipedia articles, not radiocarbon dates; each says so in its `note`. A hand entry could not be used for Newgrange or the Ness of Brodgar, because one within 5 km of a dated site (Knowth, Barnhouse) takes that site over (`merge_curated`). Los Millares and Newgrange would be better served by keeping their own recorded dates, which needs a way to exempt a site from `exclude_types`.

### Changes from the research plan (`docs/plans/research/2026-11-13-2026.md`, section 3)

- **Newgrange, Los Millares**: `[[keep_site]]` in `data/settlements/records.toml` lets their own XRONOS records (126 and 99) pass `exclude_types`. The Los Millares hand entry is removed; the two Newgrange literature dates stay and join the XRONOS records by name.
- **Eridu, Ur, Ġgantija**: searched for radiocarbon dates inside the period; none exist, so the hand entries stay and each note says so. Eridu: Hritz et al. 2012 (https://doi.org/10.2458/azu_js_rc.v54i1.12362) dated freshwater shell in Eridu's mudbrick, which the authors read as the age of the lake muds the bricks were made from, not of the settlement. Ur: the same compilation lists only a Royal Cemetery date for Ur. Ġgantija: the FRAGSUS excavations got two dates, both from the megalithic ramp and after 3000 BCE (UBA-35589, UBA-33707; Brogan et al. 2020, https://doi.org/10.17863/CAM.62652, Table 5.1), and no Ġgantija-phase material on the site could be dated (McLaughlin et al. 2020, https://doi.org/10.17863/CAM.62649). The hand entries' spans were not cut: with no dates entered there is nothing to cut them to, and the part after 3000 BCE is off the map.
- **Tell Ramad**: the position is now taken from van Zeist & Bakker-Heeres 1982 ('about 3 km SE of Qatana', after the excavators), https://ugp.rug.nl/Palaeohistoria/article/download/24836/22284/28973; see `data/settlements/CORRECTIONS.md`.
- **Cassidy et al. 2020**: title, volume and pages checked against Crossref (https://api.crossref.org/works/10.1038/s41586-020-2378-6): 'A dynastic elite in monumental Neolithic society', Nature 582(7812):384–388. The entry was right.

The entries' coordinates for Eridu, Ali Kosh, Jarmo and Los Millares were corrected to the articles' (they were 7–10 km off).

## References

- Wikipedia, the articles linked in the tables above (retrieved 2026-11-12 and 2026-11-13), for each site's coordinates, what it is known for and, for the hand entries, its dates.
- Cassidy, L.M. et al. 2020. A dynastic elite in monumental Neolithic society. Nature 582(7812):384–388 (checked against Crossref, 2026-11-13). https://doi.org/10.1038/s41586-020-2378-6. The two Newgrange dates, read from the Allen Ancient DNA Resource v66.p1 annotation file (Mallick et al. 2024, https://dataverse.harvard.edu/api/access/datafile/13994515; CC0).
- Card, N., Mainland, I., Timpany, S., Towers, R., Batt, C., Bronk Ramsey, C., Dunbar, E., Reimer, P., Bayliss, A., Marshall, P. & Whittle, A. 2018. To cut a long story short: formal chronological modelling for the Late Neolithic site of Ness of Brodgar, Orkney. European Journal of Archaeology 21(2):217–263. https://doi.org/10.1017/eaa.2016.29. Read as the accepted manuscript, https://storre.stir.ac.uk/handle/1893/24423. Individual dates (facts) transcribed; no text or table copied.

- Hritz, C., Pournelle, J., Smith, J., Albadran, B., Issa, B.M. & Al-Handal, A. 2012. Mid-Holocene dates for organic-rich sediment, palustrine shell, and charcoal from southern Iraq. Radiocarbon 54(1):65–79. https://doi.org/10.2458/azu_js_rc.v54i1.12362. Read for Eridu and Ur (Table 1).
- Brogan, C., French, C., Taylor, S., Bennett, J., Parkinson, E.W., McLaughlin, R., Stoddart, S. & Malone, C. 2020. Ġgantija. In Malone, C. et al. (eds), Temple Places: Excavating cultural sustainability in prehistoric Malta, ch. 5. McDonald Institute. https://doi.org/10.17863/CAM.62652. And McLaughlin, R., Parkinson, E.W., Reimer, P.J. & Malone, C. 2020. Dating Maltese prehistory, ch. 2 of the same, https://doi.org/10.17863/CAM.62649. The volume is CC BY-NC-ND; only facts (dates, lab numbers) are used.
- Karul, N. 2021. Buried Buildings at Pre-Pottery Neolithic Karahantepe. Türk Arkeoloji ve Etnografya Dergisi 82:21–31. https://dergipark.org.tr/en/download/article-file/1683122.
- van Zeist, W. & Bakker-Heeres, J.A.H. 1982. Archaeobotanical studies in the Levant 1. Neolithic sites in the Damascus basin: Aswad, Ghoraifé, Ramad. Palaeohistoria 24. https://ugp.rug.nl/Palaeohistoria/article/download/24836/22284/28973. Tell Ramad's position (p. 173).

## Licence

Wikipedia text is CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/). Only coordinates (facts) and our own one-line paraphrases are used; no article text is copied. Credited in `ATTRIBUTIONS.md` (`wikipedia`).
