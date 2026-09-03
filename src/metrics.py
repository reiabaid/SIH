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
