"""Reia's speed-work task (docs/WORK_DIVISION_PLAN.md): is match_tiled's
MIN_POOL_POINTS early-exit threshold (currently 500) too conservative?
Sweep it against the full real 8-pair inventory and check whether a lower
threshold still gives every pair the same well_determined verdict while
running faster.

Only sift-rung0 and sift-rung1 are tested here -- LightGlue already exits
via its own path and is the slow-but-opt-in case, not what this tuning is
for.
"""
from __future__ import annotations

import json
import time

from src.io_ch2 import load_product as load_ch2
from src.io_lro import load_product as load_lro, LROReadError
from src.geo import align_pair
from src.prep import to_gray_float, local_contrast_norm
from src.match import match_tiled
from src.metrics import fit_reliability, inlier_stats
from src.types import MatchResult

D18_XML = ("data/ch2_products/ch2_ohr_ncp_20200229T0739312111_d_img_d18/"
           "miscellaneous/calibrated/20200229/"
           "ch2_ohr_ncp_20200229T0739312111_d_img_d18.xml")
D32_XML = ("data/ch2_products/ch2_ohr_ncp_20200229T0938004033_d_img_d32/"
           "miscellaneous/calibrated/20200229/"
           "ch2_ohr_ncp_20200229T0938004033_d_img_d32.xml")
CH2_XMLS = {"d18": D18_XML, "d32": D32_XML}

PAIRS = [
    ("d18", "M1164584053LE.IMG"),
    ("d32", "M1177420489LE.IMG"),
    ("d18", "M1499112398LE.IMG"),
    ("d18", "M1519299970LE.IMG"),
    ("d32", "M1519299970LE.IMG"),
    ("d18", "M1529523925LE.IMG"),
    ("d32", "M1529537951LE.IMG"),
    ("d32", "M1531872919LE.IMG"),
]
THRESHOLDS = [150, 250, 500]  # 500 = current default, kept as the control


def main():
    ch2_cache, lro_cache, aligned_cache = {}, {}, {}
    results = []

    for ch2_id, lro_file in PAIRS:
        pair_label = f"{ch2_id}_x_{lro_file[:-4]}"
        print(f"\n=== {pair_label} ===")

        if ch2_id not in ch2_cache:
            ch2_cache[ch2_id] = load_ch2(CH2_XMLS[ch2_id])
        ch2 = ch2_cache[ch2_id]
        if lro_file not in lro_cache:
            try:
                lro_cache[lro_file] = load_lro(f"data/lro_nac/{lro_file}")
            except LROReadError as e:
                print(f"  SKIP: {e}")
                continue
        lro = lro_cache[lro_file]

        cache_key = pair_label
        if cache_key not in aligned_cache:
            a_prod, b_prod = align_pair(ch2, lro)
            a = local_contrast_norm(to_gray_float(a_prod.array), sigma=15.0)
            b = local_contrast_norm(to_gray_float(b_prod.array), sigma=15.0)
            aligned_cache[cache_key] = (a, b)
        a, b = aligned_cache[cache_key]

        for rung in (0, 1):
            label = f"sift-rung{rung}"
            for threshold in THRESHOLDS:
                t0 = time.time()
                result = match_tiled(a, b, matcher="sift", rung=rung, min_pool_points=threshold)
                dt = time.time() - t0
                reliability = fit_reliability(result)
                n_inliers = int(result.inlier_mask.sum())
                row = {
                    "pair": pair_label, "config": label, "min_pool_points": threshold,
                    "wall_time_s": round(dt, 2), "total": len(result.pts_a),
                    "inliers": n_inliers, "unique": reliability["unique_inlier_locations"],
                    "well_determined": reliability["well_determined"],
                }
                print(f"  [{label} thresh={threshold}] total={row['total']} inliers={n_inliers} "
                      f"unique={row['unique']} well_determined={row['well_determined']} "
                      f"time={dt:.2f}s")
                results.append(row)

    with open("docs/research/early_exit_tuning.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nWrote docs/research/early_exit_tuning.json")


if __name__ == "__main__":
    main()
