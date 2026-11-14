"""The state of the game on one page: `python -m pipeline state`.

Runs the cheap, deterministic checks that already exist (tests, validators,
the isostyle evals, the terrain screens, the built map's report) and the
famous-site check, and writes data/state/scorecard.json and data/state/STATE.md.
Both are tracked, so git history is the trend line.

Every row has a value, an optional target from data/state/targets.toml and a
delta against the last scorecard. Only rows whose target says `gate = true`
can fail the run (exit 1); the rest are reported, not enforced. Critic runs
(data/state/critics/*.json, written by the agents in .claude/agents/) are
summarised with their age, so an old score reads as old.

    python -m pipeline state [--skip cargo,web,evals,python] [--no-write]
"""
import glob
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import tomllib
import unicodedata

STATE_DIR = "data/state"
TARGETS = os.path.join(STATE_DIR, "targets.toml")
SPAN = (-10000, -3000)  # the game's years


# --- rows -------------------------------------------------------------------

def row(section, name, value, note="", unit=""):
    return {"section": section, "name": name, "value": value, "note": note, "unit": unit}


def apply_targets(rows, targets):
    """Set `ok` (True/False, or None with no target) and `gate` on each row."""
    for r in rows:
        t = targets.get(r["name"], {})
        v = r["value"]
        r["gate"] = bool(t.get("gate", False))
        r["target"] = _target_text(t)
        if not t or v is None or isinstance(v, str):
            r["ok"] = None if not t or v is None else v == t.get("equals", v)
            continue
        ok = True
        if "min" in t:
            ok &= v >= t["min"]
        if "max" in t:
            ok &= v <= t["max"]
        if "equals" in t:
            ok &= v == t["equals"]
        r["ok"] = bool(ok)
    return rows


def _target_text(t):
    parts = []
    if "equals" in t:
        parts.append(f"= {t['equals']}")
    if "min" in t:
        parts.append(f"≥ {t['min']}")
    if "max" in t:
        parts.append(f"≤ {t['max']}")
    return " ".join(parts)


def add_deltas(rows, previous):
    old = {r["name"]: r.get("value") for r in (previous or {}).get("rows", [])}
    for r in rows:
        a, b = old.get(r["name"]), r["value"]
        num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)
        r["delta"] = round(b - a, 4) if num(a) and num(b) and b != a else None
    return rows


# --- health -----------------------------------------------------------------

def _run(cmd, cwd=None, timeout=1800):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def parse_unittest(text):
    """(tests run, failures + errors) from unittest's summary."""
    ran = re.search(r"Ran (\d+) tests?", text)
    bad = re.search(r"FAILED \(([^)]*)\)", text)
    n_bad = sum(int(x) for x in re.findall(r"(?:failures|errors)=(\d+)", bad.group(1))) if bad else 0
    return (int(ran.group(1)) if ran else 0), n_bad


def parse_cargo(text):
    """(passed, failed, compiled) summed over cargo test's result lines."""
    passed = sum(int(x) for x in re.findall(r"test result: \w+\. (\d+) passed", text))
    failed = sum(int(x) for x in re.findall(r"(\d+) failed;", text))
    compiled = "could not compile" not in text and "error[E" not in text
    return passed, failed, compiled


