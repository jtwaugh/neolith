# Sources for `data/isostyle/`

Generated from `data/ATTRIBUTIONS.toml` by `python -m pipeline attributions`; edit that file.

The evidence atlas is built from the datasets below, downloaded by `python -m isostyle fetch`
(`isostyle/config.toml` `[[sources]]`, checksums in `build/isostyle/sources/provenance.json`),
plus the settlement dates (`data/settlements/SOURCES.md`) and two tables transcribed by hand
(`data/isostyle/inputs/`). How each one becomes a layer is in `METHODS.md`. The master list of
licences and citations is `ATTRIBUTIONS.md` at the repository root; the key of each entry there
is given in brackets.

The speculative fill (`speculative/`) rests on the gap critic's judgements in `intuitions/*.toml`.
Each judgement carries its own literature list, with `checked = false` where a citation was not
read in full. They are judgements, not data, and are marked as such wherever they appear.

Removed: Paulsson 2019 megalith dates (CC BY-NC-ND), joined by lab number until 2026-11-13.

## Datasets

| Dataset | Used in | Licence | Link |
|---|---|---|---|
| Neotoma Paleoecology Database (including the European Pollen Database) [`neotoma`] | Biome anchors; isostyle cereal pollen and dung spore layers | CC-BY-4.0 | https://www.neotomadb.org |
| GEOGLOWS Hydrological Model v2 stream network [`geoglows`] | River courses (pipeline/geoglows.py, pipeline/rivers.py; Makefile -> build/geoglows); unnamed reaches in isostyle river rules | CC-BY-4.0 | https://data.geoglows.org |
| XRONOS chronological database [`xronos`] | Settlements, dates, survey intensity, every isostyle layer built on dated site-phases | CC-BY-4.0 | https://xronos.ch |
| Allen Ancient DNA Resource (AADR) v66.p1, 1240K annotation [`aadr`] | Settlements and dates; isostyle aDNA and haplogroup layers | CC0-1.0 | https://doi.org/10.7910/DVN/FFIDCW |
| Evershed et al. 2022, lipid residue site-phases [`evershed2022`] | isostyle pottery | MIT | https://github.com/AdrianTimpson/2020-03-03523A |
| Rigaud, Manen & García-Martínez de Lagrán 2018, S1 Dataset [`rigaud2018`] | isostyle ornaments | CC-BY-4.0 | https://doi.org/10.1371/journal.pone.0196488 |
| Dolbunova et al. 2023, vessel table with site coordinates [`dolbunova2023`] | isostyle pottery; data/isostyle/inputs/dolbunova2023_starts.csv | CC-BY-4.0 | https://doi.org/10.5281/zenodo.6619101 |
| Windler 2019, Spondylus database [`windler2019`] | isostyle ornaments | CC-BY-4.0 | https://doi.org/10.5281/zenodo.2840333 |
| Tsirintoulaki, Matzig & Riede 2023, dated barbed points [`tsirintoulaki2023`] | isostyle bone/antler | MIT | https://doi.org/10.5281/zenodo.7244045 |
| Perrin, BDA (Base de données archéologiques) 2021 export [`bda2021`] | isostyle flaked stone, pottery | CC-BY-4.0 | https://doi.org/10.34847/nkl.dde9fnm8 |
| SoilGrids 2.0 pH(H2O), 5 km aggregate [`soilgrids`] | isostyle bone mask; residual detection model (acid soil) | CC-BY-4.0 | https://www.isric.org/explore/soilgrids |
| MedAfriCarbon v1.0.3 [`medafricarbon`] | isostyle pottery, livestock | CC-BY-4.0 | https://doi.org/10.5281/zenodo.3689716 |
| Rotunno & Crema 2025, Saharan pottery dates [`rotunno2025`] | isostyle pottery | MIT | https://github.com/roccorot/OriginPotteryNAfrica |
| DEFC, Digitizing Early Farming Cultures (sites, areas, finds) [`defc`] | isostyle structures, finds | CC-BY-4.0 | https://arche.acdh.oeaw.ac.at/api/220828 |
| DObsiSS v2.0 (Batist), obsidian sourcing in SW Asia [`dobsiss`] | isostyle flaked stone | CC-BY-SA-4.0 | https://doi.org/10.5281/zenodo.55848 |
| Arranz-Otaegui & Roe 2023, SW Asian Neolithic flora [`arranzotaegui2023`] | isostyle cereals | CC0-1.0 | https://github.com/joeroe/SWAsiaNeolithicFounderCrops |
| ADEMNES archaeobotanical/faunal database (Riehl), via Arranz-Otaegui & Roe 2023 [`ademnes`] | isostyle domestic livestock, phases, sites | LicenseRef-ADEMNES-research-use | https://www.ademnes.de/database.php |
| Open Context integrated Anatolian zooarchaeology (EOL), summary [`opencontext-eol`] | isostyle domestic livestock | CC-BY-4.0 | https://github.com/ekansa/opencontext-eol-zooarch |
| Phelps et al. 2019, African Holocene fauna (PANGAEA 904942) [`phelps2019`] | isostyle domestic livestock | CC-BY-4.0 | https://doi.org/10.1594/PANGAEA.904942 |
| Neolithic rondel enclosures in Central Europe v1.1.0 [`rondels`] | isostyle enclosures | CC-BY-4.0 | https://doi.org/10.5281/zenodo.23738404 |
| LandClimII REVEALS land-cover reconstructions [`landclim2`] | isostyle open land | CC-BY-4.0 | https://doi.org/10.1594/PANGAEA.937075 |
| EUROEVOL dataset (sites, dates, archaeobotany, fauna) [`euroevol`] | isostyle cereals, domestic livestock | CC0-1.0 | https://discovery.ucl.ac.uk/id/eprint/1469811/ |

