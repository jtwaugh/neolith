# Sources for `data/cultures/`

`cultures.toml` is written by hand. Its traits are short summaries
made for this project; each entry cites the English Wikipedia
article revision below. `make cultures-check` fetches those
revisions and lists any trait the article text does not mention;
those are marked `unverified` in `cultures.json` and listed here.

Which culture a site belongs to comes from the period labels on its
dated samples, so it is cited to the same records as the dates
(see `data/settlements/SOURCES.md`). Wikipedia text is CC BY-SA 4.0;
no text is copied into this repository.

## Inferred cultures

`culture_inferred` and `stage_inferred` are not cited: they are guesses
for dates whose own labels give no culture (stage). A date gets the
culture that at least 2 labelled sites within 50 km attest
within 250 years of it, if it has 67% of the votes, no tie,
and the date fits that culture's range. `*_inferred_support` gives, per
culture, the most sites that agreed and the nearest one's distance (km).

Holdout test (each labelled date voted on by the other sites, as if unlabelled):

| Field | Known dates | Answered | Right |
|---|---|---|---|
| culture | 10015 | 4119 (41%) | 3930 (95%) |
| stage | 23179 | 10657 (46%) | 9892 (93%) |

Rates count dates, so well-dated sites weigh most. A neighbour can be
the same place under another name; ignoring neighbours closer than
10 km lowered culture accuracy from 96% to 94% (2026-11-12 build).

