# tests/test_report.py — scripts/report.py against fabricated MatchResults.
# No real matcher or imagery; the overlay/metrics files are checked directly.

import json
import os

import cv2
import numpy as np
import pytest
from PIL import Image

from scripts.report import GAP_PX, INLIER_COLOR, OUTLIER_COLOR, _json_safe, render_overlay, write_report
from src.types import MatchResult


def _match_result(pts_a, pts_b, inlier_mask, shape_a=(40, 50), shape_b=(40, 50), transform=None):
    n = len(pts_a)
    return MatchResult(
        pts_a=np.asarray(pts_a, dtype=np.float32),
        pts_b=np.asarray(pts_b, dtype=np.float32),
        scores=np.ones(n, dtype=np.float32),
        inlier_mask=np.asarray(inlier_mask, dtype=bool),
        transform=(transform if transform is not None else np.eye(3)).astype(np.float64),
        matcher="synth",
        shape_a=shape_a,
        shape_b=shape_b,
        runtime_s=0.0,
    )


def _flat_gray(shape, value=0.5):
    return np.full(shape, value, dtype=np.float32)


# ---- render_overlay ---------------------------------------------------------

def test_render_overlay_has_the_correct_combined_shape_for_mismatched_image_sizes():
    image_a = _flat_gray((40, 50))
    image_b = _flat_gray((30, 70))
    mr = _match_result([[5, 5]], [[5, 5]], [True], shape_a=(40, 50), shape_b=(30, 70))

    overlay = render_overlay(image_a, image_b, mr)

    assert overlay.shape == (max(40, 30), 50 + GAP_PX + 70, 3)
    assert overlay.dtype == np.uint8


def test_render_overlay_with_no_matches_leaves_a_blank_side_by_side_canvas():
    image_a = _flat_gray((40, 50), value=0.2)
    image_b = _flat_gray((40, 50), value=0.8)
    empty = np.zeros((0, 2), dtype=np.float32)
    mr = _match_result(empty, empty, np.zeros(0, dtype=bool), shape_a=(40, 50), shape_b=(40, 50))

    overlay = render_overlay(image_a, image_b, mr)

    expected_a = int(round(0.2 * 255))
    expected_b = int(round(0.8 * 255))
    assert np.all(overlay[:, :50] == expected_a)
    assert np.all(overlay[:, 50 + GAP_PX:] == expected_b)


def test_render_overlay_colors_inliers_and_outliers_differently():
    image_a = _flat_gray((40, 50))
    image_b = _flat_gray((40, 50))
    pts_a = [[10, 10], [30, 30]]
    pts_b = [[10, 10], [30, 30]]
    mr = _match_result(pts_a, pts_b, [True, False], shape_a=(40, 50), shape_b=(40, 50))

    overlay = render_overlay(image_a, image_b, mr)

    assert tuple(overlay[10, 10]) == INLIER_COLOR
    assert tuple(overlay[30, 30]) == OUTLIER_COLOR


def test_render_overlay_handles_points_outside_image_bounds_without_crashing():
    image_a = _flat_gray((40, 50))
    image_b = _flat_gray((40, 50))
    pts_a = [[-5, -5], [1000, 1000]]
    pts_b = [[-5, -5], [1000, 1000]]
    mr = _match_result(pts_a, pts_b, [True, False], shape_a=(40, 50), shape_b=(40, 50))

    overlay = render_overlay(image_a, image_b, mr)  # should not raise

    assert overlay.shape == (40, 50 + GAP_PX + 50, 3)


def test_render_overlay_colors_every_point_correctly_at_a_realistic_inlier_outlier_mix():
    """3 inliers and 2 outliers, spread far enough apart to check each point's
    own drawn colour individually -- stronger than checking that both
    colours merely exist somewhere in the image.
    """
    image_a = _flat_gray((80, 80))
    image_b = _flat_gray((80, 80))
    pts_a = [[5, 5], [20, 20], [35, 35], [50, 50], [65, 65]]
    mask = [True, True, True, False, False]  # 3 inliers, 2 outliers
    mr = _match_result(pts_a, pts_a, mask, shape_a=(80, 80), shape_b=(80, 80))

    overlay = render_overlay(image_a, image_b, mr)

    for (x, y), is_inlier in zip(pts_a, mask):
        expected = INLIER_COLOR if is_inlier else OUTLIER_COLOR
        assert tuple(overlay[y, x]) == expected


# ---- write_report / metrics JSON --------------------------------------------

def test_write_report_creates_a_nested_output_directory(tmp_path):
    image_a = _flat_gray((20, 20))
    image_b = _flat_gray((20, 20))
    mr = _match_result([[5, 5]], [[5, 5]], [True], shape_a=(20, 20), shape_b=(20, 20))

    output_dir = tmp_path / "nested" / "does" / "not" / "exist"
    write_report(image_a, image_b, mr, str(output_dir))

    assert (output_dir / "overlay.png").exists()
    assert (output_dir / "metrics.json").exists()

    saved = cv2.imread(str(output_dir / "overlay.png"))
    assert saved.shape == (20, 20 + GAP_PX + 20, 3)


