# tests/test_sweep.py — sweep.py's injectable core tested with fake trial
# functions (no real renderer or matcher needed), the real-pipeline wiring
# tested via monkeypatching (no DEM file exists in this repo to test against
# directly), and the plot validated by an independent library, same pattern
# as scripts/report.py's PNG check in Phase 5.

import numpy as np
import pytest
from PIL import Image

from src.sweep import (
    angular_difference,
    run_sweep,
    run_illumination_sweep,
    make_dem_trial_fn,
    plot_sweep,
    _build_sweep_figure,
)
from src.types import MatchResult


def _match_result(total, inliers):
    """A MatchResult with a chosen total match count and inlier count --
    inlier_stats() is what run_sweep actually reads, so that's all this
    needs to fake convincingly.
    """
    mask = np.array([True] * inliers + [False] * (total - inliers))
    pts = np.zeros((total, 2), dtype=np.float32)
    return MatchResult(
        pts_a=pts, pts_b=pts, scores=np.ones(total, dtype=np.float32),
        inlier_mask=mask, transform=np.eye(3, dtype=np.float64),
        matcher="synth", shape_a=(100, 100), shape_b=(100, 100), runtime_s=0.0,
    )


# ---- angular_difference: circular azimuth arithmetic -------------------------

def test_angular_difference_handles_wraparound_correctly():
    # 350 and 10 are 20 apart, not abs(350-10)=340
    assert angular_difference(350.0, 10.0) == pytest.approx(20.0)
    assert angular_difference(10.0, 350.0) == pytest.approx(20.0)  # symmetric


def test_angular_difference_of_0_and_360_is_zero():
    assert angular_difference(0.0, 360.0) == pytest.approx(0.0)


def test_angular_difference_of_identical_angles_is_zero():
    assert angular_difference(123.4, 123.4) == pytest.approx(0.0)


def test_angular_difference_of_opposite_angles_is_180():
    assert angular_difference(0.0, 180.0) == pytest.approx(180.0)
    assert angular_difference(45.0, 225.0) == pytest.approx(180.0)


@pytest.mark.parametrize("a,b,expected", [
    (0.0, 90.0, 90.0),
    (350.0, 5.0, 15.0),
    (5.0, 350.0, 15.0),
    (720.0, 10.0, 10.0),   # values outside [0,360) still resolve correctly
    (-10.0, 10.0, 20.0),   # negative input
])
def test_angular_difference_parametrized_cases(a, b, expected):
    assert angular_difference(a, b) == pytest.approx(expected)


# ---- run_sweep: the injectable core ------------------------------------------

def test_run_sweep_records_exact_success_rate_and_inlier_count_per_diff():
    known = {0: (100, 95), 30: (100, 40), 90: (100, 2)}

    def trial_fn(diff):
        total, inliers = known[diff]
        return _match_result(total, inliers)

    result = run_sweep(trial_fn, [0, 30, 90])

    assert result["diffs"] == [0, 30, 90]
    assert result["success_rate"] == pytest.approx([0.95, 0.40, 0.02])
    assert result["inlier_count"] == [95, 40, 2]


def test_run_sweep_with_empty_diffs_returns_empty_lists_not_a_crash():
    result = run_sweep(lambda diff: _match_result(10, 5), [])
    assert result == {"diffs": [], "success_rate": [], "inlier_count": []}


def test_run_sweep_with_a_single_diff():
    result = run_sweep(lambda diff: _match_result(10, 7), [45])
    assert result["diffs"] == [45]
    assert result["success_rate"] == pytest.approx([0.7])


@pytest.mark.parametrize("diffs", [range(0, 61, 30), (0, 30, 60), np.array([0, 30, 60])])
def test_run_sweep_accepts_any_iterable_of_diffs(diffs):
    result = run_sweep(lambda diff: _match_result(10, 5), diffs)
    assert len(result["diffs"]) == 3
    assert result["success_rate"] == pytest.approx([0.5, 0.5, 0.5])


def test_run_sweep_handles_a_trial_with_zero_total_matches():
    """inlier_stats' own documented convention: 0/0 -> ratio 0.0, not NaN."""
    result = run_sweep(lambda diff: _match_result(0, 0), [90])
    assert result["success_rate"] == pytest.approx([0.0])
    assert not np.isnan(result["success_rate"][0])


