# tests/test_sweep_extended.py — real verification that sun-azimuth rotation
# degrades matching faster than sun-elevation change, using the actual
# renderer and matcher, not a fake trial function with the conclusion
# hardcoded into it.
# Owner: Riddhi
#
# The first version of this file's two tests constructed trial_fn(diff)
# closures that computed `inliers = 100 - diff * 0.9` (azimuth) vs
# `100 - diff * 0.15` (elevation) directly, then asserted that exact
# hardcoded difference came back out of run_sweep. That only proves
# run_sweep's plumbing works -- already covered by tests/test_sweep.py --
# not anything about the matcher's actual illumination sensitivity, which is
# the scientific claim this project rests on. This version renders real
# images from a real (synthetic, since no DEM file is committed) heightmap
# and runs the real SIFT matcher on them.

import numpy as np

from src.sweep import make_synthetic_dem, run_illumination_sweep
from src.render import render_hillshade
from src.match import match


def _make_trial_fn(dem, spacing, base_azimuth, base_elevation, base_img, vary):
    def trial_fn(diff):
        if vary == "azimuth":
            az, el = base_azimuth + diff, base_elevation
        else:
            az, el = base_azimuth, base_elevation + diff
        test_img = render_hillshade(dem, spacing, az, el).astype(np.float32) / 255.0
        return match(base_img, test_img, matcher="sift", rung=0)
    return trial_fn


def test_azimuth_rotation_degrades_matching_faster_than_elevation_change():
    """The scientific claim itself, against a real render + a real matcher:
    azimuth changes shadow *direction* (catastrophic for SIFT), elevation
    changes shadow *length*/brightness (milder). Empirically confirmed
    before writing this assertion (not assumed): at a 30-degree difference,
    azimuth collapsed to 11 inliers while elevation only dropped to 35,
    from an identical 205-inlier baseline.
    """
    dem = make_synthetic_dem(size=256, seed=42, n_craters=40, rim_height=20.0)
    spacing = 1.0
    base_azimuth, base_elevation = 0.0, 30.0
    base_img = render_hillshade(dem, spacing, base_azimuth, base_elevation).astype(np.float32) / 255.0
    diffs = [0, 10, 20, 30]

    result = run_illumination_sweep(
        _make_trial_fn(dem, spacing, base_azimuth, base_elevation, base_img, "azimuth"),
        _make_trial_fn(dem, spacing, base_azimuth, base_elevation, base_img, "elevation"),
        diffs, diffs,
    )

    az_inliers = result["azimuth"]["inlier_count"]
    el_inliers = result["elevation"]["inlier_count"]

    assert az_inliers[0] == el_inliers[0], "diff=0 must be an identical self-match baseline for both curves"
    assert az_inliers[0] > 100, "baseline self-match should find plenty of inliers -- if not, the terrain/renderer is broken"

    # the total inliers lost across the whole sweep (not just the single
    # largest-diff point, which could be noisy) should be clearly larger
    # for azimuth than for elevation
    az_loss = az_inliers[0] - az_inliers[-1]
    el_loss = el_inliers[0] - el_inliers[-1]
    assert az_loss > el_loss, (
        f"expected azimuth rotation to lose more inliers than elevation change over the same "
        f"range, got az_loss={az_loss} ({az_inliers}) vs el_loss={el_loss} ({el_inliers})"
    )


def test_azimuth_and_elevation_start_from_the_same_baseline_but_diverge():
    """A slightly different framing of the same claim: the two curves must
    start identical (diff=0 is diff=0 regardless of which axis you call it)
    and end up clearly apart, not just numerically different at one point.
    """
    dem = make_synthetic_dem(size=256, seed=7, n_craters=40, rim_height=20.0)
    spacing = 1.0
    base_azimuth, base_elevation = 15.0, 25.0
    base_img = render_hillshade(dem, spacing, base_azimuth, base_elevation).astype(np.float32) / 255.0
    diffs = [0, 30]

    result = run_illumination_sweep(
        _make_trial_fn(dem, spacing, base_azimuth, base_elevation, base_img, "azimuth"),
        _make_trial_fn(dem, spacing, base_azimuth, base_elevation, base_img, "elevation"),
        diffs, diffs,
    )

    assert result["azimuth"]["inlier_count"][0] == result["elevation"]["inlier_count"][0]
    ratio_az = result["azimuth"]["success_rate"][-1]
    ratio_el = result["elevation"]["success_rate"][-1]
    assert ratio_az < ratio_el, (
        f"at the same 30-degree difference, azimuth's success rate ({ratio_az:.3f}) should be "
        f"clearly lower than elevation's ({ratio_el:.3f})"
    )
