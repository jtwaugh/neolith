import json, sys
from collections import Counter
path = sys.argv[1]
MODE = sys.argv[2] if len(sys.argv) > 2 else "centre"
boxes = {"samara": (47.8, 51.9, 52.0, 54.0), "volga": (45.0, 49.0, 56.0, 56.0)}
years = [-10000, -9000, -8000, -7500, -7000, -6500, -6000, -5000, -4000, -3000]
d = json.load(open(path))
for name, (x0, y0, x1, y1) in boxes.items():
    cnt = {y: Counter() for y in years}
    for f in d["features"]:
        p = f["properties"]
        cx, cy = (p["left"] + p["right"]) / 2, (p["top"] + p["bottom"]) / 2
        inside = (p["right"] > x0 and p["left"] < x1 and max(p["top"], p["bottom"]) > y0 and min(p["top"], p["bottom"]) < y1) if MODE == "touch" else (x0 <= cx <= x1 and y0 <= cy <= y1)
        if not inside:
            continue
        t = sorted((int(k), v) for k, v in p["terrain"].items())
        for y in years:
            cur = None
            for k, v in t:
                if k <= y:
                    cur = v
            cnt[y][cur] += 1
    print(f"## {name} {x0, y0, x1, y1}")
    for y in years:
        print(y, sum(cnt[y].values()), dict(cnt[y].most_common()))
