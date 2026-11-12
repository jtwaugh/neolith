"""Köppen–Geiger climate per key frame, from monthly paleoclimate.

Monthly temperature and precipitation come from Beyer, Krapp & Manica 2020
(the same NetCDF as the paleobiomes, cut down by `python -m pipeline biome`).
The classification follows Beck et al. 2018 (Sci. Data 5:180214), Table 1:
0 °C C/D boundary, B before A/C/D/E, Aw and As merged as "Aw/As".

The model's land mask is the modern coastline and its Holocene climate is too
dry over the Sahara and Arabia, so per year: Water hexes are Ocean, land the
model doesn't cover takes its neighbours' class, and `nudge` makes hexes no
drier than their terrain.
"""
import warnings

import numpy as np

from .compose import fill_from_neighbours

# Index = the `koeppen` value; must match neolith-rs values.rs KOEPPEN_CODES.
CODES = [
    "Ocean", "Af", "Am", "Aw/As", "BWh", "BWk", "BSh", "BSk", "Csa", "Csb", "Csc", "Cwa", "Cwb",
    "Cwc", "Cfa", "Cfb", "Cfc", "Dsa", "Dsb", "Dsc", "Dsd", "Dwa", "Dwb", "Dwc", "Dwd", "Dfa",
    "Dfb", "Dfc", "Dfd", "ET", "EF",
]
INDEX = {c: i for i, c in enumerate(CODES)}
OCEAN = 0
MISSING = 31  # "missingno" in the Django palette
NODATA = -1

# Moisture rank for nudging: 0 = desert (BW), 1 = steppe (BS), 2 = not arid.
DESERT, STEPPE, HUMID = 0, 1, 2
LEVELS = {"BW": DESERT, "BS": STEPPE, "humid": HUMID}


def _code_index(codes):
    """Strings like "Cfb" -> int indices; "Aw"/"As" -> "Aw/As"."""
    flat = np.array([INDEX["Aw/As"] if c in ("Aw", "As") else INDEX.get(c, NODATA)
                     for c in codes.ravel()])
    return flat.reshape(codes.shape)


def classify(T, P, lat):
    """Köppen class per cell from monthly climatologies.

    T (°C), P (mm/month): (12, ...) arrays, January first; NaN off land.
    lat: broadcastable to T[0] (summer is Apr-Sep north of the equator).
    Returns (koeppen, humid): int arrays of indices into CODES (NODATA
    where T or P is missing). `humid` is the class the cell would have
    without the B (arid) test, for `nudge`.
    """
    T, P = np.asarray(T, float), np.asarray(P, float)
    shape = T.shape[1:]
    lat = np.broadcast_to(np.asarray(lat, float), shape)
    ok = np.isfinite(T).all(0) & np.isfinite(P).all(0)
    T, P = np.where(ok, T, 0.0), np.where(ok, P, 0.0)

    north = lat >= 0
    amjjas = np.zeros(12, bool)
    amjjas[3:9] = True
    summer = np.where(north[None], amjjas.reshape((12,) + (1,) * len(shape)),
                      ~amjjas.reshape((12,) + (1,) * len(shape)))

    def half(a, mask, fn):
        return fn(np.where(mask, a, np.nan), axis=0)

    MAT, MAP = T.mean(0), P.sum(0)
    Thot, Tcold = T.max(0), T.min(0)
    Tmon10 = (T > 10).sum(0)
    Pdry = P.min(0)
    Psdry, Pswet = half(P, summer, np.nanmin), half(P, summer, np.nanmax)
    Pwdry, Pwwet = half(P, ~summer, np.nanmin), half(P, ~summer, np.nanmax)
    Psum, Pwin = half(P, summer, np.nansum), half(P, ~summer, np.nansum)

    with np.errstate(invalid="ignore", divide="ignore"):
        Pth = np.where(Pwin >= 0.7 * MAP, 2 * MAT,
                       np.where(Psum >= 0.7 * MAP, 2 * MAT + 28, 2 * MAT + 14))

    # Second letter for C and D: s before w, else f.
    s = (Psdry < 40) & (Psdry < Pwwet / 3)
    w = ~s & (Pwdry < Pswet / 10)
    sw = np.where(s, "s", np.where(w, "w", "f"))
    third = np.where(Thot >= 22, "a",
                     np.where(Tmon10 >= 4, "b",
                              np.where(Tcold < -38, "d", "c")))
    third_c = np.where(third == "d", "c", third)

    A = np.where(Pdry >= 60, "Af", np.where(Pdry >= 100 - MAP / 25, "Am", "Aw"))
    C = np.char.add(np.char.add("C", sw), third_c)
    D = np.char.add(np.char.add("D", sw), third)
    E = np.where(Thot > 0, "ET", "EF")
    humid = np.where(Thot <= 10, E,
                     np.where(Tcold >= 18, A, np.where(Tcold > 0, C, D)))
    hk = np.where(MAT >= 18, "h", "k")
    B = np.char.add(np.where(MAP < 5 * Pth, "BW", "BS"), hk)
    arid = (MAP < 10 * Pth) & (Thot > 10)
    code = np.where(arid, B, humid)

    k, h = _code_index(code), _code_index(humid)
    k[~ok], h[~ok] = NODATA, NODATA
    return k, h


