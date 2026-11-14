"""Can you click what you see, and does the UI stay put? `python -m pipeline.interact`
(`make state-ui`).

Drives the running app through its agent harness (neolith-rs/harness/) on a
private port and measures:

- **Clicks on pieces.** For each fixed view, clicks every settlement piece the
  board reports on screen at its own `screen_px`, and again a few pixels off
  centre, and checks that the record opened is that site. Clicks on a drawn
  name are tried too: players click names.
- **Crowding.** On-screen pieces with another piece closer than `crowd_px`:
  ambiguous targets.
- **The view moving under a click.** Camera change caused by a click on a
  piece. Clicking should not move the map unless asked to.
- **UI moving under the player.** The `ui` widget tree is read before and after
  ordinary actions (open a record, change year, change mode, play, close).
  Every widget present in both, matched by role and label, should stay where
  it was. Widgets that shift are listed with how far.
- **Frame time.** The harness's `perf bench` draws the board pass back to back
  on each view and gives the GPU milliseconds per pass: what the map costs
  to draw, apart from vsync and the panels.

Writes data/state/interact.json (tracked), which `python -m pipeline state` reports.
Needs a display (the app opens a window, behind others is fine) and a GPU.
"""
import argparse
import json
import math
import os
import sys
import time
import tomllib
from types import SimpleNamespace

HARNESS = "neolith-rs/harness"
VIEWS = "data/state/views.toml"
RESULT = "data/state/interact.json"
PORT = int(os.environ.get("NEOLITH_STATE_PORT", "7961"))
# Widgets a player clicks: one of these moving is worse than a label moving.
CONTROLS = ("Button", "ComboBox", "Link", "DisclosureTriangle", "Slider", "CheckBox", "RadioButton", "TextInput")

sys.path.insert(0, HARNESS)
import neolith as H  # noqa: E402


def req(port, **k):
    r = H.request(k, port)
    if not r.get("ok", False):
        raise RuntimeError(f"harness {k.get('cmd')}: {r}")
    return r


def close_record(port):
    req(port, cmd="key", key="Escape")
    req(port, cmd="set", settlement=None)


def cam_moved(a, b, tol=1e-4):
    return any(abs(a[k] - b[k]) > tol for k in ("lon", "lat", "dist", "yaw_deg", "pitch_deg"))


def crowded(points, px):
    n = 0
    for i, (x, y) in enumerate(points):
        if any(j != i and math.hypot(x - u, y - v) < px for j, (u, v) in enumerate(points)):
            n += 1
    return n


def widget_shifts(before, after, min_px):
    """Widgets in both trees (matched by role and label, in order) that moved by more than min_px."""
    def keyed(ws):
        seen, out = {}, {}
        for w in ws:
            if w["role"] in ("TextRun", "Unknown") or not w.get("label"):
                continue
            k = (w["role"], w["label"])
            seen[k] = seen.get(k, -1) + 1
            out[k + (seen[k],)] = w["centre_px"]
        return out
    a, b = keyed(before), keyed(after)
    moved = []
    for k in a.keys() & b.keys():
        d = math.hypot(a[k][0] - b[k][0], a[k][1] - b[k][1])
        if d > min_px:
            moved.append({"widget": f"{k[0]} '{k[1]}'", "px": round(d)})
    return sorted(moved, key=lambda m: -m["px"])


