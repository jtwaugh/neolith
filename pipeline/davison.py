"""When farming reaches each hex, by the population model of Davison,
Dolukhanov, Sarson & Shukurov (2006, J. Archaeol. Sci. 33: 641-652; their
"Model 2"): farmers grow logistically and diffuse, faster along coasts and
the Danube and Rhine, slower to the north, and not above 1000 m.

    dN/dt + (V.grad) N = g N (1 - N/K) + div(v grad N)

on a lon/lat raster, explicit Euler in time, as they solved it. Every
number in `DEFAULTS` is theirs unless marked. Nothing is fitted to this
project's sites (data/population/SOURCES.md).

Their paper gives no calendar date for the start; `start` is ours.
"""
import numpy as np
from scipy.spatial import cKDTree

from .raster import Affine, hex_pixels

R_KM = 6378.1   # their Earth radius

DEFAULTS = {
    "origin": [35.5, 32.0],        # Jericho
    "growth": 0.02,                # g, per year
    "diffusivity": 12.5,           # v, km2/yr: a front of 1 km/yr
    "altitude_limit": 1000.0,      # m: K and v fall to zero over ...
    "altitude_width": 100.0,       # ... about this many metres
    "river_speed": 5.0,            # km/yr along the Danube and Rhine
    "coast_speed": 10.0,           # km/yr along coasts
    "strip_km": 10.0,              # half-width of the fast strips
    "sea_scale_km": 10.0,          # v in the sea falls off over this distance from land
    "front": 0.01,                 # the front is where N reaches this share of the maximum
    # v, K and V fall linearly with latitude, "by a factor of approximately 2
    # across the distance from Greece to Denmark". Ours: the two latitudes
    # those words stand for, and 1 at 30 N, where they quote 1 km/yr.
    "latitude_one": 30.0,
    "latitude_pair": [38.0, 56.0],
    "seed_km": 30.0,               # width of the starting population (theirs: "narrow")
}


def latitude_factor(lat, cfg):
    a, b = cfg["latitude_pair"]
    # f linear with f(one) = 1 and f(b) = f(a) / 2.
    s = 0.5 / ((b - cfg["latitude_one"]) - 0.5 * (a - cfg["latitude_one"]))
    return np.clip(1.0 - s * (np.asarray(lat, dtype=float) - cfg["latitude_one"]), 0.0, 1.0)


def altitude_factor(alt, cfg):
    return 0.5 - 0.5 * np.tanh((np.asarray(alt, dtype=float) - cfg["altitude_limit"]) / cfg["altitude_width"])


def xyz(lon, lat):
    """Points on the sphere in km, so straight-line distance is near
    enough the distance over ground for anything within a few hundred km."""
    lon, lat = np.radians(lon), np.radians(lat)
    return R_KM * np.column_stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])


class Mesh:
    """Cell centres of a lon/lat raster, row 0 northmost."""

    def __init__(self, box, step):
        lon0, lat0, lon1, lat1 = box
        self.step = step
        self.lon = np.arange(lon0 + step / 2, lon1, step)
        self.lat = np.arange(lat1 - step / 2, lat0, -step)
        self.shape = (len(self.lat), len(self.lon))
        self.tf = Affine(step, -step, self.lon[0], self.lat[0])
        self.dy = R_KM * np.radians(step)
        self.dx = (R_KM * np.radians(step) * np.cos(np.radians(self.lat)))[:, None]   # (ny, 1)

    def points(self):
        lon, lat = np.meshgrid(self.lon, self.lat)
        return xyz(lon.ravel(), lat.ravel())

    def gradient(self, f):
        """Centred d/dx (east) and d/dy (north) in 1/km; one-sided at edges."""
        gx, gy = np.empty_like(f), np.empty_like(f)
        gx[:, 1:-1] = (f[:, 2:] - f[:, :-2]) / (2 * self.dx)
        gx[:, 0] = (f[:, 1] - f[:, 0]) / self.dx[:, 0]
        gx[:, -1] = (f[:, -1] - f[:, -2]) / self.dx[:, 0]
        gy[1:-1] = (f[:-2] - f[2:]) / (2 * self.dy)
        gy[0] = (f[0] - f[1]) / self.dy
        gy[-1] = (f[-2] - f[-1]) / self.dy
        return gx, gy


