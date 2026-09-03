# src/sweep.py — illumination-robustness sweep: success rate vs sun-azimuth
# difference, with a second line vs sun-elevation difference. The demo's
# centrepiece plot.
# Owner: Riddhi
#
# Split into two layers on purpose:
#   - run_sweep / run_illumination_sweep: pure orchestration, takes an
#     injectable trial_fn, no dependency on any real renderer or matcher.
#     Testable today with a fake trial_fn -- same "tests without anyone"
#     pattern as every other module in this lane.
#   - make_dem_trial_fn: the real wiring against Manya's src/render.py and
#     Reia's src/match.py. This is the actual production path, but it can't
#     be exercised end to end here -- the DEM GeoTIFF it needs isn't
#     committed to the repo (too large), so its own tests use monkeypatching
#     to verify the wiring without a real file.

import numpy as np

from src.metrics import inlier_stats
from src.types import MatchResult


def angular_difference(azimuth_a: float, azimuth_b: float) -> float:
    """Smallest circular difference between two azimuths, in [0, 180].

    Azimuth wraps at 360 deg, so a plain `abs(a - b)` is wrong whenever the
    two angles straddle the wrap point: 350 and 10 are 20 deg apart, not
    340. Not used by run_sweep/make_dem_trial_fn -- those parametrize the
    sweep directly by the diff to render, so nothing ever subtracts two
    absolute azimuths internally -- but real Product metadata (e.g.
    `subsolar_azimuth_deg` from io_lro.py) does need this to compute a
    genuine difference between two recorded angles, so it's provided here
    rather than left for someone to get wrong later.
    """
    diff = abs(azimuth_a - azimuth_b) % 360.0
    return min(diff, 360.0 - diff)


def run_sweep(trial_fn, diffs) -> dict:
    """Run `trial_fn(diff) -> MatchResult` once per value in `diffs`.

    Returns {"diffs": [...], "success_rate": [...], "inlier_count": [...]}.
    `success_rate` is each trial's inlier_ratio (fraction of candidate
    matches RANSAC kept) -- how successfully the matcher found true
    correspondences under that trial's illumination difference. Any
    exception from `trial_fn` is allowed to propagate; a bad trial should be
    visible, not silently skipped.

    Every diff must be a finite real number -- validated up front, before
    calling `trial_fn` at all, so a `None` or `NaN` slipping in from
    incomplete metadata (e.g. a Product with `subsolar_azimuth_deg = None`)
    fails here with a clear message instead of somewhere deep inside a
    renderer, a matcher, or matplotlib.
    """
    diffs = list(diffs)
    for i, diff in enumerate(diffs):
        if diff is None or not np.isfinite(diff):
            raise ValueError(
                f"run_sweep: diffs[{i}] is {diff!r} -- every diff must be a finite number. "
                "A None/NaN here usually means missing illumination metadata upstream."
            )

    success_rate = []
    inlier_count = []
    for diff in diffs:
        result = trial_fn(diff)
        stats = inlier_stats(result)
        success_rate.append(stats["inlier_ratio"])
        inlier_count.append(stats["inlier_count"])
    return {"diffs": diffs, "success_rate": success_rate, "inlier_count": inlier_count}


def run_illumination_sweep(azimuth_trial_fn, elevation_trial_fn, azimuth_diffs, elevation_diffs) -> dict:
    """Two independent sweeps, ready for plot_sweep(): `azimuth_trial_fn`
    varies sun-azimuth difference at a fixed elevation baseline,
    `elevation_trial_fn` varies sun-elevation difference at a fixed azimuth
    baseline. Each is its own call into run_sweep -- they don't need to
    share a baseline or even come from the same renderer.
    """
    return {
        "azimuth": run_sweep(azimuth_trial_fn, azimuth_diffs),
        "elevation": run_sweep(elevation_trial_fn, elevation_diffs),
    }


def make_dem_trial_fn(
    dem_path: str,
    row_start: int,
    col_start: int,
    size: int,
    base_azimuth: float,
    base_elevation: float,
    vary: str,
    matcher: str = "sift",
):
    """Build a trial_fn for run_sweep, backed by the real DEM renderer
    (src.render) and matcher (src.match). `vary` selects which of
    base_azimuth/base_elevation the returned function perturbs by the
    requested diff; the other stays fixed.

    Imports render.py's dependencies (rasterio) locally rather than at
    module load time -- they're only needed for this real-data path, not
    for run_sweep's core logic or its tests.
    """
    if vary not in ("azimuth", "elevation"):
        raise ValueError(f"make_dem_trial_fn: vary must be 'azimuth' or 'elevation', got {vary!r}")

    from src.match import match
    from src.render import load_dem_patch, render_hillshade

    dem, spacing = load_dem_patch(dem_path, row_start, col_start, size)
    base_img = render_hillshade(dem, spacing, base_azimuth, base_elevation).astype(np.float32) / 255.0

    def trial_fn(diff: float) -> MatchResult:
        if vary == "azimuth":
            az, el = base_azimuth + diff, base_elevation
        else:
            az, el = base_azimuth, base_elevation + diff
        test_img = render_hillshade(dem, spacing, az, el).astype(np.float32) / 255.0
        return match(base_img, test_img, matcher=matcher)

    return trial_fn


def _build_sweep_figure(sweep_result: dict, metric: str = "success_rate"):
    """Build the figure without saving or closing it -- split out from
    plot_sweep so tests can inspect the actual plotted data (axis labels,
    legend text, which values ended up on which line) instead of only
    checking that some PNG file exists. A file that opens fine could still
    have success_rate and inlier_count swapped, or the wrong metric plotted
    entirely; only inspecting the artists themselves catches that.
    """
    import matplotlib
    matplotlib.use("Agg")  # headless-safe: writes a file, never opens a window
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(sweep_result["azimuth"]["diffs"], sweep_result["azimuth"][metric], marker="o", label="Sun azimuth difference")
    ax.plot(sweep_result["elevation"]["diffs"], sweep_result["elevation"][metric], marker="s", label="Sun elevation difference")
    ax.set_xlabel("Illumination difference (degrees)")
    ax.set_ylabel(metric.replace("_", " ").title())
    ax.set_title("Matcher robustness to illumination change")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5)
    fig.tight_layout()
    return fig


def plot_sweep(sweep_result: dict, output_path: str, metric: str = "success_rate") -> None:
    """Draw the demo's centrepiece plot: `metric` ("success_rate" or
    "inlier_count") against illumination difference, one line for azimuth,
    one for elevation.
    """
    # _build_sweep_figure forces the Agg backend before pyplot is first
    # imported anywhere in the process -- importing pyplot here first would
    # race that and risk locking in whatever the default backend is instead
    fig = _build_sweep_figure(sweep_result, metric)
    import matplotlib.pyplot as plt

    fig.savefig(output_path, dpi=150)
    plt.close(fig)
