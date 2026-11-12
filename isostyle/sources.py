"""External datasets that record a material class at a place and time.

Each reader returns rows of: layer (a layer id in data/isostyle/layers.toml), present (1, or 0 for a recorded
absence), site, lon, lat, tpq, taq (signed years; NaN when the record has a
radiocarbon age instead), bp, std, grave, source, group. Rows sharing a
`group` (the dates of one published phase) are merged into one record.
Only MedAfriCarbon and Rotunno & Crema record absences, and only of pottery.
"""
import csv
import io
import os
import re
import zipfile

import numpy as np
import pandas as pd

COLS = ["layer", "present", "site", "lon", "lat", "tpq", "taq", "bp", "std", "grave", "source", "group"]


def _rows(material, site, lon, lat, tpq=np.nan, taq=np.nan, bp=np.nan, std=np.nan, grave=False, source="",
          present=1, group=""):
    df = pd.DataFrame({"layer": material, "present": present, "site": site,
                       "lon": pd.to_numeric(lon, errors="coerce"), "lat": pd.to_numeric(lat, errors="coerce"),
                       "tpq": tpq, "taq": taq, "bp": pd.to_numeric(bp, errors="coerce"),
                       "std": pd.to_numeric(std, errors="coerce"), "grave": grave, "source": source, "group": group})
    return df[COLS]


def evershed(path):
    d = pd.read_csv(path, encoding="latin-1")
    c = d.columns
    return _rows("pottery", d[c[0]], d[c[3]], d[c[2]], -d[c[5]].astype(float), -d[c[6]].astype(float),
                 source="Evershed et al. 2022")


def rigaud2018(path):
    a = pd.read_excel(path, sheet_name="A")
    b = pd.read_excel(path, sheet_name="B")
    src = "Rigaud et al. 2018"
    return pd.concat([
        _rows("pottery", a["SiteName"], a["Longitude"], a["Latitude"], -a["EarliestDateBC"].astype(float),
              -a["LatestDateBC"].astype(float), source=src),
        _rows("ornaments", b["SiteName"], b["Longitude"], b["Latitude"], -b["EarliestDateBC"].astype(float),
              -b["LatestDateBC"].astype(float), source=src)])


def dolbunova(path, span):
    d = pd.read_excel(path, sheet_name=0)[["Site", "Longitude", "Latitude"]].dropna().drop_duplicates()
    return _rows("pottery", d["Site"], d["Longitude"], d["Latitude"], float(span[0]), float(span[1]),
                 source="Dolbunova et al. 2023 (dataset-wide span)")


def _zip_member(path, pattern):
    z = zipfile.ZipFile(path)
    name = next(n for n in z.namelist() if re.search(pattern, n) and "__MACOSX" not in n)
    return io.BytesIO(z.read(name))


def windler(path):
    sites = pd.read_csv(_zip_member(path, r"CSV/tbl_Sites\.csv$"), sep=None, engine="python")
    dating = pd.read_csv(_zip_member(path, r"CSV/tbl_Dating\.csv$"), sep=None, engine="python")
    bins = [(c, [-float(v) for v in re.findall(r"\d+", c)]) for c in dating.columns if re.match(r"^\d{4} ?- ?\d{4}$", c)]
    span = {}
    for _, r in dating.iterrows():
        on = [b for c, b in bins if pd.notna(r[c]) and str(r[c]).strip() not in ("", "0")]
        if on:
            span[str(r["txtCulture"]).strip()] = (min(b[0] for b in on), max(b[1] for b in on))
    cul = sites["txtCulture"].astype(str).str.strip()
    ok = cul.isin(span)
    s = sites[ok]
    num = lambda v: v.astype(str).str.replace(",", ".")
    out = _rows("ornaments", s["txtSite"], num(s["dblLongitude"]), num(s["dblLatitude"]),
                [span[c][0] for c in cul[ok]], [span[c][1] for c in cul[ok]],
                grave=s["txtType"].astype(str).str.contains("grave|burial|cemeter", case=False).values,
                source="Windler 2019 (dated by culture)")
    out.attrs["dropped"] = int((~ok).sum())
    return out


