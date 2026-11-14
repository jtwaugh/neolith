# Attributions

Every upstream dataset, image and font that enters this repository or the
published app, with its licence and the citation its authors ask for.
Generated from `data/ATTRIBUTIONS.toml` by `python -m pipeline attributions`;
edit that file, not this one.

- **Code** is MIT (`LICENSE`). **Derived data** (`data/`, `neolith-rs/assets/world.bin`,
  the evidence layers) is CC BY-SA 4.0 (`LICENSE-DATA`), because some inputs are share-alike.
- *facts*: numbers read from a paper (a sea-level curve, a date, a coordinate). Facts carry
  no licence, but we cite them.
- *unknown*: the licence has not yet been confirmed on the upstream page.
- Each dataset's own write-up is in `data/<dataset>/SOURCES.md`; the original sources of
  individual radiocarbon dates are kept per date in `data/settlements/dates.csv.gz`.

## Shipped in the app

### ETOPO1 1 arc-minute global relief model (via NOAA CoastWatch ERDDAP)

- Licence: public-domain-us-gov
- Source: <https://doi.org/10.7289/V5C8276M>
- Cite: Amante, C. & Eakins, B.W. 2009. ETOPO1 1 Arc-Minute Global Relief Model. NOAA Technical Memorandum NESDIS NGDC-24. doi:10.7289/V5C8276M
- Used in: Elevation, landform, coasts and lakes (Makefile -> build/etopo*.asc)

### Beyer, Krapp & Manica 2020, Late Quaternary climate and biomes (LateQuaternary_Environment.nc)

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://doi.org/10.6084/m9.figshare.12293345>
- Cite: Beyer, R.M., Krapp, M. & Manica, A. 2020. High-resolution terrestrial climate, bioclimate and vegetation for the last 120,000 years. Scientific Data 7:236. doi:10.1038/s41597-020-0552-1
- Used in: Biomes, Köppen classes, productivity (pipeline/config.toml [model])

### QEN Global Palaeovegetation Atlas maps (Adams & Faure), Europe and Africa

- Licence: LicenseRef-not-copyrighted
- Source: <http://web.archive.org/web/20151220225453/http://www.esd.ornl.gov/projects/qen/nerc.html>
- Cite: Adams, J.M. 1997. Global land environments since the last interglacial. Oak Ridge National Laboratory, TN, USA. http://www.esd.ornl.gov/projects/qen/nerc.html; Adams, J.M. & Faure, H. (eds.) 1997. Review and Atlas of Palaeovegetation: Preliminary land ecosystem maps of the world since the Last Glacial Maximum. Quaternary Environments Network, ORNL.
- Used in: raw/maps/europe, raw/maps/africa; traced into raw/maps/composite, the drawn terrain keyframes (pipeline/config.toml [terrain.drawn])
- Note: The QEN pages state: "The maps and text are not copyrighted, but please cite this Web site." That covers Adams' own maps; the regional pages also carry figures after van Andel & Tzedakis (1996), which are not covered and must not be traced. QEN has no separate 10k or 7k 14C BP slices, so file labels in raw/maps/ name the nearest slice (see data/terrain/SOURCES.md).

### Neotoma Paleoecology Database (including the European Pollen Database)

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://www.neotomadb.org>
- Cite: Williams, J.W. et al. 2018. The Neotoma Paleoecology Database. Quaternary Research 89:156-177. Plus the dataset PIs listed per record.
- Used in: Biome anchors; isostyle cereal pollen and dung spore layers

### UNEP-WCMC mountain classes (Kapos et al. 2000), method only

- Licence: facts
- Source: <https://www.unep-wcmc.org>
- Cite: Kapos, V., Rhind, J., Edwards, M., Price, M.F. & Ravilious, C. 2000. Developing a map of the world's mountain forests. In Price & Butt (eds.), Forests in Sustainable Mountain Development. CABI.
- Used in: Landform bands applied to ETOPO1