| Entry | Sites | Wikipedia revision | Unverified traits |
|---|---|---|---|
| Palaeolithic (Lower and Middle) (`palaeolithic`) | 17 | [Paleolithic](https://en.wikipedia.org/w/index.php?title=Paleolithic&oldid=1384355404) (1384355404) | — |
| Upper Palaeolithic (`upper_palaeolithic`) | 132 | [Upper Paleolithic](https://en.wikipedia.org/w/index.php?title=Upper_Paleolithic&oldid=1379545961) (1379545961) | — |
| Epipalaeolithic (`epipalaeolithic`) | 299 | [Epipalaeolithic](https://en.wikipedia.org/w/index.php?title=Epipalaeolithic&oldid=1369638583) (1369638583) | — |
| Mesolithic (`mesolithic`) | 625 | [Mesolithic](https://en.wikipedia.org/w/index.php?title=Mesolithic&oldid=1374999382) (1374999382) | — |
| Aceramic Neolithic (`aceramic_neolithic`) | 94 | [Pre-Pottery Neolithic](https://en.wikipedia.org/w/index.php?title=Pre-Pottery_Neolithic&oldid=1360754480) (1360754480) | — |
| Neolithic (`neolithic`) | 2674 | [Neolithic](https://en.wikipedia.org/w/index.php?title=Neolithic&oldid=1384848321) (1384848321) | — |
| Chalcolithic (Copper Age) (`chalcolithic`) | 448 | [Chalcolithic](https://en.wikipedia.org/w/index.php?title=Chalcolithic&oldid=1384441085) (1384441085) | — |
| Bronze Age (`bronze_age`) | 357 | [Bronze Age](https://en.wikipedia.org/w/index.php?title=Bronze_Age&oldid=1384631621) (1384631621) | — |
| Iron Age (`iron_age`) | 21 | [Iron Age](https://en.wikipedia.org/w/index.php?title=Iron_Age&oldid=1384918549) (1384918549) | — |
| Kebaran (`kebaran`) | 4 | [Kebaran culture](https://en.wikipedia.org/w/index.php?title=Kebaran_culture&oldid=1360699391) (1360699391) | — |
| Natufian (`natufian`) | 10 | [Natufian culture](https://en.wikipedia.org/w/index.php?title=Natufian_culture&oldid=1380535068) (1380535068) | — |
| Pre-Pottery Neolithic A (`ppna`) | 23 | [Pre-Pottery Neolithic A](https://en.wikipedia.org/w/index.php?title=Pre-Pottery_Neolithic_A&oldid=1369643085) (1369643085) | — |
| Pre-Pottery Neolithic B (`ppnb`) | 69 | [Pre-Pottery Neolithic B](https://en.wikipedia.org/w/index.php?title=Pre-Pottery_Neolithic_B&oldid=1379583086) (1379583086) | — |
| Pre-Pottery Neolithic C (`ppnc`) | 10 | [Pre-Pottery Neolithic](https://en.wikipedia.org/w/index.php?title=Pre-Pottery_Neolithic&oldid=1360754480) (1360754480) | — |
| Yarmukian (`yarmukian`) | 4 | [Yarmukian culture](https://en.wikipedia.org/w/index.php?title=Yarmukian_culture&oldid=1365740888) (1365740888) | — |
| Hassuna (`hassuna`) | 5 | [Hassuna culture](https://en.wikipedia.org/w/index.php?title=Hassuna_culture&oldid=1372152289) (1372152289) | — |
| Samarra (`samarra`) | 1 | [Samarra culture](https://en.wikipedia.org/w/index.php?title=Samarra_culture&oldid=1382045696) (1382045696) | — |
| Halaf (`halaf`) | 12 | [Halaf culture](https://en.wikipedia.org/w/index.php?title=Halaf_culture&oldid=1382323524) (1382323524) | — |
| Ubaid (`ubaid`) | 17 | [Ubaid period](https://en.wikipedia.org/w/index.php?title=Ubaid_period&oldid=1383053503) (1383053503) | — |
| Uruk (`uruk`) | 10 | [Uruk period](https://en.wikipedia.org/w/index.php?title=Uruk_period&oldid=1384906777) (1384906777) | — |
| Ghassulian (`ghassulian`) | 1 | [Ghassulian](https://en.wikipedia.org/w/index.php?title=Ghassulian&oldid=1382058699) (1382058699) | — |
| Shulaveri–Shomu (`shulaveri_shomu`) | 5 | [Shulaveri–Shomu culture](https://en.wikipedia.org/w/index.php?title=Shulaveri%E2%80%93Shomu_culture&oldid=1360735933) (1360735933) | — |
| Qarunian (`qarunian`) | 5 | [Prehistoric Egypt](https://en.wikipedia.org/w/index.php?title=Prehistoric_Egypt&oldid=1384518337) (1384518337) | — |
| Faiyum A (`faiyum_a`) | 9 | [Prehistoric Egypt](https://en.wikipedia.org/w/index.php?title=Prehistoric_Egypt&oldid=1384518337) (1384518337) | — |
| Merimde (`merimde`) | 1 | [Merimde culture](https://en.wikipedia.org/w/index.php?title=Merimde_culture&oldid=1343931071) (1343931071) | — |
| El Omari (`el_omari`) | 1 | [Prehistoric Egypt](https://en.wikipedia.org/w/index.php?title=Prehistoric_Egypt&oldid=1384518337) (1384518337) | — |
| Badarian (`badarian`) | 3 | [Badarian culture](https://en.wikipedia.org/w/index.php?title=Badarian_culture&oldid=1382464528) (1382464528) | — |
| Naqada (`naqada`) | 25 | [Naqada culture](https://en.wikipedia.org/w/index.php?title=Naqada_culture&oldid=1375256530) (1375256530) | — |
| Maadi–Buto (`maadi_buto`) | 3 | [Maadi-Buto culture](https://en.wikipedia.org/w/index.php?title=Maadi-Buto_culture&oldid=1381077639) (1381077639) | — |
| Dynastic Egypt (`dynastic_egypt`) | 7 | [Early Dynastic Period of Egypt](https://en.wikipedia.org/w/index.php?title=Early_Dynastic_Period_of_Egypt&oldid=1384914774) (1384914774) | — |
| Iberomaurusian (`iberomaurusian`) | 15 | [Iberomaurusian](https://en.wikipedia.org/w/index.php?title=Iberomaurusian&oldid=1374169940) (1374169940) | — |
| Capsian (`capsian`) | 30 | [Capsian](https://en.wikipedia.org/w/index.php?title=Capsian&oldid=1384679790) (1384679790) | — |
| Neolithic of Capsian Tradition (`capsian_neolithic`) | 14 | [Capsian](https://en.wikipedia.org/w/index.php?title=Capsian&oldid=1384679790) (1384679790) | — |
| Kiffian (`kiffian`) | 3 | [Kiffian culture](https://en.wikipedia.org/w/index.php?title=Kiffian_culture&oldid=1367045255) (1367045255) | — |
| Tenerian (`tenerian`) | 5 | [Tenerian culture](https://en.wikipedia.org/w/index.php?title=Tenerian_culture&oldid=1369338834) (1369338834) | — |
| Magdalenian (`magdalenian`) | 88 | [Magdalenian](https://en.wikipedia.org/w/index.php?title=Magdalenian&oldid=1384617270) (1384617270) | — |
| Epigravettian (`epigravettian`) | 24 | [Epigravettian](https://en.wikipedia.org/w/index.php?title=Epigravettian&oldid=1376524877) (1376524877) | — |
| Hamburgian (`hamburgian`) | 4 | [Hamburg culture](https://en.wikipedia.org/w/index.php?title=Hamburg_culture&oldid=1383319216) (1383319216) | — |
| Creswellian (`creswellian`) | 3 | [Creswellian culture](https://en.wikipedia.org/w/index.php?title=Creswellian_culture&oldid=1349026187) (1349026187) | — |
| Federmesser (`federmesser`) | 5 | [Federmesser culture](https://en.wikipedia.org/w/index.php?title=Federmesser_culture&oldid=1360125186) (1360125186) | — |
| Azilian (`azilian`) | 14 | [Azilian](https://en.wikipedia.org/w/index.php?title=Azilian&oldid=1373678621) (1373678621) | — |
| Ahrensburgian (`ahrensburgian`) | 6 | [Ahrensburg culture](https://en.wikipedia.org/w/index.php?title=Ahrensburg_culture&oldid=1382895470) (1382895470) | — |
| Maglemosian (`maglemosian`) | 18 | [Maglemosian culture](https://en.wikipedia.org/w/index.php?title=Maglemosian_culture&oldid=1384843337) (1384843337) | — |
| Kongemose (`kongemose`) | 11 | [Kongemose culture](https://en.wikipedia.org/w/index.php?title=Kongemose_culture&oldid=1349026664) (1349026664) | — |
| Ertebølle (`ertebolle`) | 83 | [Ertebølle culture](https://en.wikipedia.org/w/index.php?title=Erteb%C3%B8lle_culture&oldid=1353280461) (1353280461) | — |
| Sauveterrian (`sauveterrian`) | 40 | [Sauveterrian](https://en.wikipedia.org/w/index.php?title=Sauveterrian&oldid=1372959614) (1372959614) | — |
| Tardenoisian (`tardenoisian`) | 10 | [Tardenoisian](https://en.wikipedia.org/w/index.php?title=Tardenoisian&oldid=1375019025) (1375019025) | — |
| Asturian (`asturian`) | 0 | [Asturian culture](https://en.wikipedia.org/w/index.php?title=Asturian_culture&oldid=1329932108) (1329932108) | — |
| Starčevo–Körös–Criș (`starcevo_koros_cris`) | 61 | [Starčevo–Körös–Criș culture](https://en.wikipedia.org/w/index.php?title=Star%C4%8Devo%E2%80%93K%C3%B6r%C3%B6s%E2%80%93Cri%C8%99_culture&oldid=1382898294) (1382898294) | — |
| Karanovo (`karanovo`) | 6 | [Karanovo culture](https://en.wikipedia.org/w/index.php?title=Karanovo_culture&oldid=1357599658) (1357599658) | — |
| Vinča (`vinca`) | 11 | [Vinča culture](https://en.wikipedia.org/w/index.php?title=Vin%C4%8Da_culture&oldid=1379346763) (1379346763) | — |
| Sopot (`sopot`) | 9 | [Sopot culture](https://en.wikipedia.org/w/index.php?title=Sopot_culture&oldid=1330760650) (1330760650) | — |
| Alföld Linear Pottery (`alfold_linear_pottery`) | 8 | [Alföld culture](https://en.wikipedia.org/w/index.php?title=Alf%C3%B6ld_culture&oldid=1280939237) (1280939237) | — |
| Tisza (`tisza`) | 9 | [Tisza culture](https://en.wikipedia.org/w/index.php?title=Tisza_culture&oldid=1334768932) (1334768932) | — |
| Tiszapolgár (`tiszapolgar`) | 7 | [Tiszapolgár culture](https://en.wikipedia.org/w/index.php?title=Tiszapolg%C3%A1r_culture&oldid=1368853665) (1368853665) | — |
| Kodjadermen–Gumelnița–Karanovo VI (`gumelnita`) | 13 | [Gumelnița–Kodžadermen-Karanovo VI complex](https://en.wikipedia.org/w/index.php?title=Gumelni%C8%9Ba%E2%80%93Kod%C5%BEadermen-Karanovo_VI_complex&oldid=1360731703) (1360731703) | — |
| Cucuteni–Trypillia (`cucuteni_trypillia`) | 46 | [Cucuteni–Trypillia culture](https://en.wikipedia.org/w/index.php?title=Cucuteni%E2%80%93Trypillia_culture&oldid=1380722213) (1380722213) | — |
| Baden (`baden`) | 39 | [Baden culture](https://en.wikipedia.org/w/index.php?title=Baden_culture&oldid=1377271760) (1377271760) | — |
| Bug–Dniester (`bug_dniester`) | 5 | [Bug–Dniester culture](https://en.wikipedia.org/w/index.php?title=Bug%E2%80%93Dniester_culture&oldid=1383604126) (1383604126) | — |
| Yamnaya (`yamnaya`) | 16 | [Yamnaya culture](https://en.wikipedia.org/w/index.php?title=Yamnaya_culture&oldid=1384637244) (1384637244) | — |
| Linear Pottery (LBK) (`lbk`) | 163 | [Linear Pottery culture](https://en.wikipedia.org/w/index.php?title=Linear_Pottery_culture&oldid=1383367696) (1383367696) | — |
| Stroke-ornamented Ware (SBK) (`stroke_ornamented`) | 10 | [Stroke-ornamented ware culture](https://en.wikipedia.org/w/index.php?title=Stroke-ornamented_ware_culture&oldid=1383728815) (1383728815) | — |
| Großgartach (`grossgartach`) | 6 | [Grossgartach culture](https://en.wikipedia.org/w/index.php?title=Grossgartach_culture&oldid=1344276271) (1344276271) | — |
| Rössen (`rossen`) | 20 | [Rössen culture](https://en.wikipedia.org/w/index.php?title=R%C3%B6ssen_culture&oldid=1325126170) (1325126170) | — |
| Lengyel (`lengyel`) | 62 | [Lengyel culture](https://en.wikipedia.org/w/index.php?title=Lengyel_culture&oldid=1383351602) (1383351602) | — |
| Michelsberg (`michelsberg`) | 54 | [Michelsberg culture](https://en.wikipedia.org/w/index.php?title=Michelsberg_culture&oldid=1375608220) (1375608220) | — |
| Funnel Beaker (TRB) (`funnelbeaker`) | 225 | [Funnelbeaker culture](https://en.wikipedia.org/w/index.php?title=Funnelbeaker_culture&oldid=1373647642) (1373647642) | — |
| Globular Amphora (`globular_amphora`) | 12 | [Globular Amphora culture](https://en.wikipedia.org/w/index.php?title=Globular_Amphora_culture&oldid=1377032753) (1377032753) | — |
| Corded Ware (`corded_ware`) | 16 | [Corded Ware culture](https://en.wikipedia.org/w/index.php?title=Corded_Ware_culture&oldid=1381228762) (1381228762) | — |
| Bell Beaker (`bell_beaker`) | 50 | [Bell Beaker culture](https://en.wikipedia.org/w/index.php?title=Bell_Beaker_culture&oldid=1381906404) (1381906404) | — |
| Swifterbant (`swifterbant`) | 28 | [Swifterbant culture](https://en.wikipedia.org/w/index.php?title=Swifterbant_culture&oldid=1382135390) (1382135390) | — |
| Vlaardingen (`vlaardingen`) | 7 | [Vlaardingen culture](https://en.wikipedia.org/w/index.php?title=Vlaardingen_culture&oldid=1382136212) (1382136212) | — |
| Pitted Ware (`pitted_ware`) | 46 | [Pitted Ware culture](https://en.wikipedia.org/w/index.php?title=Pitted_Ware_culture&oldid=1368849338) (1368849338) | — |
| Wartberg (`wartberg`) | 4 | [Wartberg culture](https://en.wikipedia.org/w/index.php?title=Wartberg_culture&oldid=1361175720) (1361175720) | — |
| Egolzwil (`egolzwil`) | 1 | [Wauwilermoos pile dwelling settlement (Egolzwil 3)](https://en.wikipedia.org/w/index.php?title=Wauwilermoos_pile_dwelling_settlement_%28Egolzwil_3%29&oldid=1324391627) (1324391627) | — |
| Cortaillod (`cortaillod`) | 22 | [Cortaillod culture](https://en.wikipedia.org/w/index.php?title=Cortaillod_culture&oldid=1381902264) (1381902264) | — |
| Pfyn (`pfyn`) | 22 | [Pfyn culture](https://en.wikipedia.org/w/index.php?title=Pfyn_culture&oldid=1354705802) (1354705802) | — |
| Horgen (`horgen`) | 21 | [Horgen culture](https://en.wikipedia.org/w/index.php?title=Horgen_culture&oldid=1353167688) (1353167688) | — |
| Altheim (`altheim`) | 2 | [Altheim culture](https://en.wikipedia.org/w/index.php?title=Altheim_culture&oldid=1349897756) (1349897756) | — |
| Mondsee (`mondsee`) | 7 | [Mondsee group](https://en.wikipedia.org/w/index.php?title=Mondsee_group&oldid=1355329586) (1355329586) | — |
| Cerny (`cerny`) | 10 | [Cerny culture](https://en.wikipedia.org/w/index.php?title=Cerny_culture&oldid=1344502342) (1344502342) | — |
| Villeneuve-Saint-Germain / Blicquy (`villeneuve_saint_germain`) | 7 | [Villeneuve-Saint-Germain](https://en.wikipedia.org/w/index.php?title=Villeneuve-Saint-Germain&oldid=1381816527) (1381816527) | — |
| Chasséen (`chasseen`) | 92 | [Chasséen culture](https://en.wikipedia.org/w/index.php?title=Chass%C3%A9en_culture&oldid=1357473489) (1357473489) | — |
| Seine-Oise-Marne (`seine_oise_marne`) | 5 | [Seine–Oise–Marne culture](https://en.wikipedia.org/w/index.php?title=Seine%E2%80%93Oise%E2%80%93Marne_culture&oldid=1350573375) (1350573375) | — |
| Artenac (`artenac`) | 3 | [Artenacian culture](https://en.wikipedia.org/w/index.php?title=Artenacian_culture&oldid=1381229245) (1381229245) | — |
| Véraza (`veraza`) | 12 | [Véraza culture](https://en.wikipedia.org/w/index.php?title=V%C3%A9raza_culture&oldid=1323829885) (1323829885) | — |
| Montbolo (`montbolo`) | 10 | [Montbolo culture](https://en.wikipedia.org/w/index.php?title=Montbolo_culture&oldid=1370887730) (1370887730) | — |
| Impressed Ware (`impressed_ware`) | 56 | [Cardium pottery](https://en.wikipedia.org/w/index.php?title=Cardium_pottery&oldid=1376493748) (1376493748) | — |
| Cardial (`cardial`) | 116 | [Cardium pottery](https://en.wikipedia.org/w/index.php?title=Cardium_pottery&oldid=1376493748) (1376493748) | — |
| Stentinello (`stentinello`) | 5 | [Stentinello culture](https://en.wikipedia.org/w/index.php?title=Stentinello_culture&oldid=1373253743) (1373253743) | — |
| Square-mouthed Pottery (VBQ) (`square_mouthed_pottery`) | 9 | [Square-mouthed vases culture](https://en.wikipedia.org/w/index.php?title=Square-mouthed_vases_culture&oldid=1332368707) (1332368707) | — |
| Ozieri (`ozieri`) | 2 | [Ozieri culture](https://en.wikipedia.org/w/index.php?title=Ozieri_culture&oldid=1358759482) (1358759482) | — |
| Early Neolithic of Britain and Ireland (`british_early_neolithic`) | 11 | [Neolithic British Isles](https://en.wikipedia.org/w/index.php?title=Neolithic_British_Isles&oldid=1367503164) (1367503164) | — |
