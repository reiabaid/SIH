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


def test_lightglue_matcher_finds_real_correspondences():
    """Regression test for a normalization bug found 2026-09-04: match()'s own
    contract hands _match_lightglue a 0..1 float image, but LightGlue's
    numpy_image_to_torch unconditionally divides by 255 again internally --
    silently crushing every image to near-black (max ~0.004) and making
    SuperPoint find zero keypoints, always, regardless of image content.
    This test would have caught it immediately; nothing before this
    exercised matcher="lightglue" at all (only "sift" was parametrized
    above), which is exactly how the bug went unnoticed.
    """
    img = _synthetic_crater_field(size=256, seed=4)
    warped, H_true = make_synthetic_pair(
        img, seed=13, rotation_deg=5.0, scale_range=(0.97, 1.03), translation_frac=0.02
    )

    result = match(img, warped, matcher="lightglue")

    assert result.inlier_mask.sum() >= 8, "too few inliers -- did the normalization bug come back?"
    rmse = _true_homography_rmse(result.pts_a, result.pts_b, result.inlier_mask, H_true)
    assert rmse < 1.0, f"lightglue RMSE against ground truth was {rmse:.3f} px, expected < 1.0"


def test_match_handles_no_overlap_gracefully():
    a = np.zeros((64, 64), dtype=np.float32)
    b = np.ones((64, 64), dtype=np.float32)
    result = match(a, b, matcher="sift")
    assert result.pts_a.shape[0] == result.pts_b.shape[0]
    assert result.transform.shape == (3, 3)


def test_rung1_beats_rung0_under_illumination_flip():
    """The premise this whole approach rests on: when gradient direction reverses
    180 degrees (photometric inversion, standing in for a full sun-angle flip),
    plain SIFT (rung 0) should lose most of its matches, while the mod-pi
    orientation descriptor (rung 1) should hold onto meaningfully more of them.
    """
    img = _synthetic_crater_field(size=512, seed=2)
    warped, H_true = make_synthetic_pair(
        img, seed=7, rotation_deg=5.0, scale_range=(0.97, 1.03), translation_frac=0.02
    )
    warped_inverted = 1.0 - warped  # exact 180-degree gradient reversal everywhere

    result_rung0 = match(img, warped_inverted, matcher="sift", rung=0)
    result_rung1 = match(img, warped_inverted, matcher="sift", rung=1)

    inliers_0 = int(result_rung0.inlier_mask.sum())
    inliers_1 = int(result_rung1.inlier_mask.sum())

    assert inliers_1 > inliers_0, (
        f"expected rung 1 to beat rung 0 under an illumination flip, "
        f"got rung0={inliers_0} inliers, rung1={inliers_1} inliers"
    )
    assert inliers_1 >= 8, f"rung 1 only found {inliers_1} inliers under the flip — too few to be useful"


def test_subpixel_rmse_holds_under_illumination_flip():
    """Sub-pixel accuracy must survive an illumination flip, not just match count.

    The earlier flip test above only checks inlier *count* (measured before sub-pixel
    refinement), so it could not catch the refine silently switching off under inverted
    contrast. This asserts the recovered *position* stays sub-pixel against ground truth
    under the flip — which guards the statement's non-negotiable sub-pixel requirement
    in exactly the illumination condition the project targets.
    """
    img = _synthetic_crater_field(size=512, seed=3)
    warped, H_true = make_synthetic_pair(
        img, seed=11, rotation_deg=5.0, scale_range=(0.97, 1.03), translation_frac=0.02
    )
    warped_inverted = 1.0 - warped

    result = match(img, warped_inverted, matcher="sift", rung=1)

    assert result.inlier_mask.sum() >= 8, "too few inliers to trust the RMSE under flip"
    rmse = _true_homography_rmse(result.pts_a, result.pts_b, result.inlier_mask, H_true)
    assert rmse < 1.0, f"sub-pixel RMSE under illumination flip was {rmse:.3f} px, expected < 1.0"


def test_pipeline_exposes_rung_and_lcn_toggle():
    """pipeline.run_pipeline must pass `rung` through and let LCN be turned off, so the
    four-cell ablation (raw / +LCN / +modpi / +both) is runnable through the pipeline
    rather than only by calling match() directly.
    """
    from src.types import Product
    from src.pipeline import run_pipeline

    img = _synthetic_crater_field(size=256, seed=5)
    warped, _ = make_synthetic_pair(
        img, seed=9, rotation_deg=4.0, scale_range=(0.98, 1.02), translation_frac=0.02
    )

    def _product(arr, pid):
        return Product(array=arr, gsd_m=1.0, corners={}, source="SYNTH", product_id=pid)

    out = run_pipeline(_product(img, "a"), _product(warped, "b"),
                       matcher="sift", rung=1, use_lcn=False)

    # rung reached match() (the matcher name encodes it) and the toggle was recorded
    assert out["match_result"]["matcher"] == "sift-rung1"
    assert out["config"] == {"matcher": "sift", "rung": 1, "use_lcn": False, "align": False}


# ---- match_tiled: pool-then-globally-refit matching for large rasters ----