def tsirintoulaki(path):
    d = pd.read_csv(_zip_member(path, r"barbed_points_edit\.csv$"), sep=None, engine="python")
    d.columns = [c.strip() for c in d.columns]
    return _rows("bone_antler", d["Site"], d["Longitude"], d["Latitude"], bp=pd.to_numeric(d["Age_C14_BP"], errors="coerce"),
                 std=pd.to_numeric(d["SD"], errors="coerce"), source="Tsirintoulaki et al. 2023")


BDA_FLAGS = {"Céramique présence": "pottery", "Industrie osseuse présence": "bone_antler",
             "Macrooutillage présence": "ground_stone", "IndLith présence": "flaked_stone"}


def bda(path):
    occ = pd.read_excel(_zip_member(path, r"Occupations\.xlsx$"))
    sites = pd.read_excel(_zip_member(path, r"Sites\.xlsx$"))
    sites["k"] = pd.to_numeric(sites["id_sites_2019"], errors="coerce")
    m = occ.merge(sites[["k", "Nom complet", "Latitude", "Longitude"]], left_on="id_site_lié", right_on="k", how="inner")
    out = []
    for col, mat in BDA_FLAGS.items():
        s = m[m[col].astype(str).str.lower().eq("oui") & m["TPQ_BCE"].notna() & m["TAQ_BCE"].notna()]
        out.append(_rows(mat, s["Nom complet"], s["Longitude"], s["Latitude"], s["TPQ_BCE"].astype(float),
                         s["TAQ_BCE"].astype(float), grave=s["Pratiques funéraires"].notna().values,
                         source="BDA (Perrin 2021)"))
    return pd.concat(out)


# ------------------------------------------------------- North Africa, SW Asia
def _yes(v):
    return str(v).strip().lower() in ("yes", "<")


def medafricarbon(path):
    """MedAfriCarbon phases, one row per radiocarbon date of the phase.
    Pottery: yes / "<" (low frequency) present, "no" absent. Flaked stone:
    present if any lithic tool class is yes; ground stone: present if
    polished axes/adzes are yes. A "no" for a lithic class is not an absence
    of the material class, so it is not used."""
    rd = lambda n: pd.read_csv(_zip_member(path, rf"(^|/){n}$"), encoding_errors="replace")
    ph, dt, st = rd("phaseTable.csv"), rd("dateTable.csv"), rd("siteTable.csv")
    dt = dt[pd.to_numeric(dt["CRA"], errors="coerce").notna() & pd.to_numeric(dt["Error"], errors="coerce").gt(0)]
    d = dt.merge(ph, on=["Site_ID", "Phase_ID"]).merge(st, on="Site_ID")
    lith = ["Lithics_Backed_Tools_Geometrics", "Lithics_Notches_Denticulates", "Lithics_Arrowheads", "Lithics_Bifacial_Tools"]
    common = dict(site=d["Site_Name"], lon=d["Decimal_Degrees_Long"], lat=d["Decimal_Degrees_Lat"], bp=d["CRA"],
                  std=d["Error"], source="MedAfriCarbon (Lucarini et al. 2020)", group="maf:" + d["Phase_ID"].astype(str))
    pot = d["Pottery"].astype(str).str.strip().str.lower()
    parts = []
    for sel, present in ((pot.isin(["yes", "<"]), 1), (pot.eq("no"), 0)):
        parts.append(_rows("pottery", **{k: v[sel] if hasattr(v, "__getitem__") and not isinstance(v, str) else v
                                         for k, v in common.items()}, present=present))
    fl = d[lith].apply(lambda c: c.map(_yes)).any(axis=1)
    parts.append(_rows("flaked_stone", **{k: v[fl] if not isinstance(v, str) else v for k, v in common.items()}))
    gs = d["Lithics_Polished_Axes_Adzes"].map(_yes)
    parts.append(_rows("ground_stone", **{k: v[gs] if not isinstance(v, str) else v for k, v in common.items()}))
    return pd.concat(parts)


