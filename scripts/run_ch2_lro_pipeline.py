"""Real end-to-end run: CH2 OHRC d32 x LRO NAC M1499112398LE, through the fixed
pipeline (align_pair + tiled matching + coordinate inversion), for both rungs.

Supersedes the earlier ad-hoc investigation in demo/real_pair_result/summary.json
(4 inliers, diagnosed as likely a bad LRO corner fix -- that was written before
webgeocalc was installed, so LRO's corners were silently the (0,0) sentinel and
align_pair was aligning "the whole Moon" onto d32's footprint, not the real
~26% overlap). Real SPICE geometry now resolves via NAIF WebGeocalc.

Writes demo/real_pair_result/summary.json (metrics only -- the registered
GeoTIFF via build_deliverable needs GDAL's Python bindings, not installed
here; match_points.csv/geojson and the overlay PNG don't need it and are
written by this script directly).
"""

from __future__ import annotations

import json
import os
import time

from src.deliverable import write_match_points, write_match_geojson, write_overlay
from src.io_ch2 import load_product as load_ch2
from src.io_lro import load_product as load_lro
from src.metrics import coverage, fit_reliability, inlier_stats, rmse
from src.pipeline import run_pipeline
from src.types import MatchResult

D32_XML = ("data/ch2_products/ch2_ohr_ncp_20200229T0938004033_d_img_d32/"
          "miscellaneous/calibrated/20200229/"
          "ch2_ohr_ncp_20200229T0938004033_d_img_d32.xml")
LRO_IMG = "data/lro_nac/M1499112398LE.IMG"
OUT_DIR = "demo/real_pair_result"


def _to_match_result(mr: dict) -> MatchResult:
    return MatchResult(
        pts_a=mr["pts_a"], pts_b=mr["pts_b"], scores=mr["scores"],
        inlier_mask=mr["inlier_mask"], transform=mr["transform"], matcher=mr["matcher"],
        shape_a=mr["shape_a"], shape_b=mr["shape_b"], runtime_s=mr["runtime_s"],
    )


def main() -> None:
    print("Loading d32 (CH2 OHRC, rasterio)...")
    d32 = load_ch2(D32_XML)
    print(f"  {d32.product_id}: {d32.array.shape}, gsd={d32.gsd_m:.4f}m")

    print("Loading M1499112398LE (LRO NAC, pdr + NAIF WebGeocalc)...")
    lro = load_lro(LRO_IMG)
    print(f"  {lro.product_id}: {lro.array.shape}, gsd={lro.gsd_m:.4f}m, "
         f"geometry_source={lro.meta.get('geometry_source')}")

    os.makedirs(OUT_DIR, exist_ok=True)
    runs = {}
    for rung in (0, 1):
        label = f"sift-rung{rung}"
        print(f"\nRunning pipeline: align=True, matcher=sift, rung={rung} (tiled, real scale)...")
        t0 = time.time()
        out = run_pipeline(d32, lro, matcher="sift", rung=rung, align=True)
        elapsed = time.time() - t0
        mr = out["match_result"]
        result = _to_match_result(mr)
        n_total, n_inliers = len(result.pts_a), int(result.inlier_mask.sum())
        reliability = fit_reliability(result)
        print(f"  [{label}] total={n_total} inliers={n_inliers} "
             f"unique_locations={reliability['unique_inlier_locations']} "
             f"wall_time={elapsed:.1f}s match_runtime={result.runtime_s:.1f}s")
        if reliability["trivial_fit"]:
            print(f"  [{label}] WARNING: trivial_fit=True -- {reliability['unique_inlier_locations']} "
                 "unique inlier location(s) is at or below what a homography's 8 degrees of "
                 "freedom can satisfy exactly regardless of correctness. Do not read "
                 "reprojection_residual below as evidence of accurate registration.")

        metrics = {
            "matcher": result.matcher,
            "wall_time_s": elapsed,
            **rmse(result),
            **inlier_stats(result),
            **coverage(result),
            **reliability,
        }
        runs[label] = metrics

        if rung == 0 and n_total > 0:
            write_match_points(os.path.join(OUT_DIR, "match_points.csv"), result, d32, lro)
            write_match_geojson(os.path.join(OUT_DIR, "match_points.geojson"), result, d32, lro)

    summary = {
        "ch2_product": d32.product_id,
        "lro_product": lro.product_id,
        "ch2_gsd_m": d32.gsd_m,
        "lro_gsd_m": lro.gsd_m,
        "lro_geometry_source": lro.meta.get("geometry_source"),
        "note": ("Real end-to-end run through the fixed pipeline (align_pair wired in, "
                "tiled matching with global-pool RANSAC, coordinate inversion back to "
                "each product's own original pixel frame). webgeocalc installed and "
                "NAIF SPICE geometry resolved successfully for the LRO product -- the "
                "earlier weak result (4 inliers) was diagnosed against a (0,0) sentinel "
                "corner fallback, not real geometry."),
        "runs": runs,
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {OUT_DIR}/summary.json")


if __name__ == "__main__":
    main()