def moisture(k):
    """Moisture rank of Köppen indices (DESERT/STEPPE/HUMID)."""
    k = np.asarray(k)
    return np.where(np.isin(k, [INDEX["BWh"], INDEX["BWk"]]), DESERT,
                    np.where(np.isin(k, [INDEX["BSh"], INDEX["BSk"]]), STEPPE, HUMID))


def nudge(k, humid, terrain, wanted):
    """Make hexes no drier than their terrain. `wanted`: {terrain class:
    "BS"|"humid"}; others are left alone. A desert needing steppe keeps
    its h/k; anything needing humid takes `humid` (the classifier's non-B
    class). Never makes a hex drier. Returns (k, nudged mask)."""
    need = np.array([LEVELS.get(wanted.get(t, "BW"), DESERT) for t in terrain])
    have = moisture(k)
    out = k.copy()
    to_steppe = (need == STEPPE) & (have == DESERT)
    out[to_steppe & (k == INDEX["BWh"])] = INDEX["BSh"]
    out[to_steppe & (k == INDEX["BWk"])] = INDEX["BSk"]
    to_humid = (need == HUMID) & (have < HUMID) & (humid >= 0)
    out[to_humid] = humid[to_humid]
    return out, out != k


def align(k, terrain, neighbours, force=None, centres=None):
    """Make one year's Köppen agree with its terrain: Water -> Ocean;
    terrain classes in `force` ({class: code}) take that code; land with no
    class (NODATA, or Ocean where the sea has since retreated) takes its land
    neighbours' majority, growing inward. Leftovers (islands of exposed
    shelf) take the nearest classed land hex when `centres` (N, 2) is
    given, else MISSING."""
    k = np.asarray(k).astype(int).copy()
    water = terrain == "Water"
    for cls, code in (force or {}).items():
        k[(terrain == cls)] = INDEX[code]
    k[water] = OCEAN
    gap = ~water & ((k == OCEAN) | (k < 0))
    k[gap] = NODATA
    out = np.asarray(fill_from_neighbours(k, gap, neighbours, exclude=(OCEAN, NODATA),
                                          default=MISSING), int)
    left = out == MISSING
    have = ~water & ~left
    if centres is not None and left.any() and have.any():
        c = np.asarray(centres, float)
        src = np.flatnonzero(have)
        for i in np.flatnonzero(left):
            out[i] = out[src[np.argmin(((c[src] - c[i]) ** 2).sum(1))]]
    return out


def codes(k):
    """Köppen indices -> code strings (the `climate` property)."""
    names = np.array(CODES + ["missingno"], object)
    return names[np.asarray(k, int)]


def _circular_mean(a, width):
    """Running mean over `width` months (odd), wrapping December to January."""
    h = width // 2
    if h <= 0:
        return a
    return np.mean([np.roll(a, s, axis=0) for s in range(-h, h + 1)], axis=0)


