"""Both images are on one common geo grid, so the true registration should be
close to a pure translation. Instead of a fragile 8-DOF homography (whose
extrapolation across an 11 km strip swings by km), vote on the displacement
b - a of ALL pooled candidate matches: the densest cluster is the shift.
Reports the shift (east/north m) and how many candidates back it, per pair and
rung, so the same CH2 image can be compared across LRO references.

    python -m scripts.translation_vote
"""
import json

import numpy as np

from scripts.validate_ch2_crop import CH2_XMLS, PAIRS
from src.align_cache import cached_align_pair
from src.io_ch2 import load_product as load_ch2
from src.io_lro import load_product as load_lro
from src.match import match_tiled
from src.prep import local_contrast_norm, to_gray_float

OUT = "docs/research/translation_vote.json"
BIN_PX, RADIUS_PX = 20, 30


def vote(pts_a, pts_b):
    d = pts_b - pts_a
    if len(d) == 0:
        return None
    bins = np.floor(d / BIN_PX).astype(int)
    keys, counts = np.unique(bins, axis=0, return_counts=True)
    # densest 3x3 neighbourhood of bins (robust to a cluster straddling a bin edge)
    best, best_n = None, 0
    for k in keys:
        n = int((np.abs(bins - k).max(axis=1) <= 1).sum())
        if n > best_n:
            best, best_n = k, n
    centre = np.median(d[np.abs(bins - best).max(axis=1) <= 1], axis=0)
    members = np.linalg.norm(d - centre, axis=1) <= RADIUS_PX
    return centre, int(members.sum()), len(d)


def main():
    rows = []
    for ch2_id, lro_file in PAIRS:
        lro = load_lro(f"data/lro_nac/{lro_file}")
        ch2 = load_ch2(CH2_XMLS[ch2_id], overlap_hint=lro)
        pa, pb = cached_align_pair(ch2, lro)
        a = local_contrast_norm(to_gray_float(pa.array))
        b = local_contrast_norm(to_gray_float(pb.array))
        for rung in (0, 1):
            r = match_tiled(a, b, matcher="sift", rung=rung, min_pool_points=100000)  # no early exit
            v = vote(r.pts_a, r.pts_b)
            if v is None:
                row = {"ch2": ch2_id, "lro": lro_file[:-4], "rung": rung, "candidates": 0}
            else:
                c, n, total = v
                row = {"ch2": ch2_id, "lro": lro_file[:-4], "rung": rung, "candidates": total,
                       "support": n, "east_m": round(float(c[0]) * pa.gsd_m, 1),
                       "north_m": round(float(-c[1]) * pa.gsd_m, 1)}
            print(row, flush=True)
            rows.append(row)
            json.dump(rows, open(OUT, "w"), indent=2)


if __name__ == "__main__":
    main()
