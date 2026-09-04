"""
Generates demo/win_plot.png in dark presentation style matching
crater_two_suns.png, gradient_flip_diagram.png and premise_plot.png.
Uses generate_win_plot.py's data pipeline (real DEM if present, else synthetic),
then re-plots with the team's consistent dark theme.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.sweep import run_sweep, make_synthetic_dem
from src.match import match
from src.render import load_dem_patch, render_hillshade

# ── Style matching other deck assets ────────────────────────────────────────
DARK_BG  = "#0d1117"
PANEL_BG = "#161b22"
GRID     = "#21262d"
TEXT     = "#e6edf3"
SUBTEXT  = "#8b949e"

# Check if torch is available for LightGlue
try:
    import torch  # noqa: F401
    _TORCH_OK = True
except ImportError:
    _TORCH_OK = False

METHODS = [
    {"label": "SIFT  (rung 0, baseline)",  "matcher": "sift",      "rung": 0, "color": "#f85149", "marker": "o", "ls": "--"},
    {"label": "Mod-pi  (rung 1, our fix)", "matcher": "sift",      "rung": 1, "color": "#3fb950", "marker": "s", "ls": "-"},
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

# ── Terrain: real DEM if available, else synthetic ────────────────────────────
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

# ── Run sweeps ────────────────────────────────────────────────────────────────
from src.types import MatchResult
results = {}
for m in METHODS:
    if m.get("requires_torch") and not _TORCH_OK:
        print(f"  Skipping {m['label']} (torch not installed)")
        results[m["label"]] = {"diffs": diffs, "inlier_count": [None]*len(diffs), "success_rate": [None]*len(diffs)}
        continue
    print(f"  Running {m['label']} ...")
    def _trial(diff, matcher=m["matcher"], rung=m["rung"]):
        test_img = render_hillshade(dem, spacing, diff, base_elevation).astype(np.float32) / 255.0
        kwargs = {"rung": rung} if matcher == "sift" else {}
        try:
            return match(base_img, test_img, matcher=matcher, **kwargs)
        except Exception:
            return MatchResult(
                pts_a=np.zeros((0, 2)), pts_b=np.zeros((0, 2)),
                scores=np.zeros(0), inlier_mask=np.zeros(0, bool),
                transform=np.eye(3), matcher=matcher,
                shape_a=tuple(base_img.shape[:2]), shape_b=tuple(test_img.shape[:2]),
                runtime_s=0.0,
            )
    results[m["label"]] = run_sweep(_trial, diffs)
    print(f"    inlier_count = {results[m['label']]['inlier_count']}")

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(13, 7), facecolor=DARK_BG)
ax.set_facecolor(PANEL_BG)

# Shaded zones. Mod-pi's invariance is exact only for a true ~180-degree sun
# reversal (a global intensity negation) -- an arbitrary azimuth rotation
# reshuffles which slopes are lit rather than uniformly flipping bright/dark,
# so both matchers collapse together well past 70 degrees. Verified directly:
# rung 1 finds 0 total matches (not just 0 inliers) at 60/90/120 degrees on
# both real and synthetic terrain -- RANSAC's own 4-point minimum, not a
# plotting artifact. Do not shade this as a "SIFT blind zone" mod-pi escapes;
# it doesn't, until azimuth difference approaches full reversal.
ax.axvspan(25, 145, alpha=0.07, color="#f85149")
ax.axvspan(145, 190, alpha=0.07, color="#3fb950")
# Blended transform (x in data coords, y in axes-fraction) so these labels sit
# just above the x-axis regardless of the y-scale -- with LightGlue's much
# larger inlier counts sharing this axis, a fixed data-space y (e.g. -12)
# increasingly no longer lands below the SIFT/mod-pi lines as they crowd zero.
label_transform = ax.get_xaxis_transform()
ax.text(85, -0.06, "SIFT & mod-pi collapse", color="#f85149", fontsize=10, alpha=0.8,
       ha="center", transform=label_transform)
ax.text(167, -0.06, "mod-pi recovers\n(near-full reversal)", color="#3fb950", fontsize=9, alpha=0.85,
       ha="center", transform=label_transform)

for m in METHODS:
    lbl = m["label"]
    sw  = results[lbl]
    # Filter out None entries (e.g. LightGlue skipped when torch absent)
    pairs = [(d, v) for d, v in zip(sw["diffs"], sw["inlier_count"]) if v is not None]
    if not pairs:
        ax.plot([], [], label=f"{lbl}  [not available — torch not installed]",
                color=m["color"], linestyle=":")
        continue
    xs, ys = zip(*pairs)
    ax.plot(xs, ys,
            label=lbl, color=m["color"], marker=m["marker"],
            linestyle=m["ls"], linewidth=2.8, markersize=9,
            markerfacecolor=DARK_BG, markeredgewidth=2.2, markeredgecolor=m["color"])

ax.set_xlim(-5, 190)
ax.set_xlabel("Sun Azimuth Difference  (degrees)", fontsize=14, labelpad=8)
ax.set_ylabel("Inlier Match Count", fontsize=14, labelpad=8)
ax.set_title("Standard matching fails under any sun-angle change.\nMod-pi recovers only near full reversal (~150-180 deg).",
             fontsize=15, fontweight="bold", color=TEXT, pad=14)
ax.grid(True, linestyle="--", alpha=0.25)
legend = ax.legend(fontsize=11, framealpha=0.15, edgecolor=GRID,

                   facecolor=PANEL_BG, labelcolor=TEXT)

fig.text(0.5, 0.01,
         f"Terrain: {terrain_source} | elevation fixed at {base_elevation}° | "
         "azimuth sweep on x-axis  |  pipeline: src/sweep.py + src/match.py",
         ha="center", fontsize=9, color=SUBTEXT, style="italic")

os.makedirs("demo", exist_ok=True)
out = "demo/win_plot.png"
fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=DARK_BG)
print(f"Saved -> {out}")