def test_run_sweep_rejects_a_none_diff_with_a_clear_error_before_calling_trial_fn():
    """Missing illumination metadata (e.g. a real Product with
    subsolar_azimuth_deg = None) should fail here, with a message pointing
    at which diff was bad -- not deep inside a renderer or matplotlib.
    """
    calls = []

    def trial_fn(diff):
        calls.append(diff)
        return _match_result(10, 5)

    with pytest.raises(ValueError, match=r"diffs\[1\]"):
        run_sweep(trial_fn, [0.0, None, 30.0])

    assert calls == []  # validated before any trial ran, not partway through


def test_run_sweep_rejects_a_nan_diff():
    with pytest.raises(ValueError, match="finite"):
        run_sweep(lambda diff: _match_result(10, 5), [0.0, float("nan")])


def test_run_sweep_rejects_an_infinite_diff():
    with pytest.raises(ValueError, match="finite"):
        run_sweep(lambda diff: _match_result(10, 5), [float("inf")])


def test_run_sweep_handles_nonzero_matches_with_zero_inliers():
    """Distinct from the 0-total-0-inlier case above: candidate matches were
    found, but none survived RANSAC -- still a clean 0.0, not a crash.
    """
    result = run_sweep(lambda diff: _match_result(50, 0), [90])
    assert result["success_rate"] == pytest.approx([0.0])
    assert result["inlier_count"] == [0]


def test_run_sweep_all_trials_failing_still_produces_a_result_and_a_plot(tmp_path):
    """0/10/20/30 -> every trial fails. run_sweep must not raise, and the
    resulting all-zero data must still plot without a ZeroDivisionError or
    an empty-axes crash.
    """
    result = run_illumination_sweep(
        lambda d: _match_result(20, 0), lambda d: _match_result(20, 0),
        azimuth_diffs=[0, 10, 20, 30], elevation_diffs=[0, 10, 20, 30],
    )
    assert result["azimuth"]["success_rate"] == pytest.approx([0.0, 0.0, 0.0, 0.0])

    output_path = tmp_path / "all_failed.png"
    plot_sweep(result, str(output_path))  # must not raise
    assert output_path.exists()


def test_run_sweep_works_with_non_uniformly_spaced_diffs():
    diffs = [0, 15, 37, 52, 90]  # not an even step
    result = run_sweep(lambda d: _match_result(100, 100 - d), diffs)
    assert result["diffs"] == diffs
    assert result["success_rate"] == pytest.approx([1.0, 0.85, 0.63, 0.48, 0.10])


def test_run_sweep_is_deterministic_given_a_deterministic_trial_fn():
    """run_sweep itself introduces no randomness: same trial_fn, same diffs,
    run twice, gives back-to-back identical results. (Whatever randomness
    match.py's own RANSAC has internally is outside this module's control --
    this only guarantees the orchestration layer doesn't add any of its own,
    e.g. via unseeded ordering or hidden state.)
    """
    def trial_fn(diff):
        rng = np.random.default_rng(int(diff))  # deterministic per-diff, not global state
        n_inliers = int(50 + 10 * np.sin(diff))
        return _match_result(100, max(0, n_inliers))

    diffs = [0, 15, 37, 52, 90]
    first = run_sweep(trial_fn, diffs)
    second = run_sweep(trial_fn, diffs)
    assert first == second


def test_run_sweep_lets_a_trial_fn_exception_propagate():
    def broken_trial_fn(diff):
        raise RuntimeError(f"renderer exploded at diff={diff}")

    # diffs are processed in order, so the exception halts on the first one (0),
    # not silently continuing to try the rest
    with pytest.raises(RuntimeError, match="exploded at diff=0"):
        run_sweep(broken_trial_fn, [0, 30])


