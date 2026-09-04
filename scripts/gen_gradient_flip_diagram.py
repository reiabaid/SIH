"""
Generates a presentation-ready gradient-flip diagram explaining the mod-π fix.
Shows: intensity profile + gradient arrow under Sun A (0°), Sun B (180°), and after mod-π.
Output: demo/gradient_flip_diagram.png
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
from matplotlib.gridspec import GridSpec

# ── Style ───────────────────────────────────────────────────────────────────
DARK_BG   = "#0d1117"
PANEL_BG  = "#161b22"
ACCENT_A  = "#58a6ff"   # blue  – Sun A
ACCENT_B  = "#f85149"   # red   – Sun B
ACCENT_FX = "#3fb950"   # green – after mod-π
TEXT      = "#e6edf3"
SUBTEXT   = "#8b949e"
GRID      = "#21262d"

plt.rcParams.update({
    "figure.facecolor":  DARK_BG,
    "axes.facecolor":    PANEL_BG,
    "axes.edgecolor":    GRID,
    "axes.labelcolor":   TEXT,
    "text.color":        TEXT,
    "xtick.color":       SUBTEXT,
    "ytick.color":       SUBTEXT,
    "grid.color":        GRID,
    "font.family":       "DejaVu Sans",
})

# ── Synthetic intensity profile of a crater rim ─────────────────────────────
x = np.linspace(0, 1, 300)

def rim_profile(sun_from_left=True):
    """Crater rim: bright slope facing sun, dark shadow on the other side."""
    profile = np.zeros_like(x)
    # Rim peak
    rim = np.exp(-((x - 0.5)**2) / 0.004)
    if sun_from_left:
        bright = np.exp(-((x - 0.35)**2) / 0.012) * 0.85
        shadow = -np.exp(-((x - 0.65)**2) / 0.012) * 0.6
    else:
        bright = np.exp(-((x - 0.65)**2) / 0.012) * 0.85
        shadow = -np.exp(-((x - 0.35)**2) / 0.012) * 0.6
    profile = 0.35 + rim * 0.5 + bright + shadow
    return np.clip(profile, 0, 1)

I_A = rim_profile(sun_from_left=True)   # Sun at 0° (from left)
I_B = rim_profile(sun_from_left=False)  # Sun at 180° (from right)

# Gradient at the rim edge (centre of the image ~x=0.5)
grad_A = np.gradient(I_A)
grad_B = np.gradient(I_B)

# Peak gradient location
pk = np.argmax(np.abs(grad_A))
gA = grad_A[pk]   # positive
gB = grad_B[pk]   # negative (flipped!)

# ── Layout ──────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(18, 8), facecolor=DARK_BG)
gs = GridSpec(2, 3, figure=fig,
              left=0.06, right=0.97, top=0.88, bottom=0.13,
              wspace=0.38, hspace=0.52)

ARROW_KW = dict(arrowstyle="-|>", mutation_scale=20, lw=2.5, zorder=5)

def plot_panel(ax, profile, color, title, grad_val, arrow_label, show_mod=False):
    ax.set_facecolor(PANEL_BG)
    ax.plot(x, profile, color=color, lw=2.5, label="Intensity I(x)")
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.05, 1.15)
    ax.set_xlabel("Position along edge  →", fontsize=10, labelpad=4)
    ax.set_ylabel("Pixel Intensity", fontsize=10)
    ax.set_title(title, fontsize=13, fontweight="bold", color=TEXT, pad=8)
    ax.grid(True, alpha=0.25)

    # Gradient arrow at rim
    xp = x[pk]
    yp = float(profile[pk])
    sign = np.sign(grad_val)
    dx = sign * 0.14
    c = ACCENT_FX if show_mod else color
    ax.annotate("", xy=(xp + dx, yp + abs(dx)*0.6*sign),
                xytext=(xp, yp),
                arrowprops=dict(arrowstyle="-|>", color=c,
                                mutation_scale=22, lw=2.5))
    ax.text(xp + dx + 0.01*sign, yp + abs(dx)*0.65*sign,
            arrow_label, color=c, fontsize=11, fontweight="bold")

    # Tiny annotation: gradient value
    ax.text(0.98, 0.04,
            f"∇I ≈ {grad_val:+.3f}" if not show_mod else "∇I mod π  →  same ↑",
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=9, color=SUBTEXT, style="italic")

# ── Panel 0: Top-row labels (sun icons) ─────────────────────────────────────
for col, (label, col_c) in enumerate([
    ("☀  Sun azimuth  0°\n(light from the left)", ACCENT_A),
    ("☀  Sun azimuth 180°\n(light from the right)", ACCENT_B),
    ("✓  After  mod π\n(orientation only)", ACCENT_FX),
]):
    ax_lbl = fig.add_subplot(gs[0, col])
    plot_panel(ax_lbl,
               I_A if col < 2 else I_A,
               ACCENT_A if col == 0 else (ACCENT_B if col == 1 else ACCENT_FX),
               label,
               gA if col == 0 else (gB if col == 1 else gA),
               "∇ →" if col == 0 else ("∇ ←" if col == 1 else "∇ ↑"),
               show_mod=(col == 2))
    if col == 2:
        # Overlay both profiles faintly
        ax_lbl.plot(x, I_B, color=ACCENT_B, lw=1.2, alpha=0.35, ls="--")

# ── Bottom row: gradient magnitude bar + explanation boxes ───────────────────
for col, (title, val, color, note) in enumerate([
    ("SIFT descriptor\nunder Sun A",  abs(gA), ACCENT_A,
     "Gradient bin: ~45°\n→ strong match at 45°"),
    ("SIFT descriptor\nunder Sun B",  abs(gB), ACCENT_B,
     "Gradient bin: ~225°\n→ completely different bin\n→ MATCH FAILS ✗"),
    ("mod-π descriptor\nboth suns",   abs(gA), ACCENT_FX,
     "Orientation bin: ~45°\n(same for both lightings)\n→ MATCH HOLDS ✓"),
]):
    ax_b = fig.add_subplot(gs[1, col])
    ax_b.set_facecolor(PANEL_BG)
    # Polar-style compass showing gradient direction
    theta = np.linspace(0, 2*np.pi, 360)
    ax_b.set_aspect("equal")
    ax_b.set_xlim(-1.4, 1.4); ax_b.set_ylim(-1.4, 1.4)
    ax_b.set_xticks([]); ax_b.set_yticks([])
    ax_b.set_title(title, fontsize=11, fontweight="bold", color=TEXT, pad=6)

    # Draw circle
    circ = plt.Circle((0, 0), 1.0, color=GRID, fill=False, lw=1.5)
    ax_b.add_patch(circ)

    if col == 0:
        angles = [45]
        colors_arr = [ACCENT_A]
    elif col == 1:
        angles = [45, 225]   # original + flipped
        colors_arr = [ACCENT_A, ACCENT_B]
    else:
        angles = [45]        # mod π collapses both to same
        colors_arr = [ACCENT_FX]

    for ang, c in zip(angles, colors_arr):
        r = np.radians(ang)
        ax_b.annotate("", xy=(np.cos(r), np.sin(r)),
                      xytext=(0, 0),
                      arrowprops=dict(arrowstyle="-|>", color=c,
                                      mutation_scale=18, lw=2.5))

    ax_b.text(0, -1.32, note, ha="center", va="top",
              fontsize=9.5, color=TEXT,
              bbox=dict(boxstyle="round,pad=0.4", fc=PANEL_BG,
                        ec=color, lw=1.5))

# ── Title ────────────────────────────────────────────────────────────────────
fig.text(0.5, 0.965,
         "Why SIFT fails under illumination change — and what mod π fixes",
         ha="center", va="top", fontsize=17, fontweight="bold", color=TEXT)
fig.text(0.5, 0.935,
         "Reversing the sun flips the gradient direction by 180°. "
         "SIFT sees a different descriptor. Taking gradient mod π collapses "
         "direction → orientation, making matching illumination-invariant.",
         ha="center", va="top", fontsize=11, color=SUBTEXT, wrap=True)

import os
os.makedirs("demo", exist_ok=True)
out = "demo/gradient_flip_diagram.png"
fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=DARK_BG)
print(f"Saved -> {out}")
