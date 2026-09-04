# src/metrics.py — RMSE, inlier stats, grid coverage for a MatchResult
# Owner: Riddhi

import numpy as np

from src.types import MatchResult


def _reprojection_rmse(pts_a: np.ndarray, pts_b: np.ndarray, transform: np.ndarray) -> float:
    """RMSE of `transform @ pts_a` against `pts_b`, in pixels. NaN if there are
    no points to measure — distinct from 0.0, which would misleadingly read
    as a perfect match rather than "nothing to evaluate".
    """
    if len(pts_a) == 0:
        return float("nan")

    ones = np.ones((len(pts_a), 1), dtype=np.float64)
    homog = np.hstack([pts_a.astype(np.float64), ones])
    projected = (transform @ homog.T).T
    projected = projected[:, :2] / projected[:, 2:3]

    err = np.linalg.norm(projected - pts_b.astype(np.float64), axis=1)
    return float(np.sqrt(np.mean(err ** 2)))


def rmse(match_result: MatchResult, gt_transform: "np.ndarray | None" = None) -> dict:
    """Reprojection error of inliers under the fitted transform (`reprojection_residual`),
    and — when a ground-truth homography is supplied, e.g. for a synthetic
    pair with a known answer — the error against that ground truth instead
    (`rmse_ground_truth`, `None` when no ground truth is given).
    """
    inlier_mask = match_result.inlier_mask
    pts_a = match_result.pts_a[inlier_mask]
    pts_b = match_result.pts_b[inlier_mask]

    return {
        "rmse_ground_truth": (
            _reprojection_rmse(pts_a, pts_b, gt_transform) if gt_transform is not None else None
        ),
        "reprojection_residual": _reprojection_rmse(pts_a, pts_b, match_result.transform),
    }



def inlier_stats(match_result: MatchResult) -> dict:
    """How many matches survived RANSAC, and as a fraction of all matches."""
    total = len(match_result.inlier_mask)
    count = int(np.sum(match_result.inlier_mask))
    ratio = count / total if total > 0 else 0.0
    return {"inlier_count": count, "total_matches": total, "inlier_ratio": ratio}


# A projective homography has 8 degrees of freedom -- exactly 4 point
# correspondences (8 equations) satisfy it with zero reprojection error,
# regardless of whether those points are real matches or coincidental noise.
# A RANSAC fit whose inliers reduce to 4 or fewer *distinct* locations proves
# nothing about registration accuracy, however small reprojection_residual
# comes out -- that low residual is the fit's own construction, not evidence.
# Verified against a real failure: a real CH2 x LRO run reported 8 "inliers"
# (four locations, each duplicated by overlapping tiles) whose own pairwise
# offsets disagreed by hundreds of pixels, yet reprojection_residual was a
# deceptive 0.0066px.
MIN_TRUSTED_INLIER_LOCATIONS = 5


def fit_reliability(match_result: MatchResult, min_unique_inliers: int = MIN_TRUSTED_INLIER_LOCATIONS) -> dict:
    """Whether the inlier set is large enough for reprojection_residual to mean
    anything. See MIN_TRUSTED_INLIER_LOCATIONS for why a trivial fit can report
    a perfect residual while being pure noise.

    Duplicate inlier locations (the same physical keypoint found by more than
    one overlapping tile in match_tiled) are collapsed by rounding to the
    nearest pixel before counting -- they are not independent evidence.
    """
    inliers = match_result.pts_a[match_result.inlier_mask]
    if len(inliers) == 0:
        unique = 0
    else:
        rounded = np.round(inliers).astype(np.int64)
        unique = len(np.unique(rounded, axis=0))

    return {
        "unique_inlier_locations": int(unique),
        "trivial_fit": bool(unique <= 4),
        "well_determined": bool(unique >= min_unique_inliers),
    }


def coverage(match_result: MatchResult, grid: int = 8) -> dict:
    """Divide image A into a `grid` x `grid` grid; using inlier points only,
    count cells containing at least one match. Makes the statement's
    "uniform distribution" requirement measurable: a matcher finding 500
    points in one corner should score badly, and this is how.

    Returns `occupied_fraction` (cells with >=1 inlier, out of grid*grid) and
    `coefficient_of_variation` (std/mean of per-cell inlier counts — low
    means evenly spread, high means bunched up).
    """
    if grid <= 0:
        raise ValueError(f"coverage: grid must be positive (got {grid!r})")

    h, w = match_result.shape_a
    total_cells = grid * grid
    pts = match_result.pts_a[match_result.inlier_mask]

    if len(pts) == 0:
        return {"occupied_fraction": 0.0, "coefficient_of_variation": float("nan")}

    cell_h, cell_w = h / grid, w / grid
    cols = np.clip((pts[:, 0] // cell_w).astype(int), 0, grid - 1)
    rows = np.clip((pts[:, 1] // cell_h).astype(int), 0, grid - 1)
    cell_indices = rows * grid + cols

    counts = np.bincount(cell_indices, minlength=total_cells)
    occupied_fraction = float(np.count_nonzero(counts) / total_cells)

    mean = counts.mean()
    cv = float(counts.std() / mean) if mean > 0 else float("nan")

    return {"occupied_fraction": occupied_fraction, "coefficient_of_variation": cv}
