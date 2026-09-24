"""Does local_contrast_norm(downsample=4) change registration results?

LCN was ~14s of a ~70s cold run (docs/research/pipeline_time_breakdown.json).
downsample=4 was measured ~4.7x faster on one raster but never validated on the
full real inventory. Runs the Auto cascade (as production does) with
lcn_downsample 1 vs 4 on all 8 real pairs and compares verdict, inlier count and
the agreement of the two fitted transforms (mean displacement, in pixels of
product A's frame, over a 5x5 grid of points).

    python -m scripts.validate_lcn_downsample
"""
from __future__ import annotations

import json
import time

import numpy as np

from scripts.validate_ch2_crop import CH2_XMLS, PAIRS, _to_match_result
from src.io_ch2 import load_product as load_ch2
from src.io_lro import load_product as load_lro
from src.metrics import fit_reliability
from src.pipeline import run_pipeline

OUT = "docs/research/lcn_downsample_validation.json"


def _transform_gap(t1, t2, shape):
    h, w = shape
    xs, ys = np.meshgrid(np.linspace(0, w - 1, 5), np.linspace(0, h - 1, 5))
    pts = np.stack([xs.ravel(), ys.ravel(), np.ones(25)])
    p1, p2 = t1 @ pts, t2 @ pts
    p1, p2 = p1[:2] / p1[2], p2[:2] / p2[2]
    return float(np.linalg.norm(p1 - p2, axis=0).mean())


def main():
    rows = []
    for ch2_id, lro_file in PAIRS:
        label = f"{ch2_id}_x_{lro_file[:-4]}"
        lro = load_lro(f"data/lro_nac/{lro_file}")
        ch2 = load_ch2(CH2_XMLS[ch2_id], overlap_hint=lro)
        runs = {}
        for ds in (1, 4):
            t0 = time.time()
            out = run_pipeline(ch2, lro, align=True, cascade=True, lcn_downsample=ds)
            elapsed = time.time() - t0
            mr = _to_match_result(out["match_result"])
            rel = fit_reliability(mr)
            runs[ds] = (mr, {
                "seconds": round(elapsed, 1), "rung": out["config"]["rung"],
                "inliers": int(mr.inlier_mask.sum()), "unique": rel["unique_inlier_locations"],
                "well_determined": rel["well_determined"]})
            print(f"{label} ds={ds}: {runs[ds][1]}", flush=True)
        gap = _transform_gap(runs[1][0].transform, runs[4][0].transform, runs[1][0].shape_a)
        rows.append({"pair": label, "ds1": runs[1][1], "ds4": runs[4][1],
                     "transform_gap_px": round(gap, 2)})
        print(f"{label}: transform gap {gap:.2f}px", flush=True)
        json.dump(rows, open(OUT, "w"), indent=2)


if __name__ == "__main__":
    main()
