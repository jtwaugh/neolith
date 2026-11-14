# Plan: an ancestry map mode from the AADR

*Plan, 2026-11-13. Follows `AUDIENCE_QUESTIONS.md` (personas 1, 2, 7 and 8).*

## Why

Neolith already ingests the Allen Ancient DNA Resource (AADR v66.p1, CC0; `isostyle/people.py`),
but only as 16 uniparental haplogroup share layers (`y_i2` … `mt_other`). That is the least
legible way to show ancient DNA:

- only 2,223 of 4,078 in-window samples have a Y call, because women have none;
- a haplogroup is one lineage, not a population's ancestry;
- "R1b = Indo-Europeans" is exactly the misreading the steppe crowd brings.

The way the field tells this story (Reich, Lazaridis, Haak, Allentoft) is through **autosomal
ancestry proportions**: how much of each person is western hunter-gatherer, Anatolian farmer,
Iranian/Caucasus farmer, eastern hunter-gatherer and so on, read across a map and through time.
This plan computes those proportions for every AADR individual in the window from the same CC0
release. It shows them as one *Ancestry* map mode with sample pins and an inspector strip of
individuals over time.

**Outcome:** a player can watch Anatolian-farmer ancestry move up the Danube and across the
Mediterranean between 7000 and 4000 BCE. They can see hunter-gatherer ancestry return in the
Middle Neolithic, and the EHG + Iran/CHG mixture that becomes "steppe" building at the 3000 BCE
edge. Every hex says how many genomes stand behind it.

## Principles (from the repo's standing rules)

- **Recorded, not speculative.** The proportions are model estimates computed from recorded
  genotypes, with a fit statistic per sample. They get **no speculative gap fill**: unsampled
  land stays unknown and drawn as such. This is the layer most likely to be screenshotted as
  proof (persona 1 in `AUDIENCE_QUESTIONS.md`).
- **Add beside, never replace.** The haplogroup layers stay, and ancestry is a new set.
- **Sources in the repo.** Every reference group, paper and tool goes into a `SOURCES.md` with a
  link, and registers in `data/ATTRIBUTIONS.toml`. The AADR entry already exists. The table also
  carries the AADR's per-sample publication field, so each genome cites its original paper.
- **Licence.** Inputs are CC0 (AADR). ADMIXTOOLS 2 is a build tool, not shipped. The output table
  is CC BY-SA like the rest of `data/`.
- **No arrows.** Movement is shown as change over time in place, never as drawn migration
  vectors.
- **Parallel sessions.** The `neolith-rs/crates/app/src/board/*` files currently have uncommitted
  edits from other sessions. Run ListAgents and SendMessage before phase 3 touches `view.rs`,
  `panels.rs` or the board shaders.

---

## Phase 0: feasibility spike (go/no-go)

**Question:** with the AADR 1240K genotypes and a fixed source set, what share of in-window
individuals get a usable qpAdm fit, by region and epoch?

1. **Toolchain.** Install R and ADMIXTOOLS 2 (`uqrmaie1/admixtools`) outside the Python venv.
   Pin the version in `isostyle/ancestry/README.md`. Neither `make test` nor CI depends on R:
   the R step writes a committed table, the same way other expensive inputs are handled.
2. **Fetch.** Add the v66.p1 1240K EIGENSTRAT trio (`.geno/.snp/.ind`) to `isostyle/config.toml`
   `[[sources]]`, with `fetch` recording checksums as usual. The files are several GB, so they go
   in `build/isostyle/sources/` and are never committed. Confirm the exact Dataverse file IDs and
   sizes on the DOI page (10.7910/DVN/FFIDCW) before writing the config.
3. **Subset.** From the `.ind`, keep:
   - targets: in-window individuals passing `people.load_aadr`'s filters, with at least
     30,000 SNPs covered;
   - the source and outgroup labels below.

   Write a small EIGENSTRAT subset to `build/isostyle/ancestry/`.
4. **Model.** A distal six-source set, each defined in config as a list of AADR group labels.
   The labels must be checked against the `.anno`: they vary across releases, and `.SG`/`.DG`
   suffixes matter.

   | key | name in the app | reference individuals (indicative) |
   |---|---|---|
   | `whg` | Western hunter-gatherer | Villabruna cluster (Loschbour, Bichon, Villabruna) |
   | `ehg` | Eastern hunter-gatherer | Karelia, Samara HG |
   | `ana` | Anatolian farmer | Barcın, Menteşe Neolithic |
   | `irn` | Iranian farmer / Caucasus HG | Ganj Dareh N, Kotias, Satsurblia |
   | `lev` | Levantine forager | Natufian |
   | `naf` | North African forager | Taforalt |

   **Outgroups ("right"):** Mbuti, Ust'-Ishim, Kostenki14, MA1 (Mal'ta), Han, Papuan/Onge, and
   Mota (Ethiopia, 4.5 ka) to separate `naf` from `lev`. Build the f2 blocks once with
   `extract_f2` (`maxmiss` tuned; per-target `allsnps = TRUE` style fitting for low coverage).