def probe_clicks(port, views, cfg, log):
    jit = cfg["jitter_px"]
    offsets = [(jit, 0), (-jit, 0), (0, jit), (0, -jit)]
    out = []
    for v in views:
        req(port, cmd="set", year=v["year"], mode=v.get("mode", "terrain"))
        req(port, cmd="camera", lon=v["lon"], lat=v["lat"], dist=v["dist"])
        close_record(port)
        st = req(port, cmd="state", fields=["settlements", "camera", "board_rect_px"])
        # Only pieces a player can reach: a piece standing at the board's edge
        # can have its click point (and its off-centre ones) under the menu bar.
        x0, y0, x1, y1 = st["board_rect_px"]
        on_board = lambda p: x0 + jit < p["screen_px"][0] < x1 - jit and y0 + jit < p["screen_px"][1] < y1 - jit
        pieces = [p for p in st["settlements"]["pieces"] if on_board(p)][: cfg["pieces_per_view"]]
        labels = st["settlements"]["labels_drawn"][: cfg["pieces_per_view"]]
        cam0 = st["camera"]
        hit = jhit = jn = lhit = moved = 0
        misses = []
        for p in pieces:
            x, y = p["screen_px"]
            a = req(port, cmd="click", x=x, y=y)["after"]
            ok = a.get("settlement_popup") == p["name"]
            hit += ok
            if not ok:
                misses.append(f"{p['name']} -> {a.get('settlement_popup')}")
            if cam_moved(cam0, a["camera"]):
                moved += 1
                req(port, cmd="camera", lon=v["lon"], lat=v["lat"], dist=v["dist"])
            close_record(port)
            for dx, dy in offsets:
                a = req(port, cmd="click", x=x + dx, y=y + dy)["after"]
                jn += 1
                jhit += a.get("settlement_popup") == p["name"]
                if cam_moved(cam0, a["camera"]):
                    req(port, cmd="camera", lon=v["lon"], lat=v["lat"], dist=v["dist"])
                close_record(port)
        for lb in labels:
            r = lb["rect_px"]
            a = req(port, cmd="click", x=(r[0] + r[2]) / 2, y=(r[1] + r[3]) / 2)["after"]
            lhit += a.get("settlement_popup") == lb["name"]
            if cam_moved(cam0, a["camera"]):
                req(port, cmd="camera", lon=v["lon"], lat=v["lat"], dist=v["dist"])
            close_record(port)
        pts = [tuple(p["screen_px"]) for p in st["settlements"]["pieces"]]
        row = {"view": v["name"], "pieces": len(pieces), "hit": hit, "jitter_tries": jn, "jitter_hit": jhit,
               "labels": len(labels), "label_hit": lhit, "camera_moved": moved,
               "crowded": crowded(pts, cfg["crowd_px"]), "on_screen": len(pts), "misses": misses[:5]}
        log(f"{v['name']}: pieces {hit}/{len(pieces)}, off-centre {jhit}/{jn}, names {lhit}/{len(labels)}, "
            f"camera moved {moved}, crowded {row['crowded']}/{len(pts)}")
        out.append(row)
    return out


def probe_perf(port, views, cfg, log):
    """GPU ms per board pass on each view (harness `perf bench`). The first
    bench on a view is thrown away: it pays for anything not yet uploaded."""
    out = []
    for v in views:
        req(port, cmd="set", year=v["year"], mode=v.get("mode", "terrain"), playing=False)
        req(port, cmd="camera", lon=v["lon"], lat=v["lat"], dist=v["dist"])
        close_record(port)
        req(port, cmd="wait", seconds=0.5)
        req(port, cmd="perf", bench=5)
        runs = sorted(req(port, cmd="perf", bench=cfg["bench_passes"]).get("bench_ms") or 0.0 for _ in range(3))
        out.append({"view": v["name"], "board_pass_ms": round(runs[1], 2), "runs": [round(r, 2) for r in runs]})
        log(f"perf: {v['name']}: {runs[1]:.2f} ms per board pass (of {', '.join(f'{r:.2f}' for r in runs)})")
    return out


