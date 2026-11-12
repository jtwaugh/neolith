"""Presence, evidence, uncertainty and overlay maps on the game grid.

Sea is the page colour; land without enough evidence is grey; ice and
acid-soil masks have their own neutrals. None of those is ever a value.
"""
import json

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
import numpy as np
from matplotlib.collections import PolyCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from .plots import HAIR, ICE, INK, INK2, MUTED, NO_EVIDENCE, RAMP, SURFACE

ACID = "#d9c49a"
BELOW = "#c4c2ba"           # some evidence, under the threshold
DIVERGE = ["#c2352f", "#eaa39b", "#f0efec", "#9ec5f4", "#256abf"]   # red .. grey .. blue
DASHES = ["-", (0, (7, 3)), (0, (3, 2)), (0, (7, 2, 1, 2)), "-", (0, (7, 3)), (0, (3, 2)), (0, (7, 2, 1, 2))]
F_BINS = ([0.0, 0.2, 0.4, 0.6, 0.8], ["0–20%", "20–40%", "40–60%", "60–80%", "80–100%"])


def value_bins(L):
    """Five equal bins: shares in %, continuous and grid layers in their units."""
    if L["kind"] in ("continuous", "grid"):
        lo, hi = L["vmin"], L["vmax"]
        step = (hi - lo) / 5
        edges = [lo + k * step for k in range(5)]
        unit = L.get("units_label", "")
        fmt = (lambda v: f"{v:g}") if step >= 1 else (lambda v: f"{v:.1f}")
        labels = [f"{fmt(a)}–{fmt(a + step)} {unit}".strip() for a in edges]
        labels[0] = f"under {fmt(edges[1])} {unit}".strip()
        labels[-1] = f"{fmt(edges[-1])}+ {unit}".strip()
        return [-np.inf] + edges[1:], labels
    return F_BINS


class Canvas:
    def __init__(self, grid, countries_path):
        self.verts = [np.asarray(g.exterior.coords) for g in grid.geometry]
        self.lon, self.lat = grid["lon"].values, grid["lat"].values
        b = grid.total_bounds
        self.bounds = b
        try:
            c = gpd.read_file(countries_path, bbox=tuple(b))
            self.borders = c.boundary
        except Exception:
            self.borders = None
        tri = mtri.Triangulation(self.lon, self.lat)
        t = tri.triangles
        ex, ey = self.lon[t], self.lat[t]
        edge = np.max(np.hypot(ex - np.roll(ex, 1, axis=1), ey - np.roll(ey, 1, axis=1)), axis=1)
        self.tri, self.long_edge = tri, edge > 0.8

    def panels(self, n, title, subtitle):
        ncol = 4
        nrow = int(np.ceil(n / ncol))
        fig, axes = plt.subplots(nrow, ncol, figsize=(ncol * 4.3, nrow * 5.9 + 1.6), squeeze=False)
        for ax in axes.ravel():
            ax.set_axis_off()
        fig.suptitle(title, x=0.012, ha="left", fontsize=15, fontweight="bold")
        fig.text(0.012, 1 - 0.52 / fig.get_figheight(), subtitle, fontsize=9.5, color=INK2, va="top", wrap=True)
        return fig, axes.ravel()

    def draw(self, ax, colours, heading):
        ax.add_collection(PolyCollection(self.verts, facecolors=colours, edgecolors="none", rasterized=True))
        if self.borders is not None:
            self.borders.plot(ax=ax, color=INK2, linewidth=0.25, alpha=0.55, aspect=None)
        b = self.bounds
        ax.set_xlim(b[0], b[2])
        ax.set_ylim(b[1], b[3])
        ax.set_aspect(1.41, adjustable="box", anchor="N")
        ax.set_title(heading, fontsize=9.5, color=INK, pad=3, loc="left")

    def contour(self, ax, values, ok, levels, **kw):
        """Marching-triangles contours; triangles touching a cell that is not
        `ok`, or spanning a gap in the grid, are removed. Returns segments."""
        self.tri.set_mask(self.long_edge | ~ok[self.tri.triangles].all(axis=1))
        if (~self.tri.mask).sum() == 0:
            return {}
        cs = ax.tricontour(self.tri, np.where(ok, values, 0.0), levels=levels, **kw)
        return {lv: [s for s in segs if len(s) > 1] for lv, segs in zip(cs.levels, cs.allsegs)}

    def finish(self, fig, handles, path, ncol=4):
        fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.012, 0.004), frameon=False,
                   fontsize=9, ncol=ncol, alignment="left")
        fig.tight_layout(rect=(0, 0.9 / fig.get_figheight(), 1, 1 - 1.0 / fig.get_figheight()), w_pad=0.3, h_pad=1.6)
        fig.savefig(path, dpi=120)
        plt.close(fig)


