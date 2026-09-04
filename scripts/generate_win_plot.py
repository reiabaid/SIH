# scripts/generate_win_plot.py — Generate demo/win_plot.png for presentation slides
# Owner: Riddhi

import os
import numpy as np

from src.sweep import run_sweep, plot_win_sweep, make_synthetic_dem
from src.match import match
from src.render import load_dem_patch, render_hillshade

REAL_DEM_PATH = "data/dem/LDEM_60S_240MPP_ADJ.tiff"


def _load_terrain(dem_path: str = REAL_DEM_PATH):
    """Real DEM if present, otherwise a synthetic multi-crater heightmap that
    goes through the exact same render_hillshade/match pipeline. Never
    fabricates result numbers -- only the source of terrain changes; every
    number that comes out is still computed by a real run.
    """
    try:
        dem, spacing = load_dem_patch(dem_path, 2000, 2000, 512)
        print(f"Using real DEM: {dem_path}")
        return dem, spacing, "real_dem"
    except (FileNotFoundError, ValueError) as e:
        print(
            f"Real DEM not available ({e}) -- using a synthetic multi-crater "
            "heightmap instead. Every number below is still computed by the "
            "real pipeline (render_hillshade + match + metrics); only the "
            "terrain source differs from a real DEM."
        )
        dem = make_synthetic_dem(size=256, seed=42, n_craters=40, rim_height=20.0)
        return dem, 1.0, "synthetic_dem"


def generate_win_plot(out_path: str = "demo/win_plot.png", dem_path: str = REAL_DEM_PATH) -> dict:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    dem, spacing, source = _load_terrain(dem_path)

    base_elevation = 30.0
    diffs = [0, 15, 30, 60, 90, 120, 150, 180]
    base_img = render_hillshade(dem, spacing, 0.0, base_elevation).astype(np.float32) / 255.0

    def make_trial(matcher: str, rung: int):
        def trial_fn(diff):
            test_img = render_hillshade(dem, spacing, diff, base_elevation).astype(np.float32) / 255.0
            kwargs = {"rung": rung} if matcher == "sift" else {}
            return match(base_img, test_img, matcher=matcher, **kwargs)
        return trial_fn

    print(f"Running sweeps against {source} terrain ({len(diffs)} azimuth steps x 3 methods)...")
    multi_results = {
        "SIFT (Rung 0 Baseline)": run_sweep(make_trial("sift", 0), diffs),
        "Mod-X (Rung 1 Solar-Robust)": run_sweep(make_trial("sift", 1), diffs),
        "LightGlue (Learned Matcher)": run_sweep(make_trial("lightglue", 0), diffs),
    }

    for label, sweep in multi_results.items():
        print(f"  {label}: inlier_count={sweep['inlier_count']}")

    plot_win_sweep(multi_results, out_path, metric="inlier_count")
    print(f"Win plot generated at: {out_path} (terrain: {source})")
    return multi_results


if __name__ == "__main__":
    generate_win_plot()