## References

- Williams, J.W. et al. 2018. The Neotoma Paleoecology Database. Quaternary Research 89:156-177. Plus the dataset PIs listed per record. https://www.neotomadb.org
- GEOGloWS ECMWF Streamflow Service, Hydrological Model Version 2.0 (GEOGloWS v2), stream network and attribute table, https://geoglows-v2.s3.amazonaws.com (licenses.md). Changes: reaches of 1,000 km² or more upstream inside the map box, lines reversed to run downstream, joined to the attribute table on LINKNO, and an endorheic flag derived by the project. https://data.geoglows.org
- Roe, J., Hinz, M., Hafner, A. et al. 2025. XRONOS: an open data infrastructure for archaeological chronology. Journal of Computer Applications in Archaeology 8(1). doi:10.5334/jcaa.191. Original sources of each date are kept in data/settlements/dates.csv.gz. https://xronos.ch
- Mallick, S., Micco, A., Mah, M. et al. 2024. The Allen Ancient DNA Resource (AADR): a curated compendium of ancient human genomes. Scientific Data 11:182. Plus the original genetics papers per sample. https://doi.org/10.7910/DVN/FFIDCW
- Evershed, R.P., Davey Smith, G., Roffet-Salque, M. et al. 2022. Dairying, diseases and the evolution of lactase persistence in Europe. Nature 608:336-345. doi:10.1038/s41586-022-05010-7. Data (c) 2021 Adrian Timpson, MIT License. https://github.com/AdrianTimpson/2020-03-03523A
- Rigaud, S., Manen, C. & García-Martínez de Lagrán, I. 2018. Symbols in motion: flexible cultural boundaries and the fast spread of the Neolithic in the western Mediterranean. PLoS ONE 13:e0196488. https://doi.org/10.1371/journal.pone.0196488
- Dolbunova, E., Lucquin, A., McLaughlin, T.R. et al. 2023. The transmission of pottery technology among prehistoric European hunter-gatherers. Nature Human Behaviour 7:171-183. https://doi.org/10.5281/zenodo.6619101
- Windler, A. 2019. Spondylus database (Zenodo 2840333). https://doi.org/10.5281/zenodo.2840333
- Tsirintoulaki, K., Matzig, D.N. & Riede, F. 2022. Research compendium (Zenodo 7244045), (c) 2022 David N. Matzig, MIT License. Paper: Open Archaeology, doi:10.1515/opar-2022-0276. https://doi.org/10.5281/zenodo.7244045
- Perrin, T. 2021. BDA export (Nakala, doi:10.34847/nkl.dde9fnm8). https://doi.org/10.34847/nkl.dde9fnm8
- Poggio, L., de Sousa, L.M., Batjes, N.H. et al. 2021. SoilGrids 2.0: producing soil information for the globe with quantified spatial uncertainty. SOIL 7:217-240. https://www.isric.org/explore/soilgrids
- Lucarini, G., Wilkinson, T., Crema, E.R. et al. 2020. The MedAfriCarbon radiocarbon database and web application. Journal of Open Archaeology Data 8:1. https://doi.org/10.5281/zenodo.3689716
- Rotunno, R. & Crema, E.R. 2025. Bayesian analyses of radiocarbon dates suggest multiple origins of ceramic technology in Early Holocene Africa. Nature Communications 16:8819. doi:10.1038/s41467-025-63887-0. Code and data (c) 2024 roccorot, MIT License. https://github.com/roccorot/OriginPotteryNAfrica
- Aspöck, E., Štuhec, S., Kopetzky, K. & Kucera, M. Digitizing Early Farming Cultures (DEFC). Austrian Academy of Sciences, ARCHE. https://arche.acdh.oeaw.ac.at/api/220828
- Batist, Z. DObsiSS: Database of Obsidian Sourcing Studies, v2.0 (Zenodo 55848). https://doi.org/10.5281/zenodo.55848
- Arranz-Otaegui, A. & Roe, J. 2023. Revisiting the concept of the 'Neolithic founder crops' in southwest Asia. Vegetation History and Archaeobotany 32:475-499. https://github.com/joeroe/SWAsiaNeolithicFounderCrops
- ADEMNES: The GRF-funded Archaeobotanical Database of Eastern Mediterranean and Near Eastern Sites, last update 2015. www.ademnes.de. Riehl, S. & Kümmel, C. 2005. Redistributed in Arranz-Otaegui & Roe 2023. https://www.ademnes.de/database.php
- Arbuckle, B.S., Kansa, S.W., Kansa, E. et al. 2014. Data sharing reveals complexity in the westward spread of domestic animals across Neolithic Turkey. PLoS ONE 9:e99845. Data via Open Context. https://github.com/ekansa/opencontext-eol-zooarch
- Phelps, L.N., Broennimann, O., Manning, K. et al. 2019. Reconstructing the Holocene spread of livestock in Africa (dataset). PANGAEA. doi:10.1594/PANGAEA.904942 https://doi.org/10.1594/PANGAEA.904942
- Vondrovský, V., Bartík, J., Furholt, K. et al. 2026. Neolithic (4850-4500 BCE) rondel enclosures in Central Europe: a curated geospatial and structural dataset, v1.1.0. Zenodo. doi:10.5281/zenodo.23738404 https://doi.org/10.5281/zenodo.23738404
- Fyfe, R. et al. 2021. LandClimII REVEALS land-cover reconstructions (PANGAEA 937075). Github, M. et al. 2022, Climate of the Past 18:1059. https://doi.org/10.1594/PANGAEA.937075
- Manning, K., Colledge, S., Crema, E. et al. 2016. The Cultural Evolution of Neolithic Europe. EUROEVOL Dataset 1-2. Journal of Open Archaeology Data 5:e2, e3; Colledge, S. 2016. EUROEVOL Dataset 3: Archaeobotanical. JOAD 5:e4. https://discovery.ucl.ac.uk/id/eprint/1469811/
