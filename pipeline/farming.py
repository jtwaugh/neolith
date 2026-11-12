"""When farming reaches each hex: a front spreading from one origin at one
speed along the shortest path over land, with short sea crossings.

This is the model Pinhasi, Fort & Ammerman (2005) fitted to 735 dated early
Neolithic sites: arrival = origin date + shortest-path distance / speed. The
origin, date and speed are theirs and are not refitted to this project's
site list (data/population/SOURCES.md).

It says when farming could first be present, not whether the land can be
farmed: the app decides that per year from the hex's climate and rivers."""
import heapq

import numpy as np

EARTH_KM = 6371.0
# Terrain a front does not enter. It waits at the edge until the hex opens.
CLOSED = ("Water", "Ice")


def distance_km(a, b):
    """Great-circle distance between (lon, lat) points in degrees."""
    lon1, lat1, lon2, lat2 = map(np.radians, (a[0], a[1], b[0], b[1]))
    h = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return float(2 * EARTH_KM * np.arcsin(np.sqrt(h)))


def links(centres, neighbours, reach_km):
    """Per hex, [(other hex, km)]: its neighbours, plus every hex within
    `reach_km` (a sea crossing: the sea is what lies between two land hexes
    that are not neighbours). Found by walking outward ring by ring."""
    out = []
    for i in range(len(centres)):
        seen, ring, found = {i}, [i], []
        while ring:
            nxt = []
            for j in ring:
                for k in neighbours[j]:
                    if k in seen:
                        continue
                    seen.add(k)
                    d = distance_km(centres[i], centres[k])
                    if d <= reach_km or k in neighbours[i]:
                        found.append((k, d))
                        nxt.append(k)
            ring = nxt
        out.append(found)
    return out


def opens(terrain, years):
    """(N, T) bool: hex is open (not Water or Ice) at years[t]."""
    return np.column_stack([~np.isin(terrain[y], CLOSED) for y in years])


def arrival(centres, neighbours, terrain, years, cfg):
    """Year farming reaches each hex (float; NaN if not by years[-1]).

    A hex is entered at `time at the previous hex + km / speed`. If it is
    Water or Ice then, the front waits for the first listed year it is not.
    The origin is the open hex nearest cfg["origin"] at cfg["start"]."""
    years = sorted(years)
    ya = np.array(years, dtype=float)
    is_open = opens(terrain, years)
    net = links(centres, neighbours, cfg.get("sea_reach_km", 0.0))

    def enter(i, t):
        """Earliest time at or after t that hex i is open, or None."""
        k = max(int(np.searchsorted(ya, t, side="right")) - 1, 0)
        if is_open[i, k]:
            return t
        later = np.flatnonzero(is_open[i, k + 1:])
        return float(ya[k + 1 + later[0]]) if len(later) else None

    start = float(cfg["start"])
    k0 = max(int(np.searchsorted(ya, start, side="right")) - 1, 0)
    d0 = np.array([distance_km(cfg["origin"], c) for c in centres])
    d0[~is_open[:, k0]] = np.inf
    origin = int(d0.argmin())
    out = np.full(len(centres), np.nan)
    heap = [(start, origin)]
    while heap:
        t, i = heapq.heappop(heap)
        if not np.isnan(out[i]) or t > years[-1]:
            continue
        out[i] = t
        for j, km in net[i]:
            if np.isnan(out[j]):
                tj = enter(j, t + km / cfg["speed_km_per_year"])
                if tj is not None:
                    heapq.heappush(heap, (tj, j))
    return out, origin
