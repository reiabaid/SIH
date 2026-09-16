"""Reia's Day-of-speed-work task 1 (docs/WORK_DIVISION_PLAN.md): a real,
stage-by-stage time breakdown for run_pipeline on real pairs, so the rest of
the speed work optimizes the actual bottleneck instead of guessing.

Times, separately, per pair:
  - product load (io_ch2/io_lro, includes SPICE/WebGeocalc network calls)
  - align_pair (common-grid resampling)
  - local_contrast_norm (LCN, both images)
  - tiled matching + RANSAC (match_tiled), per matcher/rung
  - deliverable write (build_deliverable + control network)

Does not modify src/pipeline.py -- replicates its exact steps with timers
around each, so production code stays untouched while we find out where
time actually goes.
"""
from __future__ import annotations

import json
import time

from src.io_ch2 import load_product as load_ch2
from src.io_lro import load_product as load_lro
from src.geo import align_pair
from src.prep import to_gray_float, local_contrast_norm
from src.match import match_tiled
from src.deliverable import write_match_points

D32_XML = ("data/ch2_products/ch2_ohr_ncp_20200229T0938004033_d_img_d32/"
           "miscellaneous/calibrated/20200229/"
           "ch2_ohr_ncp_20200229T0938004033_d_img_d32.xml")
D18_XML = ("data/ch2_products/ch2_ohr_ncp_20200229T0739312111_d_img_d18/"
           "miscellaneous/calibrated/20200229/"
           "ch2_ohr_ncp_20200229T0739312111_d_img_d18.xml")

PAIRS = [
    ("d32", D32_XML, "M1519299970LE.IMG"),
    ("d18", D18_XML, "M1519299970LE.IMG"),
    ("d32", D32_XML, "M1531872919LE.IMG"),
]
CONFIGS = [("sift", 0), ("sift", 1), ("lightglue", 0)]


def timed(label, fn, *a, **kw):
    t0 = time.time()
    out = fn(*a, **kw)
    dt = time.time() - t0
    print(f"    {label}: {dt:.2f}s")
    return out, dt


def main():
    report = []
    for ch2_id, ch2_xml, lro_file in PAIRS:
        pair_label = f"{ch2_id}_x_{lro_file[:-4]}"
        print(f"\n=== {pair_label} ===")
        row = {"pair": pair_label}

        (ch2, ), t_load_a = timed("load ch2", lambda: (load_ch2(ch2_xml),))
        (lro, ), t_load_b = timed("load lro (incl. SPICE)", lambda: (load_lro(f"data/lro_nac/{lro_file}"),))
        row["load_ch2_s"] = round(t_load_a, 2)
        row["load_lro_s"] = round(t_load_b, 2)

        (a_prod, b_prod), t_align = timed("align_pair", align_pair, ch2, lro)
        row["align_pair_s"] = round(t_align, 2)

        a_gray = to_gray_float(a_prod.array)
        b_gray = to_gray_float(b_prod.array)

        def do_lcn():
            return local_contrast_norm(a_gray, sigma=15.0), local_contrast_norm(b_gray, sigma=15.0)
        (a_lcn, b_lcn), t_lcn = timed("local_contrast_norm (both)", do_lcn)
        row["lcn_s"] = round(t_lcn, 2)

        row["aligned_shape"] = list(a_lcn.shape)

        for matcher, rung in CONFIGS:
            label = f"{matcher}-rung{rung}" if matcher == "sift" else matcher
            result, t_match = timed(f"match_tiled [{label}]", match_tiled, a_lcn, b_lcn, matcher=matcher, rung=rung)
            n_inliers = int(result.inlier_mask.sum())
            print(f"      -> total={len(result.pts_a)} inliers={n_inliers}")
            row[f"match_{label}_s"] = round(t_match, 2)
            row[f"match_{label}_inliers"] = n_inliers

        report.append(row)

    print("\n\n=== SUMMARY ===")
    print(json.dumps(report, indent=2))
    with open("docs/research/pipeline_time_breakdown.json", "w") as f:
        json.dump(report, f, indent=2)
    print("\nWrote docs/research/pipeline_time_breakdown.json")


if __name__ == "__main__":
    main()
