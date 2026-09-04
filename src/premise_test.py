# src/premise_test.py — premise test demonstrating SIFT failure under sun-azimuth change
# Owner: Riddhi
# Refactored to call production pipeline src.match.match directly.

import os
import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.render import load_dem_patch, render_hillshade
from src.match import match
from src.metrics import inlier_stats
from src.types import MatchResult


def match_images(img1: np.ndarray, img2: np.ndarray, matcher: str = "sift", rung: int = 0) -> MatchResult:
    """Match two images using the production match() pipeline.

    img1, img2 can be float32 in [0, 1] or uint8 in [0, 255].
    """
    a = img1.astype(np.float32) / 255.0 if img1.dtype == np.uint8 else img1.astype(np.float32)
    b = img2.astype(np.float32) / 255.0 if img2.dtype == np.uint8 else img2.astype(np.float32)
    return match(a, b, matcher=matcher, rung=rung)


def draw_match_result(img_a: np.ndarray, img_b: np.ndarray, result: MatchResult) -> np.ndarray:
    """Draw inlier/outlier matches from a MatchResult onto a side-by-side image."""
    a_u8 = (np.clip(img_a, 0.0, 1.0) * 255).astype(np.uint8) if img_a.dtype != np.uint8 else img_a
    b_u8 = (np.clip(img_b, 0.0, 1.0) * 255).astype(np.uint8) if img_b.dtype != np.uint8 else img_b

    if len(result.pts_a) == 0:
        stacked = np.hstack((a_u8, b_u8))
        return cv2.cvtColor(stacked, cv2.COLOR_GRAY2BGR) if len(stacked.shape) == 2 else stacked

    kp1 = [cv2.KeyPoint(x=float(pt[0]), y=float(pt[1]), size=3) for pt in result.pts_a]
    kp2 = [cv2.KeyPoint(x=float(pt[0]), y=float(pt[1]), size=3) for pt in result.pts_b]
    matches = [cv2.DMatch(_queryIdx=i, _trainIdx=i, _distance=0) for i in range(len(result.pts_a))]
    mask_list = result.inlier_mask.astype(int).tolist()

    draw_params = dict(
        matchColor=(0, 255, 0),       # Green for inliers
        singlePointColor=(0, 0, 255),  # Red for outliers
        matchesMask=mask_list,
        flags=cv2.DrawMatchesFlags_DEFAULT,
    )
    return cv2.drawMatches(a_u8, kp1, b_u8, kp2, matches, None, **draw_params)


def run_premise_test(dem_path: str = "data/dem/LDEM_60S_240MPP_ADJ.tiff", out_dir: str = "demo") -> dict:
    MATCH_OUT_DIR = os.path.join(out_dir, "premise_matches")
    os.makedirs(MATCH_OUT_DIR, exist_ok=True)

    try:
        dem, spacing = load_dem_patch(dem_path, 2000, 2000, 512)
    except (FileNotFoundError, Exception) as e:
        print(f"Skipping premise test execution: {e}")
        return {}

    elevation = 30.0
    azimuths = [0, 15, 30, 60, 120]

    print("Rendering images...")
    renders = {}
    for az in azimuths:
        renders[az] = render_hillshade(dem, spacing, az, elevation)

    base_img = renders[0]

    results_az = []
    results_inliers = []

    print("\n--- SIFT MATCHING RESULTS (via src.match.match) ---")
    print(f"{'Azimuth Diff':<15} | {'Total Matches':<15} | {'Inlier Count':<15} | {'Inlier Ratio'}")
    print("-" * 65)

    for az in azimuths:
        test_img = renders[az]
        res = match_images(base_img, test_img, matcher="sift", rung=0)
        stats = inlier_stats(res)

        tot = stats["total_matches"]
        inliers = stats["inlier_count"]
        ratio = stats["inlier_ratio"]

        results_az.append(az)
        results_inliers.append(inliers)

        print(f"{az:<15} | {tot:<15} | {inliers:<15} | {ratio:.2f}")

        img_matches = draw_match_result(base_img, test_img, res)
        out_path = os.path.join(MATCH_OUT_DIR, f"premise_matches_az{az}.png")
        cv2.imwrite(out_path, img_matches)

    # Plot
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(results_az, results_inliers, marker="o", linestyle="-", color="#00a8ff", linewidth=2)
    ax.set_title("SIFT inlier count collapses as sun azimuth diverges")
    ax.set_xlabel("Sun Azimuth Difference (°)")
    ax.set_ylabel("Inlier Count")
    ax.grid(True, linestyle="--", alpha=0.7)
    fig.tight_layout()

    plot_path = os.path.join(out_dir, "premise_plot.png")
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    print(f"\nSaved plot to {plot_path}")
    print(f"Saved match overlays to {MATCH_OUT_DIR}/")

    return {"azimuths": results_az, "inlier_counts": results_inliers}


def main():
    run_premise_test()


if __name__ == "__main__":
    main()