def test_run_sweep_success_rate_can_be_non_monotonic_and_is_recorded_as_is():
    """run_sweep doesn't enforce or assume a decreasing trend -- it just
    records whatever the trial function reports, in order.
    """
    known = {0: 0.9, 10: 0.95, 20: 0.3}  # a (contrived) non-monotonic case

    def trial_fn(diff):
        return _match_result(100, int(known[diff] * 100))

    result = run_sweep(trial_fn, [0, 10, 20])
    assert result["success_rate"] == pytest.approx([0.9, 0.95, 0.3])


# ---- run_illumination_sweep: two independent sweeps --------------------------

def test_run_illumination_sweep_keeps_azimuth_and_elevation_independent():
    def azimuth_trial_fn(diff):
        return _match_result(100, 100 - diff)  # linear falloff, distinct pattern

    def elevation_trial_fn(diff):
        return _match_result(100, 100)  # flat -- elevation barely matters

    result = run_illumination_sweep(azimuth_trial_fn, elevation_trial_fn, [0, 10, 20], [0, 45, 90])

    assert result["azimuth"]["diffs"] == [0, 10, 20]
    assert result["azimuth"]["success_rate"] == pytest.approx([1.0, 0.9, 0.8])
    assert result["elevation"]["diffs"] == [0, 45, 90]
    assert result["elevation"]["success_rate"] == pytest.approx([1.0, 1.0, 1.0])


def test_run_illumination_sweep_allows_different_length_diff_lists():
    result = run_illumination_sweep(
        lambda d: _match_result(10, 5), lambda d: _match_result(10, 5),
        azimuth_diffs=[0, 10, 20, 30], elevation_diffs=[0, 90],
    )
    assert len(result["azimuth"]["diffs"]) == 4
    assert len(result["elevation"]["diffs"]) == 2


# ---- make_dem_trial_fn: real-pipeline wiring, verified via monkeypatching ----

def test_make_dem_trial_fn_rejects_an_invalid_vary_argument():
    with pytest.raises(ValueError, match="vary"):
        make_dem_trial_fn("fake.tiff", 0, 0, 512, 30.0, 45.0, vary="bearing")


def test_make_dem_trial_fn_wires_azimuth_perturbation_correctly(monkeypatch):
    calls = []

    def fake_load_dem_patch(path, row_start, col_start, size):
        assert (path, row_start, col_start, size) == ("fake.tiff", 100, 200, 512)
        return np.zeros((512, 512), dtype=np.float32), 240.0

    def fake_render_hillshade(dem, spacing, azimuth_deg, elevation_deg):
        calls.append((azimuth_deg, elevation_deg))
        return np.full((512, 512), 128, dtype=np.uint8)

    def fake_match(a, b, matcher="sift"):
        assert matcher == "lightglue"
        return _match_result(10, 5)

    monkeypatch.setattr("src.render.load_dem_patch", fake_load_dem_patch)
    monkeypatch.setattr("src.render.render_hillshade", fake_render_hillshade)
    monkeypatch.setattr("src.match.match", fake_match)

    trial_fn = make_dem_trial_fn(
        "fake.tiff", 100, 200, 512, base_azimuth=30.0, base_elevation=45.0,
        vary="azimuth", matcher="lightglue",
    )
    # constructing the trial_fn renders the base image once
    assert calls == [(30.0, 45.0)]

    result = trial_fn(15.0)
    assert isinstance(result, MatchResult)
    # base azimuth (30) + diff (15) = 45; elevation stays at the fixed base (45)
    assert calls[-1] == (45.0, 45.0)

    trial_fn(-10.0)
    assert calls[-1] == (20.0, 45.0)  # 30 + (-10)


def test_make_dem_trial_fn_zero_diff_is_the_baseline_case(monkeypatch):
    """diff=0 is the most basic trial: same illumination as the base image.
    Confirms it's treated as an ordinary value, not a special case that
    skips rendering or matching -- azimuth/elevation stay exactly at the
    base angles, and match() still runs normally against two identical
    renders.
    """
    calls = []
    monkeypatch.setattr("src.render.load_dem_patch", lambda *a, **k: (np.zeros((32, 32), dtype=np.float32), 100.0))
    monkeypatch.setattr(
        "src.render.render_hillshade",
        lambda dem, spacing, azimuth_deg, elevation_deg: (calls.append((azimuth_deg, elevation_deg)), np.zeros((32, 32), dtype=np.uint8))[1],
    )
    match_calls = []
    monkeypatch.setattr("src.match.match", lambda a, b, matcher="sift": (match_calls.append((a, b)), _match_result(50, 50))[1])

    trial_fn = make_dem_trial_fn("fake.tiff", 0, 0, 32, base_azimuth=30.0, base_elevation=45.0, vary="azimuth")
    result = trial_fn(0.0)

    assert calls[-1] == (30.0, 45.0)  # unperturbed -- base azimuth + 0
    assert isinstance(result, MatchResult)
    assert len(match_calls) == 1
    np.testing.assert_array_equal(match_calls[0][0], match_calls[0][1])  # same image both sides


