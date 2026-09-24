"""Is the CH2-vs-LRO offset a property of the CH2 image's georeferencing?

Every real fit sits 2-5.5 km from the metadata-implied position. If that is a
systematic CH2 georeferencing error, then registering the SAME CH2 image against
DIFFERENT LRO references (whose own geometry is consistent) must give the SAME
east/north offset vector. Compares the vectors per CH2 image, per rung.

Offset = mean displacement of a 5x5 grid of points on the common north-up
working grid under the fitted A->B transform, in metres (east +, north +).

    python -m scripts.offset_consistency
"""
import json

import numpy as np

from scripts.validate_ch2_crop import CH2_XMLS, PAIRS
from src.align_cache import cached_align_pair
from src.io_ch2 import load_product as load_ch2
from src.io_lro import load_product as load_lro
from src.match import match_tiled
from src.metrics import fit_reliability
from src.prep import local_contrast_norm, to_gray_float

OUT = "docs/research/offset_consistency.json"


def _offset_en_m(transform, shape, gsd_m):
    h, w = shape[:2]
    xs, ys = np.meshgrid(np.linspace(0, w - 1, 5), np.linspace(0, h - 1, 5))
    pts = np.stack([xs.ravel(), ys.ravel(), np.ones(25)])
    q = transform @ pts
    d = q[:2] / q[2] - pts[:2]
    return float(d[0].mean() * gsd_m), float(-d[1].mean() * gsd_m)


def main():
    rows = []
    for ch2_id, lro_file in PAIRS:
        lro = load_lro(f"data/lro_nac/{lro_file}")
        ch2 = load_ch2(CH2_XMLS[ch2_id], overlap_hint=lro)
        pa, pb = cached_align_pair(ch2, lro)
        a = local_contrast_norm(to_gray_float(pa.array))
        b = local_contrast_norm(to_gray_float(pb.array))
        for rung in (0, 1):
            r = match_tiled(a, b, matcher="sift", rung=rung)
            rel = fit_reliability(r)
            east, north = _offset_en_m(r.transform, r.shape_a, pa.gsd_m)
            row = {"ch2": ch2_id, "lro": lro_file[:-4], "rung": rung,
                   "well_determined": rel["well_determined"],
                   "unique": rel["unique_inlier_locations"],
                   "east_m": round(east, 1), "north_m": round(north, 1)}
            print(row, flush=True)
            rows.append(row)
            json.dump(rows, open(OUT, "w"), indent=2)


if __name__ == "__main__":
    main()
