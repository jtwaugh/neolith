"""Autosomal ancestry proportions per ancient individual (AADR v66.p1, CC0).

`python -m isostyle ancestry` picks the in-window individuals and the
reference and outgroup individuals named in [ancestry], writes them as a
small PACKEDANCESTRYMAP set in build/isostyle/ancestry/, runs qpAdm per
individual with ADMIXTOOLS 2 (isostyle/ancestry/run.R) and writes the
committed table, data/ancestry/ancestry.csv.gz. It is opt-in: it needs R
and the 7 GB genotype file, and `build` never calls it. Method and sources:
data/ancestry/SOURCES.md.

The AADR .geno is "TGENO": a 48-byte header, then one row per individual of
ceil(nsnp / 4) bytes, two bits per SNP (0, 1, 2 copies of the reference
allele; 3 missing), first SNP in the high bits.
"""
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

from . import people

STATUSES = ("fit", "no_fit", "low_coverage", "reference")
CHUNK = 150           # targets per genotype file handed to R
HEADER = 48
OUT_COLS = ["individual", "group", "locality", "lat", "lon", "bp", "sd", "snps", "publication", "status", "model", "p"]


def out_columns(order):
    return OUT_COLS + [f"w_{k}" for k in order] + [f"se_{k}" for k in order]


def _passes(assessment):
    a = assessment.astype(str).str.upper().str.replace("MERGE_", "").str.replace("PROVISIONAL_", "")
    return a.str.startswith("PASS")


def reference_sets(acfg, anno):
    """{population: [genetic ids]} for the sources and outgroups, one genotype
    per individual (the best covered). `anno` is people.load_anno's table."""
    out = {}
    specs = [(k, acfg["sources"][k]) for k in acfg["order"]] + [(r["pop"], r) for r in acfg["right"]]
    for pop, spec in specs:
        d = anno[anno["group"].isin(spec["groups"])]
        missing = sorted(set(spec["groups"]) - set(d["group"]))
        if missing:
            raise LookupError(f"ancestry: {pop}: no such AADR group label(s): {missing}")
        if spec.get("ids"):
            lost = sorted(set(spec["ids"]) - set(d["gid"]))
            if lost:
                raise LookupError(f"ancestry: {pop}: genetic id(s) not in its groups: {lost}")
            d = d[d["gid"].isin(spec["ids"])]
        else:
            d = d[_passes(d["assessment"])]
        d = d.sort_values("snps", ascending=False).drop_duplicates("individual")
        if d.empty:
            raise LookupError(f"ancestry: {pop}: no usable individual")
        out[pop] = list(d["gid"])
    return out