def test_match_tiled_recovers_correct_registration_on_repetitive_terrain():
    """match_tiled must show the same "wild per-tile matches disappear once
    pooled into one global RANSAC fit" property tests/test_tiling.py verifies
    by hand-rolling the tile loop -- this checks match_tiled's own public
    function does it end to end, on the same deliberately-adversarial
    repeating crater field.
    """
    from src.match import match_tiled
    from tests.test_tiling import _repetitive_crater_field

    size = 512
    img = _repetitive_crater_field(size, seed=1)
    warped, H_true = make_synthetic_pair(
        img, seed=99, rotation_deg=2.0, scale_range=(0.99, 1.01), translation_frac=0.01
    )

    result = match_tiled(img, warped, matcher="sift", rung=0, tile_size=160, overlap=32)

    assert result.matcher == "sift-rung0-tiled"
    assert result.shape_a == img.shape and result.shape_b == warped.shape
    assert result.inlier_mask.sum() >= 20

    rmse = _true_homography_rmse(result.pts_a, result.pts_b, result.inlier_mask, H_true)
    assert rmse < 1.5, f"pooled RMSE against ground truth was {rmse:.2f}px -- a wild match survived"


def test_match_tiled_returns_empty_result_gracefully_on_featureless_input():
    from src.match import match_tiled

    blank_a = np.full((256, 256), 0.5, dtype=np.float32)
    blank_b = np.full((256, 256), 0.5, dtype=np.float32)

    result = match_tiled(blank_a, blank_b, tile_size=128, overlap=16)

    assert result.matcher == "sift-rung0-tiled"
    assert len(result.pts_a) == 0
    assert len(result.inlier_mask) == 0
    np.testing.assert_array_equal(result.transform, np.eye(3))


def test_pipeline_align_true_returns_points_in_each_products_own_pixel_space():
    """With align=True, run_pipeline must invert match points out of align_pair's
    shared working grid back into each product's own original raster frame
    before returning them -- what cnet.py (Sample/Line) and a registered-raster
    export against the untouched source image both need. Set up a pair with a
    real GSD mismatch (a hi-res product and a 4x coarser downsample of it, same
    footprint) so the aligned working grid is a different size than either
    product's own array; if inversion weren't happening, pts_a would come back
    sized to the small aligned grid instead of product_a's real, larger frame.
    """
    import cv2
    from src.types import Product
    from src.pipeline import run_pipeline
    from src.geo import _meters_per_degree

    size_hi = 256
    factor = 4
    hi_img = _synthetic_crater_field(size=size_hi, seed=21)
    lo_img = cv2.resize(hi_img, (size_hi // factor, size_hi // factor), interpolation=cv2.INTER_AREA)

    lat0, lat1, lon0, lon1 = 0.0, 1.0, 0.0, 1.0
    m_per_deg_lat, _ = _meters_per_degree((lat0 + lat1) / 2.0)
    gsd_hi = (lat1 - lat0) / (size_hi - 1) * m_per_deg_lat
    gsd_lo = (lat1 - lat0) / (size_hi // factor - 1) * m_per_deg_lat
    corners = {"ul": (lat1, lon0), "ur": (lat1, lon1), "ll": (lat0, lon0), "lr": (lat0, lon1)}

    product_a = Product(array=hi_img, gsd_m=gsd_hi, corners=dict(corners), source="SYNTH", product_id="a")
    product_b = Product(array=lo_img, gsd_m=gsd_lo, corners=dict(corners), source="SYNTH", product_id="b")

    out = run_pipeline(product_a, product_b, matcher="sift", rung=0, use_lcn=False, align=True)
    match_result = out["match_result"]

    assert len(match_result["pts_a"]) > 0, "need at least some matches for this check to mean anything"
    # aligned working grid is ~64px (coarser GSD wins); a correctly-inverted pts_a
    # must reach well past that, back out in product_a's own ~256px frame.
    assert match_result["pts_a"][:, 0].max() > 100
    assert match_result["pts_a"][:, 1].max() > 100
    # shape_a/shape_b must follow pts_a/pts_b into original-pixel space too --
    # a downstream consumer like metrics.coverage grids by shape_a, and would
    # silently measure the wrong frame if shape stayed at the aligned grid's size.
    assert tuple(match_result["shape_a"]) == product_a.array.shape
    assert tuple(match_result["shape_b"]) == product_b.array.shape

    # match_result["transform"] was fit on the *aligned* grid (A_px -> B_px there);
    # pipeline.py must re-compose it into original-pixel space alongside the points,
    # or reprojecting an inlier through it against pts_b lands nowhere close --
    # this caught a real bug where the transform was left stale (thousands of px
    # of "error" on points RANSAC had just classified as inliers).
    from src.metrics import rmse as _rmse
    from src.types import MatchResult as _MatchResult
    mr_obj = _MatchResult(
        pts_a=match_result["pts_a"], pts_b=match_result["pts_b"], scores=match_result["scores"],
        inlier_mask=match_result["inlier_mask"], transform=match_result["transform"],
        matcher=match_result["matcher"], shape_a=match_result["shape_a"],
        shape_b=match_result["shape_b"], runtime_s=match_result["runtime_s"],
    )
    residual = _rmse(mr_obj)["reprojection_residual"]
    assert residual < 5.0, (
        f"reprojection residual against the (re-composed) transform was {residual:.1f}px "
        "-- transform is stale relative to the inverted points"
    )
