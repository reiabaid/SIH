"""
scripts/check_inliers_d32.py

Loads d32 (CH2 OHRC) and M1499112398LE (LRO NAC) — the best-overlap pair
found by scripts/check_ch2_lro_overlap.py — aligns them onto a common grid
via src.geo.align_pair, runs src.match.match, and reports the inlier count.

CH2's array is read with rasterio directly (osgeo/GDAL isn't installed here,
but rasterio's bundled GDAL can open the PDS4 label the same way).
"""

import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
import rasterio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.io_ch2 import _parse_corners, _local_findall
from src.io_lro import load_product as load_lro_product
from src.types import Product
from src.geo import align_pair
from src.match import match

D32_XML = "data/ch2_products/ch2_ohr_ncp_20200229T0938004033_d_img_d32/miscellaneous/calibrated/20200229/ch2_ohr_ncp_20200229T0938004033_d_img_d32.xml"
LRO_IMG = "data/lro_nac/M1499112398LE.IMG"


def load_ch2_full(xml_path: str) -> Product:
    root = ET.parse(xml_path).getroot()
    corners = _parse_corners(root, xml_path)

    with rasterio.open(xml_path) as ds:
        array = ds.read(1).astype(np.float32)
    arr_min, arr_max = float(array.min()), float(array.max())
    array = (array - arr_min) / (arr_max - arr_min)

    gsd_m = float(_local_findall(root, "pixel_resolution")[0].text)
    product_id = _local_findall(root, "logical_identifier")[0].text.strip()

    return Product(array=array, gsd_m=gsd_m, corners=corners, source="OHRC", product_id=product_id)


def main():
    print("Loading d32 (rasterio) ...")
    d32 = load_ch2_full(D32_XML)
    print(f"  d32: shape={d32.array.shape}, gsd={d32.gsd_m}")

    print("Loading M1499112398LE (pdr) ...")
    lro = load_lro_product(LRO_IMG)
    print(f"  lro: shape={lro.array.shape}, gsd={lro.gsd_m}")

    print("Aligning onto common grid ...")
    aligned_ch2, aligned_lro = align_pair(d32, lro)
    print(f"  aligned shape: {aligned_ch2.array.shape}, common gsd: {aligned_ch2.gsd_m}")

    for matcher, kwargs in [("sift", {"rung": 0}), ("sift", {"rung": 1})]:
        result = match(aligned_ch2.array, aligned_lro.array, matcher=matcher, **kwargs)
        n_total = len(result.pts_a)
        n_inliers = int(result.inlier_mask.sum())
        label = f"{matcher} rung={kwargs['rung']}"
        print(f"\n[{label}] total matches={n_total}, inliers={n_inliers}, runtime={result.runtime_s:.2f}s")


if __name__ == "__main__":
    main()
