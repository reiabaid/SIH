"""
Generates the opening slide image: same crater rendered under Sun 0° and Sun 180°,
side-by-side with annotation. No DEM needed — uses a synthetic crater DEM.
Output: demo/crater_two_suns.png
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.render import compute_surface_normals, sun_direction


DARK_BG  = "#0d1117"
TEXT     = "#e6edf3"
SUBTEXT  = "#8b949e"
ACCENT_A = "#58a6ff"
ACCENT_B = "#f85149"

# ── Synthetic crater DEM (no file required) ──────────────────────────────────
SIZE = 512
y, x = np.ogrid[-1:1:SIZE*1j, -1:1:SIZE*1j]
r = np.sqrt(x**2 + y**2)

# Bowl-shaped crater with a rim
rim     = np.exp(-((r - 0.55)**2) / 0.008) * 280
bowl    = np.where(r < 0.55, -180 * (1 - (r/0.55)**2), 0)
floor   = np.where(r < 0.30, 40 * (1 - (r/0.30)**2), 0)
# Background gentle slope
slope   = x * 40 + y * 20
# Small secondary crater
r2 = np.sqrt((x-0.72)**2 + (y-0.30)**2)
secondary = np.exp(-((r2 - 0.10)**2) / 0.003) * 60 - np.where(r2<0.10, 40*(1-(r2/0.10)**2), 0)
# Add terrain noise
rng = np.random.default_rng(42)
noise = rng.normal(0, 6, (SIZE, SIZE))

dem = (slope + rim + bowl + floor + secondary + noise).astype(np.float32)
# Smooth slightly
from numpy.lib.stride_tricks import sliding_window_view

def _box_smooth(arr, k=5):
    pad = k // 2
    padded = np.pad(arr, pad, mode="reflect")
    view = sliding_window_view(padded, (k, k))
    return view.mean(axis=(-2, -1)).astype(np.float32)

dem = _box_smooth(dem, k=7)

pixel_spacing = 240.0  # metres, matching LDEM

def render_hillshade(dem, pixel_spacing, azimuth_deg, elevation_deg=20.0):
    normals = compute_surface_normals(dem, pixel_spacing)
    sun_vec = sun_direction(azimuth_deg, elevation_deg)
    illum = np.dot(normals, sun_vec)
    illum = np.clip(illum, 0, 1)
    return (illum * 255).astype(np.uint8)

img_A = render_hillshade(dem, pixel_spacing, azimuth_deg=0,   elevation_deg=20)
img_B = render_hillshade(dem, pixel_spacing, azimuth_deg=180, elevation_deg=20)

# ── Figure ───────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(16, 8), facecolor=DARK_BG)
fig.subplots_adjust(left=0.04, right=0.96, top=0.88, bottom=0.10, wspace=0.06)

for ax, img, color, label, sun_note in [
    (axes[0], img_A, ACCENT_A, "Sun azimuth  0°\n(light from North)", "Standard matcher: ACCEPTS"),
    (axes[1], img_B, ACCENT_B, "Sun azimuth 180°\n(light from South)", "Standard matcher: REJECTS ✗"),
]:
    ax.imshow(img, cmap="gray", vmin=0, vmax=255, aspect="equal")
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor(color); spine.set_linewidth(3)
    ax.set_title(label, color=color, fontsize=16, fontweight="bold", pad=10)
    ax.text(0.5, -0.04, sun_note, transform=ax.transAxes,
            ha="center", va="top", fontsize=13, color=SUBTEXT, style="italic")

# Sun direction arrows
for ax, az_deg, color in [(axes[0], 0, ACCENT_A), (axes[1], 180, ACCENT_B)]:
    r = np.radians(az_deg)
    # Arrow from centre outward showing sun direction
    cx, cy = 0.5, 0.5
    dx = np.sin(r) * 0.22
    dy = -np.cos(r) * 0.22   # image y is flipped
    ax.annotate("", xy=(cx + dx, cy + dy), xytext=(cx, cy),
                xycoords="axes fraction",
                arrowprops=dict(arrowstyle="-|>", color=color,
                                mutation_scale=20, lw=2.5))

# Main title
fig.text(0.5, 0.96,
         "Same crater — two different sun angles",
         ha="center", va="top", fontsize=20, fontweight="bold", color=TEXT)
fig.text(0.5, 0.925,
         "Shadows reverse completely. Every standard feature matcher (SIFT, ORB) "
         "thinks these are different places.",
         ha="center", va="top", fontsize=13, color=SUBTEXT)

# PLACEHOLDER watermark (to be swapped for real CH-2 × LRO)
fig.text(0.97, 0.02, "[PLACEHOLDER: synthetic DEM — swap for real CH-2 × LRO on slide 1]",
         ha="right", va="bottom", fontsize=8, color="#444c56", style="italic")

os.makedirs("demo", exist_ok=True)
out = "demo/crater_two_suns.png"
fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=DARK_BG)
print(f"Saved -> {out}")