def test_make_dem_trial_fn_wires_elevation_perturbation_correctly(monkeypatch):
    calls = []

    monkeypatch.setattr("src.render.load_dem_patch", lambda *a, **k: (np.zeros((64, 64), dtype=np.float32), 100.0))
    monkeypatch.setattr(
        "src.render.render_hillshade",
        lambda dem, spacing, azimuth_deg, elevation_deg: (calls.append((azimuth_deg, elevation_deg)), np.zeros((64, 64), dtype=np.uint8))[1],
    )
    monkeypatch.setattr("src.match.match", lambda a, b, matcher="sift": _match_result(10, 5))

    trial_fn = make_dem_trial_fn("fake.tiff", 0, 0, 64, base_azimuth=0.0, base_elevation=30.0, vary="elevation")
    calls.clear()  # only care about calls made by trial_fn itself, not the base-image render

    trial_fn(20.0)
    assert calls[-1] == (0.0, 50.0)  # azimuth fixed at base (0), elevation 30 + 20


def test_make_dem_trial_fn_only_renders_the_base_image_once(monkeypatch):
    """The base image is computed at construction time and reused across
    every trial_fn(diff) call, not re-rendered each time.
    """
    render_calls = []

    monkeypatch.setattr("src.render.load_dem_patch", lambda *a, **k: (np.zeros((32, 32), dtype=np.float32), 50.0))

    def fake_render_hillshade(dem, spacing, azimuth_deg, elevation_deg):
        render_calls.append((azimuth_deg, elevation_deg))
        return np.zeros((32, 32), dtype=np.uint8)

    monkeypatch.setattr("src.render.render_hillshade", fake_render_hillshade)
    monkeypatch.setattr("src.match.match", lambda a, b, matcher="sift": _match_result(10, 5))

    trial_fn = make_dem_trial_fn("fake.tiff", 0, 0, 32, base_azimuth=10.0, base_elevation=20.0, vary="azimuth")
    assert len(render_calls) == 1  # just the base image

    trial_fn(5.0)
    trial_fn(15.0)
    trial_fn(25.0)
    # base render (1) + one render per trial_fn call (3) = 4, not 6 (no double-rendering the base each time)
    assert len(render_calls) == 4


# ---- plot_sweep ---------------------------------------------------------------

def _fake_sweep_result():
    return {
        "azimuth": {"diffs": [0, 30, 60, 90], "success_rate": [1.0, 0.8, 0.3, 0.05], "inlier_count": [100, 80, 30, 5]},
        "elevation": {"diffs": [0, 30, 60, 90], "success_rate": [1.0, 0.95, 0.9, 0.85], "inlier_count": [100, 95, 90, 85]},
    }


def test_plot_sweep_produces_a_valid_png_openable_by_an_independent_library(tmp_path):
    output_path = tmp_path / "sweep.png"
    plot_sweep(_fake_sweep_result(), str(output_path))

    assert output_path.exists()
    with Image.open(output_path) as img:
        img.verify()

    with Image.open(output_path) as img:
        assert img.width > 0
        assert img.height > 0


def test_plot_sweep_supports_the_inlier_count_metric_too(tmp_path):
    output_path = tmp_path / "sweep_counts.png"
    plot_sweep(_fake_sweep_result(), str(output_path), metric="inlier_count")

    assert output_path.exists()
    with Image.open(output_path) as img:
        img.verify()


