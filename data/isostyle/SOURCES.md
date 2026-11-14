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
| Allen Ancient DNA Resource (AADR) v66.p1, 1240K annotation and genotypes [`aadr`] | Settlements and dates; isostyle aDNA, haplogroup and ancestry layers | CC0-1.0 | https://doi.org/10.7910/DVN/FFIDCW |
| Salem et al. 2025, Takarkori genomes (sample metadata) [`salem2025`] | isostyle aDNA and mt haplogroup layers; data/isostyle/inputs/supplementary_genomes.toml | facts | https://doi.org/10.1038/s41586-025-08793-7 |
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
- Salem, N. et al. 2025. Ancient DNA from the Green Sahara reveals ancestral North African lineage. Nature 641. https://doi.org/10.1038/s41586-025-08793-7. Reads: ENA PRJEB84057. https://doi.org/10.1038/s41586-025-08793-7
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

## Literature checked for the gap critic's judgements

Generated from the `literature` lists in `intuitions/*.toml`: the entries with `checked = true`, each with the page it was checked against and how much of it was read. Unchecked entries are left out.

### adna_samples

- Posth et al. 2023, 'Palaeogenomics of Upper Palaeolithic to Neolithic European hunter-gatherers', Nature 615 https://doi.org/10.1038/s41586-023-05726-0 (AADR annotation + abstract)
- Saag et al. 2021, 'Genetic ancestry changes in Stone to Bronze Age transition in the East European plain', Sci. Adv. 7 https://doi.org/10.1126/sciadv.abd6535 (AADR annotation + abstract)
- Mathieson et al. 2015, 'Genome-wide patterns of selection in 230 ancient Eurasians', Nature 528 https://doi.org/10.1038/nature16152 (AADR annotation + abstract)
- Allentoft et al. 2024, 'Population genomics of post-glacial western Eurasia', Nature 625 https://doi.org/10.1038/s41586-023-06865-0 (AADR annotation + abstract)
- Wang et al. 2019, 'Ancient human genome-wide data from a 3000-year interval in the Caucasus corresponds with eco-geographic regions', Nat. Commun. 10 https://doi.org/10.1038/s41467-018-08220-8 (AADR annotation + abstract)
- Mathieson et al. 2018, 'The genomic history of southeastern Europe', Nature 555 https://doi.org/10.1038/nature25778 (AADR annotation + abstract)
- Nikitin et al. 2025, 'A genomic history of the North Pontic Region from the Neolithic to the Bronze Age', Nature 639 https://doi.org/10.1038/s41586-024-08372-2 (AADR annotation + abstract)
- Mittnik et al. 2018, 'The genetic prehistory of the Baltic Sea region', Nat. Commun. 9 https://doi.org/10.1038/s41467-018-02825-9 (AADR annotation + abstract)
- Günther et al. 2018, 'Population genomics of Mesolithic Scandinavia', PLoS Biol. 16 https://doi.org/10.1371/journal.pbio.2003703 (AADR annotation + abstract)
- Lamnidis et al. 2018, 'Ancient Fennoscandian genomes reveal origin and spread of Siberian ancestry in Europe', Nat. Commun. 9 https://doi.org/10.1038/s41467-018-07483-5 (AADR annotation + abstract)
- Rivollat et al. 2020, 'Ancient genome-wide DNA from France highlights the complexity of interactions between Mesolithic hunter-gatherers and Neolithic farmers', Sci. Adv. 6 https://doi.org/10.1126/sciadv.aaz5344 (AADR annotation + abstract)
- Olalde et al. 2019, 'The genomic history of the Iberian Peninsula over the past 8000 years', Science 363 https://doi.org/10.1126/science.aav4040 (AADR annotation + abstract)
- Brace et al. 2019, 'Ancient genomes indicate population replacement in Early Neolithic Britain', Nat. Ecol. Evol. 3 https://doi.org/10.1038/s41559-019-0871-9 (AADR annotation + abstract)
- Antonio et al. 2019, 'Ancient Rome: a genetic crossroads of Europe and the Mediterranean', Science 366 (includes Italian Mesolithic-Neolithic) https://doi.org/10.1126/science.aay6826 (AADR annotation + abstract)
- Fernandes et al. 2020, 'The spread of steppe and Iranian-related ancestry in the islands of the western Mediterranean', Nat. Ecol. Evol. 4 https://doi.org/10.1038/s41559-020-1102-0 (AADR annotation + abstract)
- Kılınç et al. 2016, 'The demographic development of the first farmers in Anatolia', Curr. Biol. 26 https://doi.org/10.1016/j.cub.2016.07.057 (AADR annotation + abstract)
- Lazaridis et al. 2022, 'The genetic history of the Southern Arc: a bridge between West Asia and Europe', Science 377 https://doi.org/10.1126/science.abm4247 (AADR annotation + abstract)
- Lazaridis et al. 2016, 'Genomic insights into the origin of farming in the ancient Near East', Nature 536 https://doi.org/10.1038/nature19310 (AADR annotation + abstract)
- Harney et al. 2018, 'Ancient DNA from Chalcolithic Israel reveals the role of population mixture in cultural transformation', Nat. Commun. 9 https://doi.org/10.1038/s41467-018-05649-9 (AADR annotation + abstract)
- Narasimhan et al. 2019, 'The formation of human populations in South and Central Asia', Science 365 https://doi.org/10.1126/science.aat7487 (AADR annotation + abstract)
- Martiniano et al. 2024, 'Ancient genomes illuminate Eastern Arabian population history and adaptation against malaria', Cell Genomics 4 (Tylos-period Bahrain) https://doi.org/10.1016/j.xgen.2024.100507 (AADR annotation + abstract)
- Salem et al. 2025, 'Ancient DNA from the Green Sahara reveals ancestral North African lineage', Nature 641 https://doi.org/10.1038/s41586-025-08793-7 (AADR annotation + abstract)
- Morez Jacobs et al. 2025, 'Whole-genome ancestry of an Old Kingdom Egyptian', Nature (Nuwayrat) https://doi.org/10.1038/s41586-025-09195-5 (AADR annotation + abstract)
- Wang et al. 2022, '4000-year-old hair from the Middle Nile highlights unusual ancient DNA degradation pattern and a potential source of early eastern Africa pastoralists', Sci. Rep. 12 https://doi.org/10.1038/s41598-022-25384-y (abstract + AADR annotation)
- Sereno et al. 2008, 'Lakeside cemeteries in the Sahara: 5000 years of Holocene population and environmental change', PLoS ONE 3 (Gobero) https://doi.org/10.1371/journal.pone.0002995 (abstract)
- Stojanowski, Irish & Sereno 2026, 'Early to Middle Holocene hunter-fisher-gatherers from the Green Sahara (Gobero, Niger): dental evidence for regional African affinities', Am. J. Biol. Anthropol. 190 https://doi.org/10.1002/ajpa.70262 (abstract + repository page)
- Lipson et al. 2020, 'Ancient West African foragers in the context of African population history', Nature 577 (Shum Laka) https://doi.org/10.1038/s41586-020-1929-1 (AADR annotation + abstract)
- Gallego Llorente et al. 2015, 'Ancient Ethiopian genome reveals extensive Eurasian admixture throughout the African continent', Science 350 (Mota) https://doi.org/10.1126/science.aad2879 (AADR annotation + abstract)
- Fregel et al. 2018, 'Ancient genomes from North Africa evidence prehistoric migrations to the Maghreb from both the Levant and Europe', PNAS 115 https://doi.org/10.1073/pnas.1800851115 (AADR annotation + abstract)
- van de Loosdrecht et al. 2018, 'Pleistocene North African genomes link Near Eastern and sub-Saharan African human populations', Science 360 https://doi.org/10.1126/science.aar8380 (AADR annotation + abstract)