def block_mean(arr, tf, mesh):
    """Mean of a finer raster's cells in each mesh cell (NaN where none)."""
    lon = tf.x0 + np.arange(arr.shape[1]) * tf.a
    lat = tf.y0 + np.arange(arr.shape[0]) * tf.e
    ci = np.floor((lon - (mesh.lon[0] - mesh.step / 2)) / mesh.step).astype(int)
    ri = np.floor(((mesh.lat[0] + mesh.step / 2) - lat) / mesh.step).astype(int)
    ok_c, ok_r = (ci >= 0) & (ci < mesh.shape[1]), (ri >= 0) & (ri < mesh.shape[0])
    a = arr[np.ix_(ok_r, ok_c)].astype(float)
    good = np.isfinite(a)
    tot, cnt = np.zeros(mesh.shape), np.zeros(mesh.shape)
    rr, cc = np.meshgrid(ri[ok_r], ci[ok_c], indexing="ij")
    np.add.at(tot, (rr, cc), np.where(good, a, 0.0))
    np.add.at(cnt, (rr, cc), good)
    return np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)


def tangent(mesh, field):
    """Unit vectors (east, north) along the contours of `field`."""
    gx, gy = mesh.gradient(field)
    n = np.hypot(gx, gy)
    n[n == 0] = 1.0
    return -gy / n, gx / n


def fields(mesh, altitude, land, rivers, cfg):
    """The model's coefficient fields on the mesh.

    altitude: metres; land: bool; rivers: list of (lon, lat) polylines.
    Returns dict: v (km2/yr), K (0-1), g (per yr), and the advection speed
    `m` (km/yr) with its unit direction (`tx`, `ty`; the sense is chosen
    each step, towards falling density)."""
    ny, nx = mesh.shape
    pts = mesh.points()
    flat_land = land.ravel()
    reach = 6 * max(cfg["strip_km"], cfg["sea_scale_km"])

    def distance(to):
        d, _ = cKDTree(pts[to]).query(pts, distance_upper_bound=reach)
        return np.minimum(d, reach).reshape(ny, nx)

    to_sea, to_land = distance(~flat_land), distance(flat_land)
    signed = np.where(land, to_sea, -to_land)          # + inland, - offshore
    lat2d = np.broadcast_to(mesh.lat[:, None], mesh.shape)
    lf = latitude_factor(lat2d, cfg)
    af = altitude_factor(np.where(land, np.nan_to_num(altitude), 0.0), cfg)

    K = np.where(land, af * lf, 0.0)
    v = cfg["diffusivity"] * np.where(land, af * lf, lf * np.exp(-to_land / cfg["sea_scale_km"]))
    g = np.where(land, cfg["growth"], 0.0)

    # Coasts: fast within a strip either side of the shoreline.
    half = mesh.dy / 2                                   # the shoreline lies between cell centres
    coast = np.exp(-(np.maximum(np.abs(signed) - half, 0.0) / cfg["strip_km"]) ** 2)
    cx, cy = tangent(mesh, signed)
    m_coast = cfg["coast_speed"] * coast

    # Rivers: fast within a strip of the line, along the line.
    m_river, rx, ry = np.zeros(mesh.shape), np.zeros(mesh.shape), np.zeros(mesh.shape)
    if rivers:
        P, T = [], []
        for line in rivers:
            line = np.asarray(line, dtype=float)
            for (x0, y0), (x1, y1) in zip(line[:-1], line[1:]):
                n = max(int(np.hypot((x1 - x0) * 80, (y1 - y0) * 111) / 2.0), 1)   # a point every ~2 km
                t = (np.arange(n) + 0.5) / n
                P.append(np.column_stack([x0 + t * (x1 - x0), y0 + t * (y1 - y0)]))
                e, nth = (x1 - x0) * np.cos(np.radians((y0 + y1) / 2)), (y1 - y0)
                T.append(np.tile([e, nth] / max(np.hypot(e, nth), 1e-12), (n, 1)))
        P, T = np.vstack(P), np.vstack(T)
        d, j = cKDTree(xyz(P[:, 0], P[:, 1])).query(pts, distance_upper_bound=reach)
        near = np.isfinite(d)
        env = np.zeros(len(pts))
        env[near] = np.exp(-(d[near] / cfg["strip_km"]) ** 2)
        m_river = (cfg["river_speed"] * env).reshape(ny, nx)
        rx.ravel()[near], ry.ravel()[near] = T[j[near], 0], T[j[near], 1]

    # One strip per cell: whichever is faster there.
    river = m_river > m_coast
    m = np.where(river, m_river, m_coast) * lf * np.where(land, af, 1.0)
    tx, ty = np.where(river, rx, cx), np.where(river, ry, cy)
    f32 = lambda a: np.ascontiguousarray(a, dtype=np.float32)
    return {k: f32(a) for k, a in dict(v=v, K=K, g=g, m=m, tx=tx, ty=ty).items()}


