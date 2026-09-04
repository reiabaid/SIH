"""Build demo/synthetic_deliverable/ -- a complete, valid Deliverable 2 example
(registered raster, match points, overlay, metrics, ISIS control network) using
a synthetic crater field.

Why synthetic and not the real CH2 x LRO pair: the one real overlapping pair
available (d32 x M1499112398LE) does not currently have a trustworthy
registration -- metrics.fit_reliability correctly flags it trivial_fit=True
(see PROJECT_STATUS.md). Rather than package a spurious result as Deliverable
2, this produces a real, honestly-labelled working example through the exact
same pipeline (align, match, sub-pixel refine, metrics, deliverable export,
control network) so the format and mechanism are demonstrated correctly while
the real-pair investigation continues separately.

Usage:
    python -m scripts.make_synthetic_deliverable
"""

from __future__ import annotations

import os

import numpy as np

from src.cnet import write_control_network
from src.deliverable import build_deliverable
from src.pipeline import run_pipeline
from src.types import Product
from tests.make_synthetic import make_synthetic_pair

OUT_DIR = "demo/synthetic_deliverable"

# A plausible south-pole box near Mehak's real CH2 footprint (see
# TARGET_AREA.md) -- not tied to a real product, just a consistent box so the
# exported GeoTIFF/CSV/GeoJSON lon/lat columns are physically sane numbers
# rather than degenerate (0,0) placeholders.
CORNERS = {
    "ul": (-73.45, 42.70), "ur": (-73.45, 42.80),
    "ll": (-73.55, 42.70), "lr": (-73.55, 42.80),
}


def _synthetic_crater_field(size=512, seed=0, n_craters=60):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    img = 0.5 + 0.05 * rng.standard_normal((size, size)).astype(np.float32)
    for _ in range(n_craters):
        cx, cy = rng.uniform(0, size, size=2)
        r = rng.uniform(6, 28)
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        rim = np.exp(-((dist - r) ** 2) / (2 * (r * 0.25) ** 2))
        floor = -0.3 * np.clip(1 - dist / r, 0, 1)
        img += 0.4 * rim + floor
    return np.clip(img, 0.0, 1.0).astype(np.float32)


def main() -> None:
    print("Step 1/4: building synthetic crater field pair")
    base = _synthetic_crater_field(size=512, seed=7)
    warped, _ = make_synthetic_pair(
        base, seed=21, rotation_deg=3.0, scale_range=(0.98, 1.02), translation_frac=0.015
    )
    product_a = Product(array=base, gsd_m=1.0, corners=dict(CORNERS),
                        source="SYNTH", product_id="synthetic_a")
    product_b = Product(array=warped, gsd_m=1.0, corners=dict(CORNERS),
                        source="SYNTH", product_id="synthetic_b")

    print("Step 2/4: running pipeline (matcher=lightglue, the strongest benchmarked method)")
    out = run_pipeline(product_a, product_b, matcher="lightglue", align=False)
    mr = out["match_result"]
    from src.types import MatchResult
    result = MatchResult(
        pts_a=mr["pts_a"], pts_b=mr["pts_b"], scores=mr["scores"],
        inlier_mask=mr["inlier_mask"], transform=mr["transform"], matcher=mr["matcher"],
        shape_a=mr["shape_a"], shape_b=mr["shape_b"], runtime_s=mr["runtime_s"],
    )
    print(f"  {len(result.pts_a)} matches, {int(result.inlier_mask.sum())} inliers")

    print("Step 3/4: writing registered raster and point deliverables")
    metrics = build_deliverable(product_a, product_b, result, OUT_DIR)
    print(f"  wrote {OUT_DIR}")
    print(f"  reprojection residual: {metrics['reprojection_residual']:.4f} px")
    print(f"  unique inlier locations: {metrics['unique_inlier_locations']} "
         f"(trivial_fit={metrics['trivial_fit']})")

    print("Step 4/4: writing ISIS control network")
    cnet_path = os.path.join(OUT_DIR, "control_network.net")
    write_control_network(result, product_a, product_b, cnet_path,
                          network_id="SIH26166_SYNTH_DEMO", inliers_only=True)
    print(f"  wrote {cnet_path}")


if __name__ == "__main__":
    main()
