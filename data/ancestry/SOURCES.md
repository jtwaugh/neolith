# Ancestry table: method and sources

`ancestry.csv.gz` gives, for each ancient individual in the map's window, how much of their
autosomal ancestry is modelled as coming from each of six reference groups. It is computed from
the genotypes of the Allen Ancient DNA Resource (AADR) v66.p1, which is CC0. The table itself is
CC BY-SA 4.0 like the rest of `data/`.

The proportions are **model estimates from recorded genotypes**. They describe shared ancestry,
not peoples, languages or cultures. Land without genomes gets no value anywhere downstream: the
six `anc_*` isostyle layers are `fill = false`, so the speculative step never fills them.

## The table

One row per individual (`python -m isostyle ancestry`, code in `isostyle/ancestry.py` and
`isostyle/ancestry/run.R`):

| column | meaning |
|---|---|
| `individual`, `group`, `locality`, `lat`, `lon` | AADR individual id, group label, site and coordinates |
| `bp`, `sd` | AADR date mean and standard deviation, years before 1950 |
| `snps` | autosomal SNPs covered on the 1240K set |
| `publication` | AADR's abbreviation for the paper that first reported the individual |
| `status` | `fit`, `no_fit`, `low_coverage` or `reference` (below) |
| `model` | the sources of the accepted model, e.g. `whg+ana`; for `reference` rows, the source the individual belongs to |
| `p` | the accepted model's qpAdm p-value |
| `w_whg … w_naf` | the weight of each source: 0 where the source is not in the model; blank unless `fit` or `reference` |
| `se_whg … se_naf` | block-jackknife standard error of each weight in the model |

Statuses:

- `fit`: a model was accepted. The weights sum to 1.
- `no_fit`: no model of up to four sources was accepted.
- `low_coverage`: fewer than 30,000 SNPs; not modelled.
- `reference`: the individual is one of those a source group is made of. It is 100% its own
  source by construction, so it is shown but flagged, and it does not enter the map surfaces.

## Method

1. **Individuals.** Every AADR individual that passes AADR's assessment, has coordinates and a
   date, lies in the map's box and has at least 0.01% of its date distribution inside the
   10,500–2,500 BCE span (the same filters as the haplogroup layers, `isostyle/people.py`). For
   an individual with several genotype versions the best covered one is used.
2. **Genotypes.** AADR v66.p1 1240K, autosomes only. Pseudo-haploid and diploid samples are
   handled by ADMIXTOOLS 2 (`adjust_pseudohaploid = TRUE`).
3. **f-statistics.** Per individual, f2 blocks over the SNPs covered in that individual and in
   every reference population (`f2_from_geno`, `maxmiss = 0`, 5 cM blocks). About 430,000 SNPs
   are covered in all reference populations, so that is the ceiling.
4. **Rotating qpAdm.** Models of one, two, three and four of the six sources are tried, smallest
   first. For a given model the sources left out join the outgroups. A model is accepted when
   its p-value is at least 0.01 and every weight lies in [0, 1] within 2 standard errors. Among
   accepted models of the smallest size the one with the highest p wins. Accepted weights are
   clipped to [0, 1] and renormalised.

**Known limits.**

- The smallest model that fits wins, so a minor component of a few percent is often absorbed:
  an LBK farmer with about 5% hunter-gatherer ancestry is usually reported as 100% Anatolian
  farmer. Read small differences with the standard errors.
- A p-value threshold accepts more easily when there is less data: low-coverage individuals fit
  simple models that better data might reject.
- `irn` pools Neolithic Iran (Ganj Dareh) with the Caucasus hunter-gatherers (Kotias, Satsurblia).
  The table cannot tell the two apart.
- Six distal sources cannot describe ancestry from outside them (for example sub-Saharan
  African or East Asian ancestry); such individuals mostly end as `no_fit`.
- Dates are AADR's; many are archaeological context dates with wide errors.

## Reference groups

Labels are AADR v66.p1 Group IDs, set in `isostyle/config.toml` `[ancestry]` and checked against
the annotation by `isostyle/tests/test_ancestry.py`.

