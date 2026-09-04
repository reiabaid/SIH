"""
Generates demo/coverage_plot.png -- the statement's "uniform distribution
across the images" requirement, made visible, across the same azimuth sweep
as gen_win_plot.py's inlier-count win plot. Companion evidence, same dark
presentation style as win_plot.png/premise_plot.png/gradient_flip_diagram.png.

Inlier count alone doesn't show whether matches are spread across the image
or clumped in one high-contrast corner -- metrics.coverage's occupied_fraction
(fraction of an 8x8 grid containing >=1 inlier) is what actually measures
that. Plotting it across the same sweep shows *why* LightGlue is the
stronger result, not just that it finds more points.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.sweep import make_synthetic_dem
from src.render import load_dem_patch, render_hillshade
from src.match import match
from src.metrics import coverage
from src.types import MatchResult

DARK_BG = "#0d1117"
PANEL_BG = "#161b22"
GRID = "#21262d"
TEXT = "#e6edf3"
SUBTEXT = "#8b949e"

try:
    import torch  # noqa: F401
    _TORCH_OK = True
except ImportError:
    _TORCH_OK = False

METHODS = [
    {"label": "SIFT  (rung 0, baseline)",  "matcher": "sift",      "rung": 0, "color": "#f85149", "marker": "o", "ls": "--"},
    {"label": "Mod-pi  (rung 1)",          "matcher": "sift",      "rung": 1, "color": "#3fb950", "marker": "s", "ls": "-"},
    {"label": "LightGlue  (learned)",      "matcher": "lightglue", "rung": 0, "color": "#58a6ff", "marker": "^", "ls": "-", "requires_torch": True},
]

plt.rcParams.update({
    "figure.facecolor": DARK_BG,
    "axes.facecolor":   PANEL_BG,
    "axes.edgecolor":   GRID,
    "axes.labelcolor":  TEXT,
    "text.color":       TEXT,
    "xtick.color":      SUBTEXT,
    "ytick.color":      SUBTEXT,
    "grid.color":       GRID,
    "font.family":      "DejaVu Sans",
    "font.size":        13,
})

REAL_DEM_PATH = "data/dem/LDEM_60S_240MPP_ADJ.tiff"
terrain_source = "synthetic_dem"
try:
    dem, spacing = load_dem_patch(REAL_DEM_PATH, 2000, 2000, 512)
    terrain_source = "real_dem"
    print(f"Using real DEM: {REAL_DEM_PATH}")
except (FileNotFoundError, ValueError) as e:
    print(f"Real DEM not available ({e}) -- using synthetic multi-crater heightmap.")
    dem = make_synthetic_dem(size=256, seed=42, n_craters=40, rim_height=20.0)
    spacing = 1.0

base_elevation = 30.0
diffs = [0, 15, 30, 60, 90, 120, 150, 180]
base_img = render_hillshade(dem, spacing, 0.0, base_elevation).astype(np.float32) / 255.0

results = {}
for m in METHODS:
    if m.get("requires_torch") and not _TORCH_OK:
        print(f"  Skipping {m['label']} (torch not installed)")
        results[m["label"]] = [None] * len(diffs)
        continue
    print(f"  Running {m['label']} ...")
    occupied = []
    for diff in diffs:
        test_img = render_hillshade(dem, spacing, diff, base_elevation).astype(np.float32) / 255.0
        kwargs = {"rung": m["rung"]} if m["matcher"] == "sift" else {}
        try:
            result = match(base_img, test_img, matcher=m["matcher"], **kwargs)
        except Exception:
            result = MatchResult(
                pts_a=np.zeros((0, 2)), pts_b=np.zeros((0, 2)),
                scores=np.zeros(0), inlier_mask=np.zeros(0, bool),
                transform=np.eye(3), matcher=m["matcher"],
                shape_a=tuple(base_img.shape[:2]), shape_b=tuple(test_img.shape[:2]),
                runtime_s=0.0,
            )
        occupied.append(coverage(result)["occupied_fraction"])
    results[m["label"]] = occupied
    print(f"    occupied_fraction = {[round(v, 3) for v in occupied]}")

fig, ax = plt.subplots(figsize=(13, 7), facecolor=DARK_BG)
ax.set_facecolor(PANEL_BG)

for m in METHODS:
    lbl = m["label"]
    ys = results[lbl]
    pairs = [(d, v) for d, v in zip(diffs, ys) if v is not None]
    if not pairs:
        ax.plot([], [], label=f"{lbl}  [not available — torch not installed]",
                color=m["color"], linestyle=":")
        continue
    xs, yv = zip(*pairs)
    ax.plot(xs, yv,
            label=lbl, color=m["color"], marker=m["marker"],
            linestyle=m["ls"], linewidth=2.8, markersize=9,
            markerfacecolor=DARK_BG, markeredgewidth=2.2, markeredgecolor=m["color"])

ax.set_xlim(-5, 190)
ax.set_ylim(-0.05, 1.05)
ax.set_xlabel("Sun Azimuth Difference  (degrees)", fontsize=14, labelpad=8)
ax.set_ylabel("Coverage  (fraction of 8x8 grid with >=1 inlier)", fontsize=13, labelpad=8)
ax.set_title("Uniform match coverage: classical descriptors clump, LightGlue spreads",
             fontsize=16, fontweight="bold", color=TEXT, pad=14)
ax.grid(True, linestyle="--", alpha=0.25)
ax.legend(fontsize=11, framealpha=0.15, edgecolor=GRID, facecolor=PANEL_BG, labelcolor=TEXT)

fig.text(0.5, 0.01,
         f"Terrain: {terrain_source} | elevation fixed at {base_elevation}° | "
         "metric: metrics.coverage occupied_fraction (statement's \"uniform distribution\" requirement) | "
         "pipeline: src/sweep.py + src/match.py + src/metrics.py",
         ha="center", fontsize=9, color=SUBTEXT, style="italic")

os.makedirs("demo", exist_ok=True)
out = "demo/coverage_plot.png"
fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=DARK_BG)
print(f"Saved -> {out}")