def health(skip, log):
    rows = []
    if "python" not in skip:
        n = bad = 0
        for d in ("pipeline/tests", "isostyle/tests"):
            code, out = _run([sys.executable, "-m", "unittest", "discover", "-s", d, "-t", "."])
            a, b = parse_unittest(out)
            n, bad = n + a, bad + b + (1 if code and not b else 0)
        rows += [row("Health", "python tests failing", bad, f"{n} run (`make test`)")]
        log(f"python tests: {n} run, {bad} failing")
    if "cargo" not in skip:
        code, out = _run(["cargo", "test", "--workspace", "-q"], cwd="neolith-rs")
        passed, failed, compiled = parse_cargo(out)
        if not compiled:
            failed = max(failed, 1)
        rows += [row("Health", "rust tests failing", failed,
                     f"{passed} passed (`cargo test --workspace`)" + ("" if compiled else "; did not compile"))]
        log(f"cargo tests: {passed} passed, {failed} failing")
    if "cargo" not in skip and "web" not in skip:
        # A smoke test of the web build: the app type-checks for the browser
        # target. Not the whole of `trunk build` (no bundling, no wasm-opt),
        # but it catches native-only code reaching the web app, and needs no trunk.
        code, out = _run(["cargo", "check", "-p", "neolith-app", "--target", "wasm32-unknown-unknown", "-q"], cwd="neolith-rs")
        errors = len(re.findall(r"^error", out, re.M)) or (1 if code else 0)
        note = "`cargo check --target wasm32-unknown-unknown`"
        if code and "target may not be installed" in out:
            note += "; needs `rustup target add wasm32-unknown-unknown`"
        rows += [row("Health", "web build errors", errors, note)]
        log(f"web build check: {errors} errors")
    from . import places
    cfg = tomllib.load(open("pipeline/config.toml", "rb"))
    msgs = []
    n = places.check(cfg, log=msgs.append)
    rows.append(row("Health", "place plan problems", n, msgs[-1] if msgs else ""))
    sys.path.insert(0, ".")
    from isostyle import intuitions
    icfg = tomllib.load(open("isostyle/config.toml", "rb"))
    imsgs = []
    ok = intuitions.run(icfg, log=imsgs.append)
    bad = sum("problems" in m for m in imsgs)
    rows.append(row("Health", "intuition files invalid", 0 if ok else max(bad, 1),
                    f"{sum(m.startswith('intuitions: ') and 'judgements' in m for m in imsgs)} files"))
    return rows


# --- speculative fill ---------------------------------------------------------

def fill(log):
    from isostyle import evals
    icfg = tomllib.load(open("isostyle/config.toml", "rb"))
    res, _ = evals.measure(icfg, log=lambda m: None)
    failing = sum(not r["ok"] for r in res["regressions"])
    bad = [k for k, v in res["guards"].items() if not v]
    log(f"evals: score {res['score']:.3f}, {failing}/{len(res['regressions'])} cases failing")
    o = res["overall"]
    return [
        row("Speculative fill", "evals guards failing", len(bad), ", ".join(bad) or "observed, coverage, holdout, drift, spread, regressions"),
        row("Speculative fill", "evals score", round(res["score"], 3), "1.0 = the unsmoothed fill; lower is smoother"),
        row("Speculative fill", "regression cases failing", failing,
            f"of {len(res['regressions'])}; allowed {res['allowed_failing']} (data/isostyle/evals/regressions.toml)"),
        row("Speculative fill", "holdout error", round(o["holdout"], 4)),
        row("Speculative fill", "flicker", round(o["flicker"], 3), "mean over layers (isostyle/evals.py)"),
    ]


# --- terrain ------------------------------------------------------------------

def parse_anchors(text):
    m = re.search(r"Same main game class: \d+ \((\d+)%\); compatible[^:]*: \d+ \((\d+)%\)", text)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def parse_suspects(line):
    return {k: int(n) for n, k in re.findall(r"(\d+) ([a-z ]+?)(?:,|$)", line.split(": ", 1)[-1])}


def terrain(log):
    rows = []
    path = "data/terrain/anchors_report.md"
    if os.path.exists(path):
        same, compat = parse_anchors(open(path).read())
        rows += [row("Terrain", "pollen anchors same class", same, "at 6 ka, published vs map", "%"),
                 row("Terrain", "pollen anchors compatible", compat, "at 6 ka", "%")]
    if os.path.exists("build/combined_map.geojson"):
        from . import look
        cfg = tomllib.load(open("pipeline/config.toml", "rb"))
        with tempfile.TemporaryDirectory() as d:
            line = look.suspects(cfg, d)
        counts = parse_suspects(line)
        log(f"suspects: {counts}")
        rows.append(row("Terrain", "terrain suspects", sum(counts.values()),
                        ", ".join(f"{v} {k}" for k, v in counts.items()) + " (`python -m pipeline suspects`)"))
    return rows


# --- the built map ------------------------------------------------------------

def parse_report(text):
    out = {}
    m = re.search(r"Grid: (\d+) hexes", text)
    out["hexes"] = int(m.group(1)) if m else None
    m = re.search(r"(\d+) of (\d+) settlements have their own hex as Water", text)
    if m:
        out["on_water"], out["settlements"] = int(m.group(1)), int(m.group(2))
    sec = text.split("## Settlements on Water", 1)[-1].split("\n## ", 1)[0]
    # The "Longest on Water" table: the last column is years offshore.
    cells = [ln.strip(" |").split("|") for ln in sec.splitlines() if ln.startswith("| ") and "settlement" not in ln]
    out["offshore"] = sum(1 for c in cells if c[-1].strip().isdigit() and int(c[-1]) > 0)
    return out