def test_write_report_produces_exactly_the_two_expected_filenames(tmp_path):
    """Checks the directory listing directly, not just that each file we
    expect happens to exist -- catches an accidental third file or a typo'd
    name that a file-exists check alone could miss.
    """
    image_a = _flat_gray((20, 20))
    image_b = _flat_gray((20, 20))
    mr = _match_result([[5, 5]], [[5, 5]], [True], shape_a=(20, 20), shape_b=(20, 20))

    output_dir = tmp_path / "run1"
    write_report(image_a, image_b, mr, str(output_dir))

    assert set(os.listdir(output_dir)) == {"overlay.png", "metrics.json"}


def test_write_report_overlay_png_is_a_valid_image_openable_by_an_independent_library(tmp_path):
    """Proves the file is a real, uncorrupted image -- not just that
    cv2.imwrite returned without error and a file of some size exists.
    Deliberately uses PIL rather than cv2 to read it back, since a bug that
    corrupts the file in a way cv2 happens to tolerate could still break
    every other PNG reader (or member 6's browser-based viewer).
    """
    image_a = _flat_gray((30, 40))
    image_b = _flat_gray((30, 40))
    mr = _match_result([[5, 5]], [[5, 5]], [True], shape_a=(30, 40), shape_b=(30, 40))

    output_dir = tmp_path / "report"
    write_report(image_a, image_b, mr, str(output_dir))

    with Image.open(output_dir / "overlay.png") as img:
        img.verify()  # raises if the file is truncated/corrupted

    with Image.open(output_dir / "overlay.png") as img:
        assert img.width == 40 + GAP_PX + 40
        assert img.height == 30


def test_write_report_json_has_no_bare_nan_tokens_for_an_empty_match_result(tmp_path):
    """Both rmse and coverage produce NaN for an empty MatchResult -- if that
    NaN reaches the JSON file as a bare token, a strict parser (e.g. plain
    JS JSON.parse, which member 6's viewer will use) would fail to load it.
    """
    image_a = _flat_gray((20, 20))
    image_b = _flat_gray((20, 20))
    empty = np.zeros((0, 2), dtype=np.float32)
    mr = _match_result(empty, empty, np.zeros(0, dtype=bool), shape_a=(20, 20), shape_b=(20, 20))

    output_dir = tmp_path / "report"
    write_report(image_a, image_b, mr, str(output_dir))

    raw_text = (output_dir / "metrics.json").read_text()
    assert "NaN" not in raw_text

    loaded = json.loads(raw_text)  # must not raise
    assert loaded["reprojection_residual"] is None
    assert loaded["coefficient_of_variation"] is None
    assert loaded["inlier_ratio"] == 0.0  # inlier_stats' own empty convention is 0.0, not NaN


def test_write_report_returned_metrics_match_the_written_file(tmp_path):
    image_a = _flat_gray((80, 80))
    image_b = _flat_gray((80, 80))
    pts_a = [[5, 5], [15, 5], [5, 15], [15, 15]]
    mr = _match_result(pts_a, pts_a, [True, True, True, True], shape_a=(80, 80), shape_b=(80, 80))

    output_dir = tmp_path / "report"
    returned = write_report(image_a, image_b, mr, str(output_dir))

    loaded = json.loads((output_dir / "metrics.json").read_text())

    assert loaded["reprojection_residual"] == pytest.approx(returned["reprojection_residual"])
    assert loaded["inlier_count"] == returned["inlier_count"]
    assert loaded["occupied_fraction"] == pytest.approx(returned["occupied_fraction"])


def test_write_report_overwrites_a_previous_report_in_the_same_directory(tmp_path):
    image_a = _flat_gray((20, 20))
    image_b = _flat_gray((20, 20))
    output_dir = tmp_path / "report"

    mr_first = _match_result([[1, 1]] * 5, [[1, 1]] * 5, [True] * 5, shape_a=(20, 20), shape_b=(20, 20))
    write_report(image_a, image_b, mr_first, str(output_dir))

    mr_second = _match_result([[1, 1]] * 2, [[1, 1]] * 2, [False, False], shape_a=(20, 20), shape_b=(20, 20))
    second_metrics = write_report(image_a, image_b, mr_second, str(output_dir))

    loaded = json.loads((output_dir / "metrics.json").read_text())
    assert loaded["inlier_count"] == 0
    assert loaded["total_matches"] == 2
    assert second_metrics["total_matches"] == 2


# ---- _json_safe --------------------------------------------------------------

def test_json_safe_replaces_nested_nan_with_none():
    payload = {"a": float("nan"), "b": [1.0, float("nan"), {"c": float("nan")}], "d": 3.0, "e": None}
    result = _json_safe(payload)

    assert result == {"a": None, "b": [1.0, None, {"c": None}], "d": 3.0, "e": None}
    json.dumps(result)  # must not raise, and must not contain a bare NaN token
    assert "NaN" not in json.dumps(result)
