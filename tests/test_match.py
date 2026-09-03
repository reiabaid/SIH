# tests/test_match.py — RMSE against a known ground-truth homography must be sub-pixel.

import numpy as np
import pytest

from src.match import match
from tests.make_synthetic import make_synthetic_pair


def _synthetic_crater_field(size=512, seed=0, n_craters=60):
    """A textured field of crater-like blobs — enough corner/edge structure for SIFT
    to find keypoints on, without needing real lunar imagery yet.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    img = 0.5 + 0.05 * rng.standard_normal((size, size)).astype(np.float32)

    for _ in range(n_craters):
        cx, cy = rng.uniform(0, size, size=2)
        r = rng.uniform(6, 28)
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        rim = np.exp(-((dist - r) ** 2) / (2 * (r * 0.25) ** 2))
        floor = -0.3 * np.clip(1 - dist / r, 0, 1)
        img += 0.4 * rim + floor

    return np.clip(img, 0.0, 1.0).astype(np.float32)


def _true_homography_rmse(pts_a, pts_b, inlier_mask, H_true):
    pts_a_in = pts_a[inlier_mask]
    pts_b_in = pts_b[inlier_mask]
    if len(pts_a_in) == 0:
        return np.inf

    ones = np.ones((len(pts_a_in), 1), dtype=np.float64)
    homog = np.hstack([pts_a_in.astype(np.float64), ones])
    projected = (H_true @ homog.T).T
    projected = projected[:, :2] / projected[:, 2:3]

    err = np.linalg.norm(projected - pts_b_in.astype(np.float64), axis=1)
    return float(np.sqrt(np.mean(err ** 2)))


@pytest.mark.parametrize("matcher", ["sift"])
def test_match_rmse_subpixel_on_synthetic_pair(matcher):
    img = _synthetic_crater_field(size=512, seed=1)
    warped, H_true = make_synthetic_pair(
        img, seed=42, rotation_deg=8.0, scale_range=(0.95, 1.05), translation_frac=0.03
    )

    result = match(img, warped, matcher=matcher)

    assert result.inlier_mask.sum() >= 8, "too few inliers to trust the RMSE"

    rmse = _true_homography_rmse(result.pts_a, result.pts_b, result.inlier_mask, H_true)
    assert rmse < 1.0, f"RMSE against ground truth was {rmse:.3f} px, expected < 1.0"


def test_match_handles_no_overlap_gracefully():
    a = np.zeros((64, 64), dtype=np.float32)
    b = np.ones((64, 64), dtype=np.float32)
    result = match(a, b, matcher="sift")
    assert result.pts_a.shape[0] == result.pts_b.shape[0]
    assert result.transform.shape == (3, 3)
