# Speculative fill: evals

Settings: `{"blend_rings": 16, "smooth_iters": 16, "smooth_rate": 0.5, "time_smooth": 0.4, "blend_conf": 0, "kernel_cap": 0, "hold_rings": 0, "bridge": 1.0, "time_from_observed": 1, "soft_sources": 1, "soft_power": 0.1, "bridge_conf": 0, "bridge_hold": 1}`

**Score 0.294** (1.000 = the unsmoothed fill). Guards: observed ok, coverage ok, holdout ok, drift ok, spread ok, regressions ok, ancestry ok.

| Metric | Now | Unsmoothed |
|---|---|---|
| rough_os | 0.0199 | 0.0713 |
| rough_ss | 0.0039 | 0.0056 |
| rough_oo | 0.0078 | 0.0078 |
| cliffs | 0.0004 | 1.7913 |
| rule_edge_cliffs | 0.0000 | 1.1719 |
| conf_edges | 16.8990 | 16.8990 |
| time_step | 0.0235 | 0.0225 |
| flicker | 0.5160 | 2.7998 |
| holdout | 0.0268 | 0.0901 |
| drift | 0.0278 | 0.0000 |
| coverage | 0.9993 | 0.9993 |

## Spread order

- cereals: Anatolia & Cyprus 10000, Balkans & Greece 6000, Central Europe 5000, British Isles 4000 (ok)
- domestic_livestock: Anatolia & Cyprus 7000, Balkans & Greece 6000, Central Europe 6000, British Isles 5000 (ok)

## Regression cases

