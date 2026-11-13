#!/usr/bin/env python3
"""Drive a running Neolith app through its agent harness (`neolith --harness`).

Stdlib only. Every subcommand prints the app's JSON reply. Screen
coordinates are screenshot pixels (what you see in the PNG).

    harness/neolith.py launch                 # build + start the app with the harness, wait for it
    harness/neolith.py state [--brief] [--fields year,camera]   # game state read from the app's memory
    harness/neolith.py ui [--filter Play]     # widgets on screen: role, label, state, rect and centre in pixels
    harness/neolith.py press "Köppen"         # click the widget whose label matches (exact, else substring)
    harness/neolith.py shot [out.png]         # screenshot of the whole window
    harness/neolith.py start [--year -7000]   # leave the start screen
    harness/neolith.py set --mode koeppen --year -6000 --playing true --speed 200
    harness/neolith.py set --hillshade 0 --borders 0 --art off --art-blend false --flat-lighting true   # isolate layers
    harness/neolith.py set --fill false | set --fill-margin 0.4    # camera: tabletop view / more edge room
    harness/neolith.py camera --lon 30 --lat 38 --dist 0.4 --pitch 50
    harness/neolith.py click 900 500 [--button right] [--mod shift]
    harness/neolith.py double-click 900 500
    harness/neolith.py drag 900 500 700 500 [--button right]
    harness/neolith.py scroll 900 500 [--dy 300]       # positive dy zooms in, negative out
    harness/neolith.py key space | key 1 | key z --mod cmd    # egui names; aliases: Num1, esc, left …
    harness/neolith.py pick 900 500          # the hex under a screen pixel
    harness/neolith.py hex 35 32 | hex --lon 35 --lat 32 | hex --id 12345
    harness/neolith.py project 35.2 31.8 | project --lon 35.2 --lat 31.8   # lon/lat -> screen pixel (null if off screen)

Every action replies with "after": the camera, year, mode, hover and popup once
the app has settled, so you rarely need a separate `state`.
    harness/neolith.py wait 2.5              # let the clock run (seconds of app time)
    harness/neolith.py raw '{"cmd": "state"}'
    harness/neolith.py refs [--per-game 6]   # reference screenshots of shipped strategy games -> build/critic/refs/
    harness/neolith.py quit

The port defaults to $NEOLITH_HARNESS_PORT or 7878.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RS = os.path.dirname(HERE)
PORT = int(os.environ.get("NEOLITH_HARNESS_PORT", "7878"))
SHOTS = os.environ.get("NEOLITH_SHOTS", os.path.join(os.path.dirname(RS), "build", "critic", "shots"))


def request(req, port=PORT, timeout=120):
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
        s.sendall((json.dumps(req) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(1 << 20)
            if not chunk:
                break
            buf += chunk
    return json.loads(buf)


def alive(port=PORT):
    try:
        return request({"cmd": "ping"}, port, timeout=2).get("ok", False)
    except OSError:
        return False


def launch(args):
    if alive(args.port):
        return {"ok": True, "already_running": True, "port": args.port}
    build = subprocess.run(["cargo", "build", "--release", "-q", "-p", "neolith-app"], cwd=RS)
    if build.returncode:
        return {"ok": False, "error": "cargo build failed"}
    exe = os.path.join(RS, "target", "release", "neolith")
    cmd = [exe, "--harness", str(args.port), "--size", args.size]
    if args.world:
        cmd += ["--world", os.path.abspath(args.world)]
    os.makedirs(SHOTS, exist_ok=True)
    log = open(os.path.join(SHOTS, "app.log"), "ab")
    proc = subprocess.Popen(cmd, cwd=RS, stdout=log, stderr=log, start_new_session=True)
    deadline = time.time() + 60
    while time.time() < deadline:
        if proc.poll() is not None:
            return {"ok": False, "error": f"the app exited ({proc.returncode}); see {log.name}"}
        if alive(args.port):
            # Wait for the world to load (the start screen).
            while time.time() < deadline:
                st = request({"cmd": "state"}, args.port)
                if st.get("screen") != "loading":
                    return {"ok": True, "pid": proc.pid, "port": args.port, "screen": st.get("screen")}
                time.sleep(0.2)
        time.sleep(0.3)
    return {"ok": False, "error": "timed out waiting for the harness"}


# Shipped grand-strategy / 4X games the critic compares against (Steam app ids).
# The images are the publishers' own store screenshots, fetched into build/
# (git-ignored) for side-by-side comparison only.
REFERENCE_GAMES = {
    "victoria3": 529340,
    "crusader_kings3": 1158310,
    "europa_universalis4": 236850,
    "hearts_of_iron4": 394360,
    "old_world": 597180,
    "civilization6": 289070,
}
REFS = os.path.join(os.path.dirname(SHOTS), "refs")


def fetch_refs(per_game):
    import urllib.request
    out = {}
    for slug, appid in REFERENCE_GAMES.items():
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}&filters=screenshots"
        req = urllib.request.Request(url, headers={"User-Agent": "neolith-critic-harness"})
        try:
            data = json.load(urllib.request.urlopen(req, timeout=30))[str(appid)]["data"]["screenshots"]
        except Exception as e:  # network, rate limit, delisted
            out[slug] = {"error": str(e)}
            continue
        d = os.path.join(REFS, slug)
        os.makedirs(d, exist_ok=True)
        files = []
        for i, shot in enumerate(data[:per_game]):
            path = os.path.join(d, f"{i:02d}.jpg")
            if not os.path.exists(path):
                r = urllib.request.Request(shot["path_full"], headers={"User-Agent": "neolith-critic-harness"})
                with open(path, "wb") as f:
                    f.write(urllib.request.urlopen(r, timeout=60).read())
            files.append(path)
        out[slug] = {"store": f"https://store.steampowered.com/app/{appid}/", "files": files}
    with open(os.path.join(REFS, "index.json"), "w") as f:
        json.dump(out, f, indent=1)
    return {"ok": True, "dir": REFS, "games": out}


def press(args):
    """Clicks the widget whose label equals `args.label` (case-insensitive), else
    the only one that contains it."""
    try:
        widgets = request({"cmd": "ui"}, args.port)["widgets"]
    except OSError as e:
        return {"ok": False, "error": f"cannot reach the harness ({e})"}
    want = args.label.lower()
    exact = [w for w in widgets if w["label"].lower() == want]
    partial = [w for w in widgets if want in w["label"].lower()]
    hits = exact or partial
    if len(hits) != 1:
        return {"ok": False, "error": f"{len(hits)} widgets match {args.label!r}",
                "matches": [{"label": w["label"], "role": w["role"], "centre_px": w["centre_px"]} for w in hits[:12]]}
    w = hits[0]
    x, y = w["centre_px"]
    out = request({"cmd": "click", "x": x, "y": y, "button": args.button}, args.port)
    out["pressed"] = {"label": w["label"], "role": w["role"], "centre_px": w["centre_px"]}
    return out


def parse_bool(v):
    return {"true": True, "1": True, "on": True, "false": False, "0": False, "off": False}[v.lower()]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=PORT)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("launch")
    a.add_argument("--world")
    a.add_argument("--size", default="1600x1000", help="window size in points, WxH")
    a = sub.add_parser("state")
    a.add_argument("--brief", action="store_true", help="keyframe count, 10 pieces, label count")
    a.add_argument("--fields", help="comma-separated top-level keys to keep")
    a = sub.add_parser("ui")
    a.add_argument("--filter")
    a = sub.add_parser("press")
    a.add_argument("label")
    a.add_argument("--button", default="left")
    sub.add_parser("ping")
    sub.add_parser("quit")
    a = sub.add_parser("shot")
    a.add_argument("path", nargs="?")
    a = sub.add_parser("start")
    a.add_argument("--year", type=int)
    a = sub.add_parser("set")
    for k in ("mode", "tool", "art", "settlement"):
        a.add_argument(f"--{k}")
    a.add_argument("--evidence", help="evidence layer id for --mode evidence, e.g. domestic_livestock")
    a.add_argument("--year", type=int)
    a.add_argument("--speed", type=float)
    a.add_argument("--inspect", help="hex id, or 'none'")
    for k in ("hillshade", "borders", "grout", "bevel", "art-strength", "saturation", "relief-exaggeration", "mountain-height", "fill-margin", "depth"):
        a.add_argument(f"--{k}", type=float)
    for k in ("playing", "editor", "flat", "relief", "rivers", "survey", "style-window", "user-input", "art-blend", "flat-lighting", "fill"):
        a.add_argument(f"--{k}", type=parse_bool)
    a.add_argument("--tab", help="sidebar tab: Selected, Chronicle or Map")
    a = sub.add_parser("camera")
    for k in ("lon", "lat", "yaw", "pitch", "dist"):
        a.add_argument(f"--{k}", type=float)
    for name in ("click", "double-click", "move", "pick", "scroll"):
        a = sub.add_parser(name)
        a.add_argument("x", type=float)
        a.add_argument("y", type=float)
        a.add_argument("--button", default="left")
        a.add_argument("--mod", action="append", default=[])
        a.add_argument("--dy", type=float, default=240, help="positive zooms in")
        a.add_argument("--dx", type=float, default=0)
    a = sub.add_parser("drag")
    for k in ("x", "y", "to_x", "to_y"):
        a.add_argument(k, type=float)
    a.add_argument("--button", default="left")
    a.add_argument("--mod", action="append", default=[])
    a.add_argument("--steps", type=int, default=12)
    a = sub.add_parser("key")
    a.add_argument("key", help="egui key name: space, z, ArrowUp, Escape, …")
    a.add_argument("--mod", action="append", default=[])
    a = sub.add_parser("text")
    a.add_argument("text")
    for name in ("hex", "project"):
        a = sub.add_parser(name)
        a.add_argument("pos", nargs="*", type=float, metavar="LON LAT")
        a.add_argument("--lon", type=float)
        a.add_argument("--lat", type=float)
        if name == "hex":
            a.add_argument("--id", type=int)
    a = sub.add_parser("wait")
    a.add_argument("seconds", type=float, nargs="?", default=1.0)
    a.add_argument("--frames", type=int)
    a = sub.add_parser("refs")
    a.add_argument("--per-game", type=int, default=6)
    a = sub.add_parser("raw")
    a.add_argument("json")

    args = p.parse_args(argv)
    c = args.cmd
    if c == "launch":
        out = launch(args)
    elif c == "refs":
        out = fetch_refs(args.per_game)
    elif c == "press":
        out = press(args)
    else:
        if c == "raw":
            req = json.loads(args.json)
        elif c == "shot":
            path = args.path or os.path.join(SHOTS, time.strftime("shot-%Y%m%d-%H%M%S.png"))
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            req = {"cmd": "screenshot", "path": os.path.abspath(path)}
        elif c == "set":
            req = {"cmd": "set"}
            for k in ("mode", "evidence", "tool", "art", "year", "speed", "playing", "editor", "flat", "relief", "rivers", "survey", "tab"):
                if getattr(args, k) is not None:
                    req[k] = getattr(args, k)
            if args.style_window is not None:
                req["style_window"] = args.style_window
            if args.user_input is not None:
                req["user_input"] = args.user_input
            for k in ("hillshade", "borders", "grout", "bevel", "art_strength", "saturation", "relief_exaggeration", "mountain_height",
                      "fill_margin", "art_blend", "flat_lighting", "fill", "depth"):
                if getattr(args, k) is not None:
                    req[k] = getattr(args, k)
            if args.settlement is not None:
                req["settlement"] = None if args.settlement.lower() == "none" else args.settlement
            if args.inspect is not None:
                req["inspect"] = None if args.inspect.lower() == "none" else int(args.inspect)
        elif c == "camera":
            req = {"cmd": "camera", **{k: getattr(args, k) for k in ("lon", "lat", "yaw", "pitch", "dist") if getattr(args, k) is not None}}
        elif c in ("click", "double-click", "move", "pick", "scroll"):
            req = {"cmd": c.replace("-", "_"), "x": args.x, "y": args.y, "button": args.button, "modifiers": args.mod}
            if c == "scroll":
                req.update(dx=args.dx, dy=args.dy)
        elif c == "drag":
            req = {"cmd": "drag", "x": args.x, "y": args.y, "to_x": args.to_x, "to_y": args.to_y,
                   "button": args.button, "modifiers": args.mod, "steps": args.steps}
        elif c == "key":
            req = {"cmd": "key", "key": args.key, "modifiers": args.mod}
        elif c == "text":
            req = {"cmd": "text", "text": args.text}
        elif c in ("hex", "project"):
            if args.pos and len(args.pos) != 2:
                p.error(f"{c} takes LON LAT, or --lon/--lat")
            lon, lat = args.pos if args.pos else (args.lon, args.lat)
            req = {"cmd": c, **({"lon": lon, "lat": lat} if lon is not None and lat is not None else {})}
            if c == "hex" and args.id is not None:
                req = {"cmd": "hex", "id": args.id}
        elif c == "wait":
            req = {"cmd": "wait", "frames": args.frames} if args.frames is not None else {"cmd": "wait", "seconds": args.seconds}
        elif c == "start":
            req = {"cmd": "start", **({"year": args.year} if args.year is not None else {})}
        elif c == "state":
            req = {"cmd": "state", "brief": args.brief}
            if args.fields:
                req["fields"] = [f.strip() for f in args.fields.split(",") if f.strip()]
        elif c == "ui":
            req = {"cmd": "ui", **({"filter": args.filter} if args.filter else {})}
        else:
            req = {"cmd": c}
        try:
            out = request(req, args.port)
        except OSError as e:
            out = {"ok": False, "error": f"cannot reach the harness on port {args.port} ({e}); run `launch` first"}
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print()
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
