import csv, re, sys
src, out = sys.argv[1], sys.argv[2]
pat = re.compile(r"\((\d+)\s*(?:±|\+-|\+/-)\s*(\d+)\s*BP,\s*([^)\]]+?)\s*\)")
rows, seen = [], set()
with open(src, encoding="utf-8", errors="replace") as f:
    r = csv.reader(f, delimiter="\t"); next(r)
    for x in r:
        if x[16].strip() != "Russia": continue
        try: lat, lon = float(x[17]), float(x[18])
        except ValueError: continue
        if not (-16.5 <= lon <= 65.1 and 6 <= lat <= 71.1): continue
        for bp, sd, lab in pat.findall(x[12]):
            bp, sd = int(bp), int(sd)
            if not (4400 <= bp <= 11500): continue  # roughly 10,500-3000 BCE before calibration
            lab = lab.strip()
            if lab in seen: continue
            seen.add(lab)
            loc = x[15].strip()
            site = loc.split(" (")[0].strip()
            rows.append({"labnr": lab, "bp": bp, "std": sd, "lon": lon, "lat": lat, "site": site,
                         "type": "burial", "period": x[14].strip(),
                         "source": "AADR v66.p1 1240K annotation", "page": f"Genetic ID {x[0].strip()}; locality '{loc}'",
                         "precision": "AADR locality coordinates as published (precision varies; usually the site, sometimes a village)",
                         "refs": f"{x[6].strip()} {x[7].strip()}".strip()})
cols = list(rows[0])
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(rows)
sites = {(r["site"], r["lon"], r["lat"]) for r in rows}
print(len(rows), "dates", len(sites), "sites")
