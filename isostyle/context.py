"""Layers that explain gaps: modern country, land then and now, ice."""
import json

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from pipeline.elevation import load_asc

from . import grid as gridmod

# Macro-regions for summaries, by Natural Earth ADM0_A3 code.
REGIONS = {
    "Britain & Ireland": "GBR IRL IMN",
    "France & Benelux": "FRA BEL NLD LUX MCO",
    "Iberia": "ESP PRT AND",
    "Italy & Malta": "ITA MLT SMR VAT",
    "Central Europe": "DEU CHE AUT CZE SVK POL HUN LIE",
    "Nordic": "DNK NOR SWE FIN ISL",
    "Baltic states": "EST LVA LTU",
    "Balkans & Greece": "SVN HRV BIH SRB MNE MKD ALB KOS GRC BGR ROU MDA",
    "Ukraine, Belarus, Russia": "UKR BLR RUS",
    "Anatolia, Caucasus, Levant": "TUR GEO ARM AZE CYP CYN SYR IRQ IRN LBN",
    "North Africa": "MAR DZA TUN",
}
REGION_OF = {code: name for name, codes in REGIONS.items() for code in codes.split()}


def countries(path, crs):
    c = gpd.read_file(path)[["ADM0_A3", "NAME", "geometry"]].to_crs(crs)
    return c


def nearest_country(x, y, ctry, max_km):
    """ADM0_A3 of the country containing each point, or the nearest within max_km."""
    pts = gpd.GeoDataFrame({"i": np.arange(len(x))}, geometry=gpd.points_from_xy(x, y), crs=ctry.crs)
    j = gpd.sjoin_nearest(pts, ctry[["ADM0_A3", "geometry"]], max_distance=max_km * 1000.0, how="left")
    j = j[~j.index.duplicated()]
    return j["ADM0_A3"].fillna("").values


def sea_level(curve, years):
    c = np.array(curve, float)
    return np.interp(years, c[:, 0], c[:, 1])


def land_fractions(grid, etopo_path, levels):
    """Share of each cell above sea level, for each level in `levels` (m) and
    for today (level 0, returned last). Area-weighted over ETOPO cells.
    Ignores isostatic rebound and lake basins."""
    arr, tf = load_asc(etopo_path)
    rows, cols = np.indices(arr.shape)
    lat = (tf.y0 + rows * tf.e).ravel()
    lon = (tf.x0 + cols * tf.a).ravel()
    z = arr.ravel()
    b = grid.to_crs("EPSG:4326").total_bounds
    sel = (lon >= b[0] - 1) & (lon <= b[2] + 1) & (lat >= b[1] - 1) & (lat <= b[3] + 1) & ~np.isnan(z)
    lon, lat, z = lon[sel], lat[sel], z[sel]
    cell = gridmod.locate(grid, lon, lat)
    ok = cell >= 0
    cell, z, w = cell[ok], z[ok], np.cos(np.radians(lat[ok]))
    tot = np.bincount(cell, weights=w, minlength=len(grid))
    out = np.zeros((len(grid), len(levels) + 1))
    for k, lv in enumerate(list(levels) + [0.0]):
        out[:, k] = np.bincount(cell, weights=w * (z > lv), minlength=len(grid))
    return out / np.maximum(tot, 1e-12)[:, None]


def ice(grid, terrain_path, years):
    """True where the hex-map pipeline's terrain has "Ice" at the nearest hex
    centre in that year. The terrain is a step function of sparse year keys."""
    feats = json.load(open(terrain_path))["features"]
    cen = np.array([[(f["properties"]["left"] + f["properties"]["right"]) / 2,
                     (f["properties"]["top"] + f["properties"]["bottom"]) / 2] for f in feats])
    near = cKDTree(cen).query(np.column_stack([grid["lon"], grid["lat"]]))[1]
    out = np.zeros((len(grid), len(years)), dtype=bool)
    for i, k in enumerate(near):
        t = sorted((int(y), v) for y, v in feats[k]["properties"]["terrain"].items())
        for j, year in enumerate(years):
            val = None
            for y, v in t:
                if y <= year:
                    val = v
            out[i, j] = (val if val is not None else t[0][1]) == "Ice"
    return out


def region_name(code):
    return REGION_OF.get(code, "Other" if code else "Offshore")


def country_table(ctry):
    return pd.Series(ctry["NAME"].values, index=ctry["ADM0_A3"].values).to_dict()
