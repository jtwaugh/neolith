# neolith

**Why can't anyone build a Paradox game set in the Neolithic?**

A grand-strategy map needs every province filled: who lived there, how many, what they made, what
they ate. For 10,000–3,000 BCE across west Eurasia and north-east Africa, this project tries to fill
that map from open archaeological and palaeoenvironmental data. Then it measures how much of the
map the record can actually support, and why the rest is empty.

The short answer: we know far less than we think, and what we know is shaped by where archaeologists
have dug and published, more than by where people lived.

## What the data shows

- **About a third.** A detection model (research effort, drowned land, acid soil) estimates how many
  sites would be known if nothing hid them. Against that, the dated-site list holds roughly a third at
  every epoch: 436 against about 1,350 at 10,000 BCE, and 5,132 against about 15,500 at 4,000 BCE
  (`data/population/SOURCES.md`).
- **Research effort, not population, predicts where sites are.** Modelled forager and farmer density
  barely predicts site counts, with an exponent near zero. The amount of later-period archaeology
  nearby does predict them.
- **Modern borders show through.** Britain and Ireland have 17.8 dates per 1,000 km². Ukraine,
  Belarus and European Russia have 0.11, a 160-fold difference. Hungary has 13.2 and Romania 1.6
  (`data/isostyle/audit/AUDIT.md`).
- **Whole literatures are missing from open data.** No open compilation was found for the
  Neolithic of Ukraine, Belarus, European Russia or the Caucasus, for the Baltic states or Finland,
  or for the Mesolithic as such. The sites were dug and published, but not in a form anyone can
  download.
- **The emptiest places are interesting ones.** The Amu Darya delta, the Horn of Africa coast
  (Guardafui, Bab-el-Mandeb, the Dahlak islands), Sistan and Doggerland have no dated site in any
  epoch (`build/critic/places/index.md`, `data/places/plans/`).

## Three grades of claim, kept apart

- **Recorded:** about 8,100 dated settlements built from about 50,000 radiocarbon dates (XRONOS,
  p3k14c, NeoNet, AADR and transcribed literature), plus 34 evidence layers. The layers cover pottery,
  cereals, livestock, megaliths, aDNA haplogroups, pollen and more, smoothed with bootstrap
  firmness (`data/settlements/`, `data/isostyle/`).
- **Modelled:** palaeo-terrain and climate (Beyer et al. 2020, ETOPO1, a sea-level curve, rivers,
  lakes), productivity, expected population (Tallavaara et al. 2018) and a farming front. These say
  what *should* be there.
- **Speculative and inferred:** 809 reasoned judgements about what probably lies in each gap,
  each with a cause, a confidence and literature (`data/isostyle/intuitions/`), plus 55 inferred
  settlements. They are drawn pale and labelled as speculation. They never replace a recorded
  value, and they never feed the residuals.

## What's here

| Path | What |
|---|---|
| `neolith-rs/` | The app: a 3D hex game board (Rust, egui/wgpu; native and WebAssembly). Map modes for terrain, climate, productivity, expected population, evidence and missing sites, plus a hex inspector, timeline and editor. Deployed to Vercel. |
| `pipeline/` | Builds the hex world (`world.bin`) from the raw data: terrain, sea level, rivers, settlements, population residuals. |
| `isostyle/` | The evidence atlas: fetches the open datasets, builds the per-layer surfaces, audits the gaps and fills them speculatively. |
| `data/` | Everything the pipelines write or read by hand, each dataset with its own `SOURCES.md`. |
| `.claude/agents/` | The critic agents that write the gap judgements, the place plans and the look-and-feel reviews. |

## Run

```sh
make test                       # pipeline + isostyle tests
make maps                       # rebuild neolith-rs/assets/world.bin (downloads ETOPO1, BIOME4, HydroRIVERS)
make settlements                # rebuild the settlement list from XRONOS etc. (~660 MB of downloads)
cd neolith-rs && ./run.sh       # native app; `trunk serve` for the web build
```

See `pipeline/README.md`, `isostyle/README.md` and `neolith-rs/README.md` for details, and
`docs/POSITIONING.md` for who this is for.

## Licence and credits

Code is MIT (`LICENSE`). The derived data is CC BY-SA 4.0 (`LICENSE-DATA`). Every upstream source,
with its licence and citation, is in **`ATTRIBUTIONS.md`**, generated from `data/ATTRIBUTIONS.toml`.
The app shows the same list under *Credits & data*. Rust dependencies are listed in `THIRD_PARTY.md`.

This began in 2023 as a Django/Leaflet prototype ("a Paradox map-staring game set in the
Neolithic"); `SPEC.md` describes that version, which has since been removed.