def rotunno(path):
    """Rotunno & Crema 2025: Saharan and Sahelian dates with pottery 1/0 in
    their layer. The dates of one site with the same pottery state are one record."""
    d = pd.read_csv(path, encoding_errors="replace")
    flag = pd.to_numeric(d["pottery"], errors="coerce")
    d = d[flag.isin([0, 1])]
    return _rows("pottery", d["Sitename"], d["Longitude"], d["Latitude"], bp=d["Yrs BP"], std=d["STD"],
                 present=flag[flag.isin([0, 1])].astype(int).values, source="Rotunno & Crema 2025",
                 group=("rot:" + d["Site_code"].astype(str) + ":" + flag[flag.isin([0, 1])].astype(int).astype(str)).values)


def _csv_rows(path):
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        r = csv.reader(f)
        next(r)
        return [row for row in r if row]


_PERIOD = re.compile(r"_(\d{3,5}|None)_(\d{3,5}|None)(?=_|$|;|,)")
GROUND = re.compile(r"\b(axe|adze|grindstone|grinding stone|pestle|mortar|mace ?head|quern|polisher|grater|hammer)\b", re.I)
BONE_TYPES = re.compile(r"\b(awl|spatula|needle|harpoon|fish ?hook|spoon|point)\b", re.I)
BONE_MAT = re.compile(r"\b(bone|antler|horn)\b", re.I)
STONE_MAT = re.compile(r"\b(stone|basalt|limestone|marble|flint|obsidian|copper|metal|gold|clay|shell)\b", re.I)


def defc(sites_path, areas_path, finds_path):
    """DEFC: finds per excavated area, dated by the area's periods (start and
    end years in the period names). The export joins multi-valued fields with
    unquoted commas, so fields are found by pattern, not by column."""
    sites = {}
    for row in _csv_rows(sites_path):
        nums = []
        for v in row[7:]:
            try:
                nums.append(float(v))
            except ValueError:
                nums.append(None)
        for a, b in zip(nums, nums[1:]):
            if a is not None and b is not None and 30 <= a <= 45 and 18 <= b <= 46:
                sites.setdefault(row[1].strip(), (b, a))
                break
    areas = {}
    for row in _csv_rows(areas_path):
        text = ",".join(row)
        spans = [(int(a), int(b)) for a, b in _PERIOD.findall(text) if a != "None" and b != "None"]
        if not spans or row[1].strip() not in sites:
            continue
        lon, lat = sites[row[1].strip()]
        areas[row[0].strip()] = (row[1].strip(), lon, lat, -max(a for a, _ in spans), -min(b for _, b in spans),
                                 bool(re.search(r"cemetery|grave", row[2], re.I)))
    out = []
    for row in _csv_rows(finds_path):
        m = re.search(r"_(\d+)$", row[1].strip())
        if not m or m.group(1) not in areas:
            continue
        site, lon, lat, tpq, taq, grave = areas[m.group(1)]
        text = ",".join(row[3:])
        kind = row[3].strip().lower()
        mats = []
        if kind == "pottery":
            mats.append("pottery")
        elif kind == "lithics":
            mats.append("flaked_stone")
        elif kind == "small finds":
            if "- jewellery" in text or re.search(r"\b(bead|pendant)\b", text, re.I):
                mats.append("ornaments")
            if GROUND.search(text):
                mats.append("ground_stone")
            if BONE_MAT.search(text) and ("- tool" in text) or (BONE_TYPES.search(text) and not STONE_MAT.search(text)):
                mats.append("bone_antler")
        for mat in mats:
            out.append((mat, site, lon, lat, tpq, taq, grave, f"defc:{m.group(1)}"))
    d = pd.DataFrame(out, columns=["material", "site", "lon", "lat", "tpq", "taq", "grave", "group"])
    d = d.drop_duplicates(["material", "group"])
    return _rows(d["material"], d["site"], d["lon"], d["lat"], d["tpq"].astype(float), d["taq"].astype(float),
                 grave=d["grave"].values, source="DEFC (Aspöck et al.)", group=d["group"].values)


