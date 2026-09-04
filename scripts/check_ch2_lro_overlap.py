"""
scripts/check_ch2_lro_overlap.py

Ad-hoc overlap check between the CH2 OHRC products (d18, d32) and every
LRO NAC product currently in data/lro_nac/ (per data/lro_inventory.csv).

CH2 corners are parsed straight from the PDS4 label XML (bypassing
io_ch2.load_product, since that needs GDAL to read the .img array, which
isn't installed here — footprint_overlap only needs corners).
"""

import csv
import glob
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.io_ch2 import _parse_corners
from src.io_lro import load_product as load_lro_product, LROReadError
from src.types import Product
from src.geo import footprint_overlap

CH2_XMLS = {
    "d18": "data/ch2_products/ch2_ohr_ncp_20200229T0739312111_d_img_d18/miscellaneous/calibrated/20200229/ch2_ohr_ncp_20200229T0739312111_d_img_d18.xml",
    "d32": "data/ch2_products/ch2_ohr_ncp_20200229T0938004033_d_img_d32/miscellaneous/calibrated/20200229/ch2_ohr_ncp_20200229T0938004033_d_img_d32.xml",
}

DUMMY_ARRAY = np.zeros((1, 1), dtype=np.float32)


def load_ch2_corners_only(xml_path: str, product_id: str) -> Product:
    root = ET.parse(xml_path).getroot()
    corners = _parse_corners(root, xml_path)
    return Product(
        array=DUMMY_ARRAY, gsd_m=0.25, corners=corners, source="OHRC",
        product_id=product_id,
    )


def main():
    ch2_products = {pid: load_ch2_corners_only(path, pid) for pid, path in CH2_XMLS.items()}

    lro_paths = sorted(glob.glob("data/lro_nac/*.IMG")) + sorted(glob.glob("data/lro_nac/*.img"))
    lro_paths = sorted(set(lro_paths))

    results = []
    for path in lro_paths:
        try:
            lro = load_lro_product(path)
        except LROReadError as e:
            print(f"SKIP {path}: {e}")
            continue

        for ch2_id, ch2 in ch2_products.items():
            fwd = footprint_overlap(ch2, lro)  # fraction of ch2 covered by lro
            bwd = footprint_overlap(lro, ch2)  # fraction of lro covered by ch2
            results.append((ch2_id, os.path.basename(path), lro.product_id, fwd, bwd))

    print(f"\n{'ch2':6} {'lro_file':22} {'lro_id':16} {'ch2_covered_by_lro':>20} {'lro_covered_by_ch2':>20}")
    for ch2_id, fname, lro_id, fwd, bwd in results:
        flag = "  <-- OVERLAP" if (fwd > 0 or bwd > 0) else ""
        print(f"{ch2_id:6} {fname:22} {lro_id:16} {fwd:20.4f} {bwd:20.4f}{flag}")


if __name__ == "__main__":
    main()
