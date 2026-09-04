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


def make_synthetic_dem(size: int = 256, seed: int = 0, n_craters: int = 40, rim_height: float = 1.0) -> np.ndarray:
    """A synthetic heightmap standing in for a real DEM patch when none is
    available: `n_craters` bowl-shaped depressions with raised rims at
    random positions -- pass it through `src.render.render_hillshade` to get
    a genuinely illumination-dependent image.

    A single smooth bowl (radially symmetric, no local texture) gives SIFT
    almost nothing to find keypoints on even at a 0 deg self-match -- this
    is deliberately many overlapping small features instead, the same shape
    of construction as `tests/test_match.py`'s `_synthetic_crater_field`,
    but as *height* rather than a pre-rendered intensity texture, since a
    flat texture has no elevation for a renderer to shade differently under
    different sun angles.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    dem = np.zeros((size, size), dtype=np.float32)
    for _ in range(n_craters):
        cx, cy = rng.uniform(0, size, size=2)
        r = rng.uniform(6, 28)
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        rim = np.exp(-((dist - r) ** 2) / (2 * (r * 0.25) ** 2))
        floor = -0.3 * np.clip(1 - dist / r, 0, 1)
        dem += rim_height * (0.4 * rim + floor)
    return dem


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
    correspondences under that trial's illumination difference. Diffs are
    sorted in increasing order so plotted curves connect points monotonically.

    Every diff must be a finite real number -- validated up front, before
    calling `trial_fn` at all.
    """
    diffs_input = list(diffs)
    for i, diff in enumerate(diffs_input):
        if diff is None or not np.isfinite(diff):
            raise ValueError(
                f"run_sweep: diffs[{i}] is {diff!r} -- every diff must be a finite number. "
                "A None/NaN here usually means missing illumination metadata upstream."
            )

    # Sort diffs monotonically to ensure clean line plotting
    diffs_sorted = sorted(diffs_input)

    success_rate = []
    inlier_count = []
    for diff in diffs_sorted:
        result = trial_fn(diff)
        stats = inlier_stats(result)
        success_rate.append(stats["inlier_ratio"])
        inlier_count.append(stats["inlier_count"])
    return {"diffs": diffs_sorted, "success_rate": success_rate, "inlier_count": inlier_count}


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
    rung: int = 0,
):
    """Build a trial_fn for run_sweep, backed by the real DEM renderer
    (src.render) and matcher (src.match). `vary` selects which of
    base_azimuth/base_elevation the returned function perturbs by the
    requested diff; the other stays fixed. `rung` selects the descriptor
    mode for SIFT (0 = raw intensity baseline, 1 = mod-pi orientation histogram).

    Imports render.py's dependencies (rasterio) locally rather than at
    module load time -- they're only needed for this real-data path, not
    for run_sweep's core logic or its tests.
    """
    if vary not in ("azimuth", "elevation"):
        raise ValueError(f"make_dem_trial_fn: vary must be 'azimuth' or 'elevation', got {vary!r}")

    if rung not in (0, 1) and matcher == "sift":
        raise ValueError(f"make_dem_trial_fn: rung for SIFT must be 0 or 1, got {rung!r}")

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
        kwargs = {}
        if matcher == "sift":
            kwargs["rung"] = rung
        return match(base_img, test_img, matcher=matcher, **kwargs)

    return trial_fn


def _build_sweep_figure(sweep_result: dict, metric: str = "inlier_count"):
    """Build the figure without saving or closing it -- split out from
    plot_sweep so tests can inspect the actual plotted data (axis labels,
    legend text, which values ended up on which line) instead of only
    checking that some PNG file exists. Default metric is inlier_count.
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


def plot_sweep(sweep_result: dict, output_path: str, metric: str = "inlier_count") -> None:
    """Draw the demo's centrepiece plot: `metric` ("inlier_count" by default,
    or "success_rate") against illumination difference, one line for azimuth,
    one for elevation.
    """
    fig = _build_sweep_figure(sweep_result, metric)
    import matplotlib.pyplot as plt

    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _build_win_plot_figure(multi_results: dict, metric: str = "inlier_count"):
    """Build multi-method comparison win plot figure (SIFT vs mod-pi vs LightGlue)
    plotting inlier_count against sun-azimuth difference.
    `multi_results` maps label -> run_sweep result dict.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    styles = [
        {"color": "#ffb703", "marker": "o", "linestyle": "-"},
        {"color": "#00f2fe", "marker": "s", "linestyle": "-"},
        {"color": "#00a8ff", "marker": "^", "linestyle": "--"}
    ]

    lines_plotted = 0
    for i, (label, sweep) in enumerate(multi_results.items()):
        if not sweep or "diffs" not in sweep or len(sweep["diffs"]) == 0:
            # Skip empty method sweep results gracefully
            continue

        y_vals = sweep[metric]
        if any(y is None or (isinstance(y, (int, float)) and y < 0) for y in y_vals):
            raise ValueError(f"plot_win_sweep: method {label!r} contains negative/invalid {metric} values")

        style = styles[lines_plotted % len(styles)]
        ax.plot(
            sweep["diffs"],
            y_vals,
            label=label,
            color=style["color"],
            marker=style["marker"],
            linestyle=style["linestyle"],
            linewidth=2,
        )
        lines_plotted += 1

    ax.set_xlabel("Sun Azimuth Difference (degrees)")
    ax.set_ylabel("Inlier Match Count" if metric == "inlier_count" else metric.replace("_", " ").title())
    ax.set_title("Illumination Invariance Win Plot (Inlier Match Count vs Sun Azimuth)")
    if lines_plotted > 0:
        ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5)
    fig.tight_layout()
    return fig


def plot_win_sweep(multi_results: dict, output_path: str, metric: str = "inlier_count") -> None:
    """Draw the win plot (demo/win_plot.png) overlaying SIFT (rung 0),
    mod-pi (rung 1), and LightGlue inlier match counts across azimuth differences.
    """
    fig = _build_win_plot_figure(multi_results, metric)
    import matplotlib.pyplot as plt

    fig.savefig(output_path, dpi=150)
    plt.close(fig)


