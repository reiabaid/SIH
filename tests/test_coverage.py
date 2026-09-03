# tests/test_coverage.py — coverage() against fabricated inlier placements
# with known, hand-checkable answers.

import numpy as np
import pytest

from src.metrics import coverage
from src.types import MatchResult


def _match_result_for_coverage(pts_a, inlier_mask, shape=(80, 80)):
    n = len(pts_a)
    return MatchResult(
        pts_a=np.asarray(pts_a, dtype=np.float32),
        pts_b=np.zeros((n, 2), dtype=np.float32),
        scores=np.ones(n, dtype=np.float32),
        inlier_mask=np.asarray(inlier_mask, dtype=bool),
        transform=np.eye(3, dtype=np.float64),
        matcher="synth",
        shape_a=shape,
        shape_b=shape,
        runtime_s=0.0,
    )


def test_coverage_perfectly_uniform_points_scores_full_marks():
    """80x80 image, grid=8 -> 10x10 cells. One point at the centre of every
    cell: every cell occupied (fraction 1.0) and every count identical
    (coefficient of variation exactly 0.0).
    """
    pts = [(col * 10 + 5, row * 10 + 5) for row in range(8) for col in range(8)]
    mr = _match_result_for_coverage(pts, np.ones(64, dtype=bool))

    result = coverage(mr, grid=8)
    assert result["occupied_fraction"] == pytest.approx(1.0)
    assert result["coefficient_of_variation"] == pytest.approx(0.0, abs=1e-9)


def test_coverage_uniform_with_multiple_points_per_cell_still_scores_zero_cv():
    """Same as the perfectly-uniform test, but 5 points per cell instead of 1
    -- proves the CV calculation is genuinely about *equal counts*, not an
    accident of every count happening to be 1.
    """
    pts = []
    for row in range(8):
        for col in range(8):
            pts.extend([(col * 10 + 5, row * 10 + 5)] * 5)

    mr = _match_result_for_coverage(pts, np.ones(len(pts), dtype=bool))

    result = coverage(mr, grid=8)
    assert result["occupied_fraction"] == pytest.approx(1.0)
    assert result["coefficient_of_variation"] == pytest.approx(0.0, abs=1e-9)


def test_coverage_distinguishes_occupied_fraction_from_coefficient_of_variation():
    """One heavily-loaded cell (10 points) plus exactly 1 point in each of the
    other 63 cells: every cell is occupied (occupied_fraction = 1.0, same as
    the perfectly-uniform case) but the distribution is clearly uneven, so CV
    must be significantly above 0 -- proving the two numbers actually measure
    different things, not the same thing twice.
    """
    pts = [(5.0, 5.0)] * 10  # 10 points in cell (0,0)
    for row in range(8):
        for col in range(8):
            if row == 0 and col == 0:
                continue
            pts.append((col * 10 + 5, row * 10 + 5))  # 1 point in each other cell

    mr = _match_result_for_coverage(pts, np.ones(len(pts), dtype=bool))
    result = coverage(mr, grid=8)

    expected_counts = np.array([10] + [1] * 63)
    expected_cv = expected_counts.std() / expected_counts.mean()

    assert result["occupied_fraction"] == pytest.approx(1.0)
    assert result["coefficient_of_variation"] == pytest.approx(expected_cv)
    assert result["coefficient_of_variation"] > 0.5, "expected a clearly uneven distribution to read as high CV"


def test_coverage_all_points_crammed_in_one_cell_scores_about_one_over_64():
    """The team's own spec example: points crammed in one corner should score
    about 1/64. 64 points, all in cell (0,0) -> occupied_fraction = 1/64
    exactly, and the coefficient of variation is hand-computable: counts are
    [64, 0, 0, ..., 0] (63 zeros), mean=1, variance=(1/64)*(63^2 + 63*1)=63,
    so cv = sqrt(63).
    """
    pts = [(5.0, 5.0)] * 64
    mr = _match_result_for_coverage(pts, np.ones(64, dtype=bool))

    result = coverage(mr, grid=8)
    assert result["occupied_fraction"] == pytest.approx(1.0 / 64.0)
    assert result["coefficient_of_variation"] == pytest.approx(np.sqrt(63))