def dobsiss(path):
    """DObsiSS v2.0: sourced obsidian per site context, dated by ASPRO period."""
    d = pd.read_csv(_zip_member(path, r"DObsiSS_2\.0\.csv$"), encoding_errors="replace")
    ch = pd.read_csv(_zip_member(path, r"/chronology\.csv$"), encoding_errors="replace")
    begin = dict(zip(ch["Period"].astype(int), ch["Begin (cal. BC)"].fillna(20000)))
    end = dict(zip(ch["Period"].astype(int), ch["End (cal. BC)"]))
    tpq, taq = [], []
    for v in d["ASPRO"].astype(str):
        ps = [int(x) for x in re.findall(r"\d+", v) if int(x) in begin]
        tpq.append(-max(begin[p] for p in ps) if ps else np.nan)
        taq.append(-min(end[p] for p in ps) if ps else np.nan)
    return _rows("flaked_stone", d["Site"], d["Longitude"], d["Latitude"], np.array(tpq, float), np.array(taq, float),
                 source="DObsiSS v2.0 (Batist)", group=("dob:" + d["Site ID"].astype(str)).values)


def jordan2016(path, half=200):
    """Jordan et al. 2016: earliest pottery-bearing date per site (African
    rows, hand-extracted; data/isostyle/inputs/README.md). Presence only,
    dated median calibrated age ± `half` years."""
    d = pd.read_csv(path)
    year = 1950 - pd.to_numeric(d["cal_bp"], errors="coerce")
    return _rows("pottery", d["site"], d["lon"], d["lat"], (year - half).values, (year + half).values,
                 source="Jordan et al. 2016 (earliest pottery)", group=("jor:" + d["site"].astype(str)).values)


# ------------------------------------------------------------- subsistence
CEREAL_CROPS = {"barley", "emmer wheat", "wheat", "einkorn wheat"}
LIVESTOCK = re.compile(r"\b(bos|ovis|capra|sus)\b", re.I)


def _phase_rows(df, layer, present_col, source, group_prefix):
    return _rows(layer, df["site"], df["lon"], df["lat"], df["tpq"].astype(float), df["taq"].astype(float),
                 present=df[present_col].astype(int).values, source=source,
                 group=(group_prefix + df["key"].astype(str)).values)


def swasia_flora(path):
    """Arranz-Otaegui & Roe 2023, SW Asian Neolithic plant remains per site
    phase (from ORIGINS, ADEMNES, COMPAG). Cereals present if barley, emmer,
    einkorn or other wheat is recorded; absent if the phase has plant remains
    but none of those. Wild-type and domestic-type grain are not told apart.
    Ages are cal BP."""
    d = pd.read_csv(path, sep="\t", low_memory=False)
    d["cer"] = d["founder_crop"].isin(CEREAL_CROPS) & (pd.to_numeric(d["n"], errors="coerce").fillna(1) > 0)
    g = d.groupby(["site_name", "phase_code"]).agg(site=("site_name", "first"), lon=("longitude", "first"),
                                                   lat=("latitude", "first"), a=("age_start", "max"),
                                                   b=("age_end", "min"), cer=("cer", "any")).reset_index()
    g["tpq"], g["taq"] = 1950 - g[["a", "b"]].max(axis=1), 1950 - g[["a", "b"]].min(axis=1)
    g["key"] = g["site_name"] + ":" + g["phase_code"].astype(str)
    return _phase_rows(g, "cereals", "cer", "Arranz-Otaegui & Roe 2023 (SW Asia flora)", "swa:")


