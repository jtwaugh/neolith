# Sources for `data/renown/`

`neolith-rs/crates/app/assets/renown.json` lists the prehistoric sites a player is most likely to look for by name, so the map names them first and at far zoom (`neolith-rs/crates/app/src/renown.rs`). It is a hand-made list, written on 2026-11-12 after the greatest-hits critic's review (`build/critic/20261112-2227-hits/report.md`) found that famous sites were labelled after catalogue entries.

## How it's made

- **renown** is an editorial judgement of how well known a site is to a general reader, not an archaeological measure: 3 for the sites in every popular account of the period, 2 for sites well known to anyone who reads about it, 1 for sites a specialist would look for. It never changes a piece's size or a recorded value; it only orders and shows labels.
- **lon / lat** are the site coordinates given by the Wikipedia article below (rounded). An entry is matched to every settlement record whose name contains the entry's name or an alias as whole words (ignoring accents and case) within `radius_km` (default 15 km). The radius is wider where the records sit off the article's point (Franchthi, Jarmo, Fayum, Ali Kosh).
- All the records an entry matches are labelled with the entry's name, once, so duplicate records of one site (Çatalhöyük ×4, Aswad / Tell Aswad, Varna / Varna Cemetery …) show one name.
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
| Newgrange | 3 | https://en.wikipedia.org/wiki/Newgrange | no |
| Carnac | 3 | https://en.wikipedia.org/wiki/Carnac_stones | yes |
| Knossos | 3 | https://en.wikipedia.org/wiki/Knossos | yes |
| Mehrgarh | 3 | https://en.wikipedia.org/wiki/Mehrgarh | no |
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
| Eridu | 2 | https://en.wikipedia.org/wiki/Eridu | no |
| Ur | 2 | https://en.wikipedia.org/wiki/Ur | no |
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
| Dimini | 1 | https://en.wikipedia.org/wiki/Dimini | no |
| Lepenski Vir | 2 | https://en.wikipedia.org/wiki/Lepenski_Vir | yes |
| Vinča | 2 | https://en.wikipedia.org/wiki/Vin%C4%8Da-Belo_Brdo | yes |
| Starčevo | 1 | https://en.wikipedia.org/wiki/Star%C4%8Devo_culture | yes |
| Karanovo | 1 | https://en.wikipedia.org/wiki/Karanovo_culture | yes |
| Varna | 2 | https://en.wikipedia.org/wiki/Varna_Necropolis | yes |
| Talianki | 2 | https://en.wikipedia.org/wiki/Talianki | yes |
| Maidanetske | 1 | https://en.wikipedia.org/wiki/Maidanetske | yes |
| Ġgantija | 2 | https://en.wikipedia.org/wiki/%C4%A0gantija | no |
| Ötzi | 2 | https://en.wikipedia.org/wiki/%C3%96tzi | yes |
| Los Millares | 1 | https://en.wikipedia.org/wiki/Los_Millares | no |
| Avebury | 2 | https://en.wikipedia.org/wiki/Avebury | yes |
| Durrington Walls | 1 | https://en.wikipedia.org/wiki/Durrington_Walls | no |
| Ness of Brodgar | 2 | https://en.wikipedia.org/wiki/Ness_of_Brodgar | no |

Sites marked "no" are not in the settlement records yet (Mehrgarh lies east of the board), so the list names them but the map cannot show them until they are added.

## References

- Wikipedia, the articles linked in the table above (retrieved 2026-11-12), for each site's coordinates and what it is known for.

## Licence

Wikipedia text is CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/). Only coordinates (facts) and our own one-line paraphrases are used; no article text is copied. Credited in `ATTRIBUTIONS.md` (`wikipedia`).
