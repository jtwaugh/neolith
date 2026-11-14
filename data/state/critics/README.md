# Critic runs

One JSON file per run of a critic agent (`.claude/agents/*-critic.md`), named
`<YYYY-MM-DD>-<critic>.json`. `python -m pipeline state` shows the latest run
of each critic in `data/state/STATE.md`, with its age. Prose reports and
screenshots stay under `build/critic/` (untracked); this is the part that lasts.

```json
{
  "critic": "gsg-critic",
  "date": "2026-11-13",
  "rubric_version": "9-category-v2",
  "report": "build/critic/20261113-1200/report.md",
  "overall": 1.9,
  "scores": {"map_hero": 2, "labels": 2},
  "findings": [
    {"id": "gsg-2026-11-13-01", "title": "One line naming the problem",
     "severity": "high|medium|low", "status": "open|fixed|wontfix",
     "where": "file:line or place/year", "check": "a command or state row that shows it fixed"}
  ]
}
```

- `overall` and `scores` only for critics with a rubric (gsg, greatest-hits).
  Scores from different `rubric_version`s are not comparable.
- Keep finding ids stable across runs: when a later run sees an earlier finding
  fixed, it copies the id with `"status": "fixed"`, so the record shows what
  changed.
- `check` should point at something mechanical where possible: a
  `data/state/targets.toml` row, an `isostyle evals` regression case, a
  `pipeline suspects` id, or a harness `state` assertion. A finding with a
  mechanical check can be added as a target and stop depending on the critic.
- Subagents may not be able to Write: the critic then puts this JSON at the end
  of its reply, and the caller saves it here.
- Files dated 2026-11-12 were backfilled from the saved prose reports on
  2026-11-13, with each finding's status checked against the code that day.