def world(log):
    rows = []
    if os.path.exists("build/report.md"):
        r = parse_report(open("build/report.md").read())
        rows += [row("Map", "settlements", r.get("settlements"), "in build/settlements.geojson"),
                 row("Map", "settlements on water", r.get("on_water"), f"{r.get('offshore')} offshore (build/report.md)")]
    if os.path.exists("build/settlements.geojson"):
        feats = json.load(open("build/settlements.geojson"))["features"]
        garbled = [f["properties"]["name"] for f in feats if re.search(r"[?�]|Ã|Â", f["properties"]["name"] or "")]
        rows.append(row("Map", "garbled site names", len(garbled), ", ".join(garbled[:6])))
    path = "data/population/residuals.json"
    if os.path.exists(path):
        d = json.load(open(path))
        last = d["by_year"][max(d["by_year"], key=int)]
        y = max(d["by_year"], key=int)
        hid = 1 - last["sites"] / last["sites_if_nothing_hid_them"] if last["sites_if_nothing_hid_them"] else None
        rows += [row("Population", "sites hidden by visibility", round(100 * hid) if hid is not None else None,
                     f"{last['sites']} recorded vs {last['sites_if_nothing_hid_them']:.0f} expected at {-int(y)} BCE", "%"),
                 row("Population", "unexplained shortfall hexes", last["outcomes"].get("unexplained shortfall"),
                     f"at {-int(y)} BCE (data/population/residuals.json)")]
    return rows


# --- famous sites -------------------------------------------------------------

_FOLD = {"ı": "i", "ø": "o", "ł": "l", "đ": "d", "ß": "ss"}


def fold(s):
    """renown.rs `fold`: lower case, accents off, apostrophes dropped, other punctuation a space."""
    s = "".join(_FOLD.get(c, c) for c in (s or "").lower())
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"['’‘ʿʾ]", "", s)
    s = "".join(c if c.isalnum() else " " for c in s)
    return " ".join(s.split())


def km(a, b):
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    c = math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(math.radians(a[0] - b[0]))
    return 6371.0 * math.acos(max(-1.0, min(1.0, c)))


def famous_sites(entries, settlements):
    """One result per renown entry: the records that match it the way the app
    matches them (renown.rs `lookup`), the primary one, and what is wrong.

    An entry's `parts` names records that are separate parts of the site
    (Çatalhöyük West, a named Fayum locality): matched like aliases, as whole
    words. A part is never a stray record however far it sits from the
    primary, and is the primary only when no other record matches."""
    keys = [(e, [fold(n) for n in [e["name"], *e.get("aliases", [])]]) for e in entries]
    parts = [[p for n in e.get("parts", []) if (p := fold(n))] for e in entries]

    def is_part(i, s):
        name = f" {fold(s['name'])} "
        return any(f" {p} " in name for p in parts[i])

    hits = {i: [] for i in range(len(entries))}
    for s in settlements:
        name = f" {fold(s['name'])} "
        best = None
        for i, (e, names) in enumerate(keys):
            d = km((e["lon"], e["lat"]), s["pos"])
            if d <= e.get("radius_km", 15.0) and any(n and f" {n} " in name for n in names):
                if best is None or d < best[1]:
                    best = (i, d)
        if best:
            hits[best[0]].append((best[1], s))
    out = []
    for i, (e, _) in enumerate(keys):
        recs = sorted(hits[i], key=lambda t: (is_part(i, t[1]), round(t[0]), fold(t[1]["name"]) != fold(e["name"])))
        problems = []
        if not recs:
            problems.append("not on the map")
        else:
            s = recs[0][1]
            f, a = s.get("founding"), s.get("abandoned")
            occ = s.get("occupation") or ([[f, a]] if f is not None and a is not None else [])
            if occ and not any(lo <= SPAN[1] and hi >= SPAN[0] for lo, hi in occ):
                problems.append("dated outside 10,000-3,000 BCE")
            far = [r for d, r in recs[1:] if km(r["pos"], s["pos"]) > 2.0 and not is_part(i, r)]
            if far:
                problems.append(f"{len(far)} more records over 2 km away")
        out.append({"name": e["name"], "renown": e["renown"], "records": len(recs), "problems": problems})
    return out


