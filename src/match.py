# src/match.py — detect, match, geometric filter, sub-pixel refine, grid-balance

import time
import numpy as np
import cv2

from src.types import MatchResult
from src.prep import gradient_orientation_mod_pi

GRID_SIZE = 8
MAX_KEYPOINTS_PER_CELL = 40
# Kept tight rather than OpenCV's typical 3.0 default: even MAGSAC's inlier/outlier
# split is defined relative to this distance from the *fitted* homography, so a loose
# threshold quietly admits real 1-2px error as "inliers" and blows the sub-pixel
# requirement even though every individual match still passed geometric filtering.
RANSAC_REPROJ_THRESHOLD = 1.5
LOWE_RATIO = 0.75
SUBPIXEL_WINDOW = 5  # neighbourhood side length for the correlation-peak fit
LIGHTGLUE_MIN_SCORE = 0.2  # drop low-confidence matches before RANSAC ever sees them

MODPI_PATCH_SIZE = 16   # side length of the patch each rung-1 descriptor is built from
MODPI_CELLS = 4          # patch is split into a CELLS x CELLS grid of orientation histograms
MODPI_BINS = 8            # orientation bins per cell, spanning [0, pi)

_lightglue_models = {}  # device -> (extractor, matcher), built once and reused


def _to_uint8(arr: np.ndarray) -> np.ndarray:
    a = np.clip(arr, 0.0, 1.0)
    return (a * 255).astype(np.uint8)


