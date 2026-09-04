"""
scripts/check_overlap.py

Checks every LRO product in data/lro_nac/ against every known CH2 footprint
(derived from the geometry ground-track CSVs in data/ch2_products/) and
reports real footprint_overlap() numbers.

The point of this script, specifically: a failed SPICE geometry lookup in
io_lro.load_product() leaves a product's corners at the (0.0, 0.0) sentinel
for all four corners (no fallback exists for LRO NAC EDR/CDR, since those
labels don't carry corner coordinates directly). footprint_overlap() then
silently reports 0.0 for that product, indistinguishable from a genuine
non-overlap. This script checks meta['geometry_source'] first and reports
those products as UNKNOWN instead of a misleading 0.0000.

Run from repo root:
    python -m scripts.check_overlap
"""

import csv
import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.io_lro import load_product, LROReadError
from src.geo import footprint_overlap
from src.types import Product
import numpy as np


def _ch2_footprint_from_geometry_csv(csv_path: str, product_id: str) -> Product:
    """Build a CH2 Product's bounding-box footprint from its ground-track CSV
    (Longitude, Lattitude columns) — this works without the raster itself.
    """
    lons, lats = [], []
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            lons.append(float(row["Longitude"]))
            lats.append(float(row["Lattitude"]))

    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)
    corners = {
        "ul": (lat_max, lon_min), "ur": (lat_max, lon_max),
        "ll": (lat_min, lon_min), "lr": (lat_min, lon_max),
    }
    return Product(
        array=np.zeros((2, 2), dtype=np.float32), gsd_m=0.25,
        corners=corners, source="OHRC", product_id=product_id,
    )


def find_ch2_footprints() -> "dict[str, Product]":
    footprints = {}
    for csv_path in sorted(glob.glob("data/ch2_products/**/*_g_grd_*.csv", recursive=True)):
        # product id from filename: ch2_ohr_ncp_..._g_grd_d32.csv -> d32
        stem = os.path.splitext(os.path.basename(csv_path))[0]
        pid = stem.rsplit("_", 1)[-1]
        footprints[pid] = _ch2_footprint_from_geometry_csv(csv_path, pid)
    return footprints


def main():
    ch2_footprints = find_ch2_footprints()
    if not ch2_footprints:
        print("No CH2 geometry CSVs found under data/ch2_products/ — nothing to check against.")
        return

    lro_paths = sorted(set(
        glob.glob("data/lro_nac/*.IMG") + glob.glob("data/lro_nac/*.img")
    ))
    if not lro_paths:
        print("No LRO .IMG files found in data/lro_nac/ — nothing to check.")
        return

    print(f"CH2 footprints: {list(ch2_footprints.keys())}")
    print(f"LRO products to check: {len(lro_paths)}\n")

    header = f"{'LRO product':18}" + "".join(f"{'vs ' + pid:22}" for pid in ch2_footprints)
    print(header)
    print("-" * len(header))

    unknown = []
    real_overlaps = []

    for path in lro_paths:
        try:
            p = load_product(path)
        except LROReadError as e:
            print(f"{os.path.basename(path):18} FAILED TO LOAD: {e}")
            continue

        if p.meta.get("geometry_source") != "naif_webgeocalc":
            unknown.append(p.product_id)
            row = f"{p.product_id:18}" + "".join(f"{'UNKNOWN':22}" for _ in ch2_footprints)
            print(row)
            continue

        cells = []
        has_overlap = False
        for pid, ch2 in ch2_footprints.items():
            a = footprint_overlap(p, ch2)
            b = footprint_overlap(ch2, p)
            if a > 0 or b > 0:
                has_overlap = True
            cells.append(f"{a:.4f}/{b:.4f}")
        if has_overlap:
            real_overlaps.append(p.product_id)
        row = f"{p.product_id:18}" + "".join(f"{c:22}" for c in cells)
        print(row + ("  <<<" if has_overlap else ""))

    print()
    print(f"Real overlaps found: {real_overlaps or 'none'}")
    print(f"Unknown (geometry lookup failed, NOT confirmed non-overlapping): {unknown or 'none'}")
    if unknown:
        print("  -> these need a working geometry lookup before they can be trusted either way.")


if __name__ == "__main__":
    main()