def famous(log):
    path = "neolith-rs/crates/app/assets/renown.json"
    if not (os.path.exists(path) and os.path.exists("build/settlements.geojson")):
        return [], []
    entries = json.load(open(path))["site"]
    sets = [{"name": f["properties"]["name"], "pos": tuple(f["geometry"]["coordinates"][:2]),
             "founding": f["properties"].get("founding"), "abandoned": f["properties"].get("abandoned"),
             "occupation": f["properties"].get("occupation")}
            for f in json.load(open("build/settlements.geojson"))["features"]]
    res = famous_sites(entries, sets)
    missing = [r["name"] for r in res if "not on the map" in r["problems"]]
    off = [r["name"] for r in res if any(p.startswith("dated") for p in r["problems"])]
    dup = [r["name"] for r in res if any("more records" in p for p in r["problems"])]
    log(f"famous sites: {len(res) - len(missing)}/{len(res)} on the map")
    return [
        row("Famous sites", "famous sites missing", len(missing), ", ".join(missing) or f"all {len(res)} renown.json sites matched"),
        row("Famous sites", "famous sites dated off the map", len(off), ", ".join(off)),
        row("Famous sites", "famous sites with stray records", len(dup), ", ".join(dup)),
    ], res


# --- research debt --------------------------------------------------------------

def research(log):
    unchecked = total = 0
    for p in glob.glob("data/isostyle/intuitions/*.toml"):
        for j in tomllib.load(open(p, "rb")).get("judgement", []):
            for c in j.get("literature", []):
                total += 1
                unchecked += isinstance(c, dict) and not c.get("checked", False)
    open_items = items = sites = sites_unchecked = 0
    for p in glob.glob("data/places/plans/*.toml"):
        d = tomllib.load(open(p, "rb"))
        for r in d.get("research", []):
            items += 1
            open_items += r.get("status", "open") == "open"
        for k in d.get("known_site", []):
            sites += 1
            sites_unchecked += not k.get("checked", True)
    return [
        row("Research debt", "unchecked intuition citations", unchecked, f"of {total} (data/isostyle/intuitions)"),
        row("Research debt", "open place research items", open_items, f"of {items} (data/places/plans, `status`)"),
        row("Research debt", "unchecked known sites in plans", sites_unchecked, f"of {sites}"),
    ]


# --- fixed views (pipeline/visual.py) -------------------------------------------

def visual(today=None):
    path = os.path.join(STATE_DIR, "visual.json")
    if not os.path.exists(path):
        return []
    d = json.load(open(path))
    today = today or time.strftime("%Y-%m-%d")
    age = int((time.mktime(time.strptime(today, "%Y-%m-%d")) - time.mktime(time.strptime(d["date"], "%Y-%m-%d"))) / 86400)
    by = lambda st: [v["name"] for v in d["views"] if v["status"] == st]
    note = f"`make state-visual`, {age} days ago"
    return [row("Fixed views", "views failed to render", len(by("failed")), ", ".join(by("failed")) or note),
            row("Fixed views", "views changed since accepted", len(by("changed")),
                (", ".join(by("changed")) + "; look, then `make state-visual GOLDEN=1`") if by("changed") else note)]


# --- clicking and UI stability (pipeline/interact.py) --------------------------------

def interact(today=None):
    path = os.path.join(STATE_DIR, "interact.json")
    if not os.path.exists(path):
        return []
    d = json.load(open(path))
    s = d["summary"]
    today = today or time.strftime("%Y-%m-%d")
    age = int((time.mktime(time.strptime(today, "%Y-%m-%d")) - time.mktime(time.strptime(d["date"], "%Y-%m-%d"))) / 86400)
    pct = lambda x: round(100 * x)
    n = sum(c["pieces"] for c in d["clicks"])
    def worst(k):
        from .interact import CONTROLS
        pick = (lambda m: m["widget"].split(" ", 1)[0] in CONTROLS) if k == "controls_moved" else (lambda m: True)
        return "; ".join(u["action"] + ": " + ", ".join(f"{m['widget']} {m['px']} px" for m in u["moved"] if pick(m))
                         for u in d["ui"] if u.get(k))
    src = f"`make state-ui`, {age} days ago"
    return [
        row("Clicking and UI", "piece clicks that open the piece", pct(s["piece_click_rate"]), f"{n} pieces in {len(d['clicks'])} views; {src}", "%"),
        row("Clicking and UI", "off-centre clicks that open the piece", pct(s["off_centre_click_rate"]),
            f"{d['settings']['jitter_px']} px off centre", "%"),
        row("Clicking and UI", "name clicks that open the site", pct(s["name_click_rate"]), "clicking a drawn settlement name", "%"),
        row("Clicking and UI", "crowded pieces", pct(s["crowded_share"]),
            f"on-screen pieces with another within {d['settings']['crowd_px']} px", "%"),
        row("Clicking and UI", "clicks that moved the camera", s["camera_moved_on_click"]),
        row("Clicking and UI", "controls that moved under the player", s.get("ui_controls_moved", 0), worst("controls_moved")),
        row("Clicking and UI", "labels that moved under the player", s["ui_widgets_moved"] - s.get("ui_controls_moved", 0),
            worst("widgets_moved")),
    ] + ([row("Performance", "board pass time", s["board_pass_ms"],
              f"GPU ms per board pass, worst of {len(d.get('perf', []))} views at {d['settings'].get('size', '1600x1000')}; "
              f"mean {s['board_pass_mean_ms']} ms; {src}", " ms")] if s.get("board_pass_ms") is not None else [])