def grid_balance_keypoints(keypoints, descriptors, shape, grid=GRID_SIZE, cap=MAX_KEYPOINTS_PER_CELL):
    """Cap keypoints per grid cell so matches spread across the image instead of
    piling into one high-contrast region — the statement's uniform-distribution
    requirement, enforced at selection time rather than hoped for.
    """
    h, w = shape[:2]
    cell_h, cell_w = h / grid, w / grid
    buckets = {}
    for i, kp in enumerate(keypoints):
        cx, cy = kp.pt
        cell = (min(int(cy // cell_h), grid - 1), min(int(cx // cell_w), grid - 1))
        buckets.setdefault(cell, []).append(i)

    keep = []
    for idxs in buckets.values():
        idxs_sorted = sorted(idxs, key=lambda i: keypoints[i].response, reverse=True)
        keep.extend(idxs_sorted[:cap])

    kept_kps = [keypoints[i] for i in keep]
    kept_desc = descriptors[keep] if descriptors is not None else None
    return kept_kps, kept_desc


def _subpixel_refine(pts_a, pts_b, img_a, img_b, window=SUBPIXEL_WINDOW):
    """Refine each match to sub-pixel accuracy: correlate a small patch around the
    point in A against B's neighbourhood, fit a quadratic to the 3x3 around the
    correlation peak, take its analytic maximum.
    """
    half = window // 2
    refined_b = pts_b.copy()
    ha, wa = img_a.shape[:2]
    hb, wb = img_b.shape[:2]

    for i in range(len(pts_a)):
        ax, ay = pts_a[i]
        bx, by = pts_b[i]
        ax_i, ay_i = int(round(ax)), int(round(ay))
        bx_i, by_i = int(round(bx)), int(round(by))

        if not (half <= ax_i < wa - half and half <= ay_i < ha - half):
            continue
        if not (half + 1 <= bx_i < wb - half - 1 and half + 1 <= by_i < hb - half - 1):
            continue

        patch = img_a[ay_i - half: ay_i + half + 1, ax_i - half: ax_i + half + 1].astype(np.float32)

        search = img_b[
            by_i - half - 1: by_i + half + 2,
            bx_i - half - 1: bx_i + half + 2,
        ].astype(np.float32)
        result = cv2.matchTemplate(search, patch, cv2.TM_CCOEFF_NORMED)
        # result is 3x3: the correlation of `patch` at each 1-pixel offset around (bx_i, by_i)
        if result.shape != (3, 3):
            continue

        peak_y, peak_x = np.unravel_index(np.argmax(result), result.shape)
        if peak_y == 0 or peak_y == 2 or peak_x == 0 or peak_x == 2:
            # peak on the border — no interior maximum, skip sub-pixel fit
            continue

        dx = _parabolic_offset(result[peak_y, peak_x - 1], result[peak_y, peak_x], result[peak_y, peak_x + 1])
        dy = _parabolic_offset(result[peak_y - 1, peak_x], result[peak_y, peak_x], result[peak_y + 1, peak_x])

        refined_b[i, 0] = bx_i + (peak_x - 1) + dx
        refined_b[i, 1] = by_i + (peak_y - 1) + dy

    return refined_b


def _parabolic_offset(f_m1, f_0, f_p1):
    """Analytic maximum of a quadratic fit through three equally-spaced samples."""
    denom = f_m1 - 2 * f_0 + f_p1
    if abs(denom) < 1e-8:
        return 0.0
    return 0.5 * (f_m1 - f_p1) / denom


def _gradient_magnitude_u8(gray_u8: np.ndarray) -> np.ndarray:
    """Gradient-magnitude image, normalised to a 0..255 float range.

    The sub-pixel stage correlates this instead of raw intensity. Under a sun-angle
    flip the intensity gradient reverses sign, so a normalised-correlation peak on raw
    pixels inverts and the refine silently no-ops (verified: 0/N points refined under a
    contrast flip). Gradient *magnitude* is identical under that flip — |grad(1-x)| =
    |grad(x)| — so the correlation peak stays positive and the refine keeps working
    exactly when the illumination change makes it matter.
    """
    _, mag = gradient_orientation_mod_pi(gray_u8.astype(np.float32))
    mag = mag - float(mag.min())
    denom = float(mag.max())
    if denom > 1e-8:
        mag = mag / denom
    return (mag * 255.0).astype(np.float32)


def _describe_modpi(gray_u8: np.ndarray, keypoints, patch_size=MODPI_PATCH_SIZE,
                     cells=MODPI_CELLS, bins=MODPI_BINS):
    """Rung-1 descriptor: for each keypoint, a grid of gradient-orientation-mod-pi
    histograms (magnitude-weighted), instead of SIFT's signed 0-360 gradient
    descriptor. Unsigned orientation is what survives a sun-angle flip.
    """
    theta_mod, mag = gradient_orientation_mod_pi(gray_u8.astype(np.float32))
    half = patch_size // 2
    cell = patch_size // cells
    h, w = gray_u8.shape[:2]

    kept_kps, descs = [], []
    for kp in keypoints:
        x, y = int(round(kp.pt[0])), int(round(kp.pt[1]))
        if not (half <= x < w - half and half <= y < h - half):
            continue
        patch_theta = theta_mod[y - half:y + half, x - half:x + half]
        patch_mag = mag[y - half:y + half, x - half:x + half]

        desc = []
        for cy in range(cells):
            for cx in range(cells):
                ct = patch_theta[cy * cell:(cy + 1) * cell, cx * cell:(cx + 1) * cell].ravel()
                cm = patch_mag[cy * cell:(cy + 1) * cell, cx * cell:(cx + 1) * cell].ravel()
                hist, _ = np.histogram(ct, bins=bins, range=(0, np.pi), weights=cm)
                desc.append(hist)
        desc = np.concatenate(desc).astype(np.float32)
        norm = np.linalg.norm(desc)
        if norm > 1e-6:
            desc = desc / norm
        kept_kps.append(kp)
        descs.append(desc)

    if not descs:
        return [], None
    return kept_kps, np.stack(descs)


def _match_sift(a: np.ndarray, b: np.ndarray, rung: int = 0) -> MatchResult:
    """rung=0: plain SIFT (raw intensity, signed gradient descriptor) — the baseline
    that's expected to struggle under an illumination flip.
    rung=1: SIFT keypoint locations, but re-described with the mod-pi orientation
    histogram from _describe_modpi — the illumination-robust fix.
    """
    t0 = time.time()
    a8, b8 = _to_uint8(a), _to_uint8(b)
    matcher_name = f"sift-rung{rung}"

    sift = cv2.SIFT_create()
    kp_a, desc_a = sift.detectAndCompute(a8, None)
    kp_b, desc_b = sift.detectAndCompute(b8, None)

    if desc_a is None or desc_b is None or len(kp_a) < 4 or len(kp_b) < 4:
        return _empty_result(a, b, matcher_name, time.time() - t0)

    kp_a, desc_a = grid_balance_keypoints(kp_a, desc_a, a.shape)
    kp_b, desc_b = grid_balance_keypoints(kp_b, desc_b, b.shape)

    if rung == 1:
        kp_a, desc_a = _describe_modpi(a8, kp_a)
        kp_b, desc_b = _describe_modpi(b8, kp_b)
        if desc_a is None or desc_b is None or len(kp_a) < 4 or len(kp_b) < 4:
            return _empty_result(a, b, matcher_name, time.time() - t0)
    elif rung != 0:
        raise ValueError(f"unknown rung: {rung!r}, expected 0 or 1")

    bf = cv2.BFMatcher(cv2.NORM_L2)
    raw_matches = bf.knnMatch(desc_a, desc_b, k=2)

    good = []
    for pair in raw_matches:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < LOWE_RATIO * n.distance:
            good.append(m)

    if len(good) < 4:
        return _empty_result(a, b, matcher_name, time.time() - t0)

    pts_a = np.float32([kp_a[m.queryIdx].pt for m in good])
    pts_b = np.float32([kp_b[m.trainIdx].pt for m in good])
    scores = np.float32([1.0 - (m.distance / (good[-1].distance + 1e-8)) for m in good])

    return _finalize(pts_a, pts_b, scores, a8, b8, matcher_name, t0)


def _get_lightglue_models(device: str):
    """Build SuperPoint + LightGlue once per device and reuse them.

    Reconstructing these on every match() call is expensive (most of the observed
    runtime on CPU was model construction, not inference) and would be disastrous
    once pipeline.py starts tiling a large raster into many tile-pair matches.
    """
    if device not in _lightglue_models:
        from lightglue import LightGlue, SuperPoint

        extractor = SuperPoint(max_num_keypoints=2048).eval().to(device)
        matcher = LightGlue(features="superpoint").eval().to(device)
        _lightglue_models[device] = (extractor, matcher)
    return _lightglue_models[device]


def _match_lightglue(a: np.ndarray, b: np.ndarray) -> MatchResult:
    t0 = time.time()
    import torch
    from lightglue.utils import numpy_image_to_torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    extractor, matcher = _get_lightglue_models(device)

    img_a = numpy_image_to_torch(a).to(device)
    img_b = numpy_image_to_torch(b).to(device)

    with torch.no_grad():
        feats_a = extractor.extract(img_a.unsqueeze(0))
        feats_b = extractor.extract(img_b.unsqueeze(0))
        result = matcher({"image0": feats_a, "image1": feats_b})

    matches = result["matches"][0].cpu().numpy()
    kpts_a = feats_a["keypoints"][0].cpu().numpy()
    kpts_b = feats_b["keypoints"][0].cpu().numpy()
    conf = result["scores"][0].cpu().numpy() if "scores" in result else np.ones(len(matches))

    if len(matches) < 4:
        return _empty_result(a, b, "lightglue", time.time() - t0)

    pts_a = kpts_a[matches[:, 0]]
    pts_b = kpts_b[matches[:, 1]]
    scores = conf.astype(np.float32)

    # Low-confidence matches are the likeliest mismatches, and RANSAC's reprojection
    # threshold alone doesn't catch a wrong-but-locally-consistent match. Drop them
    # before fitting the homography rather than trusting RANSAC to do it.
    keep = scores >= LIGHTGLUE_MIN_SCORE
    if keep.sum() < 4:
        return _empty_result(a, b, "lightglue", time.time() - t0)
    pts_a, pts_b, scores = pts_a[keep], pts_b[keep], scores[keep]

    return _finalize(pts_a, pts_b, scores, _to_uint8(a), _to_uint8(b), "lightglue", t0)


def _finalize(pts_a, pts_b, scores, a8, b8, matcher_name, t0) -> MatchResult:
    # MAGSAC instead of plain RANSAC: same call, no threshold to hand-tune — it
    # estimates the noise scale itself rather than needing a fixed inlier cutoff.
    transform, ransac_mask = cv2.findHomography(
        pts_a, pts_b, cv2.USAC_MAGSAC, RANSAC_REPROJ_THRESHOLD
    )
    if transform is None:
        return _empty_result(a8, b8, matcher_name, time.time() - t0)

    inlier_mask = ransac_mask.ravel().astype(bool)
    # Refine on gradient magnitude, not raw intensity, so the correlation peak survives
    # an illumination polarity flip (see _gradient_magnitude_u8).
    pts_b_refined = _subpixel_refine(pts_a, pts_b, _gradient_magnitude_u8(a8), _gradient_magnitude_u8(b8))

    return MatchResult(
        pts_a=pts_a.astype(np.float32),
        pts_b=pts_b_refined.astype(np.float32),
        scores=scores.astype(np.float32),
        inlier_mask=inlier_mask,
        transform=transform.astype(np.float64),
        matcher=matcher_name,
        shape_a=tuple(a8.shape[:2]),
        shape_b=tuple(b8.shape[:2]),
        runtime_s=time.time() - t0,
    )


def _empty_result(a, b, matcher_name, runtime_s) -> MatchResult:
    return MatchResult(
        pts_a=np.zeros((0, 2), dtype=np.float32),
        pts_b=np.zeros((0, 2), dtype=np.float32),
        scores=np.zeros((0,), dtype=np.float32),
        inlier_mask=np.zeros((0,), dtype=bool),
        transform=np.eye(3, dtype=np.float64),
        matcher=matcher_name,
        shape_a=tuple(a.shape[:2]),
        shape_b=tuple(b.shape[:2]),
        runtime_s=runtime_s,
    )


def match(a: np.ndarray, b: np.ndarray, matcher: str = "sift", rung: int = 0) -> MatchResult:
    """Detect, match, geometric filter, sub-pixel refine.

    a, b: 2D grayscale float32 arrays in 0..1.
    matcher: "sift" or "lightglue".
    rung: only applies to matcher="sift". 0 = raw-intensity SIFT descriptor
      (baseline, expected to struggle under an illumination flip). 1 = same
      keypoints, re-described with gradient-orientation-mod-pi histograms
      (illumination-robust; see src.prep.gradient_orientation_mod_pi).
    """
    if matcher == "sift":
        return _match_sift(a, b, rung=rung)
    elif matcher == "lightglue":
        return _match_lightglue(a, b)
    else:
        raise ValueError(f"unknown matcher: {matcher!r}")
