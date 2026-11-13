"""River reaches from the GEOGLOWS v2 stream network (TDX-Hydro).

Replaces HydroRIVERS (WWF licence, which can't be passed on under the
project's CC BY-SA data licence). GEOGLOWS v2 is CC BY 4.0; its streams are a
hydrologically conditioned subset of NGA's TDX-Hydro (CC BY-SA 4.0). See
data/ATTRIBUTIONS.toml (`geoglows`, `tdx-hydro`) and data/rivers/SOURCES.md.

Two downloads (`make build/geoglows`): the global attribute table
(`v2-model-table.parquet`: LINKNO, DSLINKNO, DSContArea, TerminalLink, ...)
and the global simplified stream lines (`global_streams_simplified.gpkg`,
LINKNO + geometry in EPSG:4326). They are joined on LINKNO.

The result has the same shape the river tracer used with HydroRIVERS:
  id         LINKNO
  next       DSLINKNO, 0 at an outlet (GEOGLOWS uses -1)
  upland     DSContArea in km² (upstream area at the reach's downstream end,
             like HydroRIVERS' UPLAND_SKM)
  endorheic  1 if the reach's network ends inland. GEOGLOWS has no such
             flag; a network drains to the sea if its terminal link's mouth
             is on, or next to, a hex of today's ocean (ocean_mask at sea
             level 0 with the [[sea.channel]] straits open in 1950, so the
             Black Sea and the Baltic are sea, the Caspian and Aral are not).
  coords     (N, 2) lon/lat, upstream to downstream
"""
import os
import pickle

import numpy as np


def _lines(geom):
    """Coordinates of a (Multi)LineString as one upstream-to-downstream run.
    TDX-Hydro lines run downstream to upstream (a reach starts where its
    downstream neighbour ends), so they are reversed."""
    import shapely
    if geom is None:
        return None
    if geom.geom_type == "MultiLineString":
        geom = shapely.line_merge(geom)
        if geom.geom_type == "MultiLineString":
            c = np.concatenate([np.asarray(g.coords) for g in geom.geoms])
            return c[::-1, :2].astype(np.float64)
    return np.asarray(geom.coords, dtype=np.float64)[::-1, :2]


def load(cfg, box, sea_hex=None):
    """Reaches with at least `min_upland` km² upstream inside `box` (lon0,
    lat0, lon1, lat1). `sea_hex(points) -> bool array` says whether each
    point is at the sea (see module doc); without it every outlet counts as
    the sea. Cached in cfg["cache"]."""
    import pandas as pd
    import pyogrio
    cache = cfg["cache"]
    newest = max(os.path.getmtime(p) for p in (cfg["table"], cfg["streams"]))
    if os.path.exists(cache) and os.path.getmtime(cache) >= newest:
        with open(cache, "rb") as f:
            r = pickle.load(f)
        if (r["min_upland"] == cfg["min_upland"] and r["box"] == list(box)
                and r.get("sea_checked") == (sea_hex is not None)
                and r.get("marine") == list(cfg.get("marine_lakes", []))):
            return r
    t = pd.read_parquet(cfg["table"], columns=["LINKNO", "DSLINKNO", "DSContArea", "TerminalLink"])
    t = t[t["DSContArea"] >= cfg["min_upland"] * 1e6]
    g = pyogrio.read_dataframe(cfg["streams"], bbox=tuple(box), columns=["LINKNO"])
    g = g.merge(t, on="LINKNO", how="inner")
    coords = [_lines(geom) for geom in g.geometry]
    keep = np.array([c is not None and len(c) >= 2 for c in coords])
    g = g[keep].reset_index(drop=True)
    coords = [c for c, k in zip(coords, keep) if k]
    ids = g["LINKNO"].to_numpy()
    nxt = g["DSLINKNO"].to_numpy().copy()
    nxt[nxt < 0] = 0
    up = g["DSContArea"].to_numpy() / 1e6
    # Outlets: links with no downstream link. Their mouth decides the whole
    # network's (TerminalLink's) endorheic flag.
    outlet = nxt == 0
    endo_by_terminal = {}
    if sea_hex is not None and outlet.any():
        mouths = np.array([coords[i][-1] for i in np.flatnonzero(outlet)])
        at_sea = sea_hex(mouths)
        for i, s in zip(np.flatnonzero(outlet), at_sea):
            endo_by_terminal[g["TerminalLink"].iat[i]] = 0 if s else 1
    endo = np.array([endo_by_terminal.get(tl, 0) for tl in g["TerminalLink"]], dtype=int)
    r = {"min_upland": cfg["min_upland"], "box": list(box), "sea_checked": sea_hex is not None,
         "marine": list(cfg.get("marine_lakes", [])),
         "id": ids, "next": nxt, "upland": up, "endorheic": endo, "coords": coords}
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "wb") as f:
        pickle.dump(r, f)
    return r


def sea_hex_fn(grid, arr, tf, sea, locate, lakes=(), marine=(), radius=0.25):
    """`points -> bool`: is each river mouth at today's sea?

    A mouth is at the sea if an ETOPO cell within `radius` degrees of it is
    below 0 m and that cell is today's sea: its hex, or a neighbour, is open
    ocean (ocean_mask at 0 m, with the [[sea.channel]] straits open in
    1950), or it lies in the box of a catalogued lake (data/lakes/lakes.toml)
    whose key is in `marine`: seas that are marine today but join the ocean
    through straits narrower than a hex (Kerch for the Sea of Azov, the
    Danish straits for the Baltic). Raster cells, not hex medians, because
    deltas and shallow bays (the Don, the Neva) put the mouth hex and its
    neighbours above 0 m. Below-zero cells elsewhere (the Caspian, the Dead
    Sea, Qattara) make a mouth endorheic. `locate(points) -> hex indices`."""
    from .elevation import channel_mask, hex_median, ocean_mask
    elev = hex_median(grid, arr, tf)
    edge = np.array([len(n) < 6 for n in grid.neighbours])
    ocean = ocean_mask(elev, 0.0, grid.neighbours, edge, sea["seed_depth"],
                       channel_mask(grid.centres, sea.get("channel", []), year=1950))
    near = ocean.copy()
    for h in np.flatnonzero(ocean):
        near[grid.neighbours[h]] = True
    boxes = [lk["box"] for lk in lakes if lk.get("key") in marine]
    r_px = int(np.ceil(radius / abs(tf.a)))

    def at_sea(points):
        out = np.zeros(len(points), dtype=bool)
        hexes = locate(np.asarray(points))
        for k, (x, y) in enumerate(np.asarray(points)):
            if hexes[k] < 0:
                out[k] = True       # off the grid: the river leaves the map
                continue
            c, r = int(round(float(tf.col(x)))), int(round(float(tf.row(y))))
            win = arr[max(r - r_px, 0):r + r_px + 1, max(c - r_px, 0):c + r_px + 1]
            rr, cc = np.nonzero(np.nan_to_num(win, nan=np.inf) < 0)
            if not len(rr):
                continue
            lon = tf.x0 + (cc + max(c - r_px, 0)) * tf.a
            lat = tf.y0 + (rr + max(r - r_px, 0)) * tf.e
            if any(((lon >= b[0]) & (lon <= b[2]) & (lat >= b[1]) & (lat <= b[3])).any() for b in boxes):
                out[k] = True
                continue
            h = locate(np.column_stack([lon, lat]))
            out[k] = bool(near[h[h >= 0]].any())
        return out
    return at_sea
