import os
import cv2
import numpy as np
import matplotlib.pyplot as plt



from src.render import load_dem_patch, render_hillshade


def match_images(img1: np.ndarray, img2: np.ndarray) -> tuple[int, int, float, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Match two images using SIFT and RANSAC homography.
    Returns:
        total_matches, inlier_count, inlier_ratio, kp1, kp2, matches, mask
    """
    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(img1, None)
    kp2, des2 = sift.detectAndCompute(img2, None)

    if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
        return 0, 0, 0.0, kp1, kp2, [], np.array([])

    bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    raw_matches = bf.knnMatch(des1, des2, k=2)

    good_matches = []
    for m, n in raw_matches:
        if m.distance < 0.75 * n.distance:
            good_matches.append(m)

    total_matches = len(good_matches)
    if total_matches < 4:
        return total_matches, 0, 0.0, kp1, kp2, good_matches, np.array([])

    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

    _, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    
    if mask is None:
        inlier_count = 0
    else:
        inlier_count = int(np.sum(mask))
        
    inlier_ratio = inlier_count / total_matches if total_matches > 0 else 0.0

    return total_matches, inlier_count, inlier_ratio, kp1, kp2, good_matches, mask


def main():
    DEM_PATH = "data/dem/LDEM_60S_240MPP_ADJ.tiff"
    OUT_DIR = "demo"
    MATCH_OUT_DIR = os.path.join(OUT_DIR, "premise_matches")
    os.makedirs(MATCH_OUT_DIR, exist_ok=True)

    try:
        dem, spacing = load_dem_patch(DEM_PATH, 2000, 2000, 512)
    except FileNotFoundError:
        print(f"Skipping premise test because DEM file is missing: {DEM_PATH}")
        return

    elevation = 30.0
    azimuths = [0, 15, 30, 60, 120]
    
    print("Rendering images...")
    renders = {}
    for az in azimuths:
        renders[az] = render_hillshade(dem, spacing, az, elevation)

    base_img = renders[0]
    
    results_az = []
    results_inliers = []

    print("\n--- SIFT MATCHING RESULTS ---")
    print(f"{'Azimuth Diff':<15} | {'Total Matches':<15} | {'Inlier Count':<15} | {'Inlier Ratio'}")
    print("-" * 65)

    for az in azimuths:
        test_img = renders[az]
        tot, inliers, ratio, kp1, kp2, matches, mask = match_images(base_img, test_img)
        
        results_az.append(az)
        results_inliers.append(inliers)
        
        print(f"{az:<15} | {tot:<15} | {inliers:<15} | {ratio:.2f}")

        if az == 0 and ratio < 0.95:
            print("WARNING: 0-degree baseline matching failed to yield near-perfect inliers. Check the SIFT/RANSAC pipeline!")

        # Draw matches
        if len(matches) > 0 and mask is not None and len(mask) == len(matches):
            mask_list = mask.ravel().tolist()
            # Inliers in green, outliers in red
            draw_params = dict(matchColor=(0, 255, 0),
                               singlePointColor=(0, 0, 255),
                               matchesMask=mask_list,
                               flags=cv2.DrawMatchesFlags_DEFAULT)
            
            img_matches = cv2.drawMatches(base_img, kp1, test_img, kp2, matches, None, **draw_params)
        else:
            img_matches = np.concatenate((base_img, test_img), axis=1)
            img_matches = cv2.cvtColor(img_matches, cv2.COLOR_GRAY2BGR)

        out_path = os.path.join(MATCH_OUT_DIR, f"premise_matches_az{az}.png")
        cv2.imwrite(out_path, img_matches)

    # Plot
    plt.figure(figsize=(8, 5))
    plt.plot(results_az, results_inliers, marker='o', linestyle='-', color='b', linewidth=2)
    plt.title("SIFT inlier count collapses as sun azimuth diverges")
    plt.xlabel("Sun Azimuth Difference (°)")
    plt.ylabel("Inlier Count")
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plot_path = os.path.join(OUT_DIR, "premise_plot.png")
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    print(f"\nSaved plot to {plot_path}")
    print(f"Saved match overlays to {MATCH_OUT_DIR}/")


if __name__ == "__main__":
    main()
