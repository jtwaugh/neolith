"""Maps for the audit. Missing evidence is always a neutral, never a value."""
import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PolyCollection
from matplotlib.patches import Patch
from pyproj import Transformer
from shapely.geometry import box

SURFACE, INK, INK2, MUTED, HAIR = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
# One-hue sequential ramp, light to dark (five ordered bins).
RAMP = ["#b7d3f6", "#6da7ec", "#2a78d6", "#184f95", "#0d366b"]
NO_EVIDENCE, DROWNED, ICE = "#dedcd6", "#d9c49a", "#e6def2"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "text.color": INK,
                     "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK2,
                     "xtick.color": MUTED, "ytick.color": MUTED, "figure.facecolor": SURFACE,
                     "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE})

COUNT_BINS = ([1, 2, 4, 8, 16], ["1", "2–3", "4–7", "8–15", "16+"])
DATE_BINS = ([0.5, 2, 5, 15, 50], ["0.5–2", "2–5", "5–15", "15–50", "50+"])


def _verts(grid):
    return [np.asarray(g.exterior.coords) for g in grid.geometry]


def _frame(grid, region):
    """Region outline and extent in the grid's CRS."""
    tr = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True)
    lons = np.linspace(region["lon_min"], region["lon_max"], 200)
    lats = np.linspace(region["lat_min"], region["lat_max"], 200)
    ox = np.concatenate([lons, np.full(200, region["lon_max"]), lons[::-1], np.full(200, region["lon_min"])])
    oy = np.concatenate([np.full(200, region["lat_min"]), lats, np.full(200, region["lat_max"]), lats[::-1]])
    return tr.transform(ox, oy)


def _borders(ctry, grid):
    b = grid.total_bounds
    return ctry.clip(box(b[0] - 5e4, b[1] - 5e4, b[2] + 5e4, b[3] + 5e4)).boundary


def _colours(values, bins, is_land, drowned, icy):
    col = np.full(len(values), SURFACE, dtype=object)
    col[is_land] = NO_EVIDENCE
    col[is_land & drowned] = DROWNED
    col[is_land & icy] = ICE
    for k, lo in enumerate(bins):
        col[is_land & (values >= lo)] = RAMP[k]
    return col


def _legend_handles(labels, unit):
    return ([Patch(fc=c, ec="none", label=f"{l} {unit}") for c, l in zip(RAMP, labels)]
            + [Patch(fc=NO_EVIDENCE, ec="none", label="land, no dated evidence"),
               Patch(fc=DROWNED, ec="none", label="land then, sea today (no evidence)"),
               Patch(fc=ICE, ec="none", label="ice sheet (approximate; no evidence)")])


def small_multiples(values, title, subtitle, path, grid, ctry, years, is_land, drowned, icy, region):
    bins, labels = DATE_BINS if values.dtype.kind == "f" else COUNT_BINS
    verts, borders = _verts(grid), _borders(ctry, grid)
    fx, fy = _frame(grid, region)
    ncol = 6
    nrow = int(np.ceil((len(years) + 1) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(ncol * 3.1, nrow * 3.0 + 0.9))
    for ax in axes.ravel():
        ax.set_axis_off()
        ax.set_aspect("equal")
    for j, year in enumerate(years):
        ax = axes.ravel()[j]
        ax.add_collection(PolyCollection(verts, facecolors=_colours(values[:, j], bins, is_land[:, j], drowned[:, j], icy[:, j]),
                                         edgecolors="none", rasterized=True))
        borders.plot(ax=ax, color=INK2, linewidth=0.25, alpha=0.6)
        ax.plot(fx, fy, color="#c3c2b7", linewidth=0.5)
        ax.set_xlim(min(fx), max(fx))
        ax.set_ylim(min(fy), max(fy))
        ax.set_title(f"{-year:,} BCE", fontsize=10, color=INK, pad=2)
    lax = axes.ravel()[len(years)]
    lax.legend(handles=_legend_handles(labels, "per cell"), loc="center", frameon=False, fontsize=8.5)
    fig.suptitle(title, x=0.01, ha="left", fontsize=15, fontweight="bold")
    fig.text(0.01, 1 - 0.55 / fig.get_figheight(),
             f"{subtitle}. Cells about 50 km across, EPSG:3035; each slice is ±125 years.",
             fontsize=9.5, color=INK2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.75 / fig.get_figheight()), w_pad=0.2, h_pad=0.6)
    fig.savefig(path, dpi=130)
    plt.close(fig)