def _livestock_phase(df, site_cols, n_col, dom_col, absent_min):
    """Per phase: present if a domestic cattle, sheep, goat or pig is recorded;
    absent if at least `absent_min` specimens are identified and no livestock
    taxon is domestic or of uncertain status. Else NaN (dropped)."""
    df = df.assign(n=pd.to_numeric(df[n_col], errors="coerce"))
    df["stock"] = df["taxon"].astype(str).str.contains(LIVESTOCK)
    df["dom"] = df["stock"] & df[dom_col]
    df["maybe"] = df["stock"] & df["uncertain"]
    g = df.groupby("key").agg(**{c: (c, "first") for c in site_cols}, total=("n", "sum"), n_taxa=("taxon", "nunique"),
                              dom=("dom", "any"), maybe=("maybe", "any")).reset_index()
    g["present"] = np.where(g["dom"], 1, np.where(~g["maybe"] & ((g["total"] >= absent_min) | (g["n_taxa"] >= 8)), 0, -1))
    return g[g["present"] >= 0]


def ademnes_fauna(fauna_path, phase_path, site_path, absent_min=50):
    """ADEMNES (Riehl, Tübingen) faunal lists per phase, as scraped into the
    Arranz-Otaegui & Roe 2023 repository. `domestic_status` D is domestic;
    "D / W" counts as uncertain. Phase dates are years BC."""
    f = pd.read_csv(fauna_path, sep="\t")
    ph = pd.read_csv(phase_path, sep="\t")
    st = pd.read_csv(site_path, sep="\t")
    stat = f["domestic_status"].astype(str).str.replace(" ", "").str.upper()
    f = f.assign(isdom=stat.eq("D"), uncertain=stat.eq("D/W"), key=f["site_code"].astype(str) + ":" + f["phase_code"].astype(str))
    ph = ph.assign(key=ph["site_code"].astype(str) + ":" + ph["phase_code"].astype(str))
    f = f.merge(ph[["key", "date_earliest", "date_latest"]], on="key", how="left")
    f = f.merge(st[["site_code", "latitude", "longitude"]], on="site_code", how="left")
    f = f.rename(columns={"site_name": "site", "longitude": "lon", "latitude": "lat"})
    f["tpq"] = -pd.to_numeric(f["date_earliest"], errors="coerce")
    f["taq"] = -pd.to_numeric(f["date_latest"], errors="coerce")
    f.loc[f["taq"] == 0, "taq"] = np.nan
    g = _livestock_phase(f, ["site", "lon", "lat", "tpq", "taq"], "n", "isdom", absent_min)
    g = g[g["tpq"].notna() & g["taq"].notna()]
    return _phase_rows(g.rename(columns={"present": "p"}), "domestic_livestock", "p", "ADEMNES fauna (Riehl)", "adf:")


DOMESTIC_LABEL = re.compile(r"ovis aries|capra hircus|bos taurus|sus scrofa domesticus|\bf\. (aries|hircus|taurus|domestic)", re.I)


def opencontext_eol(path, absent_min=50):
    """Open Context integrated Anatolian zooarchaeology (Arbuckle et al. 2014),
    summary per site and period. Only taxa the analyst named as the domestic
    species count as domestic; "Sheep/goat", "Bos", "Sus" are uncertain."""
    d = pd.read_csv(path)
    lab = d["EOL Taxa Label"].astype(str) + " " + d["Analyst Taxanomic Designation (Source data)"].astype(str)
    d = d.assign(taxon=lab, isdom=lab.str.contains(DOMESTIC_LABEL), key=d["Site"] + ":" + d["Start BCE"].astype(str),
                 site=d["Site"], lon=d["Longitude"], lat=d["Latitude"], tpq=-d["Start BCE"], taq=-d["End BCE"])
    d["uncertain"] = ~d["isdom"]
    g = _livestock_phase(d, ["site", "lon", "lat", "tpq", "taq"], "Specimen Count", "isdom", absent_min)
    # "uncertain" here is any livestock-genus taxon not named domestic, so an
    # absence needs no livestock genus at all.
    return _phase_rows(g.rename(columns={"present": "p"}), "domestic_livestock", "p",
                       "Open Context Anatolian zooarchaeology", "oce:")


