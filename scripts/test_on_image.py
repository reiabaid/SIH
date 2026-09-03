# scripts/test_on_image.py — run the matcher on a real photo, warped with a known
# homography (and optional illumination change), and report recovered-vs-true RMSE.
#
# Usage: python scripts/test_on_image.py data/image.png [--illum]

import argparse
import sys
import numpy as np
import cv2

from src.match import match
from src.prep import to_gray_float, local_contrast_norm
from tests.make_synthetic import make_synthetic_pair


def rmse_against_truth(pts_a, pts_b, inlier_mask, H_true):
    pts_a_in = pts_a[inlier_mask]
    pts_b_in = pts_b[inlier_mask]
    if len(pts_a_in) == 0:
        return np.inf
    ones = np.ones((len(pts_a_in), 1))
    homog = np.hstack([pts_a_in.astype(np.float64), ones])
    projected = (H_true @ homog.T).T
    projected = projected[:, :2] / projected[:, 2:3]
    err = np.linalg.norm(projected - pts_b_in.astype(np.float64), axis=1)
    return float(np.sqrt(np.mean(err ** 2)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image_path")
    parser.add_argument("--matcher", default="sift", choices=["sift", "lightglue"])
    parser.add_argument("--illum", action="store_true", help="simulate a sun-angle change")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    raw = cv2.imread(args.image_path, cv2.IMREAD_GRAYSCALE)
    if raw is None:
        print(f"could not read {args.image_path}", file=sys.stderr)
        sys.exit(1)

    img = to_gray_float(raw)
    warped, H_true = make_synthetic_pair(
        img,
        seed=args.seed,
        rotation_deg=10.0,
        scale_range=(0.9, 1.1),
        translation_frac=0.04,
        illumination=args.illum,
        illumination_angle_deg=60.0,
        illumination_strength=0.6,
    )

    a = local_contrast_norm(img, sigma=15.0)
    b = local_contrast_norm(warped, sigma=15.0)

    result = match(a, b, matcher=args.matcher)
    n_inliers = int(result.inlier_mask.sum())
    rmse = rmse_against_truth(result.pts_a, result.pts_b, result.inlier_mask, H_true)

    print(f"matcher:      {result.matcher}")
    print(f"illumination: {'on (' + str(60.0) + ' deg ramp)' if args.illum else 'off'}")
    print(f"matches:      {len(result.pts_a)}")
    print(f"inliers:      {n_inliers}")
    print(f"RMSE vs true: {rmse:.3f} px")
    print(f"runtime:      {result.runtime_s:.3f} s")

    # save a visual side-by-side for a sanity check
    out = cv2.hconcat([
        cv2.cvtColor((a * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR),
        cv2.cvtColor((b * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR),
    ])
    cv2.imwrite("demo/test_on_image_preview.png", out)
    print("wrote demo/test_on_image_preview.png")


if __name__ == "__main__":
    main()
