# Neolith

## Token hygiene
- Never cat/Read whole data files (`*.geojson`, `*.csv.gz`, `*.json` under `data/`). Use jq/python one-liners, `head -n`, `wc`, or Read with offset/limit.
- Pipe long command output through `| tail -n 40` or `| grep`; pipeline scripts should print a summary, not dumps.
- Locate with `grep -n`, then Read with offset/limit; avoid long `sed -n` ranges over big files.
- Replies and agent reports: terse, findings first, no restating the task.
- Subagents: give each a narrow scope (one region/layer/period), what's already ruled out, and a turn budget. Do mechanical edits inline rather than delegating them.
