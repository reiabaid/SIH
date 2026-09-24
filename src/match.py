# src/match.py — detect, match, geometric filter, sub-pixel refine, grid-balance

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import cv2

from src.types import MatchResult
from src.prep import gradient_orientation_mod_pi, log_gabor_max_index_map, tile, untile_points

TILE_SIZE = 1024   # side length in px; large rasters (OHRC strips run ~55000x12000)
TILE_OVERLAP = 128  # must exceed the largest expected inter-image shift at tile scale
SIMILARITY_MAX_ITERS = 100_000  # 2-point samples; cheap, and inlier ratios are ~1-3%
MIN_POOL_POINTS = 500  # match_tiled's early-exit threshold; see match_tiled's docstring

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
MODPI_BINS = 8            # log-Gabor orientation channels per cell (also norient for log_gabor_max_index_map)

_lightglue_models = {}  # device -> (extractor, matcher), built once and reused
_lightglue_lock = threading.Lock()  # guards first-time model construction across
                                    # match_tiled's worker threads


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

    Skips points where the initial match is already within 0.1 px of integer
    alignment (the refine would move them by <0.01 px anyway — not worth the
    cv2.matchTemplate call). Also skips boundary points that can't supply a
    full search window.
    """
    half = window // 2
    refined_b = pts_b.copy()
    ha, wa = img_a.shape[:2]
    hb, wb = img_b.shape[:2]
    refined_count = 0

    for i in range(len(pts_a)):
        ax, ay = pts_a[i]
        bx, by = pts_b[i]

        # Skip if already within 0.1 px of integer alignment — the parabolic
        # fit would contribute <0.01 px correction, not worth the overhead.
        if abs(bx - round(bx)) < 0.1 and abs(by - round(by)) < 0.1:
            continue

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
        refined_count += 1

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
    """Rung-1 descriptor: for each keypoint, a grid of magnitude-weighted
    histograms over RIFT-style Maximum-Index-Map orientation-channel labels,
    instead of SIFT's signed 0-360 gradient descriptor.

    This used to be built from raw Sobel gradient-orientation-mod-pi (see
    gradient_orientation_mod_pi, still used elsewhere for sub-pixel refine).
    That representation only survives a *global* illumination sign flip --
    exactly what the synthetic ablation test constructs -- because it's the
    same texture with every gradient reversed. On real cross-sensor pairs
    (independent optics/noise/dynamic range, a genuinely non-uniform
    illumination difference, not a clean 1-x inversion), verified this session
    (2026-09-15) via a real-data true-match-vs-random-pair descriptor-distance
    test: raw gradient orientation carried ~zero discriminative signal at
    genuine correspondences (mean true-match distance was *not* below the
    random-pair mean) despite passing the pure-inversion unit test, which is
    why rung 1 scored 0 matches against every real CH2xLRO pair in the
    inventory. log_gabor_max_index_map's "which log-Gabor orientation channel
    wins" is a ranking/ordinal quantity, not a raw derivative -- the same
    literature-backed intuition behind RIFT/HAPCG (docs/research/reia.md),
    and far less sensitive to independent per-sensor contrast/gain than a
    Sobel gradient's absolute direction and magnitude.

    Vectorized across all keypoints at once (patch gather via fancy indexing,
    per-cell histograms via np.add.at) instead of a per-keypoint Python loop --
    this was the actual bottleneck behind rung 1 running ~4-10x slower than
    SIFT/LightGlue on real tiled imagery even before the MIM swap.
    """
    mim, mag = log_gabor_max_index_map(gray_u8.astype(np.float32), nscale=3, norient=bins, downsample=2)
    half = patch_size // 2
    cell = patch_size // cells
    h, w = gray_u8.shape[:2]

    kept_kps = [kp for kp in keypoints
               if half <= int(round(kp.pt[0])) < w - half and half <= int(round(kp.pt[1])) < h - half]
    if not kept_kps:
        return [], None

    xs = np.array([int(round(kp.pt[0])) for kp in kept_kps])
    ys = np.array([int(round(kp.pt[1])) for kp in kept_kps])
    n = len(kept_kps)

    # Gather every keypoint's patch_size x patch_size neighbourhood at once.
    offs = np.arange(-half, half)
    row_idx = np.broadcast_to((ys[:, None, None] + offs[None, :, None]), (n, patch_size, patch_size))
    col_idx = np.broadcast_to((xs[:, None, None] + offs[None, None, :]), (n, patch_size, patch_size))
    bin_idx = mim[row_idx, col_idx]  # already an integer channel index in [0, bins)
    mag_patches = mag[row_idx, col_idx]

    descs = np.zeros((n, cells * cells * bins), dtype=np.float32)
    cell_pixels = cell * cell
    kp_repeat = np.repeat(np.arange(n), cell_pixels)
    for cy in range(cells):
        for cx in range(cells):
            r0, c0 = cy * cell, cx * cell
            cell_bins = bin_idx[:, r0:r0 + cell, c0:c0 + cell].reshape(n, cell_pixels)
            cell_mag = mag_patches[:, r0:r0 + cell, c0:c0 + cell].reshape(n, cell_pixels)

            hist = np.zeros((n, bins), dtype=np.float32)
            np.add.at(hist, (kp_repeat, cell_bins.ravel()), cell_mag.ravel())

            out_col = (cy * cells + cx) * bins
            descs[:, out_col:out_col + bins] = hist

    norms = np.linalg.norm(descs, axis=1)
    safe = norms > 1e-6
    descs[safe] /= norms[safe, None]

    return kept_kps, descs


def _match_sift(a: np.ndarray, b: np.ndarray, rung: int = 0) -> MatchResult:
    """rung=0: plain SIFT (raw intensity, signed gradient descriptor) — the baseline
    that's expected to struggle under an illumination flip.
    rung=1: SIFT keypoint locations, but re-described with the log-Gabor
    Maximum-Index-Map histogram from _describe_modpi — the illumination-robust fix.
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
        with _lightglue_lock:
            if device not in _lightglue_models:  # re-check: another thread may have built it while we waited
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

    # numpy_image_to_torch unconditionally divides by 255 -- it expects a raw
    # 0..255-scale image, not match()'s own 0..1 contract. Passing `a`/`b`
    # straight through double-normalizes them to ~0.004 max, which SuperPoint
    # sees as an all-black image and finds zero keypoints on. Scale back up
    # first so the library's own /255 lands on the correct final range.
    img_a = numpy_image_to_torch(a * 255.0).to(device)
    img_b = numpy_image_to_torch(b * 255.0).to(device)

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
    #
    # setRNGSeed: USAC_MAGSAC draws random sample sets internally and OpenCV's
    # RNG is unseeded by default, so identical input points could otherwise
    # fit a different homography (and a different inlier count/well_determined
    # verdict) on every run -- confirmed 2026-09-16 by rerunning the same real
    # pair/config/tile-pooling and getting 10 vs 14 inliers from byte-identical
    # pooled input. Seeding immediately before the fit makes it reproducible.
    cv2.setRNGSeed(0)
    transform, ransac_mask = cv2.findHomography(
        pts_a, pts_b, cv2.USAC_MAGSAC, RANSAC_REPROJ_THRESHOLD
    )
    if transform is None:
        return _empty_result(a8, b8, matcher_name, time.time() - t0)

    inlier_mask = ransac_mask.ravel().astype(bool)
    # Compute gradient magnitude once, reuse for all sub-pixel refinements.
    # Previously this was called inside _subpixel_refine which recomputed it
    # on the full image for every call — wasted work since the gradient doesn't
    # change between the two calls (a and b are the same pair throughout).
    grad_a = _gradient_magnitude_u8(a8)
    grad_b = _gradient_magnitude_u8(b8)
    pts_b_refined = _subpixel_refine(pts_a, pts_b, grad_a, grad_b)

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