def coverage(n_phase, path, grid, ctry, years, is_land, drowned, icy, region):
    """One map: in what share of the slices does each cell have any evidence."""
    land_any = is_land.any(axis=1)
    share = (n_phase > 0).sum(axis=1) / np.maximum(is_land.sum(axis=1), 1)
    bins, labels = [1e-9, 0.1, 0.25, 0.5, 0.75], ["under 10%", "10–25%", "25–50%", "50–75%", "over 75%"]
    never_dry_now = drowned.any(axis=1) & ((n_phase > 0).sum(axis=1) == 0)
    col = _colours(share, bins, land_any, np.zeros(len(grid), bool), np.zeros(len(grid), bool))
    verts, borders = _verts(grid), _borders(ctry, grid)
    fx, fy = _frame(grid, region)
    fig, ax = plt.subplots(figsize=(11, 9.6))
    ax.set_axis_off()
    ax.set_aspect("equal")
    ax.add_collection(PolyCollection(verts, facecolors=col, edgecolors=SURFACE, linewidths=0.15, rasterized=True))
    hv = [v for v, m in zip(verts, never_dry_now) if m]
    ax.add_collection(PolyCollection(hv, facecolors=DROWNED, edgecolors=INK2, linewidths=0.0, hatch="////", rasterized=True))
    borders.plot(ax=ax, color=INK2, linewidth=0.45, alpha=0.7)
    ax.plot(fx, fy, color="#c3c2b7", linewidth=0.6)
    ax.set_xlim(min(fx), max(fx))
    ax.set_ylim(min(fy), max(fy))
    handles = ([Patch(fc=c, ec="none", label=l) for c, l in zip(RAMP, labels)]
               + [Patch(fc=NO_EVIDENCE, ec="none", label="land, never any dated evidence"),
                  Patch(fc=DROWNED, ec=INK2, hatch="////", lw=0, label="dry land in some slices, sea today")])
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=9, title="Share of the 29 slices with evidence",
              title_fontsize=9.5, alignment="left")
    fig.suptitle("How often each cell has any dated site-phase, 10,000–3,000 BCE", x=0.02, ha="left",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def timeline(by_slice, path):
    yrs = np.array([r["slice"] for r in by_slice])
    fig, (a, b) = plt.subplots(2, 1, figsize=(9, 6.4), sharex=True, height_ratios=[1, 1.15])
    share = np.array([r["share_with_evidence"] for r in by_slice]) * 100
    two = np.array([r["cells_with_2plus_sites"] / r["land_cells"] for r in by_slice]) * 100
    a.plot(yrs, share, color=SERIES[0], linewidth=2, label="at least one dated site-phase")
    a.plot(yrs, two, color=SERIES[1], linewidth=2, label="two or more dated sites")
    a.text(yrs[-1] + 40, share[-1], f"{share[-1]:.0f}%  ≥ 1 site-phase", va="center", fontsize=8.5, color=INK2)
    a.text(yrs[-1] + 40, two[-1], f"{two[-1]:.0f}%  ≥ 2 sites", va="center", fontsize=8.5, color=INK2)
    a.set_ylabel("% of land cells")
    a.set_ylim(0, None)
    a.set_title("Share of land cells with dated evidence in the slice", loc="left", fontsize=11, fontweight="bold")
    a.legend(frameon=False, loc="upper left", fontsize=8.5)
    keys = [("phases_with_culture_label", "named culture label"), ("phases_with_stage_only", "stage label only (e.g. “Neolithic”)"),
            ("phases_unlabelled", "no usable label")]
    bottom = np.zeros(len(yrs))
    for (k, lab), c in zip(keys, SERIES):
        v = np.array([r[k] for r in by_slice], float)
        b.bar(yrs, v, width=200, bottom=bottom, color=c, label=lab, edgecolor=SURFACE, linewidth=0.8)
        bottom += v
    b.set_ylabel("site-phases")
    b.set_title("Site-phases per slice, by the kind of label their source gives", loc="left", fontsize=11, fontweight="bold")
    b.legend(frameon=False, loc="upper left", fontsize=8.5)
    b.set_xticks(np.arange(-10000, -2999, 1000))
    b.set_xticklabels([f"{-y:,}" for y in np.arange(-10000, -2999, 1000)])
    b.set_xlabel("slice centre, BCE")
    b.set_xlim(yrs[0] - 200, yrs[-1] + 1100)
    for ax in (a, b):
        ax.grid(axis="y", color=HAIR, linewidth=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