# --- colour (neolith-rs palette.rs, `ramp_contrast_audit`) --------------------------

def ramps(skip, log):
    """Neighbouring steps of the map-mode ramps that are hard to tell apart with
    red-green colour blindness. The numbers come from a Rust test that prints them."""
    if "cargo" in skip:
        return []
    code, out = _run(["cargo", "test", "-q", "-p", "neolith-app", "ramp_contrast_audit", "--", "--nocapture"], cwd="neolith-rs")
    m = re.search(r"^RAMP_AUDIT (\{.*\})$", out, re.M)
    if not m:
        return [row("Map", "ramp steps hard to tell apart colour-blind", None, "the audit did not run (`cargo test -p neolith-app ramp_contrast_audit`)")]
    d = json.loads(m.group(1))
    log(f"ramp contrast: {d['weak_steps']} weak steps, least {d['least']} at {d['least_at']}")
    note = (", ".join(d["weak"]) + "; " if d["weak"] else "") + (
        f"{d['ramps']} ramps, protanopia and deuteranopia; a step is weak under ΔE {d['min_step']:g}; least {d['least']} ({d['least_at']})")
    return [row("Map", "ramp steps hard to tell apart colour-blind", d["weak_steps"], note)]


# --- critics --------------------------------------------------------------------

def critics(today=None):
    """The latest run of each critic in data/state/critics/<date>-<critic>.json."""
    today = today or time.strftime("%Y-%m-%d")
    latest = {}
    for p in sorted(glob.glob(os.path.join(STATE_DIR, "critics", "*.json"))):
        d = json.load(open(p))
        latest[d["critic"]] = (p, d)
    out = []
    for name, (p, d) in sorted(latest.items()):
        f = d.get("findings", [])
        age = (time.mktime(time.strptime(today, "%Y-%m-%d")) - time.mktime(time.strptime(d["date"], "%Y-%m-%d"))) / 86400
        out.append({"critic": name, "date": d["date"], "age_days": int(age), "rubric": d.get("rubric_version"),
                    "overall": d.get("overall"), "open": sum(x.get("status", "open") == "open" for x in f),
                    "findings": len(f), "file": p})
    return out


# --- freshness ------------------------------------------------------------------

FRESH = [
    ("build/report.md", ["pipeline/config.toml", "data/settlements/settlements.geojson"], "make maps"),
    ("neolith-rs/assets/world.bin", ["build/combined_map.geojson", "build/settlements.geojson"], "make maps"),
    ("data/terrain/anchors_report.md", ["build/combined_map.geojson"], "make anchors"),
    ("data/isostyle/evals/report.md", ["data/isostyle/evals/regressions.toml", "isostyle/config.toml",
                                       "data/isostyle/surfaces.csv.gz"], "python -m isostyle evals"),
    ("data/isostyle/speculative/speculative.csv.gz", ["data/isostyle/intuitions"], "python -m isostyle speculative"),
    # `make residuals` writes world.bin after residuals.json, so compare with its input instead.
    ("data/population/residuals.json", ["build/settlements.geojson"], "make residuals"),
]


def _mtime(p):
    if os.path.isdir(p):
        return max((os.path.getmtime(f) for f in glob.glob(os.path.join(p, "*"))), default=0)
    return os.path.getmtime(p) if os.path.exists(p) else None