def time_step(mesh, F, safety=0.8):
    """Their stability limit: the population can't cross a cell in a step."""
    dx, dy = mesh.dx, mesh.dy
    with np.errstate(divide="ignore", invalid="ignore"):
        diff = dx ** 2 * dy ** 2 / (2 * F["v"] * (dx ** 2 + dy ** 2))
        adv = np.minimum(dx / (2 * F["m"] * np.abs(F["tx"])), dy / (2 * F["m"] * np.abs(F["ty"])))
    return safety * float(min(np.nanmin(diff[F["v"] > 0]), np.nanmin(np.where(F["m"] > 0, adv, np.inf))))


def run(mesh, F, origin, years, cfg, progress=None):
    """Years after the start at which the front reaches each cell (NaN if
    it doesn't within `years`)."""
    f = np.float32
    ny, nx = mesh.shape
    dx, dy = mesh.dx.astype(f), f(mesh.dy)
    cos = np.cos(np.radians(mesh.lat))[:, None]
    cos_face = np.cos(np.radians(mesh.lat[:-1] - mesh.step / 2))[:, None]
    # Diffusion in flux form on the sphere, with the diffusivity at cell faces.
    ax = (0.5 * (F["v"][:, 1:] + F["v"][:, :-1]) / dx ** 2).astype(f)
    ay = (0.5 * (F["v"][1:] + F["v"][:-1]) * cos_face / dy ** 2).astype(f)
    inv_cos = (1.0 / cos).astype(f)
    mx, my = F["m"] * F["tx"], F["m"] * F["ty"]          # velocity for sense +1
    K, g = F["K"], F["g"]
    with np.errstate(divide="ignore"):
        g_over_K = np.where(K > 1e-6, g / np.maximum(K, 1e-6), 0.0).astype(f)
    dead = (g > 0) & (K <= 1e-6)                          # land that carries nobody

    lon, lat = np.meshgrid(mesh.lon, mesh.lat)
    d0 = np.linalg.norm(xyz(lon.ravel(), lat.ravel()) - xyz([origin[0]], [origin[1]]), axis=1).reshape(ny, nx)
    N = (K * np.exp(-(d0 / cfg["seed_km"]) ** 2)).astype(f)
    if N.max() < cfg["front"]:
        raise ValueError("the origin carries no population: is it on land below the altitude limit?")

    dt = f(time_step(mesh, F))
    steps = int(np.ceil(years / dt))
    arrival = np.full(mesh.shape, np.nan, dtype=f)
    arrival[N >= cfg["front"]] = 0.0
    fx, fy = np.zeros((ny, nx + 1), f), np.zeros((ny + 1, nx), f)
    bx, by = np.zeros_like(N), np.zeros_like(N)           # backward differences
    wx, wy = np.zeros_like(N), np.zeros_like(N)           # forward differences
    for step in range(1, steps + 1):
        np.subtract(N[:, 1:], N[:, :-1], out=fx[:, 1:-1])
        np.subtract(N[:-1], N[1:], out=fy[1:-1])          # north minus south across each face
        # Tangential slope of N along the strips, by one-sided differences.
        bx[:, 1:], wx[:, :-1] = fx[:, 1:-1] / dx, fx[:, 1:-1] / dx
        by[:-1], wy[1:] = fy[1:-1] / dy, fy[1:-1] / dy    # towards north: by uses the cell to the south
        # Sense: V points towards falling density, so (V.grad)N <= 0.
        sense = -np.sign(mx * (bx + wx) + my * (by + wy))
        vx, vy = sense * mx, sense * my
        # Upwind: take the slope from the side the flow comes from.
        adv = (np.where(vx > 0, bx, wx) * vx + np.where(vy > 0, by, wy) * vy)
        diff = (ax * fx[:, 1:-1])
        fx[:, 1:-1] = diff
        fy[1:-1] *= ay
        div = (fx[:, 1:] - fx[:, :-1]) + (fy[:-1] - fy[1:]) * inv_cos
        N += dt * (div - adv + g * N - g_over_K * N * N)
        np.clip(N, 0.0, None, out=N)
        N[dead] = 0.0
        if step % 4 == 0 or step == steps:
            new = np.isnan(arrival) & (N >= cfg["front"])
            arrival[new] = step * dt
        if progress and step % 2000 == 0:
            progress(step, steps, float(step * dt))
    return arrival


