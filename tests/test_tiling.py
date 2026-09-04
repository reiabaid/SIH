# tests/test_tiling.py — tests for keypoint grid-balancing and tile-based
# matching on repetitive lunar crater terrain
# Owner: Riddhi

import numpy as np
import cv2
import pytest

from src.match import grid_balance_keypoints, GRID_SIZE, MAX_KEYPOINTS_PER_CELL, match
from src.prep import tile, untile_points
from src.types import MatchResult
from tests.make_synthetic import make_synthetic_pair


def test_grid_balance_keypoints_caps_dense_clusters_on_repetitive_crater_features():
    """Simulate a high-contrast crater rim generating 200 keypoints in a single grid cell
    and sparse keypoints elsewhere. grid_balance_keypoints must cap the dense cell to
    MAX_KEYPOINTS_PER_CELL (40).
    """
    shape = (512, 512)
    keypoints = []
    descriptors = []

    # Dense cluster in top-left cell (y in 0..64, x in 0..64)
    for i in range(200):
        kp = cv2.KeyPoint(x=float(np.random.uniform(5, 55)), y=float(np.random.uniform(5, 55)), size=5, response=float(100 + i))
        keypoints.append(kp)
        descriptors.append(np.full(128, i, dtype=np.float32))

    # Sparse keypoints in another cell (bottom-right cell, y in 450..500, x in 450..500)
    for i in range(10):
        kp = cv2.KeyPoint(x=float(np.random.uniform(450, 500)), y=float(np.random.uniform(450, 500)), size=5, response=float(50 + i))
        keypoints.append(kp)
        descriptors.append(np.full(128, 200 + i, dtype=np.float32))

    descriptors = np.array(descriptors, dtype=np.float32)

    kept_kps, kept_descs = grid_balance_keypoints(keypoints, descriptors, shape, grid=GRID_SIZE, cap=MAX_KEYPOINTS_PER_CELL)

    # Top-left cell capped at 40 + bottom-right cell 10 = 50 total kept
    assert len(kept_kps) == 50
    assert len(kept_descs) == 50

    # Count points in top-left cell (0..64 px)
    top_left_count = sum(1 for kp in kept_kps if kp.pt[0] < 64 and kp.pt[1] < 64)
    assert top_left_count == MAX_KEYPOINTS_PER_CELL


def test_grid_balance_keypoints_preserves_highest_response_features_in_each_cell():
    shape = (256, 256)
    keypoints = [
        cv2.KeyPoint(x=10, y=10, size=5, response=10.0),
        cv2.KeyPoint(x=15, y=15, size=5, response=100.0),
        cv2.KeyPoint(x=20, y=20, size=5, response=50.0),
    ]
    descriptors = np.array([[1], [2], [3]], dtype=np.float32)

    kept_kps, kept_descs = grid_balance_keypoints(keypoints, descriptors, shape, grid=8, cap=2)

    assert len(kept_kps) == 2
    # Kept highest responses: 100.0 (index 1) and 50.0 (index 2)
    assert [kp.response for kp in kept_kps] == [100.0, 50.0]
    np.testing.assert_array_equal(kept_descs, [[2], [3]])