def model_hash(acfg, refs):
    """Names the per-individual result cache: it changes when the model does."""
    import hashlib
    key = json.dumps([refs, acfg["order"], acfg["p_min"], acfg["z_bound"], acfg["max_sources"], acfg["rotate"]], sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()[:10]


def targets(cfg, anno_path):
    """In-window individuals passing people.load_aadr's filters, inside the map's box."""
    d = people.load_aadr(anno_path)
    r, years = cfg["region"], np.array(cfg["time"]["slices"], dtype=float)
    half = (years[1] - years[0]) / 2
    edges = np.array([[years[0] - half, years[-1] + half]])
    w = people.normal_mass((1950 - d["bp"]).values.astype(float), np.maximum(d["sd"].fillna(25).values, 25.0), edges)[:, 0]
    box = d["lon"].between(r["lon_min"], r["lon_max"]) & d["lat"].between(r["lat_min"], r["lat_max"])
    return d[box & (w > 1e-4)].reset_index(drop=True)


def stratified(t, n, seed, always=()):
    """About n targets spread over 15-degree boxes and 1000-year bins."""
    key = (t["lon"] // 15).astype(int).astype(str) + "/" + (t["lat"] // 15).astype(int).astype(str) + "/" + (t["bp"] // 1000).astype(int).astype(str)
    rng = np.random.default_rng(seed)
    order = t.assign(_k=key, _r=rng.random(len(t))).sort_values("_r")
    order["_rank"] = order.groupby("_k").cumcount()
    pick = set(order.sort_values(["_rank", "_r"]).index[:n]) | set(t.index[t["individual"].isin(always)])
    return t.loc[sorted(pick)].reset_index(drop=True)


# ------------------------------------------------------------------ genotypes
def tgeno_shape(header):
    f = header[:HEADER].split()
    if f[0] != b"TGENO":
        raise ValueError(f"ancestry: expected a TGENO file, found {f[0]!r}")
    return int(f[1]), int(f[2])


def read_rows(path, rows, url=None, log=print):
    """Packed genotype rows (uint8, [len(rows), ceil(nsnp/4)]) for the given
    individual indices. If the local file is absent or incomplete and `url`
    is given, the rows are read from it by HTTP range instead."""
    # The repository redirects to a signed storage URL. It is resolved once
    # and reused for every range: one request per row to the repository
    # itself trips its rate limit (HTTP 403).
    signed = []

    def remote(a, b):
        req = urllib.request.Request(signed[0] if signed else url,
                                     headers={"Range": f"bytes={a}-{b - 1}", "User-Agent": "isostyle-pipeline/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                if not signed:
                    signed.append(r.geturl())
                return r.read()
        except urllib.error.HTTPError:
            signed.clear()          # the signed URL expired: resolve again on the retry
            raise

    size = os.path.getsize(path) if os.path.exists(path) else 0
    head = open(path, "rb").read(HEADER) if size >= HEADER else remote(0, HEADER)
    nind, nsnp = tgeno_shape(head)
    rlen = (nsnp + 3) // 4
    local = size == HEADER + nind * rlen
    if not local and not url:
        raise FileNotFoundError(f"ancestry: {path} is missing or incomplete (ISOSTYLE_FETCH_OPTIONAL=1 python -m isostyle fetch)")
    out = np.empty((len(rows), rlen), dtype=np.uint8)
    if local:
        mm = np.memmap(path, dtype=np.uint8, mode="r", offset=HEADER, shape=(nind, rlen))
        for k, i in enumerate(rows):
            out[k] = mm[i]
    else:
        # One file per row under ancestry/rows/, so an interrupted run resumes.
        from concurrent.futures import ThreadPoolExecutor
        cache = os.path.join(os.path.dirname(os.path.dirname(path)), "ancestry", "rows")
        os.makedirs(cache, exist_ok=True)

        def row(i):
            f = os.path.join(cache, f"{i}.bin")
            if not (os.path.exists(f) and os.path.getsize(f) == rlen):
                for k in range(4):
                    try:
                        b = remote(HEADER + i * rlen, HEADER + (i + 1) * rlen)
                        break
                    except Exception:
                        if k == 3:
                            raise
                        time.sleep(5 * (k + 1))
                with open(f + ".part", "wb") as h:
                    h.write(b)
                os.replace(f + ".part", f)
            return np.fromfile(f, dtype=np.uint8)

        log(f"ancestry: reading {len(rows)} genotype rows by HTTP range (local .geno incomplete)")
        with ThreadPoolExecutor(6) as ex:
            for k, b in enumerate(ex.map(row, rows)):
                out[k] = b
    return out, nsnp


def unpack(rows, nsnp):
    """[n, nsnp] genotype codes (0, 1, 2; 3 missing) from packed rows."""
    b = rows[:, :, None] >> np.array([6, 4, 2, 0], dtype=np.uint8) & 3
    return b.reshape(len(rows), -1)[:, :nsnp]


def write_geno(path, rows, nsnp, keep):
    """PACKEDANCESTRYMAP (SNP-major) from individual-major packed rows; `keep` masks SNPs."""
    nind, n = len(rows), int(keep.sum())
    rlen = max(HEADER, (nind + 3) // 4)
    idx = np.flatnonzero(keep)
    with open(path, "wb") as f:
        f.write(f"GENO {nind:7d} {n:7d} 0 0".encode().ljust(rlen, b"\0"))
        step = 50_000
        for a in range(0, n, step):
            cols = idx[a:a + step]
            g = (rows[:, cols // 4] >> (6 - 2 * (cols % 4)).astype(np.uint8)) & 3     # [nind, chunk]
            g = np.concatenate([g, np.full((rlen * 4 - nind, len(cols)), 3, dtype=np.uint8)]).T.reshape(len(cols), rlen, 4)
            f.write((g[:, :, 0] << 6 | g[:, :, 1] << 4 | g[:, :, 2] << 2 | g[:, :, 3]).astype(np.uint8).tobytes())


def write_subset(cfg, gids, pops, out_prefix, url=None, log=print, ref_pops=None):
    """The named genetic ids (labelled `pops`) as a small autosomal EIGENSTRAT set."""
    src = os.path.join(cfg["output"]["build_dir"], "sources", cfg["ancestry"]["geno"])
    ind = pd.read_csv(src + ".ind", sep=r"\s+", header=None, names=["gid", "sex", "pop"])
    pos = pd.Series(np.arange(len(ind)), index=ind["gid"])
    lost = [g for g in gids if g not in pos.index]
    if lost:
        raise LookupError(f"ancestry: genetic ids missing from the .ind: {lost[:5]}")
    rows, nsnp = read_rows(src + ".geno", pos[gids].values, url, log)
    snp = pd.read_csv(src + ".snp", sep=r"\s+", header=None, names=["id", "chr", "cm", "bp", "a1", "a2"])
    if len(snp) != nsnp:
        raise ValueError(f"ancestry: .snp has {len(snp)} rows, .geno {nsnp}")
    keep = snp["chr"].between(1, 22).values.copy()
    # qpAdm uses only SNPs covered in every reference population (maxmiss = 0),
    # so the rest are dropped here: the R step reads a third of the file.
    pops = np.asarray(pops, dtype=object)
    for pop in sorted(ref_pops or ()):
        keep &= (unpack(rows[pops == pop], nsnp) != 3).any(axis=0)
    write_geno(out_prefix + ".geno", rows, nsnp, keep)
    snp[keep].to_csv(out_prefix + ".snp", sep="\t", header=False, index=False)
    pd.DataFrame({"gid": gids, "sex": ind.set_index("gid").loc[gids, "sex"].values, "pop": list(pops)}).to_csv(
        out_prefix + ".ind", sep="\t", header=False, index=False)
    log(f"ancestry: subset {len(gids)} individuals x {int(keep.sum())} autosomal SNPs covered in every reference population -> {out_prefix}.geno")


# ---------------------------------------------------------------------- table
def assemble(acfg, t, refs, res):
    """The committed table: one row per target, statuses and weights filled in.
    `res` is run.R's result (gid, status, model, p, w_*, se_*)."""
    order = acfg["order"]
    ref_of = {g: k for k in order for g in refs[k]}
    res = res.set_index("gid") if len(res) else pd.DataFrame()
    rows = []
    for r in t.itertuples():
        row = {c: getattr(r, c) for c in OUT_COLS[:9]}
        row.update(status="", model="", p=np.nan, **{f"w_{k}": np.nan for k in order}, **{f"se_{k}": np.nan for k in order})
        src = ref_of.get(r.gid) or next((k for k in order if r.individual in
                                         {g.split(".")[0] for g in refs[k]} and r.group in acfg["sources"][k]["groups"]), None)
        if src:
            row.update(status="reference", model=src, **{f"w_{k}": 0.0 for k in order})
            row[f"w_{src}"] = 1.0
        elif not r.snps >= acfg["min_snps"]:
            row["status"] = "low_coverage"
        elif r.gid in res.index:
            x = res.loc[r.gid]
            row.update(status=x["status"], model=x["model"] if isinstance(x["model"], str) else "", p=x["p"])
            if x["status"] == "fit":
                for k in order:
                    inm = k in x["model"].split("+")
                    row[f"w_{k}"] = round(float(x[f"w_{k}"]), 4) if inm else 0.0
                    row[f"se_{k}"] = round(float(x[f"se_{k}"]), 4) if inm else np.nan
        else:
            continue            # not run (a spike subset)
        rows.append(row)
    return pd.DataFrame(rows, columns=out_columns(order))


def check_table(d, order):
    """Problems with an ancestry table, as a list of strings (empty = sound)."""
    bad = []
    if list(d.columns) != out_columns(order):
        bad.append(f"columns are {list(d.columns)}")
        return bad
    odd = sorted(set(d["status"]) - set(STATUSES))
    if odd:
        bad.append(f"unknown status values {odd}")
    if d["individual"].duplicated().any():
        bad.append("duplicate individuals")
    W = d[[f"w_{k}" for k in order]]
    fit = d["status"].isin(["fit", "reference"])
    s = W[fit].sum(axis=1)
    if ((s - 1).abs() > 0.01).any():
        bad.append(f"{int(((s - 1).abs() > 0.01).sum())} fitted rows whose weights do not sum to 1 +/- 0.01")
    if W[fit].isna().any().any():
        bad.append("fitted rows with blank weights")
    if W[~fit].notna().any().any():
        bad.append("weights on rows that are not fits")
    return bad


def validation(acfg, table):
    """[(name, individual, component, expected, got, ok)] for [[ancestry.validate]]."""
    out = []
    ix = table.set_index("individual")
    for v in acfg.get("validate", []):
        for comp, want in v["expect"].items():
            got = float(ix.loc[v["individual"], f"w_{comp}"]) if v["individual"] in ix.index else float("nan")
            out.append((v["name"], v["individual"], comp, want, got, abs(got - want) <= v.get("tol", 0.10)))
    return out


def region_of(lon, lat):
    if lat < 37 and lon < 25 or lat < 30:
        return "North Africa & Arabia"
    if lon >= 42 and lat < 42:
        return "Iran & Caucasus"
    if lon >= 25 and lat < 42:
        return "Anatolia & Levant"
    if lon >= 30:
        return "Steppe & E Europe"
    if lat >= 54:
        return "N Europe"
    if lat < 46 and lon < 12:
        return "W Mediterranean"
    if lon < 5:
        return "Atlantic Europe"
    if lat < 46.5:
        return "Balkans & Italy"
    return "Central Europe"


def report(acfg, table, secs, path):
    order = acfg["order"]
    run = table[table["status"].isin(["fit", "no_fit"])]
    t = run.assign(region=[region_of(a, b) for a, b in zip(run["lon"], run["lat"])],
                   epoch=((1950 - run["bp"]) // 1000 * 1000).astype(int))
    L = ["# Ancestry spike: qpAdm fit rate" if "spike" in os.path.basename(path) else "# Ancestry: qpAdm fit rate (full run)", "",
         f"{len(run)} individuals with >= {acfg['min_snps']} SNPs were modelled; "
         f"{int((run['status'] == 'fit').sum())} fit ({(run['status'] == 'fit').mean():.0%}). "
         f"Runtime {secs / max(len(run), 1):.1f} s per individual. Rotating outgroups: {acfg['rotate']}.", "",
         f"Other rows: {dict(table['status'].value_counts())}", "", "## By region", "", "| region | n | fit |", "|---|---|---|"]
    for k, g in t.groupby("region"):
        L.append(f"| {k} | {len(g)} | {(g['status'] == 'fit').mean():.0%} |")
    L += ["", "## By epoch (start of millennium, signed year)", "", "| epoch | n | fit |", "|---|---|---|"]
    for k, g in t.groupby("epoch"):
        L.append(f"| {k} | {len(g)} | {(g['status'] == 'fit').mean():.0%} |")
    L += ["", "## Models chosen", "", "| model | n |", "|---|---|"]
    for k, n in run[run["status"] == "fit"]["model"].value_counts().items():
        L.append(f"| {k} | {n} |")
    L += ["", "## Validation", "", "| check | individual | component | expected | got | ok |", "|---|---|---|---|---|---|"]
    val = validation(acfg, table)
    for name, ind, comp, want, got, ok in val:
        L.append(f"| {name} | {ind} | {comp} | {want:.2f} | {got:.2f} | {'yes' if ok else 'NO'} |")
    rate = float((run["status"] == "fit").mean()) if len(run) else 0.0
    gate = rate >= 0.6 and all(v[-1] for v in val)
    L += ["", f"**Gate (>= 60% fit and validations pass): {'PASS' if gate else 'FAIL'}**", ""]
    open(path, "w").write("\n".join(L))
    return gate


def run(cfg, log=print, spike=0, remote=False):
    acfg, bd = cfg["ancestry"], cfg["output"]["build_dir"]
    work = os.path.join(bd, "ancestry")
    os.makedirs(work, exist_ok=True)
    anno_path = os.path.join(bd, "sources", acfg["anno"])
    refs = reference_sets(acfg, people.load_anno(anno_path))
    t = targets(cfg, anno_path)
    log(f"ancestry: {len(t)} in-window individuals, {int((t['snps'] >= acfg['min_snps']).sum())} with >= {acfg['min_snps']} SNPs")
    if spike:
        t = stratified(t[t["snps"] >= acfg["min_snps"]], spike, cfg["surface"]["seed"],
                       [v["individual"] for v in acfg.get("validate", [])])
    ref_gids = {g for ids in refs.values() for g in ids}
    todo = t[(t["snps"] >= acfg["min_snps"]) & ~t["gid"].isin(ref_gids)]
    if os.environ.get("ANCESTRY_ONLY_CACHED"):
        # A partial run over the genotype rows already fetched (--remote): the
        # per-individual results are cached, so the full run later reuses them.
        ind = pd.read_csv(os.path.join(bd, "sources", acfg["geno"]) + ".ind", sep=r"\s+", header=None, names=["gid", "sex", "pop"])
        pos = pd.Series(np.arange(len(ind)), index=ind["gid"])
        have = [os.path.exists(os.path.join(work, "rows", f"{pos[g]}.bin")) for g in todo["gid"]]
        log(f"ancestry: partial run, {sum(have)} of {len(todo)} targets have cached genotype rows")
        todo = todo[have]
    url = next((s["url"] for s in cfg["sources"] if s["file"] == acfg["geno"] + ".geno"), None) if remote else None
    prefix = os.path.join(work, "spike" if spike else "sub")
    rscript = shutil.which("Rscript")
    if not rscript:
        raise SystemExit("ancestry: Rscript not found (isostyle/ancestry/README.md)")
    cache = os.path.abspath(os.path.join(work, "cache_" + acfg["geno"] + "_" + model_hash(acfg, refs)))
    ref_gids_list = [g for ids in refs.values() for g in ids]
    ref_pops_list = [p for p, ids in refs.items() for _ in ids]
    t0 = time.time()
    parts = []
    # In chunks: the R step reads the whole genotype file once per individual,
    # so each file holds the references and at most CHUNK targets.
    for c, k in enumerate(range(0, max(len(todo), 1), CHUNK)):
        part = todo.iloc[k:k + CHUNK]
        if part.empty:
            break
        pre = f"{prefix}_{c:03d}"
        write_subset(cfg, ref_gids_list + list(part["gid"]), ref_pops_list + list(part["gid"]), pre, url,
                     log if c == 0 else (lambda m: None), set(refs))
        json.dump({"prefix": os.path.abspath(pre), "left": acfg["order"], "right": [r["pop"] for r in acfg["right"]],
                   "targets": list(part["gid"]), "p_min": acfg["p_min"], "z_bound": acfg["z_bound"],
                   "max_sources": acfg["max_sources"], "rotate": acfg["rotate"], "cache": cache,
                   "out": os.path.abspath(pre + "_results.csv")}, open(pre + "_model.json", "w"), indent=1)
        subprocess.run([rscript, os.path.join(os.path.dirname(__file__), "ancestry", "run.R"), pre + "_model.json"], check=True)
        parts.append(pd.read_csv(pre + "_results.csv"))
        for ext in (".geno", ".snp", ".ind"):
            os.remove(pre + ext)
        log(f"ancestry: {min(k + CHUNK, len(todo))} of {len(todo)} individuals modelled")
    secs = time.time() - t0
    pd.concat(parts, ignore_index=True).to_csv(prefix + "_results.csv", index=False)
    table = assemble(acfg, t, refs, pd.read_csv(prefix + "_results.csv"))
    bad = check_table(table, acfg["order"])
    if bad:
        raise SystemExit("ancestry: " + "; ".join(bad))
    if spike:
        table.to_csv(os.path.join(work, "spike.csv"), index=False)
        gate = report(acfg, table, secs, os.path.join(work, "spike.md"))
        log(f"ancestry: spike {'passes' if gate else 'FAILS'} the gate; see {work}/spike.md")
        return gate
    os.makedirs(os.path.dirname(acfg["out"]), exist_ok=True)
    table.to_csv(acfg["out"], index=False)
    report(acfg, table, secs, os.path.join(work, "run.md"))
    log(f"ancestry: {dict(table['status'].value_counts())} -> {acfg['out']}")
    return True
