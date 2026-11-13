import csv, sys, re
from collections import Counter, defaultdict
S = "./"
cols = "labnr,bp,std,lon,lat,site,type,period,material,approximate,precision,source,page,refs".split(",")
key = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
out, seen, log = [], set(), []
for name in ["zaitseva2000", "zaretskaya", "don_volga", "kama_karelia"]:
    rows = list(csv.DictReader(open(S + name + ".csv", encoding="utf-8")))
    assert set(cols) <= set(rows[0]), (name, rows[0].keys())
    vals = defaultdict(set)
    for r in rows: vals[key(r["labnr"])].add((r["bp"], r["std"], r["site"]))
    ambiguous = {k for k, v in vals.items() if len(v) > 1 and name == "zaitseva2000"}
    n = 0
    for r in rows:
        k = key(r["labnr"])
        if not k: log.append(f"{name}: no lab {r['site']}"); continue
        if k in ambiguous: log.append(f"{name}: ambiguous lab {r['labnr']} dropped"); continue
        if name == "zaitseva2000" and r["site"].startswith("Vishennoe"): log.append(f"{name}: doubtful coords {r['labnr']}"); continue
        if k in {"hel1303", "hel269"}: log.append(f"{name}: old-wood float {r['labnr']} dropped"); continue
        if k in seen: log.append(f"{name}: repeat lab {r['labnr']} {r['bp']}±{r['std']} {r['site']}"); continue
        r["approximate"] = r["approximate"].strip().lower()
        if r["approximate"] == "true" and not r["precision"].lower().startswith("approximate"):
            r["precision"] = "approximate: " + r["precision"]
        seen.add(k); out.append({c: r[c].strip() for c in cols}); n += 1
    print(name, len(rows), "->", n, "rows,", len({r["site"] for r in out if r["source"] == out[-1]["source"]}), "sites")
with open(sys.argv[1], "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(out)
print(len(out)); print("\n".join(log))
