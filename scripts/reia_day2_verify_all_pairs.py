"""Reia's Day 2 task (docs/WEEK_PLAN.md): run the pipeline against every real
CH2 x LRO pair the inventory can actually produce (per
scripts/check_ch2_lro_overlap.py), not just the one verified pair, across
rung 0, rung 1, and LightGlue. Tables inliers / unique_locations / trivial_fit
for each pair+config so the team has a shared "what actually works" reference.

Overlapping pairs found by check_ch2_lro_overlap.py (2026-09-12):
  d18 x M1164584053LE, d32 x M1177420489LE, d18 x M1499112398LE,
  d18 x M1519299970LE, d32 x M1519299970LE (the verified pair),
  d18 x M1529523925LE, d32 x M1529537951LE, d32 x M1531872919LE
"""

from __future__ import annotations

import json
import time
import traceback

from src.io_ch2 import load_product as load_ch2
from src.io_lro import load_product as load_lro, LROReadError
from src.metrics import coverage, fit_reliability, inlier_stats, rmse
from src.pipeline import run_pipeline
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

CONFIGS = [("sift", 0), ("sift", 1), ("lightglue", 0)]

OUT_JSON = "docs/research/day2_pair_verification.json"


def _to_match_result(mr: dict) -> MatchResult:
    return MatchResult(
        pts_a=mr["pts_a"], pts_b=mr["pts_b"], scores=mr["scores"],
        inlier_mask=mr["inlier_mask"], transform=mr["transform"], matcher=mr["matcher"],
        shape_a=mr["shape_a"], shape_b=mr["shape_b"], runtime_s=mr["runtime_s"],
    )


def main() -> None:
    ch2_cache = {}
    lro_cache = {}
    table = []

    for ch2_id, lro_file in PAIRS:
        pair_label = f"{ch2_id}_x_{lro_file[:-4]}"
        print(f"\n=== Pair: {pair_label} ===")

        if ch2_id not in ch2_cache:
            print(f"Loading {ch2_id} (CH2 OHRC)...")
            ch2_cache[ch2_id] = load_ch2(CH2_XMLS[ch2_id])
        ch2 = ch2_cache[ch2_id]

        if lro_file not in lro_cache:
            print(f"Loading {lro_file} (LRO NAC)...")
            try:
                lro_cache[lro_file] = load_lro(f"data/lro_nac/{lro_file}")
            except LROReadError as e:
                print(f"  SKIP {lro_file}: {e}")
                lro_cache[lro_file] = None
        lro = lro_cache[lro_file]
        if lro is None:
            table.append({"pair": pair_label, "error": "LRO load failed"})
            continue

        for matcher, rung in CONFIGS:
            label = f"{matcher}-rung{rung}" if matcher == "sift" else matcher
            row = {"pair": pair_label, "config": label}
            try:
                t0 = time.time()
                out = run_pipeline(ch2, lro, matcher=matcher, rung=rung, align=True)
                elapsed = time.time() - t0
                mr = out["match_result"]
                result = _to_match_result(mr)
                reliability = fit_reliability(result)
                n_total, n_inliers = len(result.pts_a), int(result.inlier_mask.sum())
                row.update({
                    "wall_time_s": round(elapsed, 1),
                    "total_matches": n_total,
                    "inliers": n_inliers,
                    "unique_inlier_locations": reliability["unique_inlier_locations"],
                    "trivial_fit": reliability["trivial_fit"],
                    "well_determined": reliability["well_determined"],
                    **inlier_stats(result),
                    **coverage(result),
                })
                print(f"  [{label}] total={n_total} inliers={n_inliers} "
                      f"unique={reliability['unique_inlier_locations']} "
                      f"trivial_fit={reliability['trivial_fit']} "
                      f"well_determined={reliability['well_determined']} "
                      f"({elapsed:.1f}s)")
            except Exception as e:
                row["error"] = f"{type(e).__name__}: {e}"
                print(f"  [{label}] ERROR: {row['error']}")
                traceback.print_exc()
            table.append(row)

    with open(OUT_JSON, "w") as f:
        json.dump(table, f, indent=2, default=str)
    print(f"\nWrote {OUT_JSON}")


if __name__ == "__main__":
    main()
