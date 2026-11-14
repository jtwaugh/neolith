# Ancestry: qpAdm per ancient individual

`python -m isostyle ancestry` computes autosomal ancestry proportions for every AADR individual in
the map's window and writes the committed table `data/ancestry/ancestry.csv.gz`. Method, reference
groups and validation results are in `data/ancestry/SOURCES.md`.

The step is opt-in. `python -m isostyle build`, `make test` and CI never run it and never need R:
they read the committed table.

## Toolchain (outside the Python venv)

| Tool | Version used | Install |
|---|---|---|
| R | 4.6.2 | `brew install r` |
| ADMIXTOOLS 2 | see `data/ancestry/SOURCES.md` (GitHub `uqrmaie1/admixtools`, HEAD on 2026-11-13) | below |
| jsonlite | 2.0.0 | below |

```sh
Rscript -e 'lib <- Sys.getenv("R_LIBS_USER"); dir.create(lib, recursive = TRUE, showWarnings = FALSE)
            options(repos = "https://cloud.r-project.org", timeout = 1200)
            install.packages(c("remotes", "jsonlite"), lib = lib)
            remotes::install_github("uqrmaie1/admixtools", dependencies = NA, lib = lib, upgrade = "never")'
```

ADMIXTOOLS 2 is a build tool (GPL-3): nothing from it is shipped or committed.

## Genotypes

The AADR v66.p1 1240K trio (`.geno` 7.1 GB, `.snp`, `.ind`) is listed in `isostyle/config.toml`
as optional sources. Either fetch all of it:

```sh
ISOSTYLE_FETCH_OPTIONAL=1 .venv/bin/python -m isostyle fetch    # into build/isostyle/sources/, never committed
```

or pass `--remote`, which reads only the rows of the individuals it needs by HTTP range (the
`.geno` is stored one individual per row; about 1.3 GB for the full run) and caches them under
`build/isostyle/ancestry/rows/`. The `.snp` and `.ind` are small and always fetched whole.

## Running

```sh
.venv/bin/python -m isostyle ancestry --spike 300 [--remote]   # go/no-go: build/isostyle/ancestry/spike.md
.venv/bin/python -m isostyle ancestry [--remote]               # the full table -> data/ancestry/ancestry.csv.gz
```

`ANCESTRY_CORES` sets the number of R workers (default 6). Per-individual results are cached in
`build/isostyle/ancestry/cache_*/`, keyed by the model, so an interrupted run resumes and a
changed model starts afresh.

## Files

- `isostyle/ancestry.py`: target and reference selection, the genotype subset, the table, QA.
- `isostyle/ancestry/run.R`: f2 blocks and rotating qpAdm per individual.
- `isostyle/config.toml` `[ancestry]`: sources, outgroups, thresholds, validation individuals.
- `isostyle/tests/test_ancestry.py`: label, table, no-fill and fractional-surface tests.

After a new table: `python -m isostyle build`, `speculative`, `evals`, `export`, then
`neolith-convert --attach-samples data/isostyle/speculative/ancestry_samples.json` (or `make maps`).