def test_coverage_uses_only_inliers_ignoring_outliers():
    """60 outlier points spread across 60 different cells (would look
    perfectly uniform if wrongly included) plus 4 real inliers crammed into
    one single cell. Coverage must reflect only the 4 inliers.
    """
    outlier_pts = [(col * 10 + 5, row * 10 + 5) for row in range(8) for col in range(8)][:60]
    inlier_pts = [(75.0, 75.0)] * 4  # all four in cell (7,7)

    pts = np.array(outlier_pts + inlier_pts, dtype=np.float32)
    mask = np.array([False] * 60 + [True] * 4)

    mr = _match_result_for_coverage(pts, mask)

    result = coverage(mr, grid=8)
    assert result["occupied_fraction"] == pytest.approx(1.0 / 64.0)


def test_coverage_no_inliers_among_many_matches():
    pts = [(col * 10 + 5, row * 10 + 5) for row in range(8) for col in range(8)]
    mr = _match_result_for_coverage(pts, np.zeros(64, dtype=bool))  # none are inliers

    result = coverage(mr, grid=8)
    assert result["occupied_fraction"] == pytest.approx(0.0)
    assert np.isnan(result["coefficient_of_variation"])


def test_coverage_of_empty_match_result_is_zero_not_an_error():
    empty = np.zeros((0, 2), dtype=np.float32)
    mr = _match_result_for_coverage(empty, np.zeros(0, dtype=bool))

    result = coverage(mr, grid=8)
    assert result["occupied_fraction"] == pytest.approx(0.0)
    assert np.isnan(result["coefficient_of_variation"])


def test_coverage_clips_points_exactly_on_the_far_boundary_without_crashing():
    """A point exactly at (w, h) floor-divides to col=grid, row=grid --
    out of range for an 8x8 grid unless clipped. This is the same class of
    off-by-one that caused real bugs in Phase 2 (align_pair's grid sizing).
    """
    shape = (80, 80)
    pts = np.array([[0.0, 0.0], [79.9, 79.9], [80.0, 80.0]], dtype=np.float32)
    mr = _match_result_for_coverage(pts, np.ones(3, dtype=bool), shape=shape)

    result = coverage(mr, grid=8)
    assert np.isfinite(result["occupied_fraction"])
    assert np.isfinite(result["coefficient_of_variation"])
    assert result["occupied_fraction"] > 0.0


def test_coverage_respects_a_custom_grid_size():
    """grid=2 over an 80x80 image -> 40x40 cells. One point in each of two of
    the four cells, none in the other two -> occupied_fraction = 0.5, and a
    hand-computable cv: counts=[1,1,0,0], mean=0.5, variance=0.25, cv=1.0.
    """
    pts = [(10.0, 10.0), (50.0, 10.0)]  # cell (0,0) and cell (0,1); (1,0),(1,1) empty
    mr = _match_result_for_coverage(pts, np.ones(2, dtype=bool))

    result = coverage(mr, grid=2)
    assert result["occupied_fraction"] == pytest.approx(0.5)
    assert result["coefficient_of_variation"] == pytest.approx(1.0)


@pytest.mark.parametrize("grid,expected_fraction", [(4, 1 / 16), (8, 1 / 64), (16, 1 / 256)])
def test_coverage_one_point_occupies_one_cell_at_several_grid_sizes(grid, expected_fraction):
    """A single point near the origin lands in cell (0,0) regardless of grid
    size -- occupied_fraction should always be exactly 1/(grid*grid)."""
    pts = [(1.0, 1.0)]
    mr = _match_result_for_coverage(pts, np.ones(1, dtype=bool))

    result = coverage(mr, grid=grid)
    assert result["occupied_fraction"] == pytest.approx(expected_fraction)


def test_coverage_of_a_single_sparse_inlier():
    """One inlier point in an 8x8 grid. Cross-checked against an
    independently constructed counts array (not the function's own code
    path) rather than a hardcoded number.
    """
    pts = [(5.0, 5.0)]
    mr = _match_result_for_coverage(pts, np.ones(1, dtype=bool))

    result = coverage(mr, grid=8)

    expected_counts = np.array([1] + [0] * 63)
    expected_occupied = np.count_nonzero(expected_counts) / 64
    expected_cv = expected_counts.std() / expected_counts.mean()

    assert result["occupied_fraction"] == pytest.approx(expected_occupied)
    assert result["coefficient_of_variation"] == pytest.approx(expected_cv)


def test_coverage_rejects_non_positive_grid():
    mr = _match_result_for_coverage([(5.0, 5.0)], np.ones(1, dtype=bool))

    with pytest.raises(ValueError, match="grid"):
        coverage(mr, grid=0)

    with pytest.raises(ValueError, match="grid"):
        coverage(mr, grid=-2)