def phelps_fauna(path, absent_min=50):
    """Phelps et al. 2019 (PANGAEA 904942): African Holocene faunal
    assemblages; category "Domestic" marks domestic taxa. Dated by the
    assemblage's calculated cal BP range."""
    a = pd.read_csv(_zip_member(path, r"Appendix_1_assemblages\.csv$"))
    dt = pd.read_csv(_zip_member(path, r"Appendix_2_dates\.csv$"))
    fa = pd.read_csv(_zip_member(path, r"Appendix_3_fauna\.csv$"))
    fa = fa[pd.to_numeric(fa["present"], errors="coerce").eq(1) & ~pd.to_numeric(fa["intrusion"], errors="coerce").eq(1)]
    span = dt.groupby("assemblage_number").agg(s=("calculated_start_date", "max"), e=("calculated_end_date", "min"))
    fa = fa.merge(a, on="assemblage_number").merge(span, left_on="assemblage_number", right_index=True)
    fa = fa.assign(taxon=fa["genus"].astype(str), isdom=fa["category"].astype(str).str.lower().eq("domestic"),
                   uncertain=False, key=fa["assemblage_number"].astype(int).astype(str),
                   site=fa["assemblage_name"], lon=fa["longitude"], lat=fa["latitude"],
                   tpq=1950 - fa["s"], taq=1950 - fa["e"], NISP=pd.to_numeric(fa["NISP"], errors="coerce"))
    g = _livestock_phase(fa, ["site", "lon", "lat", "tpq", "taq"], "NISP", "isdom", absent_min)
    return _phase_rows(g.rename(columns={"present": "p"}), "domestic_livestock", "p", "Phelps et al. 2019 (Africa)", "phe:")


def load(cfg, log=print):
    d = os.path.join(cfg["output"]["build_dir"], "sources")
    spans = cfg["presence"].get("spans", {})
    readers = [("evershed2022_lipid.csv", evershed, ()), ("rigaud2018_s1.xlsx", rigaud2018, ()),
               ("dolbunova2023_ora.xlsx", dolbunova, (spans.get("dolbunova", [-6000, -4000]),)),
               ("windler2019_spondylus.zip", windler, ()), ("tsirintoulaki2023.zip", tsirintoulaki, ()),
               ("bda2021.zip", bda, ()), ("medafricarbon_v1.0.3.zip", medafricarbon, ()),
               ("rotunno2025_c14data.csv", rotunno, ()), ("dobsiss_v2.0.zip", dobsiss, ()),
               ("defc_sites.csv", defc, (os.path.join(d, "defc_areas.csv"), os.path.join(d, "defc_finds.csv"))),
               ("swasia_flora.tsv", swasia_flora, ()),
               ("ademnes_fauna.tsv", ademnes_fauna, (os.path.join(d, "ademnes_phase.tsv"), os.path.join(d, "ademnes_site.tsv"))),
               ("opencontext_eol_summary.csv", opencontext_eol, ()),
               ("phelps2019_fauna.zip", phelps_fauna, ())]
    if pc_inputs := cfg["presence"].get("inputs"):
        readers += [(os.path.abspath(p), globals()[fn], ()) for fn, p in pc_inputs.items()]
    parts = []
    for fname, fn, args in readers:
        path = os.path.join(d, fname)
        if not os.path.exists(path):
            log(f"sources: {fname} missing, skipped (run `python -m isostyle fetch`)")
            continue
        df = fn(path, *args)
        df = df.dropna(subset=["lon", "lat"])
        df = df[df["tpq"].notna() & df["taq"].notna() & (df["tpq"] < df["taq"]) | df["bp"].notna()]
        df["group"] = df["group"].fillna("").astype(str)
        df["present"] = df["present"].astype(int)
        absent = int((df["present"] == 0).sum())
        log(f"sources: {fname}: {len(df)} records ({df['layer'].value_counts().to_dict()}"
            + (f"; {absent} recorded absences" if absent else "") + ")")
        parts.append(df)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=COLS)
