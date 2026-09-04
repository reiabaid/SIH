# tests/test_premise_test.py — unit tests for premise_test.py calling src.match.match

import os
import numpy as np
import pytest
from PIL import Image

from src.premise_test import match_images, draw_match_result, run_premise_test
from src.types import MatchResult


def _fake_match_result(n_pts=10, n_inliers=8):
    pts_a = np.zeros((n_pts, 2), dtype=np.float32)
    pts_b = np.zeros((n_pts, 2), dtype=np.float32)
    scores = np.ones(n_pts, dtype=np.float32)
    inlier_mask = np.array([True] * n_inliers + [False] * (n_pts - n_inliers))
    return MatchResult(
        pts_a=pts_a,
        pts_b=pts_b,
        scores=scores,
        inlier_mask=inlier_mask,
        transform=np.eye(3),
        matcher="sift-rung0",
        shape_a=(100, 100),
        shape_b=(100, 100),
        runtime_s=0.01,
    )


def test_match_images_invokes_match_pipeline(monkeypatch):
    calls = []

    def fake_match(a, b, matcher="sift", rung=0):
        calls.append((matcher, rung))
        return _fake_match_result()

    monkeypatch.setattr("src.premise_test.match", fake_match)

    img1 = np.full((100, 100), 128, dtype=np.uint8)
    img2 = np.full((100, 100), 128, dtype=np.uint8)

    res = match_images(img1, img2, matcher="sift", rung=0)
    assert len(calls) == 1
    assert calls[0] == ("sift", 0)
    assert isinstance(res, MatchResult)


def test_draw_match_result_generates_valid_image():
    img_a = np.zeros((50, 50), dtype=np.float32)
    img_b = np.zeros((50, 50), dtype=np.float32)

    res_empty = _fake_match_result(n_pts=0, n_inliers=0)
    out_empty = draw_match_result(img_a, img_b, res_empty)
    assert out_empty.shape == (50, 100, 3)

    res_pts = _fake_match_result(n_pts=5, n_inliers=3)
    out_pts = draw_match_result(img_a, img_b, res_pts)
    assert out_pts.shape == (50, 100, 3)


def test_run_premise_test_end_to_end_with_mocked_dem(tmp_path, monkeypatch):
    monkeypatch.setattr("src.premise_test.load_dem_patch", lambda path, r, c, s: (np.zeros((64, 64), dtype=np.float32), 100.0))
    monkeypatch.setattr("src.premise_test.render_hillshade", lambda dem, sp, az, el: np.full((64, 64), 128, dtype=np.uint8))
    monkeypatch.setattr("src.premise_test.match", lambda a, b, matcher="sift", rung=0: _fake_match_result(10, 8))

    res_dict = run_premise_test(dem_path="fake.tiff", out_dir=str(tmp_path))

    assert "azimuths" in res_dict
    assert res_dict["azimuths"] == [0, 15, 30, 60, 120]
    assert res_dict["inlier_counts"] == [8, 8, 8, 8, 8]

    plot_path = tmp_path / "premise_plot.png"
    assert plot_path.exists()
    with Image.open(plot_path) as img:
        img.verify()

