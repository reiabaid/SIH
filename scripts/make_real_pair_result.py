"""Build demo/real_pair_result from two LRO products.

Usage:
    python -m scripts.make_real_pair_result path/to/A.IMG path/to/B.IMG
"""

from __future__ import annotations

import argparse

from src.deliverable import build_deliverable
from src.io_lro import load_product
from src.match import match


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product_a", help="LRO .IMG product to warp")
    parser.add_argument("product_b", help="LRO .IMG product defining the target frame")
    parser.add_argument("--out", default="demo/real_pair_result")
    parser.add_argument("--matcher", default="sift", choices=("sift", "lightglue"))
    args = parser.parse_args()

    print("Step 1/4: loading product A")
    product_a = load_product(args.product_a)
    print(f"  {product_a.product_id}: {product_a.array.shape}")
    print("Step 2/4: loading product B")
    product_b = load_product(args.product_b)
    print(f"  {product_b.product_id}: {product_b.array.shape}")
    print("Step 3/4: matching A to B")
    result = match(product_a.array, product_b.array, matcher=args.matcher)
    print(f"  {len(result.pts_a)} matches, {int(result.inlier_mask.sum())} inliers")
    print("Step 4/4: writing registered raster and point deliverables")
    metrics = build_deliverable(product_a, product_b, result, args.out)
    print(f"  wrote {args.out}")
    print(f"  fitted RMSE: {metrics['rmse_fitted']:.3f} px")


if __name__ == "__main__":
    main()