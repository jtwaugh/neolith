# Speculative fill: evals

Settings: `{"blend_rings": 12, "smooth_iters": 16, "smooth_rate": 0.5, "time_smooth": 0.4, "blend_conf": 0, "kernel_cap": 0, "hold_rings": 0, "bridge": 0.75, "time_from_observed": 1}`

**Score 0.341** (1.000 = the unsmoothed fill). Guards: observed ok, coverage ok, holdout ok, drift ok, spread ok, regressions ok.

| Metric | Now | Unsmoothed |
|---|---|---|
| rough_os | 0.0313 | 0.0717 |
| rough_ss | 0.0037 | 0.0056 |
| rough_oo | 0.0079 | 0.0079 |
| cliffs | 0.0002 | 1.7420 |
| rule_edge_cliffs | 0.0000 | 1.1152 |
| conf_edges | 16.7610 | 16.7610 |
| time_step | 0.0221 | 0.0225 |
| flicker | 0.6903 | 2.7317 |
| holdout | 0.0295 | 0.0954 |
| drift | 0.0209 | 0.0000 |
| coverage | 0.9993 | 0.9993 |

## Spread order

- cereals: Anatolia & Cyprus 9000, Balkans & Greece 6000, Central Europe 5000, British Isles 4000 (ok)
- domestic_livestock: Anatolia & Cyprus 7000, Balkans & Greece 6000, Central Europe 6000, British Isles 5000 (ok)

## Regression cases

