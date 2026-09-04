"""
Re-exports premise_plot.png in a presentation-ready dark style matching
crater_two_suns.png and gradient_flip_diagram.png.
Uses the actual data from premise_test.py (hardcoded from the real run).
Output: demo/premise_plot.png (overwrites)
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os

DARK_BG  = "#0d1117"
PANEL_BG = "#161b22"
GRID     = "#21262d"
TEXT     = "#e6edf3"
SUBTEXT  = "#8b949e"
BLUE     = "#58a6ff"

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

# ── Real data from premise_test.py — real SLDEM2015 DEM patch (2000,2000,512) ─
# Run: python -m src.premise_test  (refactored to call src.match.match)
az      = [0,    15,  30,  60, 120]
inliers = [1578, 602, 38,   4,   4]   # real DEM run, 2026-09-05

fig, ax = plt.subplots(figsize=(12, 7), facecolor=DARK_BG)
ax.set_facecolor(PANEL_BG)

# Shaded collapse zone
ax.axvspan(0, 30, alpha=0.07, color=BLUE, label="_nolegend_")
ax.axvspan(30, 130, alpha=0.07, color="#f85149", label="_nolegend_")

# Main line
ax.plot(az, inliers, color=BLUE, linewidth=3, marker='o',
        markersize=10, markerfacecolor=DARK_BG, markeredgewidth=2.5,
        markeredgecolor=BLUE, zorder=5, label="SIFT inliers")

# Callout annotations
ax.annotate(f"~{inliers[0]:,} inliers\nat 0°  (same lighting)",
            xy=(0, inliers[0]), xytext=(15, 1400),
            fontsize=11, color=TEXT,
            arrowprops=dict(arrowstyle="-|>", color=SUBTEXT, lw=1.5),
            bbox=dict(boxstyle="round,pad=0.3", fc=PANEL_BG, ec=BLUE, lw=1.5))

ax.annotate(f"~{inliers[2]} inliers\nat 30°",
            xy=(30, inliers[2]), xytext=(45, 350),
            fontsize=11, color=TEXT,
            arrowprops=dict(arrowstyle="-|>", color=SUBTEXT, lw=1.5),
            bbox=dict(boxstyle="round,pad=0.3", fc=PANEL_BG, ec="#f85149", lw=1.5))

ax.annotate("Effectively zero\nfrom 60° onward",
            xy=(60, inliers[3]), xytext=(72, 200),
            fontsize=11, color=TEXT,
            arrowprops=dict(arrowstyle="-|>", color=SUBTEXT, lw=1.5),
            bbox=dict(boxstyle="round,pad=0.3", fc=PANEL_BG, ec="#f85149", lw=1.5))

# Zone labels
ax.text(8, -80, "Matchable", color=BLUE, fontsize=10.5, alpha=0.8, ha="center")
ax.text(80, -80, "SIFT blind zone", color="#f85149", fontsize=10.5, alpha=0.8, ha="center")

ax.set_xlim(-5, 130)
ax.set_ylim(-120, 1750)
ax.set_xlabel("Sun Azimuth Difference  (degrees)", fontsize=14, labelpad=8)
ax.set_ylabel("SIFT Inlier Count", fontsize=14, labelpad=8)
ax.set_title("SIFT inlier count collapses as sun azimuth diverges",
             fontsize=17, fontweight="bold", color=TEXT, pad=14)
ax.grid(True, linestyle="--", alpha=0.25)

# Subtitle
fig.text(0.5, 0.01,
         "Premise test — NASA SLDEM2015 real DEM (~69°S, 32°E), 240 m/px, elevation 30°, "
         "azimuth sweep on one axis   |   pipeline: src.premise_test → src.match.match",
         ha="center", fontsize=9, color=SUBTEXT, style="italic")

os.makedirs("demo", exist_ok=True)
out = "demo/premise_plot.png"
fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=DARK_BG)
print(f"Saved -> {out}")