def probe_ui(port, cfg, log):
    """Ordinary actions, with the widget tree read before and after each."""
    v = cfg["ui_view"]
    req(port, cmd="set", year=v["year"], mode="terrain", playing=False)
    req(port, cmd="camera", lon=v["lon"], lat=v["lat"], dist=v["dist"])
    close_record(port)
    pieces = req(port, cmd="state", fields=["settlements"])["settlements"]["pieces"]
    steps = [
        ("open a record", lambda: req(port, cmd="click", x=pieces[0]["screen_px"][0], y=pieces[0]["screen_px"][1])),
        ("open another record", lambda: req(port, cmd="set", settlement=pieces[min(1, len(pieces) - 1)]["name"])),
        ("change year", lambda: req(port, cmd="set", year=v["year"] + 1500)),
        ("change map mode", lambda: req(port, cmd="set", mode="pop")),
        ("play 2 s", lambda: (req(port, cmd="set", playing=True), req(port, cmd="wait", seconds=2),
                              req(port, cmd="set", playing=False))),
        ("hover the board", lambda: req(port, cmd="move", x=pieces[-1]["screen_px"][0], y=pieces[-1]["screen_px"][1])),
        ("close the record", lambda: close_record(port)),
    ]
    out = []
    before = req(port, cmd="ui")["widgets"]
    for name, act in steps:
        act()
        after = req(port, cmd="ui")["widgets"]
        moved = widget_shifts(before, after, cfg["ui_shift_px"])
        controls = [m for m in moved if m["widget"].split(" ", 1)[0] in CONTROLS]
        out.append({"action": name, "widgets_moved": len(moved), "controls_moved": len(controls),
                    "max_px": max((m["px"] for m in moved), default=0), "moved": moved[:8]})
        log(f"ui: {name}: {len(moved)} widgets moved" + (f", up to {moved[0]['px']} px ({moved[0]['widget']})" if moved else ""))
        before = after
    return out


def run(log=print):
    cfg = tomllib.load(open(VIEWS, "rb"))
    icfg = {"jitter_px": 8, "crowd_px": 24, "pieces_per_view": 12, "ui_shift_px": 4, "bench_passes": 30, **cfg.get("interact", {})}
    views = [v for v in cfg["view"] if v["name"] in icfg.get("views", [])] or cfg["view"][:4]
    icfg["ui_view"] = next(v for v in cfg["view"] if v["name"] == icfg.get("ui_view", views[0]["name"]))
    started = H.alive(PORT)
    if not started:
        r = H.launch(SimpleNamespace(port=PORT, size=icfg.get("size", "1600x1000"), world=None))
        if not r.get("ok"):
            raise SystemExit(f"state-ui: could not launch the app: {r}")
    try:
        req(PORT, cmd="start")
        clicks = probe_clicks(PORT, views, icfg, log)
        ui = probe_ui(PORT, icfg, log)
        perf = probe_perf(PORT, views, icfg, log)
    finally:
        if not started:
            try:
                H.request({"cmd": "quit"}, PORT, timeout=5)
            except OSError:
                pass
    tot = lambda k: sum(c[k] for c in clicks)
    res = {"date": time.strftime("%Y-%m-%d"), "settings": {k: v for k, v in icfg.items() if k != "ui_view"},
           "summary": {
               "piece_click_rate": round(tot("hit") / max(tot("pieces"), 1), 3),
               "off_centre_click_rate": round(tot("jitter_hit") / max(tot("jitter_tries"), 1), 3),
               "name_click_rate": round(tot("label_hit") / max(tot("labels"), 1), 3),
               "camera_moved_on_click": tot("camera_moved"),
               "crowded_share": round(tot("crowded") / max(tot("on_screen"), 1), 3),
               "ui_widgets_moved": sum(u["widgets_moved"] for u in ui),
               "ui_controls_moved": sum(u["controls_moved"] for u in ui),
               "ui_max_shift_px": max((u["max_px"] for u in ui), default=0),
               "board_pass_ms": max((p["board_pass_ms"] for p in perf), default=None),
               "board_pass_mean_ms": round(sum(p["board_pass_ms"] for p in perf) / len(perf), 2) if perf else None},
           "clicks": clicks, "ui": ui, "perf": perf}
    json.dump(res, open(RESULT, "w"), indent=1, ensure_ascii=False)
    log(f"wrote {RESULT}: {res['summary']}")
    return res


def main():
    argparse.ArgumentParser(prog="python -m pipeline.interact", description=__doc__.split("\n")[0]).parse_args()
    run()


if __name__ == "__main__":
    main()