| key | name | AADR groups (individuals used) | first published in |
|---|---|---|---|
| `whg` | Western hunter-gatherer | `Luxembourg_Loschbour_Mesolithic` (Loschbour), `Switzerland_Epipaleolithic` (Bichon), `Italy_NordEst_Epigravettian` (Villabruna): 3 | Lazaridis et al. 2014; Jones et al. 2015; Fu et al. 2016 |
| `ehg` | Eastern hunter-gatherer | `Russia_Karelia_Mesolithic_HG`, `Russia_Karelia_Mesolithic`, `Russia_Samara_EN_Mesolithic`, `Russia_Sidelkino2_Mesolithic-Dup`: 21 | Mathieson et al. 2015; Posth et al. 2023; Damgaard et al. 2018; Mittnik et al. 2018; Zeng et al. 2025 |
| `ana` | Anatolian farmer | `Turkey_N` (Barcın, Menteşe and the other Neolithic Anatolian sites under that label): 47 | Mathieson et al. 2015; Yaka et al. 2021; Kılınç et al. 2016; Omrak et al. 2016; Hofmanová et al. 2016; Lazaridis et al. 2022; Marchi et al. 2022 |
| `irn` | Iranian farmer / Caucasus hunter-gatherer | `Iran_GanjDareh_N`, `Georgia_KotiasKlde_Mesolithic`, `Georgia_Satsurblia_LateUP`: 12 | Lazaridis et al. 2016; Narasimhan et al. 2019; Jones et al. 2015; Allentoft et al. 2024 |
| `lev` | Levantine forager | `Israel_Natufian`: 6 | Lazaridis et al. 2016 |
| `naf` | North African forager | `Morocco_Iberomaurusian` (Taforalt): 5 | van de Loosdrecht et al. 2018 |

