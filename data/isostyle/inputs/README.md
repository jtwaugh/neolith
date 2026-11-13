# Hand-extracted inputs

## Removed: Jordan et al. 2016 (2026-11-13)

`jordan2016_africa.csv` held the African rows of the earliest-pottery table in the supplement to
Jordan, P., Gibbs, K., Hommel, P., Piezonka, H., Silva, F. & Steele, J. 2016. Modelling the
diffusion of pottery technologies across Afro-Eurasia. *Antiquity* 90: 590–603,
https://doi.org/10.15184/aqy.2016.68. That supplement is © Antiquity Publications, all rights
reserved, so a transcribed copy can't be published under the project's CC BY-SA data licence.
The table and its reader were removed.

Of its 83 sites:
- **30** already have a pottery-bearing record within 15 km in open sources we use: Rotunno &
  Crema 2025 (MIT) and MedAfriCarbon (CC BY 4.0). Those cover the Sahara, the Nile and the Maghreb.
- **22** lie south of the map (below 5.5°N).
- **31** are on the map with no open pottery record nearby. They are listed below.

Most of the 31 have radiocarbon dates in p3k14c (CC0), which the settlements already use.
What no open dataset gives is the fact that pottery was found in the dated layer. To bring them
back, transcribe that fact from each site's **primary** excavation report, with the report cited
per row, not from Jordan's table. Until then, the pottery surface treats these places as
unobserved, and the gap critic's judgements cover them as speculation.

| Site (Jordan's name) | Lat, lon | Nearest open pottery record | Dates in p3k14c |
|---|---|---|---|
| Abu Tabari S02/1 | 17.5, 28.5 | 93 km | no |
| Abu Tabari S02/28 | 17.5, 28.5 | 93 km | no |
| Abu Tabari S02/52 | 17.5, 28.5 | 93 km | no |
| Apa | 6.4, 2.8 | 1121 km | no |
| Bosumpra, Ghana | 6.7, 0.7 | 969 km | no |
| Bou-Sfer, Algeria | 35.7, -0.8 | 31 km | no |
| Cocorba | 14.7, -0.5 | 294 km | yes |
| Daboya | 9.5, -1.4 | 589 km | yes |
| Dibeira West (DIW-50), Sudan | 21.8, 31.4 | 21 km | yes |
| Erg Tichodaïne, Algeria | 26.4, 6.8 | 247 km | no |
| Ezi-Ukwu Ukpa I | 5.9, 7.9 | 892 km | yes |
| Fadar | 15.0, -0.7 | 275 km | yes |
| Gabrong, Chad | 21.2, 17.5 | 52 km | yes |
| Gajiganna D | 12.3, 13.2 | 62 km | yes |
| Gao Lagoon, Ghana | 5.7, 0.0 | 1038 km | yes |
| Hafir, Algeria | 34.8, -2.3 | 27 km | yes |
| Iwo Eleru, Nigeria | 7.4, 5.3 | 1015 km | yes |
| Kamabai | 9.2, -12.0 | 1095 km | yes |
| Khant de Saint-Louis, Senegal | 16.5, -16.1 | 490 km | no |
| Kintampo K1 | 8.1, -1.7 | 726 km | no |
| Kintampo K6 | 8.0, -1.7 | 737 km | no |
| Kintampo K8 | 8.1, -1.7 | 726 km | no |
| Mumute | 8.7, -1.7 | 662 km | no |
| Ntereso | 9.1, -1.2 | 638 km | no |
| Oursi | 14.7, -0.5 | 294 km | yes |
| Shum Laka | 5.9, 10.1 | 750 km | yes |
| Ti-n-Akof | 15.0, -0.2 | 329 km | yes |
| Ti-n-Torha Two Caves (Libya) | 25.0, 10.3 | 22 km | yes |
| Tintane pécheur, Mauritania | 20.9, -15.3 | 143 km | no |
| Tuba Ajuz I | 12.1, 13.2 | 42 km | yes |
| Yagoua, Cameroon | 10.3, 15.2 | 255 km | yes |

## `dolbunova2023_starts.csv`

Modelled start dates (years BC) of pottery at eight sites, from the comment
block in `SI_Spatial_Temporal.r` of the Dolbunova et al. 2023 data deposit
(Zenodo 6619101, CC BY 4.0): Bayesian models of each site's earliest
pottery-bearing dates. Coordinates are those of Dolbunova's own site table
(SI_ORA.xlsx), except Rakushechny Yar, which is not in it: its point was entered
from general knowledge (lower Don, near Razdorskaya) and is approximate.

The pipeline dates each of Dolbunova's 156 sites from the start of its nearest
modelled site to 4000 BC (uniform), instead of giving every site the
dataset-wide 6000-4000 BC span.