### bone_antler

- Zhilin 2015, 'Early Mesolithic bone arrowheads from the Volga-Oka interfluve, Central Russia', Fennoscandia archaeologica XXXII, 35-54 https://journal.fi/fennoscandiaarchaeologica/article/download/126513/76331/265675 (full text (searched passages))
- David 2003, 'The Mesolithic Zvejnieki site (Latvia) in its European context: preliminary results delivered by a technological study of the bone and antler industry', Eesti Arheoloogia Ajakiri (Estonian Journal of Archaeology) 7(2), 99-122 https://doi.org/10.3176/arch.2003.2.01 (full text (searched passages))
- Tsirintoulaki, Matzig & Riede 2023, 'A 2D Geometric Morphometric Assessment of Chrono-Cultural Trends in Osseous Barbed Points of the European Final Palaeolithic and Early Mesolithic', Open Archaeology 9 https://api.openalex.org/works/doi:10.1515/opar-2022-0276 (abstract)

### cereal_pollen

- Lézine, Hély, Grenier, Braconnot & Krinner 2011, 'Sahara and Sahel vulnerability to climate changes, lessons from Holocene hydrological data', QSR 30, 3001-3012 https://insu.hal.science/insu-00647072v1 (abstract)
- Salzmann, Hoelzmann & Morczinek 2002, 'Late Quaternary climate and vegetation of the Sudanian zone of northeast Nigeria', Quaternary Research 58, 73-83 (Lake Tilla) https://doi.org/10.1006/qres.2002.2356 (abstract)
- Madella, García-Granero, Out, Ryan & Usai 2014, 'Microbotanical evidence of domestic cereals in Africa 7000 years ago', PLoS ONE 9(10), e110177 https://doi.org/10.1371/journal.pone.0110177 (abstract)
- Wengrow, Dee, Foster, Stevenson & Bronk Ramsey 2014, 'Cultural convergence in the Neolithic of the Nile Valley: a prehistoric perspective on Egypt's place in Africa', Antiquity 88, 95-111 https://doi.org/10.1017/S0003598X00050249 (abstract)
- Morales, Pérez-Jordà, Peña-Chocarro, Zapata, Ruíz-Alonso, López-Sáez & Linstädter 2013, 'The origins of agriculture in North-West Africa: macro-botanical remains from Epipalaeolithic and Early Neolithic levels of Ifri Oudadane (Morocco)', JAS 40, 2659-2669 https://crc806db.uni-koeln.de/dataset/show/the-origins-of-agriculture-in-north-west-africa-macro-botanical-remains-from-epipalaeolithic-and/ (abstract)
- Peña-Chocarro, Pérez Jordà, Morales Mateos & Zapata 2013, 'Neolithic plant use in the western Mediterranean region: preliminary results from the AGRIWESTMED project', Annali di Botanica 3, 135-141 (Kaf Taht el-Ghar, Ifri Oudadane) https://rosa.uniroma1.it/rosa04/annali_di_botanica/article/download/10306/10237/13648 (full text (searched passages))
- Parker, Goudie, Stokes, White, Hodson, Manning & Kennet 2006, 'A record of Holocene climate change from lake geochemical analyses in southeastern Arabia', Quaternary Research 66, 465-476 https://doi.org/10.1016/j.yqres.2006.07.001 (abstract)
- Crassard & Drechsler 2013, 'Towards new paradigms: multiple pathways for the Arabian Neolithic', Arabian Archaeology and Epigraphy 24, 3-8 https://doi.org/10.1111/aae.12021 (abstract)
- Heun, Schäfer-Pregl, Klawan, Castagna, Accerbi, Borghi & Salamini 1997, 'Site of einkorn wheat domestication identified by DNA fingerprinting', Science 278, 1312-1314 https://doi.org/10.1126/science.278.5341.1312 (abstract)
- van Zeist & Bottema 1977, 'Palynological investigations in western Iran', Palaeohistoria 19, 19-85 (Zeribar, Mirabad) https://ugp.rug.nl/Palaeohistoria/article/view/25018 (full text (searched passages))
- Rose 2010, 'New light on human prehistory in the Arabo-Persian Gulf Oasis', Current Anthropology 51, 849-883 https://doi.org/10.1086/657397 (abstract)

### cereals