def match_tiled(a: np.ndarray, b: np.ndarray, matcher: str = "sift", rung: int = 0,
                 tile_size: int = TILE_SIZE, overlap: int = TILE_OVERLAP,
                 min_pool_points: int = MIN_POOL_POINTS,
                 max_offset_px: "float | None" = None,
                 model: str = "homography") -> MatchResult:
    """Tile-then-pool-then-globally-refit matching for rasters too large to hand
    match() whole (an OHRC strip is ~55000x12000px).

    Matching each tile independently and trusting its own per-tile RANSAC fit is
    unsafe on repetitive terrain: a crater tile can lock onto an internally
    consistent but wrong homography one crater-period away from the truth, and
    that tile's own inlier check has no way to catch it (verified in
    tests/test_tiling.py -- individual tiles saw 30-100px error against ground
    truth despite passing their own RANSAC).

    The fix is not per-tile trust, it's pooling: every tile's raw candidate
    matches (both its "inliers" and "outliers" -- the per-tile RANSAC split is
    discarded, not propagated) are collected into one set, and a single global
    MAGSAC homography is fit across the whole image. A tile that locked onto
    the wrong period is now a small minority among the genuinely-correct
    correspondences pooled from every other tile, so it becomes a global
    outlier instead of a locally-confident wrong answer. This is the same
    mechanism tests/test_tiling.py validates directly against ground truth.

    max_offset_px: a georeferencing prior. When a and b were resampled onto one
    common geo grid (pipeline align=True) the metadata-implied registration is
    the identity, so a candidate match whose two points are more than this many
    pixels apart contradicts the metadata by more than the allowed
    georeferencing error and is dropped BEFORE the global fit. Real fits found
    without it landed 2-5 km from the metadata and disagreed with each other
    (docs/research/offset_consistency.json); on repetitive terrain the along-strip
    direction is otherwise unconstrained. None disables the prior.

    model: "homography" (8 DOF, default) or "similarity" (4 DOF: shift, rotation,
    uniform scale). On a common geo grid the residual registration is close to a
    small shift, and real pairs pool only ~1-3% correct candidates among the
    hundreds: a 4-point homography sample is then almost never all-correct, and
    the fit extrapolates km across an 11 km strip; a 2-point similarity sample
    is found orders of magnitude more often and cannot swing that way.
    """
    t0 = time.time()
    tiles_a = tile(a, tile_size, overlap)
    tiles_b = tile(b, tile_size, overlap)

    # Tiles are matched independently of each other (each call only reads its
    # own two tile arrays and the shared, already-built LightGlue model), so
    # running them across a thread pool is safe: OpenCV and PyTorch both
    # release the GIL during their actual C++/tensor compute, so this gets
    # real wall-clock parallelism on multi-core machines, not just concurrency
    # on paper. Results are pooled via `.map()`, which yields in input order
    # regardless of completion order -- output is identical to the sequential
    # version, just faster. Warm the LightGlue model on the main thread first
    # so the one-time construction cost (and its lock) isn't paid mid-pool.
    if matcher == "lightglue":
        import torch
        _get_lightglue_models("cuda" if torch.cuda.is_available() else "cpu")

    # Capped below cpu_count(): OpenCV/BLAS/PyTorch each do their own internal
    # multi-threading per call too, so matching cpu_count() 1:1 here would
    # oversubscribe rather than help. Capped at 4 to avoid melting a laptop
    # on 8+ core machines — the GIL means we only benefit from real cores,
    # and each worker already spawns its own BLAS threads.
    max_workers = min(max(1, (os.cpu_count() or 1) // 2), 4, len(tiles_a)) or 1

    def _match_one(pair):
        (ta, offset_a), (tb, offset_b) = pair
        result = match(ta, tb, matcher=matcher, rung=rung)
        if len(result.pts_a) == 0:
            return None
        pa, pb = untile_points(result.pts_a, offset_a), untile_points(result.pts_b, offset_b)
        sc = result.scores
        if max_offset_px is not None:
            keep = np.linalg.norm(pb - pa, axis=1) <= max_offset_px
            if not keep.any():
                return None
            pa, pb, sc = pa[keep], pb[keep], sc[keep]
        return pa, pb, sc

    pooled = {}  # tile index -> (a_pts, b_pts, scores), keyed by submission order

    # Use submit + as_completed for early exit: once we've accumulated enough
    # candidate matches (>= min_pool_points across all tiles processed so far),
    # skip remaining tiles rather than burning CPU on tiles that won't change
    # the global homography fit. On a 55k×12k OHRC strip this can save 30-60%
    # of wall-clock time when the early tiles already produce abundant matches.
    #
    # Tiles are collected in THREAD-COMPLETION order (as_completed), which is
    # not deterministic run-to-run -- but the final RANSAC fit's result
    # depends on the row order of its input, not just the set of points, so
    # pooling in completion order made the whole pipeline non-reproducible
    # even with a fixed RNG seed (confirmed 2026-09-16: same 429 pooled
    # points, 10/15/17 inliers across 3 reruns of the identical real pair).
    # `pooled` is keyed by each tile's stable submission index so results can
    # be re-sorted back into a fixed order below before the fit ever sees them.
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_match_one, pair): idx
                   for idx, pair in enumerate(zip(tiles_a, tiles_b))}
        from concurrent.futures import as_completed
        for future in as_completed(futures):
            out = future.result()
            if out is None:
                continue
            pooled[futures[future]] = out
            total_pts = sum(len(a_pts) for a_pts, _, _ in pooled.values())
            if total_pts >= min_pool_points:
                # Cancel remaining futures to stop burning CPU
                for f in futures:
                    f.cancel()
                break

    matcher_name = f"{matcher}-rung{rung}-tiled" if matcher == "sift" else f"{matcher}-tiled"
    if not pooled:
        return _empty_result(a, b, matcher_name, time.time() - t0)

    # Sort back into a fixed (submission-index) order -- see the comment
    # above -- so the fit's input array is byte-identical regardless of which
    # order tiles happened to finish in.
    pool_a = [pooled[i][0] for i in sorted(pooled)]
    pool_b = [pooled[i][1] for i in sorted(pooled)]
    pool_scores = [pooled[i][2] for i in sorted(pooled)]

    pts_a = np.vstack(pool_a).astype(np.float32)
    pts_b = np.vstack(pool_b).astype(np.float32)
    scores = np.concatenate(pool_scores).astype(np.float32)

    if len(pts_a) < 4:
        return _empty_result(a, b, matcher_name, time.time() - t0)

    # See _finalize's comment: seed immediately before the fit for a
    # reproducible result. This call runs after the ThreadPoolExecutor block
    # above has fully exited (no concurrent per-tile fits still running), so
    # unlike the per-tile calls inside _finalize, this one's determinism
    # isn't at the mercy of other threads' RNG draws.
    cv2.setRNGSeed(0)
    if model == "similarity":
        affine, ransac_mask = cv2.estimateAffinePartial2D(
            pts_a, pts_b, method=cv2.RANSAC, ransacReprojThreshold=RANSAC_REPROJ_THRESHOLD,
            maxIters=SIMILARITY_MAX_ITERS, confidence=0.999)
        transform = None if affine is None else np.vstack([affine, [0.0, 0.0, 1.0]])
    elif model == "homography":
        transform, ransac_mask = cv2.findHomography(
            pts_a, pts_b, cv2.USAC_MAGSAC, RANSAC_REPROJ_THRESHOLD
        )
    else:
        raise ValueError(f"unknown model: {model!r}")
    if transform is None:
        return _empty_result(a, b, matcher_name, time.time() - t0)

    inlier_mask = ransac_mask.ravel().astype(bool)
    return MatchResult(
        pts_a=pts_a, pts_b=pts_b, scores=scores, inlier_mask=inlier_mask,
        transform=transform.astype(np.float64), matcher=matcher_name,
        shape_a=tuple(a.shape[:2]), shape_b=tuple(b.shape[:2]),
        runtime_s=time.time() - t0,
    )