def build(grid, terrain, elevation, elev_tf, rivers, sea_level, box, cfg, log=lambda m: None):
    """Arrival year per hex (float; NaN where the front doesn't come by
    cfg["end"]), and stats. `terrain` is the hexes' terrain names at the
    year the coastline is taken from; `rivers` the fast-river polylines."""
    cfg = {**DEFAULTS, **cfg}
    mesh = Mesh(box, cfg["cell_deg"])
    alt = block_mean(elevation, elev_tf, mesh)
    # Land: above that year's sea, or in a hex the map has as land (ground
    # below sea level: the Jordan valley, the Caspian shore).
    hex_land = np.zeros(mesh.shape, bool)
    for i, (ring, bbox) in enumerate(zip(grid.rings, grid.bbox)):
        if terrain[i] != "Water":
            rr, cc = hex_pixels(ring, bbox, mesh.tf, mesh.shape)
            hex_land[rr, cc] = True
    land = (np.nan_to_num(alt, nan=-1e9) > sea_level) | hex_land
    F = fields(mesh, np.maximum(np.nan_to_num(alt), 0.0), land, rivers, cfg)
    years = cfg["end"] - cfg["start"]
    log(f"davison: mesh {mesh.shape[1]}x{mesh.shape[0]}, step {time_step(mesh, F):.3f} yr, {years} years")
    after = run(mesh, F, cfg["origin"], years, cfg,
                progress=lambda s, n, t: log(f"davison: {t:.0f} of {years} years"))
    out = np.full(len(grid), np.nan)
    for i, (ring, bbox) in enumerate(zip(grid.rings, grid.bbox)):
        rr, cc = hex_pixels(ring, bbox, mesh.tf, mesh.shape)
        a = after[rr, cc]
        a = a[np.isfinite(a) & land[rr, cc]]
        # The hex is reached when half its land cells are.
        n_land = int(land[rr, cc].sum())
        if n_land and len(a) * 2 >= n_land:
            out[i] = cfg["start"] + np.sort(a)[(n_land - 1) // 2]
    return out, {"mesh": mesh, "after": after, "land": land, "fields": F}
