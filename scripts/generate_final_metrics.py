# scripts/generate_final_metrics.py — produce demo/final_metrics.json and Markdown/CSV summary tables
# Owner: Riddhi

import json
import os
import numpy as np

from src.render import load_dem_patch, render_hillshade
from src.match import match
from src.metrics import inlier_stats, rmse, coverage
from src.sweep import make_synthetic_dem

REAL_DEM_PATH = "data/dem/LDEM_60S_240MPP_ADJ.tiff"


def _load_terrain(dem_path: str = REAL_DEM_PATH):
    """Real DEM if present, otherwise a synthetic multi-crater heightmap run
    through the exact same render_hillshade/match/metrics pipeline. Every
    number in the output table is computed by a real run either way -- never
    a hand-typed placeholder. Distinguished in the output JSON's
    `terrain_source` field so nobody downstream can mistake one for the
    other.
    """
    try:
        dem, spacing = load_dem_patch(dem_path, 2000, 2000, 512)
        return dem, spacing, "real_dem"
    except (FileNotFoundError, ValueError) as e:
        print(f"Real DEM not available ({e}) -- using a synthetic multi-crater heightmap instead.")
        dem = make_synthetic_dem(size=256, seed=42, n_craters=40, rim_height=20.0)
        return dem, 1.0, "synthetic_dem"


def generate_final_metrics(
    dem_path: str = REAL_DEM_PATH,
    output_path: str = "demo/final_metrics.json",
) -> dict:
    """Run evaluation for SIFT (Rung 0), Mod-X (Rung 1), and LightGlue across
    illumination conditions, generating demo/final_metrics.json and printing
    a Markdown summary table. Every number is computed by an actual pipeline
    run -- see _load_terrain for what happens when no real DEM is present.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    dem, spacing, terrain_source = _load_terrain(dem_path)
    base_elevation = 30.0
    base_azimuth = 0.0
    base_img = render_hillshade(dem, spacing, base_azimuth, base_elevation).astype(np.float32) / 255.0

    methods = [
        ("SIFT (Rung 0)", "sift", 0),
        ("Mod-X (Rung 1)", "sift", 1),
        ("LightGlue", "lightglue", 0),
    ]
    azimuth_diffs = [0, 30, 90, 180]

    method_results = {}
    for label, matcher, rung in methods:
        az_data = {}
        for diff in azimuth_diffs:
            test_img = render_hillshade(dem, spacing, base_azimuth + diff, base_elevation).astype(np.float32) / 255.0
            kwargs = {"rung": rung} if matcher == "sift" else {}
            res = match(base_img, test_img, matcher=matcher, **kwargs)

            stats = inlier_stats(res)
            errs = rmse(res, gt_transform=np.eye(3))
            cov = coverage(res)

            az_data[f"az_{diff}deg"] = {
                "total_matches": stats["total_matches"],
                "inlier_count": stats["inlier_count"],
                "inlier_ratio": round(stats["inlier_ratio"], 4),
                "reprojection_residual": round(errs["reprojection_residual"], 4) if not np.isnan(errs["reprojection_residual"]) else None,
                "rmse_ground_truth": round(errs["rmse_ground_truth"], 4) if errs["rmse_ground_truth"] is not None and not np.isnan(errs["rmse_ground_truth"]) else None,
                "occupied_fraction": round(cov["occupied_fraction"], 4),
                "coefficient_of_variation": round(cov["coefficient_of_variation"], 4) if not np.isnan(cov["coefficient_of_variation"]) else None,
                "runtime_s": round(res.runtime_s, 4),
            }
        method_results[label] = az_data

    output = {"terrain_source": terrain_source, "methods": method_results}
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nWrote final metrics to {output_path} (terrain_source: {terrain_source})")

    print("\n### Final Evaluation Metrics Summary")
    print("| Method | Inliers (0°) | Inliers (90°) | Inliers (180°) | Reproj Residual (0°) | Ground Truth RMSE (0°) | Grid Occupancy (0°) |")
    print("|---|---|---|---|---|---|---|")
    for method, data in method_results.items():
        m0 = data.get("az_0deg", {})
        m90 = data.get("az_90deg", {})
        m180 = data.get("az_180deg", {})
        print(
            f"| {method:<14} "
            f"| {m0.get('inlier_count', '-'):<12} "
            f"| {m90.get('inlier_count', '-'):<13} "
            f"| {m180.get('inlier_count', '-'):<14} "
            f"| {str(m0.get('reprojection_residual', '-')):<20} "
            f"| {str(m0.get('rmse_ground_truth', '-')):<22} "
            f"| {str(m0.get('occupied_fraction', '-')):<19} |"
        )

    return output


def main():
    generate_final_metrics()


if __name__ == "__main__":
    main()
