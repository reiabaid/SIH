"""Validate CH2's overlap_hint crop-before-decode feature (now wired into
production via src/api.py) against the full real 8-pair inventory. Same
before/after validation pattern used throughout this project.

Compares well_determined verdicts against the known-good deterministic
baseline in docs/research/day2_pair_verification.md.
"""
from __future__ import annotations

import json

from src.io_ch2 import load_product as load_ch2
from src.io_lro import load_product as load_lro, LROReadError
from src.metrics import fit_reliability
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


def _to_match_result(mr: dict) -> MatchResult:
    return MatchResult(
        pts_a=mr["pts_a"], pts_b=mr["pts_b"], scores=mr["scores"],
        inlier_mask=mr["inlier_mask"], transform=mr["transform"], matcher=mr["matcher"],
        shape_a=mr["shape_a"], shape_b=mr["shape_b"], runtime_s=mr["runtime_s"],
    )


def main():
    lro_cache = {}
    results = []

    for ch2_id, lro_file in PAIRS:
        pair_label = f"{ch2_id}_x_{lro_file[:-4]}"
        print(f"\n=== {pair_label} ===")

        if lro_file not in lro_cache:
            try:
                lro_cache[lro_file] = load_lro(f"data/lro_nac/{lro_file}")
            except LROReadError as e:
                print(f"  SKIP: {e}")
                continue
        lro = lro_cache[lro_file]

        # Load CH2 WITH the overlap hint -- this is the feature under test,
        # exactly as src/api.py's process_job_sync now does in production.
        ch2 = load_ch2(CH2_XMLS[ch2_id], overlap_hint=lro)
        cropped = "cropped_window" in ch2.meta
        print(f"  cropped={cropped} meta={ch2.meta.get('cropped_window')}")

        for rung in (0, 1):
            label = f"sift-rung{rung}"
            out = run_pipeline(ch2, lro, matcher="sift", rung=rung, align=True)
            mr = _to_match_result(out["match_result"])
            reliability = fit_reliability(mr)
            n_inliers = int(mr.inlier_mask.sum())
            row = {
                "pair": pair_label, "config": label, "cropped": cropped,
                "total": len(mr.pts_a), "inliers": n_inliers,
                "unique": reliability["unique_inlier_locations"],
                "well_determined": reliability["well_determined"],
            }
            print(f"  [{label}] total={row['total']} inliers={n_inliers} "
                  f"unique={row['unique']} well_determined={row['well_determined']}")
            results.append(row)

    with open("docs/research/ch2_crop_validation.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nWrote docs/research/ch2_crop_validation.json")


if __name__ == "__main__":
    main()