5. **Rotating qpAdm per individual.** Try one-, two-, three- and four-source subsets of the six,
   in that order. Accept the smallest model with p ≥ 0.01 and every weight in [0, 1] within 2 SE.
   Record weights, SEs, p and the model. Statuses:
   - `fit`;
   - `no_fit` (no feasible model up to four sources);
   - `low_coverage`;
   - `reference` (the individual is in a source group: shown, but flagged, because it is 100% its
     own source by construction).
6. **Run it on about 300 individuals** stratified by region and epoch. Report the fit rate and
   the runtime per individual.
7. **Validate against known results.** Each of these must land within about 10 points of the
   published estimate:
   - Cheddar Man ≈ all `whg`;
   - Ötzi ≈ mostly `ana` with a little `whg`;
   - an LBK farmer ≈ mostly `ana`;
   - a Globular Amphora individual shows `whg` resurgence;
   - a Samara Eneolithic or Khvalynsk individual ≈ `ehg` + `irn`;
   - Ganj Dareh ≈ all `irn`.

**Gate:** proceed only if at least 60% of targets with 30,000 or more SNPs fit, and the
validations pass. If not, change the source set (for example, split `irn` into Iran N and CHG, or
add a Baltic/Scandinavian HG source) and rerun the spike before going further.

**Fallback for prototyping only.** Allentoft et al. 2024 (*Nature* 625:301) publishes
per-individual ancestry for about 1,600 imputed genomes. Repository records disagree on its
licence (CC BY 4.0 vs CC BY-NC-SA). Confirm it on the article page before using any of it. If it
is NC, it can be used only for an uncommitted visual mock-up, never in `data/`.

## Phase 1: the recorded table

- `isostyle/ancestry/run.R` (the qpAdm runner) plus `isostyle/ancestry.py` (subset, orchestration,
  QA). New CLI step: `python -m isostyle ancestry`. It is opt-in because it needs R and the
  genotypes, and it is not part of `build`.
- Output, committed: `data/ancestry/ancestry.csv.gz`, one row per individual:
  - `individual`, `group`, `locality`, `lat`, `lon`, `bp`, `sd`, `snps`, `publication`;
  - `status`, `model`, `p`;
  - `w_whg … w_naf` and `se_whg … se_naf` (blank when not in the model).
- `data/ancestry/SOURCES.md`: the method, the source and outgroup label lists, the
  ADMIXTOOLS 2 version, the validation results, and links (AADR DOI, ADMIXTOOLS 2, Harney et al.
  2021 on qpAdm, the reference-population papers). Register `data:ancestry` in
  `data/ATTRIBUTIONS.toml`.
- Extend `pipeline/tests/test_sources.py` so it checks that `data/ancestry/SOURCES.md` exists and
  lists the AADR DOI.
- Add a test that the weights in each `fit` row sum to 1 ± 0.01 and that `status` values come
  from the allowed set.

## Phase 2: isostyle layers (no fill)