def _repetitive_crater_field(size, seed, spacing=48, crater_r=14):
    """Deliberately adversarial: the SAME crater shape stamped at a regular
    grid across the whole canvas. Real lunar terrain is never this perfectly
    self-similar, but that's exactly what makes it a good stress test for
    "does tiling produce wild matches on repetitive terrain" -- a real crater
    field would only be an easier case than this.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    img = 0.5 + 0.03 * rng.standard_normal((size, size)).astype(np.float32)
    for cy in range(spacing // 2, size, spacing):
        for cx in range(spacing // 2, size, spacing):
            dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
            rim = np.exp(-((dist - crater_r) ** 2) / (2 * (crater_r * 0.3) ** 2))
            floor = -0.3 * np.clip(1 - dist / crater_r, 0, 1)
            img += 0.5 * rim + floor
    return np.clip(img, 0.0, 1.0).astype(np.float32)


def test_tiling_on_repetitive_terrain_does_not_produce_wild_matches_after_pooling():
    """The real "no wild matches on repetitive terrain" property, tested
    against the actual prep.tile()/untile_points() functions and the actual
    matcher -- not grid_balance_keypoints, which is a different mechanism.

    Investigated honestly first: individual tiles matched independently
    *can* lock onto an internally-consistent but wrong homography on this
    deliberately repetitive field (the periodic crater spacing creates real
    ambiguity -- a crater in one tile legitimately looks identical to its
    neighbour one period away). Checked directly: several tiles produced
    30-100px reprojection error against ground truth despite RANSAC
    accepting them as "inliers" within that tile alone.

    But the project's own documented architecture is "tile it, match tiles,
    pool the correspondences" (see prep.py's docstring and the build-plan
    doc) -- not trust each tile's own separate homography. Pooling every
    tile's raw candidate matches into one global RANSAC fit is what this
    test actually verifies, and it is what makes the wild per-tile matches
    disappear: they become a minority of outliers once the majority of
    genuinely-correct correspondences from other tiles are pooled alongside
    them.
    """
    size = 512
    img = _repetitive_crater_field(size, seed=1)
    warped, H_true = make_synthetic_pair(
        img, seed=99, rotation_deg=2.0, scale_range=(0.99, 1.01), translation_frac=0.01
    )

    tile_size, overlap = 160, 32
    tiles_a = tile(img, tile_size, overlap)
    tiles_b = tile(warped, tile_size, overlap)
    assert len(tiles_a) == len(tiles_b) and len(tiles_a) > 1

    pool_a, pool_b = [], []
    for (ta, offset_a), (tb, offset_b) in zip(tiles_a, tiles_b):
        result = match(ta, tb, matcher="sift", rung=0)
        if len(result.pts_a) == 0:
            continue
        pool_a.append(untile_points(result.pts_a, offset_a))
        pool_b.append(untile_points(result.pts_b, offset_b))

    pool_a = np.vstack(pool_a)
    pool_b = np.vstack(pool_b)
    assert len(pool_a) >= 50, "too few pooled candidates to trust the result"

    transform, ransac_mask = cv2.findHomography(pool_a, pool_b, cv2.USAC_MAGSAC, 1.5)
    assert transform is not None
    inlier_mask = ransac_mask.ravel().astype(bool)
    assert inlier_mask.sum() >= 20, "too few global inliers survived pooling"

    inliers_a, inliers_b = pool_a[inlier_mask], pool_b[inlier_mask]
    ones = np.ones((len(inliers_a), 1))
    homog = np.hstack([inliers_a.astype(np.float64), ones])
    projected = (H_true @ homog.T).T
    projected = projected[:, :2] / projected[:, 2:3]
    err = np.linalg.norm(projected - inliers_b.astype(np.float64), axis=1)

    assert err.mean() < 1.5, f"pooled reprojection error was {err.mean():.2f}px on average -- a wild match survived"
    assert err.max() < 3.0, f"worst pooled reprojection error was {err.max():.2f}px -- a wild match survived"


def test_untile_points_correctly_maps_tile_local_to_global_coordinates():
    """A focused unit check on untile_points itself, independent of any
    matcher: a point at tile-local (5, 10) in a tile whose offset is
    (row=100, col=200) must land at global (col=205, row=110) -- pts are
    (x, y) i.e. (col, row), per untile_points' own documented convention.
    """
    pts = np.array([[5.0, 10.0], [0.0, 0.0]], dtype=np.float32)
    global_pts = untile_points(pts, offset=(100, 200))  # (row_offset, col_offset)

    expected = np.array([[205.0, 110.0], [200.0, 100.0]], dtype=np.float32)
    np.testing.assert_array_almost_equal(global_pts, expected)
