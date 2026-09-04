"""Build demo/real_pair_result from two LRO products, through the real pipeline.

Usage:
    python -m scripts.make_real_pair_result path/to/A.IMG path/to/B.IMG
"""

from __future__ import annotations

import argparse

from src.deliverable import build_deliverable
from src.io_lro import load_product
from src.pipeline import run_pipeline
from src.types import MatchResult


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product_a", help="LRO .IMG product to warp")
    parser.add_argument("product_b", help="LRO .IMG product defining the target frame")
    parser.add_argument("--out", default="demo/real_pair_result")
    parser.add_argument("--matcher", default="sift", choices=("sift", "lightglue"))
    parser.add_argument("--rung", type=int, default=0)
    parser.add_argument("--no-align", action="store_true",
                        help="skip geo.align_pair (scale/overlap normalisation) before matching")
    args = parser.parse_args()

    print("Step 1/4: loading product A")
    product_a = load_product(args.product_a)
    print(f"  {product_a.product_id}: {product_a.array.shape}")
    print("Step 2/4: loading product B")
    product_b = load_product(args.product_b)
    print(f"  {product_b.product_id}: {product_b.array.shape}")
    print("Step 3/4: running pipeline (align + match)")
    out = run_pipeline(product_a, product_b, matcher=args.matcher, rung=args.rung,
                       align=not args.no_align)
    mr = out["match_result"]
    result = MatchResult(
        pts_a=mr["pts_a"], pts_b=mr["pts_b"], scores=mr["scores"],
        inlier_mask=mr["inlier_mask"], transform=mr["transform"], matcher=mr["matcher"],
        shape_a=mr["shape_a"], shape_b=mr["shape_b"], runtime_s=mr["runtime_s"],
    )
    print(f"  {len(result.pts_a)} matches, {int(result.inlier_mask.sum())} inliers "
         f"(align={not args.no_align})")
    print("Step 4/4: writing registered raster and point deliverables")
    # build_deliverable maps pts_a/pts_b to lon/lat via each product's own corners --
    # correct here because run_pipeline(align=True) already inverted the points back
    # out of the aligned working grid into each product's original pixel frame.
    metrics = build_deliverable(product_a, product_b, result, args.out)
    print(f"  wrote {args.out}")
    print(f"  reprojection residual (fitted): {metrics['reprojection_residual']:.3f} px")


if __name__ == "__main__":
    main()