- Arranz-Otaegui & Roe 2023, Revisiting the concept of the 'Neolithic founder crops' in southwest Asia, Vegetation History and Archaeobotany 32 (SW Asian Neolithic archaeobotany compilation) https://doi.org/10.1007/s00334-023-00917-1 (abstract)
- Riehl, Zeidi & Conard 2013, Emergence of agriculture in the foothills of the Zagros Mountains of Iran (Chogha Golan), Science 341 https://doi.org/10.1126/science.1236743 (abstract)
- Savard, Nesbitt & Jones 2006, The role of wild grasses in subsistence and sedentism: new evidence from the northern Fertile Crescent (Hallan Çemi, Demirköy, Qermez Dere, M'lefaat), World Archaeology 38 https://doi.org/10.1080/00438240600689016 (abstract)
- Fairbairn 2005, A history of agricultural production at Neolithic Çatalhöyük East, Turkey, World Archaeology 37 https://doi.org/10.1080/00438240500094762 (abstract)
- Riehl, Zeidi & Conard 2013, Science 341 https://doi.org/10.1126/science.1236743 (abstract)
- Hamon et al. 2016, Gadachrili Gora: architecture and organisation of a Neolithic settlement in the middle Kura Valley (6th millennium BC, Georgia), Quaternary International 395 https://doi.org/10.1016/j.quaint.2015.01.055 (abstract (repository record))
- Hamon et al. 2016, Gadachrili Gora, Quaternary International 395 https://doi.org/10.1016/j.quaint.2015.01.055 (abstract (repository record))
- Maurer et al. 2026, Seasonality and mobility: an integrative framework for reconstructing Kura-Araxes pastoral systems at Maxta I, Nakhchivan, PLoS ONE 21(4), e0346108 https://doi.org/10.1371/journal.pone.0346108 (abstract)
- Harris 2010, Origins of Agriculture in Western Central Asia https://doi.org/10.2307/j.ctt3fj6gz (book review (Bendrey 2013, Pastoralism 3:9))
- Cleuziou & Costantini 1980, Premiers éléments sur l'agriculture protohistorique de l'Arabie orientale (Hili 8) https://doi.org/10.3406/paleo.1980.4278 (abstract and part of full text)
- Fuller & Lucas 2021, Savanna on the Nile: long-term agricultural diversification and intensification in Nubia, in The Oxford Handbook of Ancient Nubia https://doi.org/10.1093/oxfordhb/9780190496272.013.45 (abstract)
- Manning et al. 2011, 4500-year old domesticated pearl millet (Pennisetum glaucum) from the Tilemsi Valley, Mali, Journal of Archaeological Science 38 https://doi.org/10.1016/j.jas.2010.09.007 (title only)
- D'Andrea et al. 2007, Early domesticated cowpea (Vigna unguiculata) from central Ghana (Kintampo), Antiquity 81 https://doi.org/10.1017/s0003598x00095661 (abstract)
- D'Andrea 2008, T'ef (Eragrostis tef) in ancient agricultural systems of highland Ethiopia, Economic Botany 62 https://doi.org/10.1007/s12231-008-9053-4 (abstract)
- Morales et al. 2013, The origins of agriculture in North-West Africa: macro-botanical remains from Epipalaeolithic and Early Neolithic levels of Ifri Oudadane (Morocco), Journal of Archaeological Science 40 https://doi.org/10.1016/j.jas.2013.01.026 (abstract (repository record))
- Morales et al. 2013, Ifri Oudadane, Journal of Archaeological Science 40 https://doi.org/10.1016/j.jas.2013.01.026 (abstract (repository record))
- Zapata et al. 2013, Holocene environmental change in NE Morocco: archaeological and palaeobotanical evidences from Ifri Oudadane, The Holocene 23 https://crc806db.uni-koeln.de/dataset/show/holocene-environmental-change-in-ne-morocco-archaeological-and-palaeobotanical-evidences-from-ifri/ (abstract (repository record))
- Perlès 2001, The Early Neolithic in Greece https://doi.org/10.1017/cbo9780511612855 (publisher description)
- Marinova & Valamoti 2014, Crop diversity and choices in the prehistory of SE Europe: the archaeobotanical evidence from Greece and Bulgaria, in Plants and People: choices and diversity through time https://biblio.naturalsciences.be/library-1/rbins-staff-publications/articlereference.2015-02-03.1526477865 (abstract (repository record))
- Rottoli & Castiglioni 2009, Prehistory of plant growing and collecting in northern Italy, Vegetation History and Archaeobotany 18 https://doi.org/10.1007/s00334-007-0139-1 (abstract)
- Zapata et al. 2004, Early Neolithic agriculture in the Iberian Peninsula, Journal of World Prehistory 18 https://doi.org/10.1007/s10963-004-5621-4 (abstract)
- Zapata et al. 2004, Journal of World Prehistory 18 https://doi.org/10.1007/s10963-004-5621-4 (abstract)
- Behre 2007, Evidence for Mesolithic agriculture in and around central Europe?, Vegetation History and Archaeobotany 16 https://doi.org/10.1007/s00334-006-0081-7 (abstract)
- Manen et al. 2019, The Neolithic transition in the western Mediterranean: a complex and non-linear diffusion process, Radiocarbon 61 https://doi.org/10.1017/rdc.2018.98 (full text (first 100,000 characters))
- Colledge 2016, The Cultural Evolution of Neolithic Europe. EUROEVOL Dataset 3: Archaeobotanical Data, Journal of Open Archaeology Data 5 https://doi.org/10.5334/joad.42 (abstract)
- Behre 2007, Vegetation History and Archaeobotany 16 https://doi.org/10.1007/s00334-006-0081-7 (abstract)
- Bánffy 2019, First Farmers of the Carpathian Basin https://prehistoricsociety.org/publications/research-papers/8 (publisher description)
- Stevens & Fuller 2012, Did Neolithic farming fail? Antiquity 86 https://doi.org/10.1017/s0003598x00047864 (abstract)
- Stevens & Fuller 2012, Antiquity 86 https://doi.org/10.1017/s0003598x00047864 (abstract)
- McClatchie et al. 2014, Neolithic farming in north-western Europe: archaeobotanical evidence from Ireland, Journal of Archaeological Science 51 https://doi.org/10.1016/j.jas.2012.10.022 (abstract (repository record))
- Sørensen & Karg 2014, The expansion of agrarian societies towards the north, Journal of Archaeological Science 51 https://doi.org/10.1016/j.jas.2012.08.042 (abstract (repository record))
- Sørensen & Karg 2014, Journal of Archaeological Science 51 https://doi.org/10.1016/j.jas.2012.08.042 (abstract (repository record))
- Piličiauskas et al. 2018, eastern Baltic Corded Ware, Journal of Archaeological Science: Reports 21 https://doi.org/10.1016/j.jasrep.2018.08.023 (abstract (repository record))
- Endo, Nasu, Haskevych, Gershkovych, Videiko & Yanevich 2022, Re-identification of plant impressions on prehistoric pottery from Ukraine, Journal of Archaeological Science: Reports 42, 103364 https://elibrary.kubg.edu.ua/id/eprint/42600/ (abstract)
- Korenevskij 2022, The Maikop culture in the Northern Caucasus, Godišnjak Centra za balkanološka ispitivanja 41 https://doi.org/10.5644/Godisnjak.CBI.ANUBiH-41.1 (abstract)
- Rose 2010, New light on human prehistory in the Arabo-Persian Gulf Oasis, Current Anthropology 51 https://doi.org/10.1086/657397 (abstract)

### domestic_livestock

- Zeder 2011, The origins of agriculture in the Near East, Current Anthropology 52 https://doi.org/10.1086/659307 (abstract)
- Zeder 2011, Current Anthropology 52 https://doi.org/10.1086/659307 (abstract)
- Stiner et al. 2014, A forager-herder trade-off from broad-spectrum hunting to sheep management at Aşıklı Höyük, PNAS 111 https://doi.org/10.1073/pnas.1322723111 (abstract)
- Arbuckle et al. 2014, PLoS ONE 9 https://doi.org/10.1371/journal.pone.0099845 (full text (Europe PMC, searched passages))
- Vigne et al. 2012, First wave of cultivators spread to Cyprus at least 10,600 y ago, PNAS 109 https://doi.org/10.1073/pnas.1201693109 (full text (PMC))
- Zeder & Hesse 2000, The initial domestication of goats (Capra hircus) in the Zagros Mountains 10,000 years ago, Science 287 https://doi.org/10.1126/science.287.5461.2254 (abstract)
- Meshveliani et al. 2007, Mesolithic hunters at Kotias Klde, western Georgia: preliminary results, Paléorient 33 https://doi.org/10.3406/paleo.2007.5220 (abstract)
- Nishiaki, Guliyev & Kadowaki 2015, The origins of food production in the southern Caucasus: excavations at Hacı Elamxanlı Tepe, Azerbaijan, Antiquity 89 (348), Project Gallery https://antiquity.ac.uk/projgall/nishiaki348 (full text)
- Martin, McCorriston & Crassard 2009, Early Arabian pastoralism at Manayzah in Wadi Sana, Hadramawt, Proceedings of the Seminar for Arabian Studies https://shs.hal.science/halshs-00423893v1 (abstract)
- Drechsler 2009, The Dispersal of the Neolithic over the Arabian Peninsula https://doi.org/10.30861/9781407305028 (publisher description)
- Vermeersch et al. 2015, Early and Middle Holocene human occupation of the Egyptian Eastern Desert: Sodmein Cave, African Archaeological Review 32 https://doi.org/10.1007/s10437-015-9195-6 (abstract)
- Phelps et al. 2019, African Holocene faunal assemblages (PANGAEA 904942) https://doi.org/10.1594/PANGAEA.904942 (dataset description)
- Dunne et al. 2012, First dairying in green Saharan Africa in the fifth millennium BC, Nature 486 https://doi.org/10.1038/nature11186 (abstract)
- Lesur et al. 2014, The advent of herding in the Horn of Africa: new data from Ethiopia, Djibouti and Somaliland, Quaternary International 343 https://doi.org/10.1016/j.quaint.2013.11.024 (abstract)
- Manzo 2020, Back to Mahal Teglinos: new Pharaonic evidence from Eastern Sudan, Journal of Egyptian Archaeology 106 https://unora.unior.it/retrieve/handle/11574/196305/80087/Manzo_Back%20to%20Mahal%20Teglinos_JEA.pdf (full text (searched passages))
- Perlès 2001, The Early Neolithic in Greece https://doi.org/10.1017/cbo9780511612855 (publisher description)
- Orton 2012, Taphonomy and interpretation: an analytical framework for social zooarchaeology (Vinča faunas), International Journal of Osteoarchaeology 22 https://doi.org/10.1002/oa.1212 (abstract)
- Zilhão 1993 on the 'Mesolithic sheep' of southern France, Journal of Mediterranean Archaeology 6 https://doi.org/10.1558/jmea.v6i1.5 (abstract)
- Rowley-Conwy 2011, Westward Ho! The spread of agriculture from Central Europe to the Atlantic, Current Anthropology 52 https://doi.org/10.1086/658368 (abstract)
- Binder et al. 2017, Modelling the earliest north-western dispersal of Mediterranean Impressed Wares: new dates and Bayesian chronological model, Documenta Praehistorica 44: 54-77 https://journals.uni-lj.si/DocumentaPraehistorica/article/view/44.4 (full text (searched passages))
- Bánffy 2019, First Farmers of the Carpathian Basin https://www.prehistoricsociety.org/publications/research-papers/8 (publisher description)
- Piličiauskas et al. 2018, The Corded Ware culture in the Eastern Baltic: new evidence on chronology, diet, beaker, bone and flint tool function, Journal of Archaeological Science: Reports 21 https://doi.org/10.1016/j.jasrep.2018.08.023 (abstract)
- Shishlina 2008, Reconstruction of the Bronze Age of the Caspian steppes https://doi.org/10.30861/9781407303567 (publisher description)

### dung_spores

- López Sáez & López Merino 2007, 'Coprophilous fungi as a source of information of anthropic activities during the Prehistory in the Amblés Valley (Ávila, Spain): the archaeopalynological record', Revista Española de Micropaleontología 39(1-2), 103-116 https://produccioncientifica.ucm.es/documentos/5f07a3e92999527a01a3ea09 (abstract)
- Crassard et al. 2015, 'Addressing the Desert Kites Phenomenon and Its Global Range Through a Multi-proxy Approach', Journal of Archaeological Method and Theory 22, 1093-1121 https://api.archives-ouvertes.fr/search/?q=halId_s:hal-01829329&fl=title_s,abstract_s (abstract)
- Zeder & Hesse 2000, 'The initial domestication of goats (Capra hircus) in the Zagros mountains 10,000 years ago', Science 287, 2254-2257 https://europepmc.org/article/MED/10731145 (abstract)
- Petraglia et al. 2020, 'Human responses to climate and ecosystem change in ancient Arabia', PNAS 117, 8263-8270 https://pmc.ncbi.nlm.nih.gov/articles/PMC7165439/ (full text (searched passages))
- Dunne et al. 2012, 'First dairying in green Saharan Africa in the fifth millennium BC', Nature 486, 390-394 https://europepmc.org/article/MED/22722200 (abstract)

### enclosures

- Whittle, Healy & Bayliss 2011, Gathering Time: Dating the Early Neolithic Enclosures of Southern Britain and Ireland, Oxbow Books https://www.stir.ac.uk/research/hub/publication/648549 (abstract)
- Whitehouse 2014, 'The chronology of the Neolithic ditched settlements of the Tavoliere and the Ofanto valley', Accordia Research Papers 13, 57-77 https://discovery.ucl.ac.uk/id/eprint/1508583/1/Whitehouse.pdf (full text (searched passages))

### flaked_stone

- Zhilin 2015, Early Mesolithic bone arrowheads from the Volga-Oka interfluve, central Russia, Fennoscandia archaeologica 32 https://journal.fi/fennoscandiaarchaeologica/article/download/126513/76331/265675 (full text (searched passages))

### ground_stone

- Jesse 2006, A short history of the Wadi Howar, Sudan, Sudan & Nubia 10 https://www.sudarchrs.org.uk/wp-content/uploads/2019/03/SARS_SN10-Jesse_opt.pdf (full text)

### metallurgy

- Radivojević, Rehren, Pernicka, Šljivar, Brauns & Borić 2010, 'On the origins of extractive metallurgy: new evidence from Europe', Journal of Archaeological Science 37, 2775-2787 https://dienekes.blogspot.com/2010/06/earliest-copper-smelting-from-balkans.html (abstract)

### mt_haplogroup

- Posth et al. 2023, 'Palaeogenomics of Upper Palaeolithic to Neolithic European hunter-gatherers', Nature 615 https://doi.org/10.1038/s41586-023-05726-0 (AADR annotation + abstract)
- Villalba-Mouco et al. 2019, 'Survival of Late Pleistocene hunter-gatherer ancestry in the Iberian Peninsula', Curr. Biol. 29 https://doi.org/10.1016/j.cub.2019.02.006 (AADR annotation + abstract)
- Brace et al. 2019, 'Ancient genomes indicate population replacement in Early Neolithic Britain', Nat. Ecol. Evol. 3 https://doi.org/10.1038/s41559-019-0871-9 (AADR annotation + abstract)
- Fu et al. 2016, 'The genetic history of Ice Age Europe', Nature 534 https://doi.org/10.1038/nature17993 (AADR annotation + abstract)
- Mathieson et al. 2018, 'The genomic history of southeastern Europe', Nature 555 https://doi.org/10.1038/nature25778 (AADR annotation + abstract)
- Mittnik et al. 2018, 'The genetic prehistory of the Baltic Sea region', Nat. Commun. 9 https://doi.org/10.1038/s41467-018-02825-9 (AADR annotation + abstract)
- Günther et al. 2018, 'Population genomics of Mesolithic Scandinavia', PLoS Biol. 16 https://doi.org/10.1371/journal.pbio.2003703 (AADR annotation + abstract)
- Saag et al. 2017, 'Extensive farming in Estonia started through a sex-biased migration from the Steppe', Curr. Biol. 27 https://doi.org/10.1016/j.cub.2017.06.022 (AADR annotation + abstract)
- Mathieson et al. 2015, 'Genome-wide patterns of selection in 230 ancient Eurasians', Nature 528 https://doi.org/10.1038/nature16152 (AADR annotation + abstract)
- Saag et al. 2021, 'Genetic ancestry changes in Stone to Bronze Age transition in the East European plain', Sci. Adv. 7 https://doi.org/10.1126/sciadv.abd6535 (AADR annotation + abstract)
- Feldman et al. 2019, 'Late Pleistocene human genome suggests a local origin for the first farmers of central Anatolia', Nat. Commun. 10 https://doi.org/10.1038/s41467-019-09209-7 (AADR annotation + abstract)
- Kılınç et al. 2016, 'The demographic development of the first farmers in Anatolia', Curr. Biol. 26 https://doi.org/10.1016/j.cub.2016.07.057 (AADR annotation + abstract)
- Jones et al. 2015, 'Upper Palaeolithic genomes reveal deep roots of modern Eurasians', Nat. Commun. 6 https://doi.org/10.1038/ncomms9912 (AADR annotation + abstract)
- Lazaridis et al. 2016, 'Genomic insights into the origin of farming in the ancient Near East', Nature 536 https://doi.org/10.1038/nature19310 (AADR annotation + abstract)
- Harney et al. 2018, 'Ancient DNA from Chalcolithic Israel reveals the role of population mixture in cultural transformation', Nat. Commun. 9 https://doi.org/10.1038/s41467-018-05649-9 (AADR annotation + abstract)
- Lazaridis et al. 2022, 'The genetic history of the Southern Arc: a bridge between West Asia and Europe', Science 377 https://doi.org/10.1126/science.abm4247 (AADR annotation + abstract)
- Broushaki et al. 2016, 'Early Neolithic genomes from the eastern Fertile Crescent', Science 353 https://doi.org/10.1126/science.aaf7943 (AADR annotation + abstract)
- Narasimhan et al. 2019, 'The formation of human populations in South and Central Asia', Science 365 https://doi.org/10.1126/science.aat7487 (AADR annotation + abstract)
- Martiniano et al. 2024, 'Ancient genomes illuminate Eastern Arabian population history and adaptation against malaria', Cell Genomics 4 (Tylos-period Bahrain) https://doi.org/10.1016/j.xgen.2024.100507 (AADR annotation + abstract)
- Salem et al. 2025, 'Ancient DNA from the Green Sahara reveals ancestral North African lineage', Nature 641 https://doi.org/10.1038/s41586-025-08793-7 (full text)
- van de Loosdrecht et al. 2018, 'Pleistocene North African genomes link Near Eastern and sub-Saharan African human populations', Science 360 https://doi.org/10.1126/science.aar8380 (AADR annotation + abstract)
- Fregel et al. 2018, 'Ancient genomes from North Africa evidence prehistoric migrations to the Maghreb from both the Levant and Europe', PNAS 115 https://doi.org/10.1073/pnas.1800851115 (AADR annotation + abstract)
- Simões et al. 2023, 'Northwest African Neolithic initiated by migrants from Iberia and Levant', Nature 618 https://doi.org/10.1038/s41586-023-06166-6 (AADR annotation + abstract)
- Lipson et al. 2020, 'Ancient West African foragers in the context of African population history', Nature 577 (Shum Laka) https://doi.org/10.1038/s41586-020-1929-1 (AADR annotation + abstract)
- Gallego Llorente et al. 2015, 'Ancient Ethiopian genome reveals extensive Eurasian admixture throughout the African continent', Science 350 (Mota) https://doi.org/10.1126/science.aad2879 (AADR annotation + abstract)

### open_land

- Watrin, Lézine & Hély 2009, 'Plant migration and plant communities at the time of the green Sahara', CR Geoscience 341 https://comptes-rendus.academie-sciences.fr/geoscience/articles/10.1016/j.crte.2009.06.007 (full text)
- Hély, Lézine & APD contributors 2014, 'Holocene changes in African vegetation: tradeoff between climate and water availability', Climate of the Past 10, 681-686 https://cp.copernicus.org/articles/10/681/2014/ (full text (searched passages))
- Parker et al. 2004, 'Holocene vegetation dynamics in the northeastern Rub' al-Khali desert, Arabian Peninsula: a phytolith, pollen and carbon isotope study', Journal of Quaternary Science 19, 665-676 https://api.crossref.org/works/10.1002/jqs.880 (abstract)
- Djamali et al. 2008, 'A late Pleistocene long pollen record from Lake Urmia, NW Iran', Quaternary Research 69, 413-420 https://bura.brunel.ac.uk/handle/2438/4254?mode=full (abstract)
- Lamb, Eicher & Switsur 1989, 'An 18,000-year record of vegetation, lake-level and climatic change from Tigalmamine, Middle Atlas, Morocco', Journal of Biogeography 16, 65-74 https://research.aber.ac.uk/en/publications/an-18000-year-record-of-vegetation-lake-level-and-climatic-change/ (abstract)
- Salzmann & Hoelzmann 2005, 'The Dahomey Gap: an abrupt climatically induced rain forest fragmentation in West Africa during the late Holocene', The Holocene 15, 190-199 https://api.crossref.org/works/10.1191/0959683605hl799rp (abstract)
- Woldring & Bottema 2002, 'The vegetation history of East-Central Anatolia in relation to archaeology: the Eski Acıgöl pollen evidence compared with the Near Eastern environment', Palaeohistoria 43/44 (2001/2002) https://ugp.rug.nl/Palaeohistoria/article/view/25111 (abstract)
- Roberts et al. 2001, 'The tempo of Holocene climatic change in the eastern Mediterranean region: new high-resolution crater-lake sediment data from central Turkey', The Holocene 11, 721-736 https://api.crossref.org/works/10.1191/09596830195744 (abstract)
- Connor & Kvavadze 2009, 'Modelling late Quaternary changes in plant distribution, vegetation and climate using pollen data from Georgia, Caucasus', Journal of Biogeography 36, 529-545 https://api.crossref.org/works/10.1111/j.1365-2699.2008.02019.x (abstract)
- Trondman et al. 2015, 'Pollen-based quantitative reconstructions of Holocene regional vegetation cover (plant-functional types and land-cover types) in Europe suitable for climate modelling', Global Change Biology 21, 676-697 https://api.crossref.org/works/10.1111/gcb.12737 (abstract)
- Fyfe, Woodbridge & Roberts 2015, 'From forest to farmland: pollen-inferred land cover change across Europe using the pseudobiomization approach', Global Change Biology 21, 1197-1212 https://api.crossref.org/works/10.1111/gcb.12776 (abstract)
- Feurdean et al. 2021, 'The transformation of the forest steppe in the lower Danube Plain of south-eastern Europe: 6000 years of vegetation and land use dynamics', Biogeosciences 18, 1081-1103 https://bg.copernicus.org/articles/18/1081/2021/ (full text (searched passages))
- Krüger, Dörfler, Bennike & Wolters 2017, 'Life in Doggerland – palynological investigations of the environment of prehistoric hunter-gatherer societies in the North Sea Basin', E&G Quaternary Science Journal 66, 3-13 https://egqsj.copernicus.org/articles/66/3/2017/ (full text (searched passages))

### ornaments

- O'Shea & Zvelebil 1984, 'Oleneostrovski mogilnik: reconstructing the social and economic organization of prehistoric foragers in northern Russia', Journal of Anthropological Archaeology 3, 1-40 https://public.websites.umich.edu/~anth282/Olenii.pdf (full text (searched passages))
- Larsson 2010, 'A double grave with amber and bone adornments at Zvejnieki in northern Latvia', Archaeologia Baltica 13, 175-190 https://e-journals.ku.lt/journal/AB/article/1092/file/pdf (full text (searched passages))
- Rigaud, d'Errico & Vanhaeren 2015, 'Ornaments reveal resistance of North European cultures to the spread of farming', PLoS ONE 10(4), e0121166 https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0121166 (full text)
- de Beauclair 2008, 'Funerary rites in a Neolithic nomad community in Southeastern Arabia: the case of al-Buhais 18', Documenta Praehistorica 35, 143-152 https://api.crossref.org/works/10.4312/dp.35.10 (abstract)

### pottery

- Dolbunova et al. 2023, 'The transmission of pottery technology among prehistoric European hunter-gatherers', Nature Human Behaviour https://doi.org/10.1038/s41562-022-01491-8 (full text)
- Courel et al. 2021, The use of early pottery by hunter-gatherers of the Eastern European forest-steppe, Quaternary Science Reviews 269, 107143 https://doi.org/10.1016/j.quascirev.2021.107143 (abstract)
- Dolbunova et al. 2023, Nature Human Behaviour https://doi.org/10.1038/s41562-022-01491-8 (full text)
- Vybornov 2011, Time and palaeoenvironment in the Neolithisation of the Povolzhye forest-steppe, Documenta Praehistorica 38: 267-274 https://doi.org/10.4312/dp.38.21 (full text (searched passages))
- Dolbunova et al. 2020, 'Subsistence strategies and the origin of early Neolithic community in the lower Don River valley (Rakushechny Yar site, early/middle 6th millennium cal BC): first results', Quaternary International 541 https://doi.org/10.1016/j.quaint.2019.05.012 (abstract)
- Salavert, Gouriveau, Messager, Lebreton & Kiosak 2021, Multi-proxy archaeobotanical analysis from Mesolithic and Early Neolithic sites in south-west Ukraine, Environmental Archaeology 26(3): 349-362 https://shs.hal.science/halshs-02944345v1 (full text (searched passages))
- Mazurkevich & Dolbunova 2015, Documenta Praehistorica 42 https://doi.org/10.4312/dp.42.2 (full text (searched passages))
- Dolbunova et al. 2023, The transmission of pottery technology among prehistoric European hunter-gatherers, Nature Human Behaviour 7 https://europepmc.org/article/PMC/PMC9957732 (full text (searched passages))
- Tkachev & Tkacheva 2024, Early Neolithic of Southern Belarus: current state and prospects for study, Archaeology of the Eurasian Steppes 2024(4): 80-91 https://doi.org/10.24852/2587-6112.2024.4.80.91 (abstract)
- Kriiska et al. 2017, 'Late Mesolithic Narva stage in Estonia: pottery, settlement types and chronology', Estonian Journal of Archaeology 21 https://doi.org/10.3176/arch.2017.1.03 (abstract)
- Brunet 2002, Asie centrale: vers une redéfinition des complexes culturels de la fin du Pléistocène et des débuts de l'Holocène, Paléorient 28 https://doi.org/10.3406/paleo.2002.4743 (abstract)
- Riehl et al. 2013, Chogha Golan, Science https://doi.org/10.1126/science.1236743 (abstract)
- Huysecom et al. 2009, 'The emergence of pottery in Africa during the tenth millennium cal BC: new evidence from Ounjougou (Mali)', Antiquity 83 https://doi.org/10.1017/s0003598x00099245 (abstract)
- Huysecom et al. 2009, Antiquity 83 https://doi.org/10.1017/s0003598x00099245 (abstract)
- Jesse 2010, 'Early pottery in Northern Africa: an overview', Journal of African Archaeology 8 https://doi.org/10.3213/1612-1651-10171 (abstract)
- Rotunno & Crema 2025 (in atlas) https://doi.org/10.1038/s41467-025-63887-0 (abstract)
- Manning & Timpson 2014, 'The demographic response to Holocene climate change in the Sahara', Quaternary Science Reviews https://doi.org/10.1016/j.quascirev.2014.07.003 (abstract)
- Jesse 2010, Journal of African Archaeology 8 https://doi.org/10.3213/1612-1651-10171 (abstract)
- Jesse 2010, Early pottery in Northern Africa: an overview, Journal of African Archaeology 8 https://doi.org/10.3213/1612-1651-10171 (abstract)
- Jesse 2006, A short history of the Wadi Howar, Sudan, Sudan & Nubia 10 https://www.sudarchrs.org.uk/wp-content/uploads/2019/03/SARS_SN10-Jesse_opt.pdf (full text)
- Lucarini et al. 2020, MedAfriCarbon (in atlas) https://doi.org/10.5334/joad.60 (abstract and data paper overview)
- Kuper & Kröpelin 2006, 'Climate-controlled Holocene occupation in the Sahara', Science 313 https://doi.org/10.1126/science.1130989 (abstract)
- Kuper & Kröpelin 2006, Science 313 https://doi.org/10.1126/science.1130989 (abstract)
- Firew 2014, Archaeological fieldwork around Lake Tana area of Ethiopia (PhD, Bergen) https://hdl.handle.net/1956/8931 (thesis summary on the University of Bergen defence page)
- Khalidi et al. 2020, Quaternary Science Reviews 243:106459 https://doi.org/10.1016/j.quascirev.2020.106459 (abstract)
- Rose 2010, 'New light on human prehistory in the Arabo-Persian Gulf Oasis', Current Anthropology 51 https://doi.org/10.1086/657397 (abstract)
- Gaffney, Fitch & Smith 2009, Europe's Lost World: the rediscovery of Doggerland https://www.birmingham.ac.uk/news-archive/2009/new-book-brings-a-submerged-world-to-life (university press release)

### y_haplogroup

- Posth et al. 2023, 'Palaeogenomics of Upper Palaeolithic to Neolithic European hunter-gatherers', Nature 615 https://doi.org/10.1038/s41586-023-05726-0 (AADR annotation + abstract)
- Olalde et al. 2019, 'The genomic history of the Iberian Peninsula over the past 8000 years', Science 363 https://doi.org/10.1126/science.aav4040 (AADR annotation + abstract)
- Villalba-Mouco et al. 2019, 'Survival of Late Pleistocene hunter-gatherer ancestry in the Iberian Peninsula', Curr. Biol. 29 https://doi.org/10.1016/j.cub.2019.02.006 (AADR annotation + abstract)
- Brace et al. 2019, 'Ancient genomes indicate population replacement in Early Neolithic Britain', Nat. Ecol. Evol. 3 https://doi.org/10.1038/s41559-019-0871-9 (AADR annotation + abstract)
- Olalde et al. 2018, 'The Beaker phenomenon and the genomic transformation of northwest Europe', Nature 555 https://doi.org/10.1038/nature25738 (AADR annotation + abstract)
- Fu et al. 2016, 'The genetic history of Ice Age Europe', Nature 534 https://doi.org/10.1038/nature17993 (AADR annotation + abstract)
- Fernandes et al. 2020, 'The spread of steppe and Iranian-related ancestry in the islands of the western Mediterranean', Nat. Ecol. Evol. 4 https://doi.org/10.1038/s41559-020-1102-0 (AADR annotation + abstract)
- Lipson et al. 2017, 'Parallel palaeogenomic transects reveal complex genetic history of early European farmers', Nature 551 https://doi.org/10.1038/nature24476 (AADR annotation + abstract)
- Haak et al. 2015, 'Massive migration from the steppe was a source for Indo-European languages in Europe', Nature 522 https://doi.org/10.1038/nature14317 (AADR annotation + abstract)
- Rivollat et al. 2020, 'Ancient genome-wide DNA from France highlights the complexity of interactions between Mesolithic hunter-gatherers and Neolithic farmers', Sci. Adv. 6 https://doi.org/10.1126/sciadv.aaz5344 (AADR annotation + abstract)
- Günther et al. 2018, 'Population genomics of Mesolithic Scandinavia', PLoS Biol. 16 https://doi.org/10.1371/journal.pbio.2003703 (AADR annotation + abstract)
- Saag et al. 2017, 'Extensive farming in Estonia started through a sex-biased migration from the Steppe', Curr. Biol. 27 https://doi.org/10.1016/j.cub.2017.06.022 (AADR annotation + abstract)
- Mittnik et al. 2018, 'The genetic prehistory of the Baltic Sea region', Nat. Commun. 9 https://doi.org/10.1038/s41467-018-02825-9 (AADR annotation + abstract)
- Mathieson et al. 2018, 'The genomic history of southeastern Europe', Nature 555 https://doi.org/10.1038/nature25778 (AADR annotation + abstract)
- Saag et al. 2021, 'Genetic ancestry changes in Stone to Bronze Age transition in the East European plain', Sci. Adv. 7 https://doi.org/10.1126/sciadv.abd6535 (AADR annotation + abstract)
- Mathieson et al. 2015, 'Genome-wide patterns of selection in 230 ancient Eurasians', Nature 528 https://doi.org/10.1038/nature16152 (AADR annotation + abstract)
- Wang et al. 2019, 'Ancient human genome-wide data from a 3000-year interval in the Caucasus corresponds with eco-geographic regions', Nat. Commun. 10 https://doi.org/10.1038/s41467-018-08220-8 (AADR annotation + abstract)
- Nikitin et al. 2025, 'A genomic history of the North Pontic Region from the Neolithic to the Bronze Age', Nature 639 https://doi.org/10.1038/s41586-024-08372-2 (AADR annotation + abstract)
- Lazaridis et al. 2022, 'The genetic history of the Southern Arc: a bridge between West Asia and Europe', Science 377 https://doi.org/10.1126/science.abm4247 (AADR annotation + abstract)
- Feldman et al. 2019, 'Late Pleistocene human genome suggests a local origin for the first farmers of central Anatolia', Nat. Commun. 10 https://doi.org/10.1038/s41467-019-09209-7 (AADR annotation + abstract)
- Kılınç et al. 2016, 'The demographic development of the first farmers in Anatolia', Curr. Biol. 26 https://doi.org/10.1016/j.cub.2016.07.057 (AADR annotation + abstract)
- Jones et al. 2015, 'Upper Palaeolithic genomes reveal deep roots of modern Eurasians', Nat. Commun. 6 https://doi.org/10.1038/ncomms9912 (AADR annotation + abstract)
- Lazaridis et al. 2016, 'Genomic insights into the origin of farming in the ancient Near East', Nature 536 https://doi.org/10.1038/nature19310 (AADR annotation + abstract)
- Wang et al. 2023, 'Isotopic and DNA analyses reveal multiscale PPNB mobility and migration across Southeastern Anatolia and the Southern Levant', PNAS 120 (Nevalı Çori and Ba'ja genomes) https://doi.org/10.1073/pnas.2210611120 (AADR annotation + abstract)
- Harney et al. 2018, 'Ancient DNA from Chalcolithic Israel reveals the role of population mixture in cultural transformation', Nat. Commun. 9 https://doi.org/10.1038/s41467-018-05649-9 (AADR annotation + abstract)
- Broushaki et al. 2016, 'Early Neolithic genomes from the eastern Fertile Crescent', Science 353 https://doi.org/10.1126/science.aaf7943 (AADR annotation + abstract)
- Narasimhan et al. 2019, 'The formation of human populations in South and Central Asia', Science 365 https://doi.org/10.1126/science.aat7487 (AADR annotation + abstract)
- de Barros Damgaard et al. 2018, 'The first horse herders and the impact of early Bronze Age steppe expansions into Asia', Science 360 https://doi.org/10.1126/science.aar7711 (AADR annotation + abstract)
- Shinde et al. 2019, 'An ancient Harappan genome lacks ancestry from steppe pastoralists or Iranian farmers', Cell 179 https://doi.org/10.1016/j.cell.2019.08.048 (AADR annotation + abstract)
- Martiniano et al. 2024, 'Ancient genomes illuminate Eastern Arabian population history and adaptation against malaria', Cell Genomics 4 (Tylos-period Bahrain) https://doi.org/10.1016/j.xgen.2024.100507 (AADR annotation + abstract)
- Salem et al. 2025, 'Ancient DNA from the Green Sahara reveals ancestral North African lineage', Nature 641 https://doi.org/10.1038/s41586-025-08793-7 (AADR annotation + abstract)
- Morez Jacobs et al. 2025, 'Whole-genome ancestry of an Old Kingdom Egyptian', Nature (Nuwayrat) https://doi.org/10.1038/s41586-025-09195-5 (AADR annotation + abstract)
- van de Loosdrecht et al. 2018, 'Pleistocene North African genomes link Near Eastern and sub-Saharan African human populations', Science 360 https://doi.org/10.1126/science.aar8380 (AADR annotation + abstract)
- Lipson et al. 2025, 'High continuity of forager ancestry in the Neolithic period of the eastern Maghreb', Nature (Djebba) https://doi.org/10.1038/s41586-025-08699-4 (AADR annotation + abstract)
- Fregel et al. 2018, 'Ancient genomes from North Africa evidence prehistoric migrations to the Maghreb from both the Levant and Europe', PNAS 115 https://doi.org/10.1073/pnas.1800851115 (AADR annotation + abstract)
- Simões et al. 2023, 'Northwest African Neolithic initiated by migrants from Iberia and Levant', Nature 618 https://doi.org/10.1038/s41586-023-06166-6 (AADR annotation + abstract)
- D'Atanasio et al. 2018, 'The peopling of the last Green Sahara revealed by high-coverage resequencing of trans-Saharan patrilineages', Genome Biol. 19 https://doi.org/10.1186/s13059-018-1393-5 (full text)
- Lipson et al. 2020, 'Ancient West African foragers in the context of African population history', Nature 577 (Shum Laka) https://doi.org/10.1038/s41586-020-1929-1 (AADR annotation + abstract)
- Gallego Llorente et al. 2015, 'Ancient Ethiopian genome reveals extensive Eurasian admixture throughout the African continent', Science 350 (Mota) https://doi.org/10.1126/science.aad2879 (AADR annotation + abstract)