def smoothed(T, P, Tm, Pm, t, months=3, slices=1):
    """Slice t's monthly climate as the modern climatology plus a smoothed
    model anomaly (delta change): T anomaly additive, P anomaly as a log
    ratio, each averaged over slices t-slices..t+slices and a `months`-wide
    circular window. The file is already modern + anomaly, so with no
    smoothing this returns T[t], P[t]; smoothing stops single-month noise
    (e.g. a 0 mm July in Karelia) flipping hexes to the summer-dry Ds."""
    sl = slice(max(t - slices, 0), t + slices + 1)
    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        dT = np.nanmean(T[sl] - Tm, axis=0)
        dP = np.nanmean(np.log((P[sl] + 1) / (Pm + 1)), axis=0)
    T2 = Tm + _circular_mean(dT, months)
    P2 = np.clip((Pm + 1) * np.exp(_circular_mean(dP, months)) - 1, 0, None)
    return T2, P2


def at_hexes(grid, T, P, tf, shift, cells=None):
    """Classify per hex: each hex's mean monthly T and P (cells finite in
    every month), with `shift` (degC per hex) added to T, at the hex's
    latitude. Returns (koeppen, humid) per hex."""
    from . import paleobiome
    cells = cells or paleobiome.hex_cells(grid, tf, T.shape[1:])
    Th = paleobiome.hex_monthly(grid, T, tf, cells) + np.asarray(shift, float)[:, None]
    Ph = paleobiome.hex_monthly(grid, P, tf, cells)
    return classify(Th.T, Ph.T, grid.centres[:, 1])


def hex_classes(grid, pcfg, years, hex_codes, months=3, slices=1, shift=None):
    """{year: (koeppen, humid, bp)} per hex for each BCE year, from the
    monthly climate in pcfg["data"] (smoothed with `smoothed` when the
    file has the 0 BP slice). Without `shift`, each model cell is classified
    and `hex_codes(grid, codes, tf)` (paleobiome.hex_codes) takes the
    majority per hex. With `shift` (degC per hex, the lapse-rate correction
    to the hex's elevation), each hex's own mean climate is shifted and
    classified (`at_hexes`)."""
    from . import paleobiome
    _, bp, tf = paleobiome.load(pcfg["data"])
    clim = paleobiome.load_climate(pcfg["data"], ["temperature", "precipitation"])
    T, P = clim["temperature"], clim["precipitation"]
    d = np.load(pcfg["data"])
    has_modern = "modern_temperature" in d
    lat = (tf.y0 + tf.e * np.arange(T.shape[2]))[:, None]
    cells = paleobiome.hex_cells(grid, tf, T.shape[2:]) if shift is not None else None
    out = {}
    for y in years:
        t = paleobiome.bp_index(y, bp)
        if has_modern:
            Tt, Pt = smoothed(T, P, d["modern_temperature"], d["modern_precipitation"],
                              t, months, slices)
        else:
            Tt, Pt = T[t], P[t]
        if shift is not None:
            k, h = at_hexes(grid, Tt, Pt, tf, shift, cells)
            out[y] = (k, h, int(bp[t]))
        else:
            k, h = classify(Tt, Pt, lat)
            out[y] = (hex_codes(grid, k, tf), hex_codes(grid, h, tf), int(bp[t]))
    return out


def modern(grid, pcfg, hex_codes, shift=None):
    """Köppen per hex from the file's 0 BP slice (for validation), or None;
    classified the same way as `hex_classes` with the same `shift`."""
    from . import paleobiome
    d = np.load(pcfg["data"])
    if "modern_temperature" not in d:
        return None
    _, _, tf = paleobiome.load(pcfg["data"])
    Tm, Pm = d["modern_temperature"], d["modern_precipitation"]
    if shift is not None:
        return at_hexes(grid, Tm, Pm, tf, shift)[0]
    lat = (tf.y0 + tf.e * np.arange(Tm.shape[1]))[:, None]
    k, _ = classify(Tm, Pm, lat)
    return hex_codes(grid, k, tf)
