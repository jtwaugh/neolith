#!/usr/bin/env python3
"""Audit Claude Code token spend for this project.

Reads the transcripts Claude Code keeps under
~/.claude/projects/<project-slug>/ (main sessions plus their subagents),
prices every API response, and writes a self-contained HTML report with
charts, plus a short text summary on stdout.

    python3 scripts/token_audit.py                  # this repo
    python3 scripts/token_audit.py --since 2026-11-01 --out /tmp/audit.html
    python3 scripts/token_audit.py --json audit.json

Costs are estimates at list API prices (see PRICES); they track Claude
Code's own `cost-state` totals closely but ignore plan/subscription billing.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import html
import json
import os
import re
import sys
from pathlib import Path

# $/MTok: input, output, cache read. Cache writes are 1.25x input (5m TTL)
# and 2x input (1h TTL). Fast mode doubles everything.
PRICES = {
    "claude-fable-5-2": (8.0, 40.0, 0.20),
    "claude-fable-5-1": (10.0, 50.0, 1.00),
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-opus-5": (5.0, 25.0, 0.50),
    "claude-opus-4-8": (5.0, 25.0, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10),
    "claude-sonnet-5": (2.0, 10.0, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-haiku-4-5": (1.0, 5.0, 0.10),
}
WEB_SEARCH_PER_REQ = 0.01
CHARS_PER_TOKEN = 4  # rough, for tool-result sizing only
COMPACT_AT = 200_000  # context size at which a session "should" have been compacted/cleared


def project_dir(cwd: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(cwd))
    return Path.home() / ".claude" / "projects" / slug


def price(model: str, u: dict, speed: str | None) -> dict:
    pin, pout, pread = PRICES.get(model, PRICES["claude-opus-5-5"])
    mult = 2.0 if speed == "fast" else 1.0
    cc = u.get("cache_creation") or {}
    w5 = cc.get("ephemeral_5m_input_tokens", 0) or 0
    w1 = cc.get("ephemeral_1h_input_tokens", 0) or 0
    wtot = u.get("cache_creation_input_tokens", 0) or 0
    if w5 + w1 < wtot:  # breakdown missing: assume 5m
        w5 += wtot - w5 - w1
    parts = {
        "input": (u.get("input_tokens", 0) or 0) * pin,
        "cache_write": w5 * pin * 1.25 + w1 * pin * 2.0,
        "cache_read": (u.get("cache_read_input_tokens", 0) or 0) * pread,
        "output": (u.get("output_tokens", 0) or 0) * pout,
    }
    parts = {k: v * mult / 1e6 for k, v in parts.items()}
    stu = u.get("server_tool_use") or {}
    parts["web_search"] = (stu.get("web_search_requests", 0) or 0) * WEB_SEARCH_PER_REQ
    return parts


def text_len(content) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        n = 0
        for b in content:
            if isinstance(b, dict):
                if b.get("type") == "text":
                    n += len(b.get("text", ""))
                elif b.get("type") == "image":
                    n += 1600 * CHARS_PER_TOKEN  # ~1.6k tokens per image
                else:
                    n += len(json.dumps(b))
        return n
    return 0


class Thread:
    """One transcript: a main session or one subagent run."""

    def __init__(self, path: Path, session_id: str, kind: str, label: str, agent_type: str):
        self.path, self.session_id, self.kind = path, session_id, kind
        self.label, self.agent_type = label, agent_type
        self.title = ""
        self.cost = collections.Counter()
        self.tokens = collections.Counter()
        self.models = collections.Counter()
        self.requests = 0
        self.first = self.last = None
        self.peak_context = 0
        self.tool_calls = collections.Counter()
        self.tool_chars = collections.Counter()
        self.tool_carry = collections.Counter()  # $ of re-reading results on later turns
        self.cold_writes = 0  # cache writes > 20k tokens after turn 1 (expired/invalidated cache)
        self.cold_write_cost = 0.0
        self.excess_ctx_cost = 0.0  # cache reads of context beyond COMPACT_AT tokens

    @property
    def total(self) -> float:
        return sum(self.cost.values())


def load_thread(t: Thread, since: dt.datetime | None, seen: set) -> None:
    msgs = {}  # message id -> (model, usage, speed, ts, order)
    order = []
    tool_names = {}
    results = []  # (order index of result, tool name, chars)
    for line in open(t.path, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        typ = d.get("type")
        if typ in ("ai-title", "custom-title"):
            t.title = d.get("customTitle") or d.get("aiTitle") or t.title
            continue
        if typ not in ("assistant", "user"):
            continue
        ts = d.get("timestamp")
        tsd = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None
        if since and tsd and tsd < since:
            continue
        m = d.get("message") or {}
        if typ == "assistant":
            mid = m.get("id") or d.get("requestId") or d.get("uuid")
            if m.get("model") == "<synthetic>" or not m.get("usage"):
                continue
            if mid in seen and mid not in msgs:
                continue  # already counted in another file
            if mid not in msgs:
                order.append(mid)
            msgs[mid] = (m.get("model"), m["usage"], m["usage"].get("speed") or d.get("speed"), tsd, len(order) - 1)
            for b in m.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    name = b.get("name", "?")
                    if name == "Bash":
                        cmd = (b.get("input") or {}).get("command", "")
                        # skip leading `cd dir &&`, env assignments, `time`, etc.
                        cmd = re.sub(r"^\s*(cd\s+\S+\s*(&&|;)\s*|[A-Z_]+=\S+\s+|time\s+)*", "", cmd)
                        words = cmd.split()
                        name = "Bash:" + (os.path.basename(words[0]) if words else "?")[:24]
                    elif name in ("Agent", "Task"):
                        name = "Agent:" + str((b.get("input") or {}).get("subagent_type", "general"))
                    elif name == "Skill":
                        name = "Skill:" + str((b.get("input") or {}).get("skill", "?"))
                    tool_names[b.get("id")] = name
                    t.tool_calls[name] += 1
        else:
            content = m.get("content")
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        name = tool_names.get(b.get("tool_use_id"), "?")
                        results.append((len(order), name, text_len(b.get("content"))))
            if d.get("isMeta") and isinstance(content, (list, str)):
                # skill bodies, attachments injected as meta user turns
                results.append((len(order), "(injected context)", text_len(content)))

    n_turns = len(order)
    for mid in order:
        model, u, speed, tsd, idx = msgs[mid]
        seen.add(mid)
        parts = price(model, u, speed)
        for k, v in parts.items():
            t.cost[k] += v
        for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            t.tokens[k] += u.get(k, 0) or 0
        t.models[model] += sum(parts.values())
        t.requests += 1
        ctx = (u.get("input_tokens", 0) or 0) + (u.get("cache_read_input_tokens", 0) or 0) + (u.get("cache_creation_input_tokens", 0) or 0)
        t.peak_context = max(t.peak_context, ctx)
        t.excess_ctx_cost += max(0, ctx - COMPACT_AT) * PRICES.get(model, PRICES["claude-opus-5-5"])[2] / 1e6
        if idx > 0 and (u.get("cache_creation_input_tokens", 0) or 0) > 20000:
            t.cold_writes += 1
            t.cold_write_cost += parts["cache_write"]
        if tsd:
            t.first = min(t.first, tsd) if t.first else tsd
            t.last = max(t.last, tsd) if t.last else tsd

    # a tool result read at turn i is re-read (cache read) on every later turn
    # A tool result is cache-written once, then re-read on every later turn.
    model0 = msgs[order[0]][0] if order else "claude-opus-5-5"
    pin, _, rp = PRICES.get(model0, PRICES["claude-opus-5-5"])
    wp = pin * (2.0 if t.kind == "main" else 1.25)  # main threads use the 1h cache
    for at, name, chars in results:
        toks = chars / CHARS_PER_TOKEN
        t.tool_chars[name] += chars
        later = max(n_turns - at, 0)
        t.tool_carry[name] += toks * (wp + later * rp) / 1e6


def collect(root: Path, since):
    threads = []
    seen: set = set()
    sessions = {}
    # subagents first, so a main file that echoes sidechain messages is not double-counted
    for meta in sorted(root.glob("*/subagents/*.meta.json")):
        jl = meta.with_name(meta.name.replace(".meta.json", ".jsonl"))
        if not jl.exists():
            continue
        try:
            md = json.loads(meta.read_text())
        except Exception:
            md = {}
        sid = meta.parent.parent.name
        t = Thread(jl, sid, "subagent", md.get("description") or jl.stem, md.get("agentType") or "unknown")
        load_thread(t, since, seen)
        threads.append(t)
    for jl in sorted(root.glob("*/subagents/*.jsonl")):
        if not jl.with_name(jl.stem + ".meta.json").exists():
            t = Thread(jl, jl.parent.parent.name, "subagent", jl.stem, "unknown")
            load_thread(t, since, seen)
            threads.append(t)
    for jl in sorted(root.glob("*.jsonl")):
        t = Thread(jl, jl.stem, "main", "", "main thread")
        load_thread(t, since, seen)
        sessions[jl.stem] = t.title or jl.stem[:8]
        t.label = sessions[jl.stem]
        threads.append(t)
    for t in threads:
        if t.kind == "subagent":
            t.title = sessions.get(t.session_id, t.session_id[:8])
    return [t for t in threads if t.requests]


def cost_state_total(root: Path, since) -> float:
    total = 0.0
    for f in root.glob("*.jsonl"):
        last = None
        for line in open(f, encoding="utf-8", errors="replace"):
            if '"cost-state"' in line:
                try:
                    last = json.loads(line)
                except json.JSONDecodeError:
                    pass
        if last and (not since or last.get("startTime", 0) / 1000 >= since.timestamp()):
            total += last.get("totalCostUSD", 0)
    return total


# ---------------------------------------------------------------- analysis

def analyse(threads):
    total = sum(t.total for t in threads)
    by_session = collections.defaultdict(lambda: collections.Counter())
    for t in threads:
        key = t.title if t.kind == "subagent" else t.label
        by_session[(t.session_id, key)]["main" if t.kind == "main" else "subagents"] += t.total
    by_type = collections.Counter()
    by_type_n = collections.Counter()
    for t in threads:
        by_type[t.agent_type] += t.total
        by_type_n[t.agent_type] += 1
    by_kind = collections.Counter()
    for t in threads:
        by_kind.update(t.cost)
    by_model = collections.Counter()
    for t in threads:
        by_model.update(t.models)
    by_day = collections.defaultdict(collections.Counter)
    for t in threads:
        if t.first:
            by_day[t.first.date().isoformat()]["main" if t.kind == "main" else "subagents"] += t.total
    tools_carry = collections.Counter()
    tools_chars = collections.Counter()
    tools_calls = collections.Counter()
    for t in threads:
        tools_carry.update(t.tool_carry)
        tools_chars.update(t.tool_chars)
        tools_calls.update(t.tool_calls)
    return dict(
        total=total,
        by_session=by_session,
        by_type=by_type,
        by_type_n=by_type_n,
        by_kind=by_kind,
        by_model=by_model,
        by_day=by_day,
        tools_carry=tools_carry,
        tools_chars=tools_chars,
        tools_calls=tools_calls,
        cold=sum(t.cold_write_cost for t in threads),
        cold_n=sum(t.cold_writes for t in threads),
        excess=sum(t.excess_ctx_cost for t in threads),
    )


def recommendations(threads, a):
    recs = []
    total = a["total"] or 1
    k = a["by_kind"]
    sub = sum(t.total for t in threads if t.kind == "subagent")
    fable = a["by_model"].get("claude-fable-5-2", 0)
    fable_sub = sum(t.models.get("claude-fable-5-2", 0) for t in threads if t.kind == "subagent")

    if fable_sub > 0.1 * total:
        recs.append((fable_sub * 0.5,
            f"Subagents on Fable 5.2 cost ${fable_sub:,.0f} ({fable_sub/total:.0%} of spend). Fable is 2x Opus 5.5 per token. "
            "Add `model: opus` (or `sonnet` for read-only research/web sweeps) to the frontmatter of the "
            ".claude/agents/*.md critics and pass `model` on ad-hoc Agent calls; keep Fable for the hard synthesis steps."))
    elif fable > 0.2 * total:
        recs.append((fable * 0.3, f"Fable 5.2 accounts for ${fable:,.0f} ({fable/total:.0%}). Use Opus 5.5 for routine turns (/model) and switch up only for hard problems."))

    big = [t for t in threads if t.kind == "main" and t.peak_context > COMPACT_AT]
    if a["excess"] > 0.03 * total:
        names = "; ".join(f"“{t.label[:40]}” peaked at {t.peak_context/1000:.0f}k" for t in sorted(big, key=lambda t: -t.excess_ctx_cost)[:3])
        recs.append((a["excess"],
            f"{len(big)} sessions ran past {COMPACT_AT//1000}k tokens of context; re-reading everything beyond {COMPACT_AT//1000}k cost ${a['excess']:,.0f}. "
            f"Worst: {names}. Run /compact (or /clear with a short hand-off note) once a session crosses ~{COMPACT_AT//1000}k, "
            "or set autoCompact to trigger earlier, and split multi-topic sessions."))

    if k["cache_read"] > 0.4 * total:
        long = sorted((t for t in threads if t.kind == "main"), key=lambda t: -t.cost["cache_read"])[:3]
        names = "; ".join(f"“{t.label[:40]}” ({t.requests} turns, peak {t.peak_context/1000:.0f}k ctx)" for t in long)
        recs.append((k["cache_read"] * 0.3,
            f"Re-reading context is the biggest line item: ${k['cache_read']:,.0f} ({k['cache_read']/total:.0%}) of cache reads. "
            f"Every turn re-reads the whole conversation. Longest offenders: {names}. "
            "Start a fresh session (/clear) when switching topic, /compact long sessions, and push file-dump-heavy work into subagents so only the summary returns."))

    if k["cache_write"] > 0.15 * total:
        recs.append((a["cold"] * 0.7,
            f"Cache writes cost ${k['cache_write']:,.0f} ({k['cache_write']/total:.0%}); ${a['cold']:,.0f} of that is {a['cold_n']} mid-session re-writes of >20k tokens, "
            "i.e. the cache went cold (idle past TTL, model/effort switch, or edited CLAUDE.md/tools mid-session). "
            "Avoid switching /model mid-session, and resume long-idle sessions with a fresh /clear + short brief rather than re-warming a huge context."))

    top_tools = a["tools_carry"].most_common(4)
    if top_tools:
        desc = ", ".join(f"{n} (~{a['tools_chars'][n]/CHARS_PER_TOKEN/1e6:.1f}M tok, ~${c:,.0f} carried)" for n, c in top_tools)
        recs.append((sum(c for _, c in top_tools) * 0.4,
            f"Tool output is written into context once and re-read on every later turn: {desc}. "
            "Read files with offset/limit, pipe big command output through head/grep/wc, have pipeline scripts print summaries not dumps, "
            "and avoid cat-ing large JSON/GeoJSON/CSV data files."))

    if sub > 0.3 * total:
        heavy = sorted((t for t in threads if t.kind == "subagent"), key=lambda t: -t.total)[:3]
        names = "; ".join(f"{t.agent_type}: “{t.label[:40]}” ${t.total:,.0f}" for t in heavy)
        recs.append((sub * 0.15,
            f"Subagents are {sub/total:.0%} of spend. Priciest runs: {names}. "
            "Give critics a narrow scope (one region/layer per run), a turn or token budget in the brief, and `effort: low` in frontmatter for read-only agents; "
            "run sweeps as a few scoped agents, not one open-ended one."))

    if k["output"] > 0.25 * total:
        recs.append((k["output"] * 0.2,
            f"Output tokens (incl. thinking) are ${k['output']:,.0f} ({k['output']/total:.0%}). Effort is already medium; drop to /effort low for mechanical edits and data reruns, set `effort: low` on read-only Explore/research agents, and ask for terse reports."))

    return sorted(recs, key=lambda r: -r[0])


# ---------------------------------------------------------------- report

PALETTE = ["#4269d0", "#efb118", "#ff725c", "#6cc5b0", "#3ca951", "#ff8ab7", "#a463f2", "#97bbf5", "#9c6b4e", "#9498a0"]


def svg_hbar(rows, width=720, fmt=lambda v: f"${v:,.0f}", stacked_keys=None, colors=None):
    """rows: [(label, value)] or [(label, {key: value})] when stacked_keys."""
    if not rows:
        return "<p class=muted>No data.</p>"
    bar_h, gap, label_w, val_w = 20, 6, 300, 80
    plot_w = width - label_w - val_w
    vals = [sum(v.values()) if stacked_keys else v for _, v in rows]
    vmax = max(vals) or 1
    h = len(rows) * (bar_h + gap) + 4
    out = [f'<svg viewBox="0 0 {width} {h}" width="100%" role="img" style="max-width:{width}px">']
    for i, ((label, v), tot) in enumerate(zip(rows, vals)):
        y = i * (bar_h + gap)
        out.append(f'<text x="{label_w-8}" y="{y+bar_h*0.72}" text-anchor="end" class="lbl">{html.escape(str(label)[:46])}<title>{html.escape(str(label))}</title></text>')
        x = label_w
        segs = [(k, v.get(k, 0)) for k in stacked_keys] if stacked_keys else [(None, v)]
        for j, (k, sv) in enumerate(segs):
            w = sv / vmax * plot_w
            c = (colors or PALETTE)[j % len(colors or PALETTE)]
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w,0):.1f}" height="{bar_h}" rx="2" fill="{c}"><title>{html.escape(str(k or label))}: {fmt(sv)}</title></rect>')
            x += w
        out.append(f'<text x="{x+6:.1f}" y="{y+bar_h*0.72}" class="val">{fmt(tot)}</text>')
    out.append("</svg>")
    if stacked_keys:
        out.append('<div class="legend">' + "".join(
            f'<span><i style="background:{(colors or PALETTE)[j % 10]}"></i>{html.escape(k)}</span>' for j, k in enumerate(stacked_keys)) + "</div>")
    return "".join(out)


def svg_columns(days, keys, width=720, height=200):
    if not days:
        return ""
    vmax = max(sum(c.values()) for _, c in days) or 1
    pad_b, pad_l = 34, 50
    cw = (width - pad_l) / len(days)
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" style="max-width:{width}px">']
    for frac in (0, 0.5, 1):
        y = (height - pad_b) * (1 - frac)
        out.append(f'<line x1="{pad_l}" x2="{width}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/><text x="{pad_l-6}" y="{y+4:.1f}" text-anchor="end" class="val">${vmax*frac:,.0f}</text>')
    for i, (day, c) in enumerate(days):
        x = pad_l + i * cw + cw * 0.15
        y = height - pad_b
        for j, k in enumerate(keys):
            hgt = c.get(k, 0) / vmax * (height - pad_b)
            y -= hgt
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cw*0.7:.1f}" height="{hgt:.1f}" fill="{PALETTE[j]}"><title>{day} {k}: ${c.get(k,0):,.2f}</title></rect>')
        if len(days) <= 20 or i % max(1, len(days) // 12) == 0:
            out.append(f'<text x="{x+cw*0.35:.1f}" y="{height-pad_b+14}" text-anchor="middle" class="val">{day[5:]}</text>')
    out.append("</svg>")
    out.append('<div class="legend">' + "".join(f'<span><i style="background:{PALETTE[j]}"></i>{k}</span>' for j, k in enumerate(keys)) + "</div>")
    return "".join(out)


def render_html(threads, a, recs, root, cs_total, since):
    total = a["total"]
    sessions = sorted(a["by_session"].items(), key=lambda kv: -sum(kv[1].values()))[:20]
    session_rows = [(name, c) for (sid, name), c in sessions]
    types = [(f"{k} ×{a['by_type_n'][k]}", v) for k, v in a["by_type"].most_common(12)]
    runs = sorted((t for t in threads if t.kind == "subagent"), key=lambda t: -t.total)[:15]
    run_rows = [(f"{t.agent_type}: {t.label}", t.cost) for t in runs]
    kinds = ["cache_read", "cache_write", "output", "input", "web_search"]
    kind_rows = [(k.replace("_", " "), a["by_kind"][k]) for k in kinds if a["by_kind"][k] > 0]
    model_rows = a["by_model"].most_common()
    tool_rows = [(n, c) for n, c in a["tools_carry"].most_common(15)]
    days = sorted(a["by_day"].items())
    n_main = sum(1 for t in threads if t.kind == "main")
    n_sub = len(threads) - n_main
    span = [t.first for t in threads if t.first]
    rng = f"{min(span):%Y-%m-%d} → {max(span):%Y-%m-%d}" if span else ""

    tbl = "".join(
        f"<tr><td>{html.escape(t.title[:50] if t.kind=='subagent' else t.label[:50])}</td><td>{html.escape(t.agent_type)}</td>"
        f"<td>{html.escape(t.label[:60]) if t.kind=='subagent' else '—'}</td><td class=n>{t.requests}</td>"
        f"<td class=n>{t.peak_context/1000:,.0f}k</td><td class=n>${t.total:,.2f}</td></tr>"
        for t in sorted(threads, key=lambda t: -t.total)[:40])
    rec_html = "".join(f"<li><b>~${s:,.0f} addressable.</b> {html.escape(r).replace('`','')}</li>" for s, r in recs)

    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Token Spend Audit</title><style>
:root{{--bg:#fff;--fg:#1d1d1f;--muted:#6b6b73;--line:#e4e4e8;--card:#f7f7f9}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151518;--fg:#ececf0;--muted:#9a9aa3;--line:#2c2c33;--card:#1d1d22}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,system-ui,sans-serif;margin:0;padding:24px 16px;}}
main{{max-width:760px;margin:auto}} h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin:32px 0 8px}}
.muted,.val{{color:var(--muted);fill:var(--muted);font-size:12px}} .lbl{{fill:var(--fg);font-size:12px}} .grid{{stroke:var(--line)}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}}
.tile{{background:var(--card);border-radius:8px;padding:10px 12px}} .tile b{{display:block;font-size:20px}}
.legend{{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-top:4px}}
.legend i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}}
table{{border-collapse:collapse;width:100%;font-size:12px}} td,th{{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left}} .n{{text-align:right;white-space:nowrap}}
.wrap{{overflow-x:auto}} li{{margin-bottom:10px}}
</style></head><body><main>
<h1>Token spend audit</h1>
<div class=muted>{html.escape(str(root))} · {rng}{' · since '+since.date().isoformat() if since else ''} · list API prices, estimated</div>
<div class=tiles>
<div class=tile><span class=muted>Estimated spend</span><b>${total:,.0f}</b></div>
<div class=tile><span class=muted>Sessions / subagent runs</span><b>{n_main} / {n_sub}</b></div>
<div class=tile><span class=muted>Subagent share</span><b>{(total - sum(t.total for t in threads if t.kind=='main'))/max(total,1):.0%}</b></div>
<div class=tile><span class=muted>Cache-read share</span><b>{a['by_kind']['cache_read']/max(total,1):.0%}</b></div>
</div>
<div class=muted>Claude Code's own cost-state total for sessions that recorded one: ${cs_total:,.0f} (it skips sessions that never wrote a cost-state, and includes Haiku housekeeping calls).</div>

<h2>Recommendations</h2><ol>{rec_html}</ol>

<h2>Most expensive sessions (main thread vs. subagents it launched)</h2>
{svg_hbar(session_rows, stacked_keys=["main","subagents"])}
<h2>Spend by agent type</h2>{svg_hbar(types)}
<h2>Most expensive subagent runs, by token type</h2>{svg_hbar(run_rows, stacked_keys=kinds)}
<h2>Where the money goes: token type</h2>{svg_hbar(kind_rows)}
<h2>By model</h2>{svg_hbar(model_rows)}
<h2>Context carried by tool output</h2>
<div class=muted>Estimated cost of each tool's results: one cache write plus a re-read on every later turn (chars/4 tokens). Overlaps with the cache-read total above.</div>
{svg_hbar(tool_rows)}
<h2>Spend per day (by thread start)</h2>{svg_columns(days, ["main","subagents"])}
<h2>Top 40 threads</h2><div class=wrap><table><tr><th>Session</th><th>Agent</th><th>Task</th><th class=n>Turns</th><th class=n>Peak ctx</th><th class=n>Cost</th></tr>{tbl}</table></div>
</main></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=os.getcwd(), help="project directory (default: cwd)")
    ap.add_argument("--since", help="only count activity on/after YYYY-MM-DD")
    ap.add_argument("--out", default="build/token_audit.html", help="HTML report path")
    ap.add_argument("--json", help="also write the aggregates as JSON")
    args = ap.parse_args()

    root = project_dir(args.project)
    if not root.is_dir():
        sys.exit(f"no transcripts at {root}")
    since = dt.datetime.fromisoformat(args.since).replace(tzinfo=dt.timezone.utc) if args.since else None
    threads = collect(root, since)
    a = analyse(threads)
    recs = recommendations(threads, a)
    cs = cost_state_total(root, since)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(render_html(threads, a, recs, root, cs, since))

    total = a["total"]
    print(f"Estimated spend ${total:,.2f} over {len(threads)} threads (Claude Code cost-state: ${cs:,.2f})")
    print("\nBy token type:")
    for k, v in a["by_kind"].most_common():
        print(f"  {k:12} ${v:10,.2f}  {v/max(total,1):5.1%}")
    print("\nBy model:")
    for k, v in a["by_model"].most_common():
        print(f"  {k:20} ${v:10,.2f}")
    print("\nBy agent type:")
    for k, v in a["by_type"].most_common(10):
        print(f"  {k:24} ${v:10,.2f}  ×{a['by_type_n'][k]}")
    print("\nTop sessions (incl. their subagents):")
    for (sid, name), c in sorted(a["by_session"].items(), key=lambda kv: -sum(kv[1].values()))[:10]:
        print(f"  ${sum(c.values()):9,.2f}  (sub ${c['subagents']:,.0f})  {name[:60]}")
    print("\nTool output carried in context (est. $):")
    for k, v in a["tools_carry"].most_common(8):
        print(f"  {k:28} ${v:9,.2f}  {a['tools_chars'][k]/CHARS_PER_TOKEN/1e6:6.2f}M tok  ×{a['tools_calls'][k]}")
    print("\nRecommendations:")
    for s, r in recs:
        print(f"  - (~${s:,.0f}) {r}")
    print(f"\nReport: {os.path.abspath(args.out)}")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "total": total, "cost_state_total": cs,
            "by_kind": a["by_kind"], "by_model": a["by_model"], "by_type": a["by_type"],
            "sessions": [{"session": sid, "title": n, **c} for (sid, n), c in a["by_session"].items()],
            "threads": [{"session": t.session_id, "kind": t.kind, "agent_type": t.agent_type, "label": t.label,
                         "requests": t.requests, "peak_context": t.peak_context, "cost": dict(t.cost)} for t in threads],
            "tools_carry": a["tools_carry"], "recommendations": [r for _, r in recs],
        }, indent=1, default=str))


if __name__ == "__main__":
    main()