- **`people.py`.** When `data/ancestry/ancestry.csv.gz` exists, join it to the sample units on
  `individual`. A new layer key `value_field` (for example `"w_ana"`) sets `y_<id>` to the
  sample's weight: 0 where the component is absent from a fitted model, NaN unless `status ==
  fit`.
  - The kernel surfaces and leave-one-out loss in `surface.py` already work with fractional
    values (a weighted mean, and cross-entropy with soft labels). Confirm this with a unit test,
    not by assumption.
- **`layers.toml`.** Six layers in `set = "Ancestry"`, `group = "People"`, `kind = "share"`,
  `unit = "sample"`, with `evidence_word = "genomes"` and a plain-language `note` each.
- **No fill.** Add a layer flag `fill = false`. `speculative.py` then writes only observed cells
  (plus firmness) for those layers, and `export.py` leaves every other cell at code 255 (unknown).
  Test: no ancestry cell in `speculative.csv.gz` has a non-observed basis.
- **Sample export.** `export.py` also writes `data/isostyle/speculative/ancestry_samples.json`:
  per individual, its location, date mean and SD, status, weights and publication. That is about
  4,000 rows and small.
- **Evals.** Add the ancestry layers to `python -m isostyle evals`: sigma choice from cross
  validation, the share of land with at least one fitted genome per slice, and the
  validation-sample checks from phase 0 as regression guards.

## Phase 3: the app

Coordinate with the sessions editing `board/` before starting.

- **Data in.** `neolith-convert --attach-evidence` already carries the six layers. Add
  `--attach-samples <ancestry_samples.json>` (`crates/convert/src/main.rs`, `crates/core/src/io.rs`)
  so `world.bin` holds the sample points.
- **`MapMode::Ancestry`** (`view.rs`, `panels.rs` menu).
  - **Hex colour:** mix the six component colours weighted by share, in OKLab, so the mixtures
    read as honest intermediates. Choose the palette with the `dataviz` skill's validator.
    `ana` and `whg` (the main contrast) must be distinguishable for colour-blind viewers.
  - **Opacity:** follows bootstrap firmness and genome count. With no fitted genome within
    sigma, the hex is drawn in the existing "unknown" hatch, not in a colour.
- **Sample pins.** At closer zoom, one pie glyph per genome alive in the current slice, sized by
  date overlap with the slice. Hover shows the individual, the date, the model fit and the paper.
  Reuse the settlement-piece label and LOD machinery rather than new rendering paths.
- **Inspector.** For the hovered hex or region:
  - a bar of its smoothed proportions;
  - **one stacked bar per individual within ~300 km, sorted by date along a 10,000–3,000 BCE
    axis.** This is the Reich-style figure people recognise (the Britain and Iberia transects),
    built from genomes rather than from smoothed values.
- **Legend copy.** Name each component in plain words, with this footnote: "Proportions come
  from a statistical model fitted to six reference groups. They describe shared ancestry, not
  peoples, languages or cultures. Unsampled land is left blank, not guessed."
- **Timeline cue.** At the 3000 BCE slice, add a note that steppe ancestry, an EHG + Iran/CHG
  mixture, spreads after the end of the map.

## Phase 4: story and review

- Three or four "map moments" for the explainer: the farmer front at 6000 and 5000 BCE; the
  hunter-gatherer resurgence at about 4000 BCE; the Iran/CHG gradient across the Zagros and the
  Caucasus; the steppe gathering at 3000 BCE. Add one line on what is blank (Egypt, the Gulf,
  most of Russia) and why.
- Update `AUDIENCE_QUESTIONS.md`: the fit verdicts for personas 1, 2 and 8 move from poor/partial
  to good.
- Run the `greatest-hits-critic` (Çatalhöyük, Lepenski Vir, Varna, Ganj Dareh areas) and the
  `gsg-critic` on the new mode. Run the `smooth-critic` only for surface artefacts: there is no
  fill to critique.

## Later, out of scope here

- A PCA panel projecting ancient samples onto modern West Eurasian variation. It needs the
  Human Origins modern panel, whose redistribution terms must be checked first.
- Extending the window to about 2500 BCE so the steppe expansion appears (a project-wide
  decision; see `AUDIENCE_QUESTIONS.md`).
- Proximal models (for example LBK = Anatolian N + local WHG) for finer regional stories.

## Risks

| Risk | Mitigation |
|---|---|
| Low fit rate for Mesolithic and Caucasus/Iran samples | The phase-0 gate; per-region source tweaks recorded in `SOURCES.md` |
| AADR group labels drift between releases | Labels in config, with a test that every configured label exists in the `.anno` |
| qpAdm runtime on about 4,000 targets | Precompute f2 once; parallelise targets; cache per-individual results by AADR version |
| Sparse early slices (about 11 genomes at 10,000 BCE) | The no-fill rule plus firmness-based opacity: the map honestly shows almost nothing |
| Misuse as racial or ethnic proof | No arrows, plain-language legend, "not peoples" footnote, per-sample citations, no fill |

## Verification

- Phase 0: the spike report, with fit rate by region and epoch and the validation table, goes
  in `build/isostyle/ancestry/spike.md`.
- `make test` passes: the new sources-test entry, weight-sum and status tests, the no-fill test,
  and the fractional-share surface test.
- `python -m isostyle evals --check` passes, with the ancestry guards included.
- In the app (`run` skill): switch to Ancestry; scrub 7000 → 4000 BCE over the Balkans and
  Central Europe and see the `ana` colour spread; hover an LBK hex and see dated individual bars;
  check that Egypt and the Gulf show the unknown hatch. Take screenshots at three slices for the
  explainer.

## Sources

- AADR: [Mallick et al. 2024, *Scientific Data*](https://link.springer.com/article/10.1038/s41597-024-03031-7);
  [Dataverse DOI 10.7910/DVN/FFIDCW](https://doi.org/10.7910/DVN/FFIDCW);
  [Reich lab AADR page](https://reich.hms.harvard.edu/node/256)
- ADMIXTOOLS 2: [github.com/uqrmaie1/admixtools](https://github.com/uqrmaie1/admixtools);
  [`extract_f2` reference](https://uqrmaie1.github.io/admixtools/reference/extract_f2.html)
- Allentoft et al. 2024, "Population genomics of post-glacial western Eurasia", *Nature* 625:301,
  [doi:10.1038/s41586-023-06865-0](https://doi.org/10.1038/s41586-023-06865-0)
  (licence to confirm; see [eScholarship copy](https://escholarship.org/content/qt2cz9029k/qt2cz9029k.pdf))