def freshness():
    out = []
    for art, srcs, cmd in FRESH:
        a = _mtime(art)
        if a is None:
            out.append(f"`{art}` is missing (`{cmd}`)")
            continue
        newer = [s for s in srcs if (_mtime(s) or 0) > a + 1]
        if newer:
            out.append(f"`{art}` is older than {', '.join(f'`{s}`' for s in newer)} (`{cmd}`)")
    return out


# --- output -----------------------------------------------------------------------

def _fmt(v, unit=""):
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{v:g}{unit}"
    return f"{v}{unit}"


def render(card):
    mark = {True: "ok", False: "**FAIL**", None: ""}
    lines = ["# State of the game", "",
             f"`python -m pipeline state` at {card['commit']}{' (uncommitted changes)' if card['dirty'] else ''}, "
             f"{card['date']}. Targets in `data/state/targets.toml`; only gated rows fail the run. "
             f"Result: **{'pass' if card['pass'] else 'FAIL'}**.", ""]
    section = None
    for r in card["rows"]:
        if r["section"] != section:
            section = r["section"]
            lines += ["", f"## {section}", "", "| | Measure | Now | Change | Target | Note |", "|---|---|---|---|---|---|"]
        tgt = r["target"] + (" (gate)" if r["gate"] else "") if r["target"] else ""
        d = r.get("delta")
        delta = "" if d is None else (f"+{d:g}" if d > 0 else f"{d:g}")
        lines.append(f"| {mark[r['ok']]} | {r['name']} | {_fmt(r['value'], r['unit'])} | {delta} | {tgt} | {r['note']} |")
    fs = card.get("famous", [])
    bad = [f for f in fs if f["problems"]]
    if bad:
        lines += ["", "### Famous sites with problems", ""]
        lines += [f"- {f['name']} (renown {f['renown']}, {f['records']} records): {'; '.join(f['problems'])}" for f in bad]
    lines += ["", "## Critics", "",
              "Latest structured run of each agent in `.claude/agents/` (`data/state/critics/`). "
              "Scores are the model's own judgement against `neolith-rs/harness/CRITIC.md`; re-run a critic when its age matters.", ""]
    if card["critics"]:
        lines += ["| Critic | Date | Age (days) | Rubric | Overall | Open findings |", "|---|---|---|---|---|---|"]
        for c in card["critics"]:
            lines.append(f"| {c['critic']} | {c['date']} | {c['age_days']} | {c['rubric'] or ''} | "
                         f"{_fmt(c['overall'])} | {c['open']} of {c['findings']} |")
    else:
        lines.append("No structured critic runs yet.")
    lines += ["", "## Stale inputs", ""]
    lines += [f"- {s}" for s in card["stale"]] or ["None."]
    return "\n".join(lines) + "\n"


def _git():
    rc, sha = _run(["git", "rev-parse", "--short", "HEAD"])
    _, st = _run(["git", "status", "--porcelain"])
    return sha.strip() if rc == 0 else "?", bool(st.strip())


def run(skip=(), write=True, log=print):
    targets = tomllib.load(open(TARGETS, "rb")).get("row", {}) if os.path.exists(TARGETS) else {}
    rows = health(skip, log)
    if "evals" not in skip:
        rows += fill(log)
    rows += terrain(log) + world(log) + ramps(skip, log)
    frows, fres = famous(log)
    rows += frows + research(log) + visual() + interact()
    apply_targets(rows, targets)
    path = os.path.join(STATE_DIR, "scorecard.json")
    prev = json.load(open(path)) if os.path.exists(path) else None
    add_deltas(rows, prev)
    commit, dirty = _git()
    card = {"date": time.strftime("%Y-%m-%d"), "commit": commit, "dirty": dirty, "skipped": sorted(skip),
            "pass": all(r["ok"] is not False for r in rows if r["gate"]),
            "rows": rows, "famous": fres, "critics": critics(), "stale": freshness()}
    if write:
        os.makedirs(STATE_DIR, exist_ok=True)
        json.dump(card, open(path, "w"), indent=1, ensure_ascii=False)
        open(os.path.join(STATE_DIR, "STATE.md"), "w").write(render(card))
        log(f"wrote {STATE_DIR}/STATE.md and scorecard.json")
    failed = [r["name"] for r in rows if r["gate"] and r["ok"] is False]
    log(("state: pass" if card["pass"] else "state: FAIL: " + ", ".join(failed)))
    return card
