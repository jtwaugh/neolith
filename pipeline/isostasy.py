"""Fennoscandian glacio-isostatic uplift, for reconstructing past surfaces.

ETOPO1 is today's surface. Around the Baltic the land has risen since the
ice sheet melted (over 280 m at the uplift centre), so a past water surface
is tilted relative to it. `uplift(lon, lat, year)` is the uplift still to
come after `year`; subtracting it from ETOPO1 gives that year's surface, on
which a flat water level can be flooded.

Model: today's uplift rate is an elliptical dome (pipeline/config.toml
[isostasy]: centre, axes, orientation, peak rate), and the rate grows
exponentially into the past with time constant `tau`, so the uplift still to
come after a time `age` ka ago is

    U = scale * rate(lon, lat) * tau * (exp(age / tau) - 1)

`scale` and `tau` (and the axes) are fitted to dated shoreline elevations
(data/lakes/SOURCES.md, Baltic); `calibration` in the config lists them and
pipeline/tests/test_isostasy.py checks the fit.
"""
import numpy as np


def rate(lon, lat, cfg):
    """Present uplift rate (mm/yr) of the dome; zero outside it."""
    c0, c1 = cfg["centre"]
    x = (np.asarray(lon) - c0) * 111.32 * np.cos(np.radians((np.asarray(lat) + c1) / 2))
    y = (np.asarray(lat) - c1) * 110.57
    th = np.radians(cfg["azimuth"])
    u = x * np.sin(th) + y * np.cos(th)
    v = x * np.cos(th) - y * np.sin(th)
    a, b = cfg["axes"]
    return cfg["peak_rate"] * np.clip(1 - (u / a) ** 2 - (v / b) ** 2, 0, None)


def uplift(lon, lat, year, cfg):
    """Metres the surface at (lon, lat) has risen since `year` (BCE < 0)."""
    age = (1950 - year) / 1000.0
    tau = cfg["tau"]
    return cfg["scale"] * rate(lon, lat, cfg) * tau * np.expm1(age / tau)