**Outgroups ("right"), Mbuti first as the base:** `Mbuti` (11), `Russia_UstIshim_IUP` (Ust'-Ishim),
`Russia_Kostenki_UP` (Kostenki14.SG), `Russia_Malta_UP` (MA1.SG), `Han` (43), `Papuan` (17),
`India_100BP` (Andaman.SG, standing in for Onge) and `Ethiopia_MotaCave_4500BP` (mota.SG, which
separates `naf` from `lev`). MA1 is marked "Questionable" in AADR for contamination; it is used
as an outgroup only, as is usual.

## Toolchain

- R 4.6.2 (Homebrew), ADMIXTOOLS 2 version 2.0.10 (`uqrmaie1/admixtools`, GitHub HEAD on
  2026-11-13), jsonlite 2.0.0. Install notes: `isostyle/ancestry/README.md`.
- ADMIXTOOLS 2 is GPL-3 and is run as a tool. Nothing from it is shipped or committed.

## Validation

Known results the table must reproduce (`[[ancestry.validate]]` in `isostyle/config.toml`;
`python -m isostyle evals` and `isostyle/tests/test_ancestry.py` fail if one moves out of
tolerance):

| check | individual | expected | got |
|---|---|---|---|
| Cheddar Man is a western hunter-gatherer | I3016 | whg 1.00 | whg 1.00 |
| Ötzi is mostly Anatolian farmer with a little WHG | Iceman | ana 0.90, whg 0.10 | ana 0.90, whg 0.10 |
| An LBK farmer (Derenburg) is mostly Anatolian farmer | DER002 | ana 0.93 | ana 1.00 |
| Globular Amphora shows the hunter-gatherer resurgence | RISE1163 | whg 0.25, ana 0.75 | whg 0.21, ana 0.79 |
| Khvalynsk is EHG with Iran/CHG | I6737 | ehg 0.75, irn 0.25 | ehg 0.74, irn 0.26 |

The plan's sixth check, "Ganj Dareh is all `irn`", holds by construction: the Ganj Dareh
individuals are `reference` rows.

**Phase-0 spike (2026-11-13):** 287 individuals stratified by region and millennium were
modelled; 278 fit (97%), with at least 87% in every region. The gate was 60%.

**Full run (2026-11-13, `python -m isostyle ancestry --remote`):** the committed table has 4,079 rows.
3,707 individuals with at least 30,000 SNPs were modelled and 3,662 fit (99%); 45 have no
accepted model (`no_fit`), 287 are below the SNP floor (`low_coverage`) and 85 are the
reference individuals themselves (`reference`). It took about 1.8 s per individual on 7 cores.

| region | modelled | fit |
|---|---|---|
| Anatolia & Levant | 255 | 100% |
| Atlantic Europe | 292 | 100% |
| Balkans & Italy | 485 | 100% |
| Central Europe | 1,162 | 99% |
| Iran & Caucasus | 109 | 94% |
| N Europe | 390 | 100% |
| North Africa & Arabia | 55 | 96% |
| Steppe & E Europe | 622 | 97% |
| W Mediterranean | 337 | 99% |

The commonest accepted models are `whg+ana` (1,403), `ana` alone (541), `ehg+ana+irn` (362),
`whg+ehg+ana` (181) and `whg+ehg` (155). The full breakdown by region, millennium and model is
written to `build/isostyle/ancestry/run.md` on every run.

The isostyle surfaces built from the table (`anc_*` in `data/isostyle/layers.toml`) use a 200 km
kernel, chosen by cross-validation on `anc_ana` and shared by the other five so the six shares
stay comparable.

Positions follow `isostyle/people.py` `load_anno()`, including the corrections in
`data/isostyle/inputs/aadr_positions.toml` (the three Kehf el Baroud genomes sit in Morocco, not
at the AADR's Algerian coordinates, and the Shah Tepe genomes sit on the Gorgan Plain, not near
the Strait of Hormuz). Each correction carries its source in that file.

## Named unknown regions

Where no modelled genome is in reach, the Ancestry map mode hatches the hex as unknown. Inside a
named region (`neolith-rs/crates/app/assets/unknown_ancestry.json`) the legend and the hex
inspector also say why. There is one so far.

**Unknown (Sahelian).** A polygon from the Senegal coast to the Red Sea Hills, 10 to 20.5°N,
with its east edge kept off the Ethiopian highlands. As of November 2026 no ancient genome
from this band has passed quality control for 10,000-2,500 BCE:

- AADR v66.p1 has one Sahelian genome before the Christian-period Nubians: Kadruka 1, Sudan
  (KDR001, c. 2000 BCE), from mummified hair, 534 1240K SNPs, assessment CRITICAL. Teeth,
  petrous bones and crania from Neolithic Kadruka 21 yielded no authentic DNA (Wang et al. 2022).
- Gobero, Niger, has about 200 Holocene burials (Sereno et al. 2008) but no aDNA. The latest
  study uses teeth because preservation "precludes aDNA recovery" (Stojanowski, Irish & Sereno 2026).
- Reviews of West African genetic history (2017, 2020) report no human aDNA from the region.
  Searches for 2025-26 studies of Mali, Senegal, Chad and Niger found none.
- The nearest genomes are Takarkori, Libya (Salem et al. 2025; mt only on this map, see
  `data/isostyle/inputs/supplementary_genomes.toml`), Shum Laka, Cameroon, and Mota, Ethiopia.

The cause is preservation (heat breaks DNA down in bone) and little sampling. It is not an
absence of people, and the inspector says so.

## References

- AADR: Mallick, S. et al. 2024. The Allen Ancient DNA Resource (AADR): a curated compendium of
  ancient human genomes. *Scientific Data* 11:182.
  <https://link.springer.com/article/10.1038/s41597-024-03031-7>. Data: Harvard Dataverse,
  <https://doi.org/10.7910/DVN/FFIDCW> (v66.p1, CC0). Reich lab page:
  <https://reich.hms.harvard.edu/node/256>
- ADMIXTOOLS 2: Maier, R. et al. 2023. On the limits of fitting complex models of population
  history to f-statistics. *eLife* 12:e85492. <https://doi.org/10.7554/eLife.85492>. Code:
  <https://github.com/uqrmaie1/admixtools>;
  [`extract_f2` reference](https://uqrmaie1.github.io/admixtools/reference/extract_f2.html)
- qpAdm: Haak, W. et al. 2015. Massive migration from the steppe was a source for Indo-European
  languages in Europe. *Nature* 522:207. <https://doi.org/10.1038/nature14317>
- qpAdm in practice: Harney, É. et al. 2021. Assessing the performance of qpAdm. *Genetics*
  217:iyaa045. <https://doi.org/10.1093/genetics/iyaa045>
- Lazaridis, I. et al. 2014 (Loschbour). *Nature* 513:409. <https://doi.org/10.1038/nature13673>
- Jones, E. R. et al. 2015 (Bichon, Kotias, Satsurblia). *Nature Communications* 6:8912.
  <https://doi.org/10.1038/ncomms9912>
- Fu, Q. et al. 2016 (Villabruna). *Nature* 534:200. <https://doi.org/10.1038/nature17993>
- Mathieson, I. et al. 2015 (Anatolia Neolithic, Karelia and Samara hunter-gatherers). *Nature*
  528:499. <https://doi.org/10.1038/nature16152>
- Posth, C. et al. 2023 (Karelia). *Nature* 615:117. <https://doi.org/10.1038/s41586-023-05726-0>
- Damgaard, P. de B. et al. 2018 (Sidelkino). *Science* 360:eaar7711.
  <https://doi.org/10.1126/science.aar7711>
- Mittnik, A. et al. 2018. *Nature Communications* 9:442. <https://doi.org/10.1038/s41467-018-02825-9>
- Zeng, T. C. et al. 2025. *Nature*. <https://doi.org/10.1038/s41586-025-09189-3>
- Yaka, R. et al. 2021. *Current Biology* 31:2455. <https://doi.org/10.1016/j.cub.2021.03.050>
- Kılınç, G. M. et al. 2016. *Current Biology* 26:2659. <https://doi.org/10.1016/j.cub.2016.07.057>
- Omrak, A. et al. 2016. *Current Biology* 26:270. <https://doi.org/10.1016/j.cub.2015.12.019>
- Marchi, N. et al. 2022. *Cell* 185:1842. <https://doi.org/10.1016/j.cell.2022.04.008>
- Lazaridis, I. et al. 2022. *Science* 377:eabm4247. <https://doi.org/10.1126/science.abm4247>
- Lazaridis, I. et al. 2016 (Ganj Dareh, Natufians). *Nature* 536:419.
  <https://doi.org/10.1038/nature19310>
- Narasimhan, V. M. et al. 2019. *Science* 365:eaat7487. <https://doi.org/10.1126/science.aat7487>
- Allentoft, M. E. et al. 2024. Population genomics of post-glacial western Eurasia. *Nature*
  625:301. <https://doi.org/10.1038/s41586-023-06865-0>. Only its genotypes as carried in the
  CC0 AADR are used here, not its own ancestry tables.
- van de Loosdrecht, M. et al. 2018 (Taforalt). *Science* 360:548.
  <https://doi.org/10.1126/science.aar8380>
- Fu, Q. et al. 2014 (Ust'-Ishim). *Nature* 514:445. <https://doi.org/10.1038/nature13810>
- Seguin-Orlando, A. et al. 2014 (Kostenki 14). *Science* 346:1113.
  <https://doi.org/10.1126/science.aaa0114>
- Raghavan, M. et al. 2014 (Mal'ta, MA1). *Nature* 505:87. <https://doi.org/10.1038/nature12736>
- Gallego Llorente, M. et al. 2015 (Mota). *Science* 350:820.
  <https://doi.org/10.1126/science.aad2879>
- Moreno-Mayar, J. V. et al. 2018 (the Andaman genome). *Science* 362:eaav2621.
  <https://doi.org/10.1126/science.aav2621>
- Mallick, S. et al. 2016 (Simons Genome Diversity Project: Mbuti, Han, Papuan). *Nature*
  538:201. <https://doi.org/10.1038/nature18964>
- Wang, K. et al. 2022. 4000-year-old hair from the Middle Nile highlights unusual ancient DNA
  degradation pattern and a potential source of early eastern Africa pastoralists. *Scientific
  Reports* 12. <https://doi.org/10.1038/s41598-022-25384-y>
- Sereno, P. C. et al. 2008. Lakeside cemeteries in the Sahara. *PLoS ONE* 3:e2995.
  <https://doi.org/10.1371/journal.pone.0002995>
- Stojanowski, C. M., Irish, J. D. & Sereno, P. C. 2026. Early to Middle Holocene
  hunter-fisher-gatherers from the Green Sahara (Gobero, Niger): dental evidence for regional
  African affinities. *American Journal of Biological Anthropology* 190.
  <https://doi.org/10.1002/ajpa.70262>
- Salem, N. et al. 2025. Ancient DNA from the Green Sahara reveals ancestral North African
  lineage. *Nature* 641. <https://doi.org/10.1038/s41586-025-08793-7>
- Wikipedia, "Genetic history of West Africa" (read 2026-11-13), for the 2017 and 2020 review
  statements. <https://en.wikipedia.org/wiki/Genetic_history_of_West_Africa>