def _base(land, ice, extra=None, extra_colour=ACID):
    col = np.full(len(land), SURFACE, dtype=object)
    col[land] = NO_EVIDENCE
    col[land & ice] = ICE
    if extra is not None:
        col[land & extra & ~ice] = extra_colour
    return col


def _neutral_handles(acid):
    h = [Patch(fc=NO_EVIDENCE, ec="none", label="land, too little evidence (masked)"),
         Patch(fc=ICE, ec="none", label="ice (from the map keyframes)")]
    if acid:
        h.append(Patch(fc=ACID, ec="none", label="acid soil, organics rarely survive (masked)"))
    return h


def presence(cv, path, L, years, res, ok, land, ice, acid, levels, note, heads):
    value = L["kind"] in ("continuous", "grid")
    title = f"{L['name']}: {'value' if value else 'presence'}"
    lead = (f"{L['name']} ({L.get('units_label', '')})." if value
            else f"Kernel-weighted share of {L['evidence_word']} with {L['name'].lower()}.")
    fig, axes = cv.panels(len(years), title, f"{lead} {note}")
    bins, blabels = value_bins(L)
    segs = {}
    for j, year in enumerate(years):
        col = _base(land[:, j], ice[:, j], acid)
        for k, lo in enumerate(bins):
            sel = ok[:, j] & (np.nan_to_num(res["f"][:, j], nan=-np.inf) >= lo)
            col[sel] = RAMP[k]
        cv.draw(axes[j], col, f"{-year:,} BCE   {heads[j]}")
        widths = [1.5 if v == levels[len(levels) // 2] else 0.6 for v in levels]
        segs[int(year)] = cv.contour(axes[j], np.nan_to_num(res["f"][:, j]), ok[:, j], levels, colors=INK,
                                     linewidths=widths)
    mid = levels[len(levels) // 2]
    lv = (lambda v: f"{v:g} {L.get('units_label', '')}".strip()) if value else (lambda v: f"{100 * v:g}%")
    handles = ([Patch(fc=c, ec="none", label=l) for c, l in zip(RAMP, blabels)]
               + [Line2D([], [], color=INK, lw=1.5, label=f"{lv(mid)} isoline"),
                  Line2D([], [], color=INK, lw=0.6, label=", ".join(lv(v) for v in levels if v != mid) + " isolines")]
               + _neutral_handles(acid is not None))
    cv.finish(fig, handles, path)
    return segs


def evidence(cv, path, L, years, res, land, ice, acid, e_min, sigma):
    fig, axes = cv.panels(len(years), f"{L['name']}: evidence",
                          f"E = sum of slice weight × kernel weight over {L['evidence_word']} whose {L['name'].lower()} "
                          f"status is known (σ = {sigma:g} km). Cells under E = {e_min:g} are masked on the main map.")
    bins, labels = [e_min, 3, 10, 30, 100], [f"{e_min:g}–3", "3–10", "10–30", "30–100", "100+"]
    for j, year in enumerate(years):
        col = _base(land[:, j], ice[:, j], acid)
        e = res["E"][:, j]
        free = land[:, j] & ~ice[:, j] & (True if acid is None else ~acid)
        col[free & (e > 0.05)] = BELOW
        for k, lo in enumerate(bins):
            col[free & (e >= lo)] = RAMP[k]
        cv.draw(axes[j], col, f"{-year:,} BCE")
    handles = ([Patch(fc=c, ec="none", label=f"E {l}") for c, l in zip(RAMP, labels)]
               + [Patch(fc=BELOW, ec="none", label=f"some evidence, E under {e_min:g} (masked)"),
                  Patch(fc=NO_EVIDENCE, ec="none", label="land, no evidence in reach")] + _neutral_handles(acid is not None)[1:])
    cv.finish(fig, handles, path)


def uncertainty(cv, path, L, years, res, ok, land, ice, acid, n_boot):
    mid = L["levels"][len(L["levels"]) // 2]
    what = f"{mid:g} {L.get('units_label', '')}".strip() if L["kind"] == "continuous" else f"{100 * mid:g}%"
    fig, axes = cv.panels(len(years), f"{L['name']}: how firm is the {what} boundary",
                          f"Share of {n_boot} bootstrap runs ({L['evidence_word']} resampled, one date drawn from each) in which "
                          f"the cell's value is at least {what}, among runs where it has enough evidence. The line is the main run's {what} isoline.")
    bins = [0.0, 0.1, 0.35, 0.65, 0.9]
    labels = ["under 10% of runs (firmly below)", "10–35%", "35–65% (undecided)", "65–90%", "over 90% (firmly above)"]
    for j, year in enumerate(years):
        col = _base(land[:, j], ice[:, j], acid)
        for k, lo in enumerate(bins):
            col[ok[:, j] & (res["boot_above"][:, j] >= lo)] = DIVERGE[k]
        cv.draw(axes[j], col, f"{-year:,} BCE")
        cv.contour(axes[j], res["f"][:, j], ok[:, j], [mid], colors=INK, linewidths=1.2)
    handles = [Patch(fc=c, ec="none", label=l) for c, l in zip(DIVERGE, labels)] + _neutral_handles(acid is not None)
    cv.finish(fig, handles, path, ncol=3)


def overlay(cv, path, years, members, results, oks, land, ice, contrast, group):
    fig, axes = cv.panels(len(years), f"{group}: boundaries",
                          "Solid and dashed lines are 50% isolines of layers with known absences (continuous layers: their "
                          "middle level). Dotted outlines are only the edge of cells with enough evidence for the other layers.")
    for j, year in enumerate(years):
        col = np.full(land.shape[0], SURFACE, dtype=object)
        col[land[:, j]] = "#eeede9"
        col[land[:, j] & ice[:, j]] = ICE
        cv.draw(axes[j], col, f"{-year:,} BCE")
        for k, L in enumerate(members):
            m, res = L["id"], results[L["id"]]
            if contrast.get(m) or L["kind"] in ("continuous", "grid"):
                lv = L["levels"][len(L["levels"]) // 2]
                cv.contour(axes[j], np.nan_to_num(res["f"][:, j]), oks[m][:, j], [lv], colors=L["colour"],
                           linewidths=1.8, linestyles=[DASHES[k % len(DASHES)]])
            else:
                cv.contour(axes[j], oks[m][:, j].astype(float), land[:, j], [0.5], colors=L["colour"], linewidths=1.0,
                           linestyles=[(0, (1, 1.5))])
    handles = [Line2D([], [], color=L["colour"],
                      lw=1.8 if (contrast.get(L["id"]) or L["kind"] in ("continuous", "grid")) else 1.0,
                      ls=DASHES[k % len(DASHES)] if (contrast.get(L["id"]) or L["kind"] in ("continuous", "grid")) else (0, (1, 1.5)),
                      label=f"{L['name']}: " + ("boundary" if (contrast.get(L["id"]) or L["kind"] in ("continuous", "grid"))
                                                else "extent of recorded evidence"))
               for k, L in enumerate(members)]
    cv.finish(fig, handles, path, ncol=3)


def dominant(cv, path, years, members, results, oks, land, ice, setname):
    """Each cell coloured by the clade with the highest share; paler where the
    leading clade has under 40%."""
    fig, axes = cv.panels(len(years), f"{setname}: most common clade",
                          "Each cell shows the clade with the highest smoothed share among sampled individuals; pale where "
                          "the leader has under 40%. Grey: too few samples.")
    from matplotlib.colors import to_rgba
    for j, year in enumerate(years):
        col = np.full(land.shape[0], SURFACE, dtype=object)
        col[land[:, j]] = NO_EVIDENCE
        col[land[:, j] & ice[:, j]] = ICE
        F = np.vstack([np.where(oks[L["id"]][:, j], results[L["id"]]["f"][:, j], -1) for L in members])
        best, top = F.argmax(axis=0), F.max(axis=0)
        for k, L in enumerate(members):
            sel = (best == k) & (top >= 0)
            rgba = np.array(to_rgba(L["colour"]))
            col[sel & (top >= 0.4)] = L["colour"]
            from matplotlib.colors import to_hex
            col[sel & (top < 0.4)] = to_hex(rgba[:3] * 0.45 + 0.55)
        cv.draw(axes[j], col, f"{-year:,} BCE")
    handles = [Patch(fc=L["colour"], ec="none", label=L["name"]) for L in members] + [
        Patch(fc=NO_EVIDENCE, ec="none", label="too few samples")]
    cv.finish(fig, handles, path, ncol=4)


def contours_geojson(path, all_segs):
    feats = []
    for m, by_year in all_segs.items():
        for year, by_level in by_year.items():
            for level, segs in by_level.items():
                if segs:
                    feats.append({"type": "Feature",
                                  "properties": {"layer": m, "slice": year, "level": round(float(level), 2)},
                                  "geometry": {"type": "MultiLineString",
                                               "coordinates": [np.round(s, 4).tolist() for s in segs]}})
    json.dump({"type": "FeatureCollection", "features": feats}, open(path, "w"))
