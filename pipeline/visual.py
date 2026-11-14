"""Fixed views of the board, rendered headless and compared with the last
accepted renders: `python -m pipeline.visual [--accept]` (`make state-visual`).

The views are in data/state/views.toml. Each one is rendered with
`neolith --screenshot` into build/state/visual/ and compared with
build/state/golden/ (renders stay out of git, like the other maps). A view
whose render moved more than `changed_share` of its pixels by more than
`pixel_step` is flagged "changed": not a failure, a prompt to look at
it. `--accept` makes the new renders the golden ones. The numbers go to
data/state/visual.json (tracked), which `python -m pipeline state` reports.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import tomllib

import numpy as np
from PIL import Image

VIEWS = "data/state/views.toml"
OUT = "build/state/visual"
GOLDEN = "build/state/golden"
RESULT = "data/state/visual.json"
APP = "neolith-rs/target/release/neolith"
WORLD = "neolith-rs/assets/world.bin"
FLAGS = ("year", "mode", "evidence", "lon", "lat", "dist", "yaw", "pitch", "flat", "art", "hillshade", "relief")


def args_for(view, size, out):
    a = [APP, "--screenshot", out, "--world", WORLD, "--size", size]
    for k in FLAGS:
        if k in view:
            a += [f"--{k}", str(view[k])]
    return a


def diff(a, b, pixel_step):
    """(mean absolute difference 0-255, share of pixels that moved more than pixel_step)."""
    x = np.asarray(Image.open(a).convert("RGB"), dtype=np.int16)
    y = np.asarray(Image.open(b).convert("RGB"), dtype=np.int16)
    if x.shape != y.shape:
        return 255.0, 1.0
    d = np.abs(x - y).max(axis=2)
    return float(d.mean()), float((d > pixel_step).mean())


def run(accept=False, log=print):
    cfg = tomllib.load(open(VIEWS, "rb"))
    size, step, share = cfg.get("size", "640x400"), cfg.get("pixel_step", 24), cfg.get("changed_share", 0.02)
    p = subprocess.run(["cargo", "build", "--release", "-q", "-p", "neolith-app"], cwd="neolith-rs",
                       capture_output=True, text=True)
    if p.returncode:
        log(p.stderr[-2000:])
        raise SystemExit("state-visual: the app did not build")
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(GOLDEN, exist_ok=True)
    rows = []
    for v in cfg["view"]:
        out, gold = os.path.join(OUT, v["name"] + ".png"), os.path.join(GOLDEN, v["name"] + ".png")
        t0 = time.time()
        r = subprocess.run(args_for(v, size, out), capture_output=True, text=True)
        secs = round(time.time() - t0, 1)
        if r.returncode or not os.path.exists(out):
            rows.append({"name": v["name"], "status": "failed", "note": (r.stderr or r.stdout).strip()[-300:]})
            log(f"{v['name']}: render failed")
            continue
        if not os.path.exists(gold) or accept:
            os.replace(out, gold) if accept else Image.open(out).save(gold)
            rows.append({"name": v["name"], "status": "accepted", "seconds": secs})
            log(f"{v['name']}: accepted as golden")
            continue
        mean, moved = diff(out, gold, step)
        status = "changed" if moved > share else "same"
        rows.append({"name": v["name"], "status": status, "mean_diff": round(mean, 2), "moved": round(moved, 4),
                     "seconds": secs, "render": out, "golden": gold})
        log(f"{v['name']}: {status} ({100 * moved:.1f}% of pixels moved)")
    res = {"date": time.strftime("%Y-%m-%d"), "size": size, "pixel_step": step, "changed_share": share, "views": rows}
    json.dump(res, open(RESULT, "w"), indent=1)
    log(f"wrote {RESULT}")
    return res


def main():
    ap = argparse.ArgumentParser(prog="python -m pipeline.visual")
    ap.add_argument("--accept", action="store_true", help="make the new renders the golden ones")
    a = ap.parse_args()
    res = run(a.accept)
    sys.exit(1 if any(r["status"] == "failed" for r in res["views"]) else 0)


if __name__ == "__main__":
    main()
