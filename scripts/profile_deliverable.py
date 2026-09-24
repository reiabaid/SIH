"""Times each substep of src/deliverable.py's build_deliverable on the real
flagship pair (d32 x M1529537951LE, CH2 as product_a / LRO as product_b, the
order the frontend sends). build_deliverable was measured at ~18s of a ~62s
end-to-end registration -- this finds out which substep actually owns that
time, so the speed work targets the real cost rather than a guess.
"""
import os
import tempfile
import time

import cv2
import numpy as np

from src.deliverable import (_write_geotiff, write_match_geojson,
                             write_match_points, write_overlay)
from src.io_ch2 import load_product as load_ch2
from src.io_lro import load_product as load_lro
from src.pipeline import run_pipeline
from src.types import MatchResult

CH2_XML = ("data/ch2_products/ch2_ohr_ncp_20200229T0938004033_d_img_d32/"
           "miscellaneous/calibrated/20200229/"
           "ch2_ohr_ncp_20200229T0938004033_d_img_d32.xml")
LRO_IMG = "data/lro_nac/M1529537951LE.IMG"


def timed(label, fn):
    t0 = time.time()
    out = fn()
    print(f"  {label:<34} {time.time() - t0:6.2f}s", flush=True)
    return out


def main():
    lro = load_lro(LRO_IMG)
    ch2 = load_ch2(CH2_XML, overlap_hint=lro)
    print(f"product_a (CH2, cropped) array: {ch2.array.shape} "
          f"{ch2.array.nbytes / 1e9:.2f} GB", flush=True)
    print(f"product_b (LRO)          array: {lro.array.shape} "
          f"{lro.array.nbytes / 1e9:.2f} GB", flush=True)

    out = run_pipeline(ch2, lro, matcher="sift", rung=0, align=True)
    mr = out["match_result"]
    result = MatchResult(
        pts_a=mr["pts_a"], pts_b=mr["pts_b"], scores=mr["scores"],
        inlier_mask=mr["inlier_mask"], transform=mr["transform"], matcher=mr["matcher"],
        shape_a=mr["shape_a"], shape_b=mr["shape_b"], runtime_s=mr["runtime_s"],
    )

    print("\nbuild_deliverable substeps:", flush=True)
    with tempfile.TemporaryDirectory() as d:
        registered = timed("cv2.warpPerspective (A -> B frame)", lambda: cv2.warpPerspective(
            ch2.array.astype(np.float32, copy=False), result.transform,
            (lro.array.shape[1], lro.array.shape[0])))
        tif = os.path.join(d, "registered_a_to_b.tif")
        timed("_write_geotiff", lambda: _write_geotiff(tif, registered, lro))
        timed("write_match_points (csv)", lambda: write_match_points(
            os.path.join(d, "match_points.csv"), result, ch2, lro))
        timed("write_match_geojson", lambda: write_match_geojson(
            os.path.join(d, "match_points.geojson"), result, ch2, lro))
        png = os.path.join(d, "overlay_rgb.png")
        timed("write_overlay (full-res PNG)", lambda: write_overlay(png, registered, lro.array))

        print("\noutput file sizes:", flush=True)
        for name in sorted(os.listdir(d)):
            print(f"  {name:<28} {os.path.getsize(os.path.join(d, name)) / 1e6:9.1f} MB", flush=True)


if __name__ == "__main__":
    main()