- ok: Northern Italy and Liguria: mines read 1.0 (observed) at 5,000 BCE, drop to about 0.37 everywhere at 4,000 BCE (mines, 4000 BCE): 0.081 against 0.1
- ok: Algerian Saharan Atlas: sampling goes 0.40 (5,000 BCE) to 0.74 (4,000) to 0.40 (3,000). A yellow observed patc (adna_samples, 4000 BCE): 0.155 against 0.215
- ok: Atlantic Morocco: cereals 0.22 (6,000 BCE), 0.70 (5,000), 0.42 (4,000), 0.33 (3,000). The inland plain south o (cereals, 5000 BCE): 0.131 against 0.169
- ok: SE Poland: an isolated observed patch of megalithic tombs at 1.0 with a glow that runs east into Ukraine (0.46 (megalithic_tombs, 4000 BCE): 0.061 against 0.1
- ok: Western Alps and Rhone: a 10-cell observed patch at 1.0 with a round glow averaging 0.65 across the box and re (pile_dwellings, 3000 BCE): 0.035 against 0.1
- ok: Sinai, Negev and NW Arabia: observed 1.0 around the Arabah with a glow of 0.4-0.8 across Sinai and into Arabia (metallurgy, 4000 BCE): 0.07 against 0.1
- ok: Central Anatolia: a north-south string of 7 observed cells at 1.0 (Kestel area) with a glow of 0.25-0.6 over t (mines, 3000 BCE): 0.058 against 0.1
- FAIL: Middle Egypt: the observed block at 1.0 ends in a diagonal edge across the Western Desert; speculative cells b (waterlogged_organics, 3000 BCE): 0.106 against 0.1
- ok: Eastern Poland: the east edge of the observed 1.0 block; the first speculative ring is about 0.75-0.8 and the  (enclosures, 5000 BCE): 0.09 against 0.1
- FAIL: SW Anatolian lake district: cells observed at about 0.2 (6,000 BCE) and 0.33 (4,000 BCE) are filled at 0.67 at (open_land, 5000 BCE): 0.16 against 0.1

## Ancestry (recorded only, no fill)

4079 individuals: {'fit': 3662, 'low_coverage': 287, 'reference': 85, 'no_fit': 45}; 99% of modelled genomes fit. Kernel width 200 km (cross-validated on the Anatolian-farmer share).

| Slice | Land with a fitted genome in reach | Genomes |
|---|---|---|
| 10000 BCE | 0.7% | 7.3 |
| 9000 BCE | 6.4% | 31.8 |
| 8000 BCE | 8.8% | 53.1 |
| 7000 BCE | 11.8% | 120.2 |
| 6000 BCE | 22.3% | 243.4 |
| 5000 BCE | 25.2% | 865.3 |
| 4000 BCE | 32.1% | 756.5 |
| 3000 BCE | 36.7% | 1143.2 |

| Known result | Individual | Component | Expected | Got | |
|---|---|---|---|---|---|
| Cheddar Man is a western hunter-gatherer | I3016 | whg | 1.0 | 1.0 | ok |
| Oetzi is mostly Anatolian farmer with a little WHG | Iceman | ana | 0.9 | 0.899 | ok |
| Oetzi is mostly Anatolian farmer with a little WHG | Iceman | whg | 0.1 | 0.101 | ok |
| An LBK farmer (Derenburg) is mostly Anatolian farmer | DER002 | ana | 0.93 | 1.0 | ok |
| Globular Amphora shows the hunter-gatherer resurgence | RISE1163 | whg | 0.25 | 0.21 | ok |
| Globular Amphora shows the hunter-gatherer resurgence | RISE1163 | ana | 0.75 | 0.79 | ok |
| Khvalynsk is EHG with Iran/CHG | I6737 | ehg | 0.75 | 0.736 | ok |
| Khvalynsk is EHG with Iran/CHG | I6737 | irn | 0.25 | 0.264 | ok |

## Per layer

| Layer | rough_os | rough_ss | cliffs | flicker | time_step | holdout | drift |
|---|---|---|---|---|---|---|---|
| pottery | 0.023 | 0.008 | 0.0 | 1.6 | 0.119 | 0.053 | 0.078 |
| flaked_stone | 0.000 | 0.001 | 0.0 | 0.0 | 0.000 | 0.000 | 0.003 |
| ground_stone | 0.013 | 0.007 | 0.0 | 0.0 | 0.089 | 0.015 | 0.073 |
| bone_antler | 0.006 | 0.010 | 0.0 | 0.0 | 0.013 | 0.008 | 0.058 |
| ornaments | 0.005 | 0.006 | 0.0 | 0.0 | 0.014 | 0.006 | 0.033 |
| cereals | 0.023 | 0.006 | 0.0 | 0.7 | 0.039 | 0.019 | 0.049 |
| domestic_livestock | 0.027 | 0.007 | 0.0 | 0.0 | 0.091 | 0.017 | 0.053 |
| enclosures | 0.026 | 0.002 | 0.0 | 2.2 | 0.021 | 0.028 | 0.024 |
| megalithic_tombs | 0.018 | 0.002 | 0.0 | 0.0 | 0.017 | 0.021 | 0.022 |
| pile_dwellings | 0.044 | 0.001 | 0.0 | 0.0 | 0.006 | 0.051 | 0.011 |
| houses | 0.019 | 0.004 | 0.0 | 0.4 | 0.026 | 0.024 | 0.027 |
| mines | 0.030 | 0.002 | 0.0 | 0.3 | 0.015 | 0.035 | 0.025 |
| metallurgy | 0.019 | 0.001 | 0.0 | 0.4 | 0.005 | 0.000 | 0.008 |
| waterlogged_organics | 0.020 | 0.004 | 0.0 | 1.7 | 0.013 | 0.015 | 0.029 |
| cereal_pollen | 0.014 | 0.006 | 0.0 | 0.5 | 0.016 | 0.024 | 0.041 |
| dung_spores | 0.017 | 0.006 | 0.0 | 0.4 | 0.030 | 0.020 | 0.030 |
| open_land | 0.076 | 0.013 | 0.0 | 0.4 | 0.029 | 0.103 | 0.058 |
| adna_samples | 0.014 | 0.012 | 0.0 | 0.3 | 0.033 | 0.010 | 0.095 |
| y_i2 | 0.039 | 0.004 | 0.0 | 1.7 | 0.021 | 0.049 | 0.026 |
| y_g2a | 0.026 | 0.002 | 0.0 | 1.0 | 0.015 | 0.041 | 0.012 |
| y_r1b | 0.029 | 0.004 | 0.0 | 0.8 | 0.016 | 0.045 | 0.018 |
| y_r1a | 0.011 | 0.002 | 0.0 | 0.0 | 0.011 | 0.014 | 0.014 |
| y_c | 0.014 | 0.001 | 0.0 | 0.4 | 0.009 | 0.024 | 0.008 |
| y_j2 | 0.011 | 0.002 | 0.0 | 0.8 | 0.008 | 0.016 | 0.010 |
| y_h2 | 0.004 | 0.000 | 0.0 | 0.0 | 0.002 | 0.004 | 0.002 |
| y_other | 0.033 | 0.005 | 0.0 | 1.3 | 0.023 | 0.039 | 0.026 |
| mt_u5 | 0.030 | 0.003 | 0.0 | 1.0 | 0.023 | 0.059 | 0.025 |
| mt_u4 | 0.014 | 0.002 | 0.0 | 0.0 | 0.013 | 0.024 | 0.011 |
| mt_h | 0.014 | 0.002 | 0.0 | 0.6 | 0.014 | 0.032 | 0.011 |
| mt_k | 0.016 | 0.002 | 0.0 | 0.3 | 0.016 | 0.037 | 0.016 |
| mt_j | 0.006 | 0.001 | 0.0 | 0.0 | 0.006 | 0.014 | 0.006 |
| mt_t2 | 0.007 | 0.001 | 0.0 | 0.3 | 0.008 | 0.016 | 0.007 |
| mt_n1a | 0.005 | 0.000 | 0.0 | 0.0 | 0.005 | 0.012 | 0.004 |
| mt_other | 0.022 | 0.005 | 0.0 | 0.5 | 0.030 | 0.036 | 0.034 |

## Largest steps in space

| Layer | Year | Kind | Step | Pairs | Region | Box (lon0, lat0, lon1, lat1) |
|---|---|---|---|---|---|---|
| y_r1b | 4000 BCE | seam | 0.684 | 21 | Russia: steppe and forest-steppe | [47.7, 48.9, 57.7, 58.9] |
| open_land | 9000 BCE | seam | 0.577 | 29 | British Isles | [-13.4, 47.1, -3.4, 57.1] |
| open_land | 5000 BCE | seam | 0.655 | 14 | Anatolia & Cyprus | [25.6, 32.1, 35.6, 42.1] |
| open_land | 5000 BCE | seam | 0.565 | 21 | British Isles | [-5.2, 47.4, 4.8, 57.4] |
| open_land | 10000 BCE | seam | 0.567 | 20 | British Isles | [-13.4, 47.1, -3.4, 57.1] |
| open_land | 6000 BCE | seam | 0.512 | 27 | British Isles | [-5.2, 47.4, 4.8, 57.4] |
| open_land | 9000 BCE | seam | 0.456 | 40 | British Isles | [-4.7, 47.1, 5.3, 57.1] |
| open_land | 3000 BCE | seam | 0.52 | 20 | France & Low Countries | [0.9, 38.9, 10.9, 48.9] |
| open_land | 4000 BCE | seam | 0.537 | 17 | British Isles | [-5.2, 47.4, 4.8, 57.4] |
| open_land | 10000 BCE | seam | 0.537 | 16 | Central Europe | [7.8, 43.9, 17.8, 53.9] |
| mt_u5 | 6000 BCE | seam | 0.423 | 27 | Central Europe | [6.5, 49.1, 16.5, 59.1] |
| open_land | 10000 BCE | seam | 0.435 | 24 | British Isles | [-4.7, 47.1, 5.3, 57.1] |
| domestic_livestock | 3000 BCE | speculative_step | 0.463 | 16 | Horn of Africa | [31.7, 7.6, 41.7, 17.6] |
| y_i2 | 4000 BCE | seam | 0.482 | 14 | Russia: steppe and forest-steppe | [47.7, 48.4, 57.7, 58.4] |
| open_land | 9000 BCE | seam | 0.489 | 13 | Central Europe | [7.8, 43.9, 17.8, 53.9] |
| pottery | 5000 BCE | seam | 0.384 | 25 | Russia: forest north of 56°N | [28.6, 56.9, 38.6, 66.9] |
| mt_u5 | 8000 BCE | seam | 0.332 | 40 | Russia: forest north of 56°N | [35.1, 53.6, 45.1, 63.6] |
| mt_k | 6000 BCE | seam | 0.371 | 26 | Iran & Afghanistan | [43.3, 27.4, 53.3, 37.4] |
| pottery | 5000 BCE | seam | 0.435 | 14 | Russia: forest north of 56°N | [33.8, 56.9, 43.8, 66.9] |
| open_land | 4000 BCE | seam | 0.415 | 14 | Central Europe | [2.6, 47.9, 12.6, 57.9] |
| open_land | 8000 BCE | seam | 0.452 | 11 | British Isles | [-13.4, 47.1, -3.4, 57.1] |
| open_land | 5000 BCE | seam | 0.464 | 10 | Central Europe | [2.6, 47.9, 12.6, 57.9] |
| y_r1b | 4000 BCE | seam | 0.356 | 20 | Central Europe | [5.7, 47.6, 15.7, 57.6] |
| open_land | 3000 BCE | seam | 0.432 | 11 | Italy & islands | [7.0, 36.9, 17.0, 46.9] |
| y_g2a | 5000 BCE | seam | 0.383 | 15 | Balkans & Greece | [16.5, 39.4, 26.5, 49.4] |
| open_land | 5000 BCE | seam | 0.414 | 12 | France & Low Countries | [-7.3, 42.1, 2.7, 52.1] |
| open_land | 4000 BCE | seam | 0.437 | 10 | Italy & islands | [7.0, 36.9, 17.0, 46.9] |
| open_land | 6000 BCE | seam | 0.395 | 13 | British Isles | [-9.5, 52.4, 0.5, 62.4] |
| pottery | 7000 BCE | seam | 0.312 | 27 | Central Europe | [16.1, 45.6, 26.1, 55.6] |
| open_land | 7000 BCE | seam | 0.531 | 6 | Anatolia & Cyprus | [24.7, 33.1, 34.7, 43.1] |
| open_land | 4000 BCE | seam | 0.391 | 13 | Central Europe | [4.8, 42.1, 14.8, 52.1] |
| open_land | 9000 BCE | seam | 0.424 | 10 | Balkans & Greece | [17.4, 35.4, 27.4, 45.4] |
| y_r1b | 4000 BCE | seam | 0.383 | 13 | Russia: steppe and forest-steppe | [42.0, 48.6, 52.0, 58.6] |
| y_i2 | 5000 BCE | seam | 0.399 | 11 | Balkans & Greece | [17.8, 39.6, 27.8, 49.6] |
| domestic_livestock | 4000 BCE | speculative_step | 0.412 | 10 | Horn of Africa | [31.7, 7.6, 41.7, 17.6] |
| open_land | 8000 BCE | seam | 0.416 | 9 | Central Europe | [9.1, 44.1, 19.1, 54.1] |
| open_land | 3000 BCE | seam | 0.46 | 7 | Central Europe | [11.3, 44.4, 21.3, 54.4] |
| y_i2 | 4000 BCE | seam | 0.415 | 9 | Iberia | [-13.8, 34.4, -3.8, 44.4] |
| y_g2a | 4000 BCE | seam | 0.36 | 13 | France & Low Countries | [2.2, 42.6, 12.2, 52.6] |
| open_land | 6000 BCE | seam | 0.432 | 8 | Anatolia & Cyprus | [24.7, 33.1, 34.7, 43.1] |

## Largest changes between slices

| Layer | From | To | Region | Cells | Mean change |
|---|---|---|---|---|---|
| domestic_livestock | 6000 BCE | 5000 BCE | Maghreb | 1358 | 0.518 |
| pottery | 6000 BCE | 5000 BCE | Russia: forest north of 56°N | 1150 | 0.48 |
| domestic_livestock | 6000 BCE | 5000 BCE | Sahara–Sahel | 798 | 0.52 |
| domestic_livestock | 9000 BCE | 8000 BCE | Iran & Afghanistan | 725 | 0.503 |
| pottery | 7000 BCE | 6000 BCE | Russia: steppe and forest-steppe | 683 | 0.511 |
| domestic_livestock | 6000 BCE | 5000 BCE | Libya & Egypt | 563 | 0.549 |
| domestic_livestock | 7000 BCE | 6000 BCE | Central Europe | 529 | 0.521 |
| cereals | 7000 BCE | 6000 BCE | Balkans & Greece | 422 | 0.621 |
| pottery | 7000 BCE | 6000 BCE | Central Asia | 478 | 0.512 |
| pottery | 7000 BCE | 6000 BCE | Russia: forest north of 56°N | 490 | 0.492 |
| cereals | 6000 BCE | 5000 BCE | Central Europe | 398 | 0.589 |
| pottery | 6000 BCE | 5000 BCE | Scandinavia | 316 | 0.632 |
| cereals | 6000 BCE | 5000 BCE | Iberia | 311 | 0.641 |
| enclosures | 6000 BCE | 5000 BCE | Central Europe | 341 | 0.58 |
| enclosures | 6000 BCE | 5000 BCE | France & Low Countries | 330 | 0.592 |
| enclosures | 7000 BCE | 6000 BCE | Central Europe | 371 | 0.497 |
| cereals | 6000 BCE | 5000 BCE | France & Low Countries | 306 | 0.602 |
| mines | 6000 BCE | 5000 BCE | France & Low Countries | 324 | 0.558 |
| domestic_livestock | 7000 BCE | 6000 BCE | France & Low Countries | 310 | 0.58 |
| cereals | 9000 BCE | 8000 BCE | Iran & Afghanistan | 365 | 0.449 |
| cereals | 7000 BCE | 6000 BCE | Central Europe | 302 | 0.485 |
| pottery | 7000 BCE | 6000 BCE | Ukraine & Belarus | 266 | 0.54 |
| enclosures | 7000 BCE | 6000 BCE | British Isles | 250 | 0.537 |
| ground_stone | 8000 BCE | 7000 BCE | Russia: steppe and forest-steppe | 285 | 0.46 |
| pile_dwellings | 5000 BCE | 4000 BCE | Central Europe | 211 | 0.592 |
| cereals | 5000 BCE | 4000 BCE | British Isles | 189 | 0.653 |
| megalithic_tombs | 6000 BCE | 5000 BCE | France & Low Countries | 260 | 0.469 |
| domestic_livestock | 7000 BCE | 6000 BCE | Balkans & Greece | 256 | 0.476 |
| enclosures | 6000 BCE | 5000 BCE | Balkans & Greece | 178 | 0.667 |
| cereals | 7000 BCE | 6000 BCE | Italy & islands | 170 | 0.624 |
| domestic_livestock | 6000 BCE | 5000 BCE | Iberia | 206 | 0.503 |
| domestic_livestock | 6000 BCE | 5000 BCE | Central Europe | 212 | 0.474 |
| megalithic_tombs | 6000 BCE | 5000 BCE | Scandinavia | 197 | 0.5 |
| pottery | 7000 BCE | 6000 BCE | Iran & Afghanistan | 205 | 0.462 |
| megalithic_tombs | 6000 BCE | 5000 BCE | Iberia | 178 | 0.529 |
| megalithic_tombs | 6000 BCE | 5000 BCE | British Isles | 189 | 0.474 |
| domestic_livestock | 7000 BCE | 6000 BCE | Italy & islands | 170 | 0.517 |
| mines | 5000 BCE | 4000 BCE | Anatolia & Cyprus | 164 | 0.53 |
| domestic_livestock | 5000 BCE | 4000 BCE | Ukraine & Belarus | 140 | 0.465 |
| megalithic_tombs | 7000 BCE | 6000 BCE | Iberia | 136 | 0.476 |