def test_plot_sweep_handles_an_empty_sweep_result_without_crashing(tmp_path):
    empty = {
        "azimuth": {"diffs": [], "success_rate": [], "inlier_count": []},
        "elevation": {"diffs": [], "success_rate": [], "inlier_count": []},
    }
    output_path = tmp_path / "empty_sweep.png"
    plot_sweep(empty, str(output_path))  # must not raise

    assert output_path.exists()
    with Image.open(output_path) as img:
        img.verify()


def test_plot_sweep_handles_a_single_point_per_line_without_crashing(tmp_path):
    """Both lines get exactly one (x, y) pair -- checks the plotting code
    doesn't assume there's more than one point to draw a line through.
    """
    single = {
        "azimuth": {"diffs": [0], "success_rate": [1.0], "inlier_count": [100]},
        "elevation": {"diffs": [0], "success_rate": [1.0], "inlier_count": [100]},
    }
    output_path = tmp_path / "single_point.png"
    plot_sweep(single, str(output_path))  # must not raise

    assert output_path.exists()
    with Image.open(output_path) as img:
        img.verify()


def test_full_pipeline_with_a_single_diff_each_end_to_end():
    """run_illumination_sweep -> plot_sweep with azimuth=[0] and
    elevation=[0], the smallest possible real sweep. Exercises the whole
    chain, not just plot_sweep in isolation.
    """
    result = run_illumination_sweep(
        lambda d: _match_result(10, 8), lambda d: _match_result(10, 9),
        azimuth_diffs=[0], elevation_diffs=[0],
    )
    assert result["azimuth"]["success_rate"] == pytest.approx([0.8])
    assert result["elevation"]["success_rate"] == pytest.approx([0.9])

    fig = _build_sweep_figure(result)
    assert len(fig.axes[0].lines[0].get_xdata()) == 1


# ---- plot correctness: inspect the actual artists, not just "a file exists" --

def test_plot_sweep_axes_labels_and_legend_are_correct():
    fig = _build_sweep_figure(_fake_sweep_result())
    ax = fig.axes[0]

    assert "difference" in ax.get_xlabel().lower()
    assert "success rate" in ax.get_ylabel().lower()

    _, labels = ax.get_legend_handles_labels()
    assert any("azimuth" in label.lower() for label in labels)
    assert any("elevation" in label.lower() for label in labels)


def test_plot_sweep_lines_carry_the_correct_data_not_swapped():
    """The strongest check in this file: confirms the azimuth line actually
    plots the azimuth data (not elevation's, or inlier_count instead of
    success_rate) by reading the data back off the Line2D objects
    themselves.
    """
    sweep_result = _fake_sweep_result()
    fig = _build_sweep_figure(sweep_result, metric="success_rate")
    ax = fig.axes[0]

    azimuth_line, elevation_line = ax.lines
    np.testing.assert_array_equal(azimuth_line.get_xdata(), sweep_result["azimuth"]["diffs"])
    np.testing.assert_array_equal(azimuth_line.get_ydata(), sweep_result["azimuth"]["success_rate"])
    np.testing.assert_array_equal(elevation_line.get_xdata(), sweep_result["elevation"]["diffs"])
    np.testing.assert_array_equal(elevation_line.get_ydata(), sweep_result["elevation"]["success_rate"])


def test_plot_sweep_success_rate_values_stay_in_zero_to_one_range():
    """success_rate is a ratio by construction (inlier_stats never returns
    outside [0,1]) -- confirms the plotted y-data reflects that, so no NaN
    or out-of-range value could have snuck in and distorted the axes.
    """
    fig = _build_sweep_figure(_fake_sweep_result(), metric="success_rate")
    for line in fig.axes[0].lines:
        y = line.get_ydata()
        assert np.all(np.isfinite(y))
        assert np.all((y >= 0.0) & (y <= 1.0))


def test_plot_sweep_inlier_count_metric_plots_counts_not_ratios():
    sweep_result = _fake_sweep_result()
    fig = _build_sweep_figure(sweep_result, metric="inlier_count")
    azimuth_line = fig.axes[0].lines[0]
    np.testing.assert_array_equal(azimuth_line.get_ydata(), sweep_result["azimuth"]["inlier_count"])
