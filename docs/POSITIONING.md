# Who is this for?

*Memo, 2026-11-13. Written after an audit of the repository (licences, attributions, pruning).*

## What we actually have

As a game, Neolith is a good-looking map with nothing to do. The look-and-feel critic scored it
1.4/5 against shipped grand-strategy games: "no player, no goal and no verb"
(`build/critic/20261112-0104/report.md`).

As an instrument for measuring what archaeology does and doesn't know about 10,000–3,000 BCE, it is
unusual. Few public tools put these four things on one map and keep them apart:

1. **The record.** About 8,100 dated sites and about 50,000 dates from open compilations, plus 34
   evidence layers with bootstrap firmness.
2. **An expectation.** Palaeo-terrain, productivity and forager/farmer density, which say where
   people *should* have been.
3. **The difference, explained.** A detection model separates "no one lived here" from "no one
   looked" (research effort), "it's under the sea" (drowned) and "bone doesn't survive here"
   (acid soil). Its headline: the open record holds about a third of what full visibility would
   show, at every epoch. Effort, not population, predicts where sites are.
4. **Reasoned guesses about every gap.** 809 cause-coded judgements, each with a confidence, the
   literature checked and what evidence would settle it. They are kept visibly apart from the
   record.

The "why can't we build a Paradox game of this era?" framing is the hook. A province map forces
you to put a value in every hex, so it makes every blind spot obvious.

## Audiences, most actionable first

### 1. Research-data infrastructure people

XRONOS, Open Context, ARIADNE, c14bazAAR, national heritage databases, and funders of
digitisation.

**What they get:** a ranked digitisation agenda. The gap judgements tag 168 gaps
`not_in_open_compilations` and 59 `publication_access`. The audit names the regions with no open
compilation: the Neolithic of Ukraine, Belarus, European Russia and the Caucasus; the Baltics;
Finland; the Mesolithic as such. The place plans (`data/places/plans/`) name specific archives,
such as the EES Delta Survey with 783 Nile delta sites. "Fund the aggregation of X, and the map
gains Y" is a concrete pitch to people who allocate exactly that money.

**What they need from us:**
- a short public write-up of the method and the ranked list;
- the residuals as a downloadable table;
- an honest error budget.

### 2. Archaeologists and teachers

**What they get:** a hands-on demonstration of visibility bias. Students can toggle between the
expected-population and missing-sites modes and watch modern borders appear in prehistoric data.
It suits teaching on sampling, target-group background, taphonomy and drowned landscapes.
Specialists can disagree with a specific gap judgement, and each one is written to be argued with.

**What they need:**
- a stable public URL;
- a "how to read this" page;
- a way to send corrections. The judgements already say what evidence would settle them.

### 3. Game designers and worldbuilders

**What they get:**
- a plausible, sourced palaeo-world (terrain, coasts, rivers, climate) for 10,000–3,000 BCE;
- a speculative fill that is clearly marked as such: a defensible starting point for a map, a
  setting or a novel.

The data licence (CC BY-SA 4.0) allows commercial use, which is why the non-commercial inputs were
removed.

**What they need:** exports (per-epoch GeoJSON or PNG) and a plain-language guide to which layers
are record, model and guess.

### 4. Science communicators and the curious public

**What they get:** a story with a map. "We know where archaeologists worked, not where people
lived." "Doggerland, the Persian Gulf and the Red Sea mouth are blank because they're under water
or under-studied, not because they were empty." The Paradox angle reaches the large
history-strategy audience.

**What they need:** one explainer page that works on a phone, with three or four map moments.

## Weaknesses to state up front

- **Model artefacts:** the Sahel band and the Pontic block in the residuals come from the
  farmability rules, not the data. The farming front's median misfit is about 700 years. Both are
  documented in `data/population/SOURCES.md`.
- **Unchecked citations:** 399 of the gap critic's citations are marked `checked = false`.
- **Coverage depends on what is open.** Missing closed compilations (14SEA, CalPal) is part of the
  finding, but it also means the absolute numbers will move.
- **Some licences are unconfirmed.** `ATTRIBUTIONS.md` lists the ones still to confirm, and the
  terrain keyframes depend on the QEN maps.
- **The app is not yet a game.** If the game is the goal, it needs a player, a goal and a verb.

## Candidate next steps (not committed to)

1. A public explainer page: "Why there's no Paradox game of the Neolithic", built from the
   residual maps, the border-density table and the emptiest places.
2. A *Blind spots* map mode in the app that merges the missing-sites, firmness and judgement-cause
   layers into one view, coloured by *why* each place is blank.
3. A short preprint or blog post on the visibility-bias result, with the ranked digitisation
   agenda as its practical output, sent to the XRONOS and c14bazAAR maintainers.
4. Downloadable exports: residuals, per-layer surfaces and the gap judgements as CSV/GeoJSON,
   under the data licence.
