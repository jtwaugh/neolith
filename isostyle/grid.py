"""The analysis grid: an equal-area hexagon grid, or one read from a file.

Every grid is a GeoDataFrame in the working CRS with columns
cell (id), x, y (centre, metres), lon, lat (centre, degrees) and geometry.
"""
import math

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon


def slices(tcfg):
    """Slice centres (signed years) and the common half-width."""
    if tcfg.get("slices_file"):
        years = np.array(sorted(int(line) for line in open(tcfg["slices_file"]) if line.strip()))
        half = np.diff(years).min() / 2
    else:
        years = np.arange(tcfg["start"], tcfg["end"] + 1, tcfg["step"])
        half = tcfg["step"] / 2
    return years, half


def build_hex(region, cell_km, crs):
    """Flat-topped hexagons `cell_km` flat to flat, centres inside the box."""
    fwd = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    inv = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    # Project the box outline densely to find the projected extent.
    lons = np.linspace(region["lon_min"], region["lon_max"], 400)
    lats = np.linspace(region["lat_min"], region["lat_max"], 400)
    ex = np.concatenate([lons, lons, np.full(400, region["lon_min"]), np.full(400, region["lon_max"])])
    ey = np.concatenate([np.full(400, region["lat_min"]), np.full(400, region["lat_max"]), lats, lats])
    px, py = fwd.transform(ex, ey)
    h = cell_km * 1000.0             # flat-to-flat = row spacing
    rad = h / math.sqrt(3)           # circumradius
    dx = 1.5 * rad                   # column spacing
    q0, q1 = math.floor(px.min() / dx), math.ceil(px.max() / dx)
    r0, r1 = math.floor(py.min() / h) - 1, math.ceil(py.max() / h) + 1
    qs, rs = np.meshgrid(np.arange(q0, q1 + 1), np.arange(r0, r1 + 1))
    qs, rs = qs.ravel(), rs.ravel()
    x = qs * dx
    y = (rs + 0.5 * (qs % 2)) * h
    lon, lat = inv.transform(x, y)
    keep = ((lon >= region["lon_min"]) & (lon <= region["lon_max"])
            & (lat >= region["lat_min"]) & (lat <= region["lat_max"]))
    ang = np.radians(np.arange(0, 360, 60))
    cx, cy = rad * np.cos(ang), rad * np.sin(ang)
    polys = [Polygon(np.column_stack([xi + cx, yi + cy])) for xi, yi in zip(x[keep], y[keep])]
    return gpd.GeoDataFrame({
        "cell": np.arange(1, keep.sum() + 1), "q": qs[keep], "r": rs[keep],
        "x": x[keep], "y": y[keep], "lon": lon[keep], "lat": lat[keep],
    }, geometry=polys, crs=crs)


def load(path, crs):
    """A user-supplied polygon grid, reprojected to the working CRS."""
    g = gpd.read_file(path).to_crs(crs)
    g = g[g.geometry.notna()].reset_index(drop=True)
    idcol = next((c for c in ("cell", "id", "ID", "h3", "h3_index") if c in g.columns), None)
    g["cell"] = g[idcol] if idcol else np.arange(1, len(g) + 1)
    c = g.geometry.centroid
    g["x"], g["y"] = c.x, c.y
    g["lon"], g["lat"] = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform(c.x.values, c.y.values)
    return g[["cell", "x", "y", "lon", "lat", "geometry"]]


def get(cfg):
    gc = cfg["grid"]
    if gc.get("file"):
        return load(gc["file"], gc["crs"])
    return build_hex(cfg["region"], gc["cell_km"], gc["crs"])


def locate(grid, lon, lat):
    """Row index in `grid` of the cell containing each point (-1 if none)."""
    x, y = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True).transform(np.asarray(lon), np.asarray(lat))
    pts = gpd.GeoDataFrame({"i": np.arange(len(x))}, geometry=gpd.points_from_xy(x, y), crs=grid.crs)
    j = gpd.sjoin(pts, grid[["geometry"]], predicate="within", how="left")
    j = j[~j.index.duplicated()]  # a point on a shared edge joins twice
    return j["index_right"].fillna(-1).astype(int).values


# ------------------------------------------------------------- game grid
def _read_json(path, tries=5):
    """The hex-map build rewrites its output in place; retry a torn read."""
    import json
    import time
    for k in range(tries):
        try:
            with open(path) as f:
                return json.load(f)
        except json.JSONDecodeError:
            if k == tries - 1:
                raise
            time.sleep(5)


def load_game(path, years):
    """The game's hex grid (lon/lat degrees, not equal-area).

    Returns (grid, terrain): grid is a GeoDataFrame in EPSG:4326 with cell,
    lon, lat and geometry; terrain is an array (cells, slices) of the terrain
    class at each slice year, read from the year-keyed step function.
    """
    feats = _read_json(path)["features"]
    p = [f["properties"] for f in feats]
    g = gpd.GeoDataFrame({
        "cell": [q["id"] for q in p],
        "lon": [(q["left"] + q["right"]) / 2 for q in p],
        "lat": [(q["top"] + q["bottom"]) / 2 for q in p],
    }, geometry=[Polygon(f["geometry"]["coordinates"][0]) for f in feats], crs="EPSG:4326")
    terrain = np.empty((len(feats), len(years)), dtype=object)
    for i, q in enumerate(p):
        steps = sorted((int(y), v) for y, v in q["terrain"].items())
        for j, year in enumerate(years):
            val = steps[0][1]
            for y, v in steps:
                if y <= year:
                    val = v
            terrain[i, j] = val
    return g, terrain