- FAIL: Northern Italy and Liguria: mines read 1.0 (observed) at 5,000 BCE, drop to about 0.37 everywhere at 4,000 BCE (mines, 4000 BCE): 0.633 against 0.1
- FAIL: Romania and the lower Danube: enclosures go 0.18 (6,000 BCE) to 0.61 (5,000) to 0.23 (4,000). The whole strip  (enclosures, 5000 BCE): 0.65 against 0.207
- FAIL: Northern Ireland and SW Scotland: houses observed at 1.0 at 6,000 BCE, a flat speculative 0.45 at 5,000 BCE (n (houses, 5000 BCE): 0.589 against 0.1
- FAIL: Algerian Saharan Atlas: sampling goes 0.40 (5,000 BCE) to 0.74 (4,000) to 0.40 (3,000). A yellow observed patc (adna_samples, 4000 BCE): 0.564 against 0.215
- FAIL: Atlantic Morocco: cereals 0.22 (6,000 BCE), 0.70 (5,000), 0.42 (4,000), 0.33 (3,000). The inland plain south o (cereals, 5000 BCE): 0.477 against 0.169
- FAIL: SE Poland: an isolated observed patch of megalithic tombs at 1.0 with a glow that runs east into Ukraine (0.46 (megalithic_tombs, 4000 BCE): 0.189 against 0.1
- FAIL: Western Alps and Rhone: a 10-cell observed patch at 1.0 with a round glow averaging 0.65 across the box and re (pile_dwellings, 3000 BCE): 0.221 against 0.1
- FAIL: Sinai, Negev and NW Arabia: observed 1.0 around the Arabah with a glow of 0.4-0.8 across Sinai and into Arabia (metallurgy, 4000 BCE): 0.152 against 0.1
- FAIL: Central Anatolia: a north-south string of 7 observed cells at 1.0 (Kestel area) with a glow of 0.25-0.6 over t (mines, 3000 BCE): 0.206 against 0.1
- FAIL: Middle Egypt: the observed block at 1.0 ends in a diagonal edge across the Western Desert; speculative cells b (waterlogged_organics, 3000 BCE): 0.194 against 0.1
- FAIL: Eastern Poland: the east edge of the observed 1.0 block; the first speculative ring is about 0.75-0.8 and the  (enclosures, 5000 BCE): 0.194 against 0.1
- FAIL: Georgia and Armenia: a 7-cell observed patch at about 0.85 in a speculative surround of 0.5-0.6, with observed (open_land, 3000 BCE): 0.228 against 0.1
- FAIL: SW Anatolian lake district: cells observed at about 0.2 (6,000 BCE) and 0.33 (4,000 BCE) are filled at 0.67 at (open_land, 5000 BCE): 0.487 against 0.1

## Per layer

| Layer | rough_os | rough_ss | cliffs | flicker | time_step | holdout | drift |
|---|---|---|---|---|---|---|---|
| pottery | 0.020 | 0.008 | 0.0 | 1.2 | 0.119 | 0.019 | 0.063 |
| flaked_stone | 0.000 | 0.001 | 0.0 | 0.0 | 0.000 | 0.000 | 0.003 |
| ground_stone | 0.013 | 0.007 | 0.0 | 0.0 | 0.083 | 0.010 | 0.062 |
| bone_antler | 0.022 | 0.009 | 0.0 | 0.8 | 0.012 | 0.022 | 0.036 |
| ornaments | 0.018 | 0.005 | 0.0 | 0.1 | 0.014 | 0.012 | 0.022 |
| cereals | 0.028 | 0.006 | 0.0 | 1.0 | 0.038 | 0.013 | 0.038 |
| domestic_livestock | 0.030 | 0.007 | 0.0 | 0.0 | 0.089 | 0.016 | 0.047 |
| enclosures | 0.061 | 0.001 | 0.0 | 2.4 | 0.020 | 0.075 | 0.013 |
| megalithic_tombs | 0.052 | 0.002 | 0.0 | 0.2 | 0.018 | 0.034 | 0.016 |
| pile_dwellings | 0.129 | 0.001 | 0.0 | 0.0 | 0.004 | 0.110 | 0.004 |
| houses | 0.037 | 0.004 | 0.0 | 0.7 | 0.024 | 0.095 | 0.023 |
| mines | 0.109 | 0.001 | 0.0 | 1.0 | 0.007 | 0.114 | 0.007 |
| metallurgy | 0.117 | 0.000 | 0.0 | 0.0 | 0.003 | 0.000 | 0.003 |
| waterlogged_organics | 0.079 | 0.002 | 0.0 | 0.3 | 0.007 | 0.041 | 0.011 |
| cereal_pollen | 0.014 | 0.006 | 0.0 | 0.5 | 0.013 | 0.014 | 0.031 |
| dung_spores | 0.017 | 0.006 | 0.0 | 0.4 | 0.029 | 0.019 | 0.027 |
| open_land | 0.076 | 0.013 | 0.0 | 0.6 | 0.029 | 0.128 | 0.052 |
| adna_samples | 0.028 | 0.011 | 0.0 | 2.8 | 0.035 | 0.017 | 0.067 |
| y_i2 | 0.033 | 0.004 | 0.0 | 2.3 | 0.020 | 0.041 | 0.021 |
| y_g2a | 0.022 | 0.002 | 0.0 | 1.0 | 0.014 | 0.031 | 0.010 |
| y_r1b | 0.024 | 0.004 | 0.0 | 1.2 | 0.015 | 0.028 | 0.016 |
| y_r1a | 0.011 | 0.002 | 0.0 | 0.0 | 0.010 | 0.017 | 0.012 |
| y_c | 0.011 | 0.001 | 0.0 | 0.5 | 0.008 | 0.010 | 0.006 |
| y_j2 | 0.010 | 0.002 | 0.0 | 0.8 | 0.008 | 0.012 | 0.009 |
| y_h2 | 0.003 | 0.000 | 0.0 | 0.0 | 0.002 | 0.003 | 0.002 |
| y_other | 0.029 | 0.005 | 0.0 | 1.6 | 0.021 | 0.039 | 0.022 |
| mt_u5 | 0.017 | 0.003 | 0.0 | 1.6 | 0.023 | 0.019 | 0.020 |
| mt_u4 | 0.009 | 0.002 | 0.0 | 0.1 | 0.013 | 0.008 | 0.009 |
| mt_h | 0.009 | 0.001 | 0.0 | 0.6 | 0.012 | 0.011 | 0.008 |
| mt_k | 0.010 | 0.002 | 0.0 | 0.7 | 0.016 | 0.010 | 0.013 |
| mt_j | 0.004 | 0.001 | 0.0 | 0.0 | 0.006 | 0.005 | 0.005 |
| mt_t2 | 0.005 | 0.001 | 0.0 | 0.2 | 0.008 | 0.006 | 0.005 |
| mt_n1a | 0.003 | 0.000 | 0.0 | 0.0 | 0.005 | 0.004 | 0.003 |
| mt_other | 0.016 | 0.005 | 0.0 | 0.8 | 0.028 | 0.016 | 0.028 |

## Largest steps in space

| Layer | Year | Kind | Step | Pairs | Region | Box (lon0, lat0, lon1, lat1) |
|---|---|---|---|---|---|---|
| open_land | 9000 BCE | seam | 0.577 | 28 | British Isles | [-13.4, 47.1, -3.4, 57.1] |
| open_land | 5000 BCE | seam | 0.565 | 21 | British Isles | [-5.2, 47.4, 4.8, 57.4] |
| open_land | 10000 BCE | seam | 0.567 | 20 | British Isles | [-13.4, 47.1, -3.4, 57.1] |
| open_land | 9000 BCE | seam | 0.456 | 39 | British Isles | [-4.7, 47.1, 5.3, 57.1] |
| open_land | 3000 BCE | seam | 0.52 | 21 | France & Low Countries | [0.9, 38.9, 10.9, 48.9] |
| open_land | 4000 BCE | seam | 0.537 | 18 | British Isles | [-5.2, 47.4, 4.8, 57.4] |
| open_land | 10000 BCE | seam | 0.537 | 16 | Central Europe | [7.8, 43.9, 17.8, 53.9] |
| open_land | 6000 BCE | seam | 0.512 | 15 | British Isles | [-5.2, 47.4, 4.8, 57.4] |
| open_land | 10000 BCE | seam | 0.435 | 24 | British Isles | [-4.7, 47.1, 5.3, 57.1] |
| open_land | 9000 BCE | seam | 0.489 | 13 | Central Europe | [7.8, 43.9, 17.8, 53.9] |
| open_land | 4000 BCE | seam | 0.415 | 14 | Central Europe | [2.6, 47.9, 12.6, 57.9] |
| domestic_livestock | 3000 BCE | speculative_step | 0.448 | 11 | Horn of Africa | [31.7, 7.6, 41.7, 17.6] |
| open_land | 5000 BCE | seam | 0.463 | 10 | Central Europe | [2.6, 47.9, 12.6, 57.9] |
| open_land | 3000 BCE | seam | 0.432 | 12 | Italy & islands | [7.0, 36.9, 17.0, 46.9] |
| open_land | 8000 BCE | seam | 0.452 | 10 | British Isles | [-13.4, 47.1, -3.4, 57.1] |
| open_land | 5000 BCE | seam | 0.414 | 12 | France & Low Countries | [-7.3, 42.1, 2.7, 52.1] |
| open_land | 4000 BCE | seam | 0.437 | 10 | Italy & islands | [7.0, 36.9, 17.0, 46.9] |
| open_land | 4000 BCE | seam | 0.391 | 13 | Central Europe | [4.8, 42.1, 14.8, 52.1] |
| open_land | 7000 BCE | seam | 0.53 | 6 | Anatolia & Cyprus | [24.7, 33.1, 34.7, 43.1] |
| open_land | 9000 BCE | seam | 0.422 | 10 | Balkans & Greece | [17.4, 35.4, 27.4, 45.4] |
| open_land | 3000 BCE | seam | 0.46 | 7 | Central Europe | [11.3, 44.4, 21.3, 54.4] |
| open_land | 8000 BCE | seam | 0.415 | 9 | Central Europe | [9.1, 44.1, 19.1, 54.1] |
| open_land | 6000 BCE | seam | 0.431 | 8 | Anatolia & Cyprus | [24.7, 33.1, 34.7, 43.1] |
| open_land | 7000 BCE | seam | 0.36 | 12 | Central Europe | [9.1, 44.1, 19.1, 54.1] |
| open_land | 10000 BCE | seam | 0.428 | 7 | Anatolia & Cyprus | [26.9, 35.9, 36.9, 45.9] |
| open_land | 5000 BCE | seam | 0.37 | 10 | Central Europe | [4.8, 42.1, 14.8, 52.1] |
| open_land | 4000 BCE | seam | 0.374 | 9 | Central Europe | [11.3, 44.4, 21.3, 54.4] |
| open_land | 6000 BCE | seam | 0.41 | 7 | Balkans & Greece | [17.8, 37.1, 27.8, 47.1] |
| open_land | 9000 BCE | seam | 0.43 | 6 | Central Europe | [14.8, 49.4, 24.8, 59.4] |
| open_land | 7000 BCE | seam | 0.418 | 6 | Balkans & Greece | [17.8, 37.1, 27.8, 47.1] |
| domestic_livestock | 4000 BCE | speculative_step | 0.389 | 6 | Horn of Africa | [31.7, 7.6, 41.7, 17.6] |
| open_land | 3000 BCE | seam | 0.349 | 7 | Scandinavia | [15.6, 61.9, 25.6, 71.9] |
| open_land | 3000 BCE | seam | 0.371 | 6 | Scandinavia | [5.7, 57.1, 15.7, 67.1] |
| open_land | 7000 BCE | seam | 0.366 | 6 | France & Low Countries | [-2.1, 43.1, 7.9, 53.1] |
| open_land | 8000 BCE | seam | 0.37 | 5 | Central Europe | [14.8, 49.4, 24.8, 59.4] |
| open_land | 8000 BCE | seam | 0.369 | 5 | Scandinavia | [5.7, 57.1, 15.7, 67.1] |
| mines | 3000 BCE | seam | 0.315 | 7 | Anatolia & Cyprus | [29.9, 33.1, 39.9, 43.1] |
| open_land | 6000 BCE | seam | 0.349 | 5 | Central Europe | [11.3, 44.4, 21.3, 54.4] |
| open_land | 10000 BCE | seam | 0.438 | 3 | Central Europe | [7.8, 49.4, 17.8, 59.4] |
| pottery | 8000 BCE | rule_edge | 0.291 | 6 | Horn of Africa | [31.7, 7.6, 41.7, 17.6] |

## Largest changes between slices

| Layer | From | To | Region | Cells | Mean change |
|---|---|---|---|---|---|
| domestic_livestock | 6000 BCE | 5000 BCE | Maghreb | 1358 | 0.504 |
| pottery | 6000 BCE | 5000 BCE | Russia: forest north of 56°N | 1216 | 0.49 |
| pottery | 7000 BCE | 6000 BCE | Russia: steppe and forest-steppe | 1019 | 0.514 |
| pottery | 7000 BCE | 6000 BCE | Russia: forest north of 56°N | 1025 | 0.485 |
| domestic_livestock | 6000 BCE | 5000 BCE | Sahara–Sahel | 783 | 0.519 |
| domestic_livestock | 9000 BCE | 8000 BCE | Iran & Afghanistan | 726 | 0.503 |
| domestic_livestock | 6000 BCE | 5000 BCE | Libya & Egypt | 660 | 0.545 |
| enclosures | 6000 BCE | 5000 BCE | Central Europe | 433 | 0.673 |
| cereals | 6000 BCE | 5000 BCE | Central Europe | 461 | 0.624 |
| domestic_livestock | 7000 BCE | 6000 BCE | Central Europe | 487 | 0.534 |
| cereals | 7000 BCE | 6000 BCE | Balkans & Greece | 411 | 0.627 |
| pottery | 6000 BCE | 5000 BCE | Scandinavia | 367 | 0.675 |
| pottery | 7000 BCE | 6000 BCE | Ukraine & Belarus | 428 | 0.542 |
| megalithic_tombs | 5000 BCE | 4000 BCE | Central Europe | 387 | 0.541 |
| cereals | 6000 BCE | 5000 BCE | France & Low Countries | 315 | 0.664 |
| cereals | 6000 BCE | 5000 BCE | Iberia | 313 | 0.663 |
| domestic_livestock | 7000 BCE | 6000 BCE | Balkans & Greece | 373 | 0.491 |
| domestic_livestock | 7000 BCE | 6000 BCE | France & Low Countries | 304 | 0.602 |
| enclosures | 6000 BCE | 5000 BCE | British Isles | 245 | 0.744 |
| cereals | 9000 BCE | 8000 BCE | Iran & Afghanistan | 391 | 0.45 |
| pottery | 7000 BCE | 6000 BCE | Central Asia | 332 | 0.524 |
| megalithic_tombs | 6000 BCE | 5000 BCE | France & Low Countries | 275 | 0.627 |
| enclosures | 6000 BCE | 5000 BCE | France & Low Countries | 275 | 0.571 |
| cereals | 5000 BCE | 4000 BCE | British Isles | 206 | 0.689 |
| megalithic_tombs | 7000 BCE | 6000 BCE | British Isles | 199 | 0.682 |
| enclosures | 7000 BCE | 6000 BCE | Central Europe | 225 | 0.584 |
| enclosures | 6000 BCE | 5000 BCE | Balkans & Greece | 161 | 0.732 |
| domestic_livestock | 6000 BCE | 5000 BCE | Central Europe | 224 | 0.517 |
| mines | 5000 BCE | 4000 BCE | France & Low Countries | 178 | 0.635 |
| domestic_livestock | 6000 BCE | 5000 BCE | Iberia | 214 | 0.509 |
| megalithic_tombs | 8000 BCE | 7000 BCE | Iberia | 169 | 0.637 |
| cereals | 7000 BCE | 6000 BCE | Italy & islands | 165 | 0.614 |
| cereals | 7000 BCE | 6000 BCE | Central Europe | 208 | 0.485 |
| enclosures | 4000 BCE | 3000 BCE | Iberia | 143 | 0.703 |
| megalithic_tombs | 5000 BCE | 4000 BCE | Scandinavia | 201 | 0.495 |
| domestic_livestock | 5000 BCE | 4000 BCE | Ukraine & Belarus | 200 | 0.476 |
| houses | 5000 BCE | 4000 BCE | British Isles | 162 | 0.58 |
| domestic_livestock | 8000 BCE | 7000 BCE | Anatolia & Cyprus | 161 | 0.569 |
| pile_dwellings | 5000 BCE | 4000 BCE | Central Europe | 148 | 0.605 |
| domestic_livestock | 7000 BCE | 6000 BCE | Italy & islands | 169 | 0.521 |
