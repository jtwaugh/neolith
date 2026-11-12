"""Write combined_map.geojson in the SPEC §3.2 shape."""
import json
import math


def _py(v):
    return v.item() if hasattr(v, "item") else v


def _changes(by_year, i):
    """Year keys where hex i's value differs from the previous year (first always)."""
    out, prev = {}, object()
    for y, v in sorted(by_year.items()):
        val = _py(v[i])
        if val != prev:
            out[str(y)] = val
        prev = val
    return out


def features(grid, props, sparse=False, static=None):
    """props: {name: {year: array}} -> list of §3.2 features.

    sparse: write a year key only when the value changes. Same meaning under
    §3.2's step-function rule, much smaller at fine time steps.
    static: {name: array} of values that don't change over time, written as
    plain scalars (not year-keyed); NaN entries are left out.
    """
    out = []
    for i, hid in enumerate(grid.ids):
        left, top, right, bottom = (float(v) for v in grid.bbox[i])
        p = {"id": int(hid), "left": left, "top": top, "bottom": bottom, "right": right}
        for name, by_year in props.items():
            p[name] = (_changes(by_year, i) if sparse else
                       {str(y): _py(v[i]) for y, v in sorted(by_year.items())})
        for name, arr in (static or {}).items():
            val = _py(arr[i])
            if not (isinstance(val, float) and math.isnan(val)):
                p[name] = val
        out.append({"type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [grid.rings[i]]},
                    "properties": p})
    return out


def write_combined(path, grid, props, sparse=False, static=None):
    with open(path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": features(grid, props, sparse, static)}, f)