### Lambeck et al. 2014 global sea-level curve (values read from the paper)

- Licence: facts
- Source: <https://doi.org/10.1073/pnas.1411762111>
- Cite: Lambeck, K., Rouby, H., Purcell, A., Sun, Y. & Sambridge, M. 2014. Sea level and global ice volumes from the Last Glacial Maximum to the Holocene. PNAS 111:15296-15303.
- Used in: Coastlines over time (pipeline/config.toml [sea])

### GEOGLOWS Hydrological Model v2 stream network

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://data.geoglows.org>
- Cite: GEOGloWS ECMWF Streamflow Service, Hydrological Model Version 2.0 (GEOGloWS v2), stream network and attribute table, https://geoglows-v2.s3.amazonaws.com (licenses.md). Changes: reaches of 1,000 km² or more upstream inside the map box, lines reversed to run downstream, joined to the attribute table on LINKNO, and an endorheic flag derived by the project.
- Used in: River courses (pipeline/geoglows.py, pipeline/rivers.py; Makefile -> build/geoglows); unnamed reaches in isostyle river rules
- Note: Replaced HydroRIVERS on 2026-11-13. The streams are a hydrologically conditioned subset of TDX-Hydro (next entry).

### TDX-Hydro global stream and basin network (NGA)

- Licence: [CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- Source: <https://earth-info.nga.mil>
- Cite: TDX-Hydro, US National Geospatial-Intelligence Agency (NGA) with USACE ERDC and NASA, 2023; derived from the TanDEM-X DEM. Used through GEOGLOWS v2.
- Used in: Underlies the GEOGLOWS v2 stream lines (river courses)
- Note: Licence as listed in GEOGLOWS v2 licenses.md. Share-alike, which our CC BY-SA data licence satisfies.

### XRONOS chronological database

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://xronos.ch>
- Cite: Roe, J., Hinz, M., Hafner, A. et al. 2025. XRONOS: an open data infrastructure for archaeological chronology. Journal of Computer Applications in Archaeology 8(1). doi:10.5334/jcaa.191. Original sources of each date are kept in data/settlements/dates.csv.gz.
- Used in: Settlements, dates, survey intensity, every isostyle layer built on dated site-phases

### p3k14c radiocarbon database, release 2025.07

- Licence: [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/)
- Source: <https://github.com/people3k/p3k14c>
- Cite: Bird, D., Miranda, L., Vander Linden, M. et al. 2022. p3k14c, a synthetic global database of archaeological radiocarbon dates. Scientific Data 9:27. doi:10.1038/s41597-022-01118-7
- Used in: Settlements and dates
- Note: Package README: data CC0 1.0, attribution requested; code MIT; text CC BY 4.0. Data doi:10.48512/XCV8459173.

### NeoNet Mediterranean radiocarbon dataset, version 2

- Licence: [CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- Source: <https://doi.org/10.13131/archelogicadata-yb11-yb66>
- Cite: Mazzucco, N. et al. 2021. NeoNet radiocarbon database version 1. Pisa: MOD. doi:10.13131/archelogicadata-yb11-yb66. Data paper: Huet, T. et al. 2022. Journal of Open Archaeology Data 10:3, doi:10.5334/joad.87.
- Used in: Settlements and dates
- Note: Repository says CC BY-SA; data paper says CC BY. Treated as share-alike; our data licence (CC BY-SA 4.0) is compatible.

### NeoNet Atlantic radiocarbon dataset, version 1

- Licence: [CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- Source: <https://doi.org/10.13131/unipi/z332-ye56>
- Cite: Huet, T. et al. 2023. NeoNetAtl radiocarbon database. Pisa: MOD. doi:10.13131/unipi/z332-ye56
- Used in: Settlements and dates
- Note: Data host says CC BY-SA (images CC BY-NC-SA; we use no images); data paper (joad.120) says CC BY 4.0. Either is compatible with CC BY-SA.

### Allen Ancient DNA Resource (AADR) v66.p1, 1240K annotation and genotypes

- Licence: [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/)
- Source: <https://doi.org/10.7910/DVN/FFIDCW>
- Cite: Mallick, S., Micco, A., Mah, M. et al. 2024. The Allen Ancient DNA Resource (AADR): a curated compendium of ancient human genomes. Scientific Data 11:182. Plus the original genetics papers per sample.
- Used in: Settlements and dates; isostyle aDNA, haplogroup and ancestry layers
- Note: The 1240K genotypes (.geno/.snp/.ind) are read by `python -m isostyle ancestry` and never committed; the per-individual ancestry table derived from them is data/ancestry/ancestry.csv.gz (method and reference groups in data/ancestry/SOURCES.md).

### Radiocarbon dates transcribed from published papers (mostly Russian-language)

- Licence: facts
- Source: <https://github.com/jtwaugh/neolith/blob/main/data/settlements/SOURCES.md>
- Cite: Per row; the papers are listed in pipeline/config.toml [[settlements.tables]] literature and data/settlements/SOURCES.md.
- Used in: Settlements and dates

### English Wikipedia articles on cultures and famous sites (paraphrased; no text copied)

- Licence: [CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- Source: <https://en.wikipedia.org>
- Cite: Wikipedia contributors. Revisions are recorded in data/cultures/wikipedia.json and data/renown/SOURCES.md.
- Used in: data/cultures/cultures.toml; renown one-line summaries (neolith-rs/crates/app/assets/renown.json)

### Salem et al. 2025, Takarkori genomes (sample metadata)

- Licence: facts
- Source: <https://doi.org/10.1038/s41586-025-08793-7>
- Cite: Salem, N. et al. 2025. Ancient DNA from the Green Sahara reveals ancestral North African lineage. Nature 641. https://doi.org/10.1038/s41586-025-08793-7. Reads: ENA PRJEB84057.
- Used in: isostyle aDNA and mt haplogroup layers; data/isostyle/inputs/supplementary_genomes.toml
- Note: Two individuals typed from the paper's text (dates, mt calls, SNP counts); no reads or genotypes are downloaded. Position from Wikipedia ('Takarkori').

### Evershed et al. 2022, lipid residue site-phases

- Licence: [MIT](https://opensource.org/license/mit)
- Source: <https://github.com/AdrianTimpson/2020-03-03523A>
- Cite: Evershed, R.P., Davey Smith, G., Roffet-Salque, M. et al. 2022. Dairying, diseases and the evolution of lactase persistence in Europe. Nature 608:336-345. doi:10.1038/s41586-022-05010-7. Data (c) 2021 Adrian Timpson, MIT License.
- Used in: isostyle pottery

### Rigaud, Manen & García-Martínez de Lagrán 2018, S1 Dataset

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://doi.org/10.1371/journal.pone.0196488>
- Cite: Rigaud, S., Manen, C. & García-Martínez de Lagrán, I. 2018. Symbols in motion: flexible cultural boundaries and the fast spread of the Neolithic in the western Mediterranean. PLoS ONE 13:e0196488.
- Used in: isostyle ornaments

### Dolbunova et al. 2023, vessel table with site coordinates

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://doi.org/10.5281/zenodo.6619101>
- Cite: Dolbunova, E., Lucquin, A., McLaughlin, T.R. et al. 2023. The transmission of pottery technology among prehistoric European hunter-gatherers. Nature Human Behaviour 7:171-183.
- Used in: isostyle pottery; data/isostyle/inputs/dolbunova2023_starts.csv

### Windler 2019, Spondylus database

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://doi.org/10.5281/zenodo.2840333>
- Cite: Windler, A. 2019. Spondylus database (Zenodo 2840333).
- Used in: isostyle ornaments

### Tsirintoulaki, Matzig & Riede 2023, dated barbed points

- Licence: [MIT](https://opensource.org/license/mit)
- Source: <https://doi.org/10.5281/zenodo.7244045>
- Cite: Tsirintoulaki, K., Matzig, D.N. & Riede, F. 2022. Research compendium (Zenodo 7244045), (c) 2022 David N. Matzig, MIT License. Paper: Open Archaeology, doi:10.1515/opar-2022-0276.
- Used in: isostyle bone/antler

### Perrin, BDA (Base de données archéologiques) 2021 export

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://doi.org/10.34847/nkl.dde9fnm8>
- Cite: Perrin, T. 2021. BDA export (Nakala, doi:10.34847/nkl.dde9fnm8).
- Used in: isostyle flaked stone, pottery

### SoilGrids 2.0 pH(H2O), 5 km aggregate

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://www.isric.org/explore/soilgrids>
- Cite: Poggio, L., de Sousa, L.M., Batjes, N.H. et al. 2021. SoilGrids 2.0: producing soil information for the globe with quantified spatial uncertainty. SOIL 7:217-240.
- Used in: isostyle bone mask; residual detection model (acid soil)

### MedAfriCarbon v1.0.3

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://doi.org/10.5281/zenodo.3689716>
- Cite: Lucarini, G., Wilkinson, T., Crema, E.R. et al. 2020. The MedAfriCarbon radiocarbon database and web application. Journal of Open Archaeology Data 8:1.
- Used in: isostyle pottery, livestock

### Rotunno & Crema 2025, Saharan pottery dates

- Licence: [MIT](https://opensource.org/license/mit)
- Source: <https://github.com/roccorot/OriginPotteryNAfrica>
- Cite: Rotunno, R. & Crema, E.R. 2025. Bayesian analyses of radiocarbon dates suggest multiple origins of ceramic technology in Early Holocene Africa. Nature Communications 16:8819. doi:10.1038/s41467-025-63887-0. Code and data (c) 2024 roccorot, MIT License.
- Used in: isostyle pottery

### DEFC, Digitizing Early Farming Cultures (sites, areas, finds)

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://arche.acdh.oeaw.ac.at/api/220828>
- Cite: Aspöck, E., Štuhec, S., Kopetzky, K. & Kucera, M. Digitizing Early Farming Cultures (DEFC). Austrian Academy of Sciences, ARCHE.
- Used in: isostyle structures, finds

### DObsiSS v2.0 (Batist), obsidian sourcing in SW Asia

- Licence: [CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- Source: <https://doi.org/10.5281/zenodo.55848>
- Cite: Batist, Z. DObsiSS: Database of Obsidian Sourcing Studies, v2.0 (Zenodo 55848).
- Used in: isostyle flaked stone

### Arranz-Otaegui & Roe 2023, SW Asian Neolithic flora

- Licence: [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/)
- Source: <https://github.com/joeroe/SWAsiaNeolithicFounderCrops>
- Cite: Arranz-Otaegui, A. & Roe, J. 2023. Revisiting the concept of the 'Neolithic founder crops' in southwest Asia. Vegetation History and Archaeobotany 32:475-499.
- Used in: isostyle cereals

### ADEMNES archaeobotanical/faunal database (Riehl), via Arranz-Otaegui & Roe 2023

- Licence: LicenseRef-ADEMNES-research-use
- Source: <https://www.ademnes.de/database.php>
- Cite: ADEMNES: The GRF-funded Archaeobotanical Database of Eastern Mediterranean and Near Eastern Sites, last update 2015. www.ademnes.de. Riehl, S. & Kümmel, C. 2005. Redistributed in Arranz-Otaegui & Roe 2023.
- Used in: isostyle domestic livestock, phases, sites
- Note: No open licence: distributed "for research and educational purposes", please cite. Roe and Arranz-Otaegui's CC0 covers only their own rights. We ship only aggregated, smoothed surfaces and commit no ADEMNES rows.

### Open Context integrated Anatolian zooarchaeology (EOL), summary

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://github.com/ekansa/opencontext-eol-zooarch>
- Cite: Arbuckle, B.S., Kansa, S.W., Kansa, E. et al. 2014. Data sharing reveals complexity in the westward spread of domestic animals across Neolithic Turkey. PLoS ONE 9:e99845. Data via Open Context.
- Used in: isostyle domestic livestock

### Phelps et al. 2019, African Holocene fauna (PANGAEA 904942)

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://doi.org/10.1594/PANGAEA.904942>
- Cite: Phelps, L.N., Broennimann, O., Manning, K. et al. 2019. Reconstructing the Holocene spread of livestock in Africa (dataset). PANGAEA. doi:10.1594/PANGAEA.904942
- Used in: isostyle domestic livestock

### Neolithic rondel enclosures in Central Europe v1.1.0

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://doi.org/10.5281/zenodo.23738404>
- Cite: Vondrovský, V., Bartík, J., Furholt, K. et al. 2026. Neolithic (4850-4500 BCE) rondel enclosures in Central Europe: a curated geospatial and structural dataset, v1.1.0. Zenodo. doi:10.5281/zenodo.23738404
- Used in: isostyle enclosures

### LandClimII REVEALS land-cover reconstructions

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://doi.org/10.1594/PANGAEA.937075>
- Cite: Fyfe, R. et al. 2021. LandClimII REVEALS land-cover reconstructions (PANGAEA 937075). Github, M. et al. 2022, Climate of the Past 18:1059.
- Used in: isostyle open land

### EUROEVOL dataset (sites, dates, archaeobotany, fauna)

- Licence: [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/)
- Source: <https://discovery.ucl.ac.uk/id/eprint/1469811/>
- Cite: Manning, K., Colledge, S., Crema, E. et al. 2016. The Cultural Evolution of Neolithic Europe. EUROEVOL Dataset 1-2. Journal of Open Archaeology Data 5:e2, e3; Colledge, S. 2016. EUROEVOL Dataset 3: Archaeobotanical. JOAD 5:e4.
- Used in: isostyle cereals, domestic livestock
- Note: The UCL deposit is CC0 (waiver by Katie Manning) and covers the botany files; the data papers are CC BY 4.0.

### Tallavaara et al. 2018, forager population model (data and R scripts)

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://doi.org/10.5281/zenodo.1167852>
- Cite: Tallavaara, M., Eronen, J.T. & Luoto, M. 2018. Productivity, biodiversity, and pathogens influence the global hunter-gatherer population density. PNAS 115:1232-1237.
- Used in: Forager density equation, productivity constants, coast mask (neolith-rs/crates/core/src/forager.rs)

### Pinhasi, Fort & Ammerman 2005, farming-front parameters

- Licence: facts
- Source: <https://doi.org/10.1371/journal.pbio.0030410>
- Cite: Pinhasi, R., Fort, J. & Ammerman, A.J. 2005. Tracing the origin and spread of agriculture in Europe. PLoS Biology 3:e410.
- Used in: Farming arrival front (neolith-rs/crates/core/src/farming.rs)

### EB Garamond typeface (Octavio Pardo / Georg Duffner)

- Licence: [OFL-1.1](https://openfontlicense.org)
- Source: <https://github.com/octaviopardo/EBGaramond12>
- Cite: EB Garamond, Copyright 2017 The EB Garamond Project Authors. SIL Open Font License 1.1 (neolith-rs/crates/app/assets/fonts/OFL.txt).
- Used in: Map labels (neolith-rs/crates/app/assets/fonts)

### egui default fonts (Ubuntu Light, Hack, Noto Emoji, emoji-icon-font)

- Licence: UFL-1.0 AND OFL-1.1 AND (MIT OR Apache-2.0)
- Source: <https://github.com/emilk/egui/tree/master/crates/epaint_default_fonts>
- Cite: Ubuntu font (Ubuntu Font Licence 1.0), Hack (MIT/Bitstream Vera), Noto Emoji (OFL 1.1), emoji-icon-font (MIT/OFL), bundled by the epaint_default_fonts crate.
- Used in: UI text in the app (via eframe)

### Grug, caveman Wojak meme (splash-page mascot)

- Licence: LicenseRef-no-licence
- Source: <https://knowyourmeme.com/memes/grug>
- Cite: Grug, anonymous internet meme (4chan, 2017). Image via Know Your Meme: https://i.kym-cdn.com/entries/icons/original/000/025/413/oogaboogaaa.jpg
- Used in: Start screen mascot (neolith-rs/crates/app/assets/grug.jpg, cropped; grug.rgba is it resized for the app)
- Note: Anonymous author, no licence found. Anonymous works are still under copyright, so this image is not covered by the project's MIT or CC BY-SA licences and cannot be relicensed with the data. Shipped at the maintainer's request (2026-11-13) as a meme mascot; replace it if a rights holder objects.

### IM FELL English roman, by Igino Marini (subset shipped as "Neolith Fell")

- Licence: [OFL-1.1](https://openfontlicense.org)
- Source: <https://github.com/google/fonts/tree/main/ofl/imfellenglish>
- Cite: IM FELL English, Copyright (c) 2010 Igino Marini (iginomarini.com). SIL Open Font License 1.1 (neolith-rs/crates/app/assets/fonts/OFL-IMFell.txt).
- Used in: Start screen title, headings and questions (neolith-rs/crates/app/assets/fonts/NeolithFell.subset.ttf)
- Note: Subset to Latin with fontTools. Because "IM FELL" is a Reserved Font Name and a subset is a modified version, the subset's family is renamed "Neolith Fell".

### Alegreya, regular and italic (Huerta Tipográfica)

- Licence: [OFL-1.1](https://openfontlicense.org)
- Source: <https://github.com/huertatipografica/Alegreya>
- Cite: Alegreya, Copyright 2011 The Alegreya Project Authors. SIL Open Font License 1.1 (neolith-rs/crates/app/assets/fonts/OFL-Alegreya.txt).
- Used in: Start screen body text (neolith-rs/crates/app/assets/fonts/Alegreya*.subset.ttf)
- Note: From the Google Fonts repository: the variable font pinned to weight 400 and subset to Latin with fontTools.

## Committed to the repository but not shipped

### BIOME 6000 DB classified plotfile, version 1

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://doi.org/10.17864/1947.99>
- Cite: Harrison, S.P. 2017. BIOME 6000 DB classified plotfile version 1. University of Reading. doi:10.17864/1947.99
- Used in: Biome anchors (data/terrain/anchors.csv)

### EMBSeCBIO pollen database

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://doi.org/10.17864/1947.309>
- Cite: Harrison, S.P., Marinova, E. & Cruz-Silva, E. 2021. EMBSeCBIO pollen database. University of Reading. doi:10.17864/1947.309
- Used in: Biome anchors

### Cruz-Silva et al. 2022, intra-biome variation method (code and data, pinned commit)

- Licence: LicenseRef-no-licence
- Source: <https://github.com/esmeraldacs/Intra_biome_variation_method>
- Cite: Cruz-Silva, E., Harrison, S.P., Marinova, E. & Prentice, I.C. 2022. A new method based on surface-sample pollen data for reconstructing palaeovegetation patterns. Journal of Biogeography 49:1381-1396.
- Used in: Biome anchors
- Note: The repository has no LICENSE file (all rights reserved by default). The paper (doi:10.1111/jbi.14448) and its input datasets (SMPDS, EMBSeCBIO) are CC BY 4.0. We use the published method and the Reading datasets; the anchors are not shipped in the app.

## Used to build or fit, not redistributed

### HydroRIVERS v1.0 (HydroSHEDS) — REMOVED 2026-11-13

- Licence: LicenseRef-HydroSHEDS-v1
- Source: <https://www.hydrosheds.org/products/hydrorivers>
- Cite: Lehner, B. & Grill, G. 2013. Global river hydrography and network routing: baseline data and new approaches to study the world's large river systems. Hydrological Processes 27:2171-2186.
- Used in: Nothing since 2026-11-13. Was the reach network the river courses were traced along.
- Note: Replaced by GEOGLOWS v2 / TDX-Hydro: the WWF HydroSHEDS v1 licence requires an end-user agreement at least as protective as its own, which can't be passed on under CC BY-SA.

### IntCal20 radiocarbon calibration curve

- Licence: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- Source: <https://intcal.org>
- Cite: Reimer, P.J. et al. 2020. The IntCal20 Northern Hemisphere radiocarbon age calibration curve (0-55 cal kBP). Radiocarbon 62:725-757. doi:10.1017/RDC.2020.41
- Used in: Calibration of every radiocarbon date
- Note: intcal.org states no terms; the curve is published open access in Radiocarbon under CC BY 4.0.

### Wikidata (archaeological site items)

- Licence: [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/)
- Source: <https://www.wikidata.org>
- Cite: Wikidata contributors. Wikidata. https://www.wikidata.org
- Used in: Optional settlements table (disabled unless a contact is set); Q-id links in the site panel

### Jordan et al. 2016, Africa supplement (transcribed site table) — REMOVED 2026-11-13

- Licence: LicenseRef-all-rights-reserved
- Source: <https://doi.org/10.15184/aqy.2016.68>
- Cite: Jordan, P., Gibbs, K., Hommel, P. et al. 2016. Modelling the diffusion of pottery technologies across Afro-Eurasia: emerging insights and future research. Antiquity 90:590-603.
- Used in: Nothing since 2026-11-13. Was hand-transcribed to data/isostyle/inputs/jordan2016_africa.csv for the isostyle pottery layer.
- Note: The supplement is (c) Antiquity Publications Ltd, all rights reserved, so the transcribed table was dropped. Its Saharan, Nile and Maghreb sites come from Rotunno & Crema 2025 and MedAfriCarbon instead; the sites lost are listed in data/isostyle/inputs/README.md.

### Paulsson 2019, megalith radiocarbon dates (PNAS SI) — REMOVED 2026-11-13

- Licence: [CC-BY-NC-ND-4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/)
- Source: <https://doi.org/10.1073/pnas.1813268116>
- Cite: Paulsson, B.S. 2019. Radiocarbon dates and Bayesian modeling support maritime diffusion model for megaliths in Europe. PNAS 116:3460-3465.
- Used in: Nothing since 2026-11-13. Was joined by lab number into isostyle megalithic_tombs.
- Note: Dropped because NC-ND is incompatible with publishing derived data under CC BY-SA. Kept here as a record.

### Binford hunter-gatherer data via D-PLACE

- Licence: [CC-BY-NC-4.0](https://creativecommons.org/licenses/by-nc/4.0/)
- Source: <https://github.com/D-PLACE/dplace-dataset-binford>
- Cite: Binford, L.R. 2001. Constructing Frames of Reference. University of California Press. Kirby, K.R. et al. 2016. D-PLACE: a global database of cultural, linguistic and environmental diversity. PLoS ONE 11:e0158391.
- Used in: Fitting the coastal term of the forager model (one coefficient, -0.71); see data/population/SOURCES.md
- Note: No rows are committed or shipped; only a fitted coefficient, a fact about the data, enters the model.

### ADMIXTOOLS 2 (qpAdm), build tool for the ancestry table

- Licence: GPL-3.0
- Source: <https://github.com/uqrmaie1/admixtools>
- Cite: Maier, R., Flegontov, P., Flegontova, O. et al. 2023. On the limits of fitting complex models of population history to f-statistics. eLife 12:e85492. doi:10.7554/eLife.85492
- Used in: isostyle/ancestry/run.R: per-individual qpAdm for data/ancestry/ancestry.csv.gz. Run as a tool; no code or data from it is shipped.
