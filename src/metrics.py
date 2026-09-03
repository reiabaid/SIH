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
    """Reprojection error of inliers under the fitted transform (`rmse_fitted`),
    and — when a ground-truth homography is supplied, e.g. for a synthetic
    pair with a known answer — the error against that ground truth instead
    (`rmse_ground_truth`, `None` when no ground truth is given).
    """
    inlier_mask = match_result.inlier_mask
    pts_a = match_result.pts_a[inlier_mask]
    pts_b = match_result.pts_b[inlier_mask]

    return {
        "rmse_fitted": _reprojection_rmse(pts_a, pts_b, match_result.transform),
        "rmse_ground_truth": (
            _reprojection_rmse(pts_a, pts_b, gt_transform) if gt_transform is not None else None
        ),
    }


def inlier_stats(match_result: MatchResult) -> dict:
    """How many matches survived RANSAC, and as a fraction of all matches."""
    total = len(match_result.inlier_mask)
    count = int(np.sum(match_result.inlier_mask))
    ratio = count / total if total > 0 else 0.0
    return {"inlier_count": count, "total_matches": total, "inlier_ratio": ratio}


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
