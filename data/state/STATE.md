# State of the game

`python -m pipeline state` at 413420d (uncommitted changes), 2026-11-13. Targets in `data/state/targets.toml`; only gated rows fail the run. Result: **pass**.


## Health

| | Measure | Now | Change | Target | Note |
|---|---|---|---|---|---|
| ok | python tests failing | 0 |  | ≤ 0 (gate) | 329 run (`make test`) |
| ok | rust tests failing | 0 |  | ≤ 0 (gate) | 209 passed (`cargo test --workspace`) |
| ok | web build errors | 0 |  | ≤ 0 (gate) | `cargo check --target wasm32-unknown-unknown` |
| ok | place plan problems | 0 |  | ≤ 0 (gate) | 83 places, 19 plans, 0 problems |
| ok | intuition files invalid | 0 |  | ≤ 0 (gate) | 20 files |

## Speculative fill

| | Measure | Now | Change | Target | Note |
|---|---|---|---|---|---|
| ok | evals guards failing | 0 |  | ≤ 0 (gate) | observed, coverage, holdout, drift, spread, regressions |
| ok | evals score | 0.294 |  | ≤ 0.35 | 1.0 = the unsmoothed fill; lower is smoother |
| ok | regression cases failing | 2 |  | ≤ 2 | of 10; allowed 2 (data/isostyle/evals/regressions.toml) |
|  | holdout error | 0.0268 |  |  |  |
|  | flicker | 0.516 |  |  | mean over layers (isostyle/evals.py) |

## Terrain

| | Measure | Now | Change | Target | Note |
|---|---|---|---|---|---|
| ok | pollen anchors same class | 65% |  | ≥ 65 | at 6 ka, published vs map |
| ok | pollen anchors compatible | 87% |  | ≥ 85 | at 6 ka |
| ok | terrain suspects | 195 |  | ≤ 195 | 35 straight edges and thin bands, 112 surges and flickers, 28 biomes in the wrong climate, 0 floodplains lost, 20 speckle (`python -m pipeline suspects`) |

## Map

| | Measure | Now | Change | Target | Note |
|---|---|---|---|---|---|
|  | settlements | 8147 |  |  | in build/settlements.geojson |
| ok | settlements on water | 15 |  | ≤ 15 | 13 offshore (build/report.md) |
| ok | garbled site names | 0 |  | ≤ 0 |  |

## Population

| | Measure | Now | Change | Target | Note |
|---|---|---|---|---|---|
|  | sites hidden by visibility | 66% |  |  | 4688 recorded vs 13665 expected at 3000 BCE |
|  | unexplained shortfall hexes | 1033 |  |  | at 3000 BCE (data/population/residuals.json) |

## Map

| | Measure | Now | Change | Target | Note |
|---|---|---|---|---|---|
| ok | ramp steps hard to tell apart colour-blind | 3 |  | ≤ 3 | elevation, land 4-5 protan 4.2, elevation, land 4-5 deutan 2.4, evidence 1-2 protan 4.3; 7 ramps, protanopia and deuteranopia; a step is weak under ΔE 5; least 2.4 (elevation, land steps 4-5 (deutan)) |

## Famous sites

| | Measure | Now | Change | Target | Note |
|---|---|---|---|---|---|
| ok | famous sites missing | 0 |  | ≤ 0 | all 50 renown.json sites matched |
| ok | famous sites dated off the map | 0 |  | ≤ 0 |  |
| ok | famous sites with stray records | 0 |  | ≤ 0 |  |

## Research debt

| | Measure | Now | Change | Target | Note |
|---|---|---|---|---|---|
|  | unchecked intuition citations | 143 |  |  | of 411 (data/isostyle/intuitions) |
|  | open place research items | 23 |  |  | of 66 (data/places/plans, `status`) |
|  | unchecked known sites in plans | 0 |  |  | of 60 |

## Fixed views

| | Measure | Now | Change | Target | Note |
|---|---|---|---|---|---|
| ok | views failed to render | 0 |  | ≤ 0 | `make state-visual`, 0 days ago |
| ok | views changed since accepted | 0 |  | ≤ 0 | `make state-visual`, 0 days ago |

## Clicking and UI

| | Measure | Now | Change | Target | Note |
|---|---|---|---|---|---|
| ok | piece clicks that open the piece | 100% |  | ≥ 99 | 48 pieces in 4 views; `make state-ui`, 0 days ago |
| ok | off-centre clicks that open the piece | 97% |  | ≥ 95 | 8 px off centre |
| ok | name clicks that open the site | 96% |  | ≥ 95 | clicking a drawn settlement name |
| ok | crowded pieces | 26% |  | ≤ 26 | on-screen pieces with another within 24 px |
| ok | clicks that moved the camera | 0 |  | ≤ 0 |  |
| ok | controls that moved under the player | 0 |  | ≤ 0 (gate) |  |
| ok | labels that moved under the player | 0 |  | ≤ 0 (gate) |  |

## Performance

| | Measure | Now | Change | Target | Note |
|---|---|---|---|---|---|
| ok | board pass time | 45.46 ms |  | ≤ 48 | GPU ms per board pass, worst of 4 views at 1600x1000; mean 40.83 ms; `make state-ui`, 0 days ago |

## Critics

Latest structured run of each agent in `.claude/agents/` (`data/state/critics/`). Scores are the model's own judgement against `neolith-rs/harness/CRITIC.md`; re-run a critic when its age matters.

| Critic | Date | Age (days) | Rubric | Overall | Open findings |
|---|---|---|---|---|---|
| greatest-hits-critic | 2026-11-12 | 1 | 5-axis-v1 | 1.4 | 5 of 12 |
| gsg-critic | 2026-11-12 | 1 | 8-category-v1 | 1.4 | 3 of 5 |
| terrain-critic | 2026-11-13 | 0 |  | – | 2 of 6 |

## Stale inputs

None.
