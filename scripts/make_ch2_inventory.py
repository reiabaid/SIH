"""
scripts/make_ch2_inventory.py — write data/ch2_inventory.csv, one row
per Chandrayaan-2 product: id, instrument, acquisition UTC, four corner
lat/lons, GSD, pixel dimensions, file path.

Usage:
    python -m scripts.make_ch2_inventory path/to/label1.xml path/to/label2.xml ...

Or point it at a folder and it'll find every .xml under it:
    python -m scripts.make_ch2_inventory --dir .
"""

from __future__ import annotations

import argparse
import csv
import glob
import os

from src.io_ch2 import load_product


FIELDNAMES = [
    "product_id",
    "instrument",
    "acquired_utc",
    "ul_lat", "ul_lon",
    "ur_lat", "ur_lon",
    "ll_lat", "ll_lon",
    "lr_lat", "lr_lon",
    "gsd_m",
    "height_px",
    "width_px",
    "file_path",
]


def build_row(xml_path: str) -> dict:
    p = load_product(xml_path)
    h, w = p.array.shape
    row = {
        "product_id": p.product_id,
        "instrument": p.source,
        "acquired_utc": p.acquired_utc,
        "gsd_m": p.gsd_m,
        "height_px": h,
        "width_px": w,
        "file_path": xml_path,
    }
    for key in ("ul", "ur", "ll", "lr"):
        lat, lon = p.corners[key]
        row[f"{key}_lat"] = lat
        row[f"{key}_lon"] = lon
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml_paths", nargs="*", help="One or more .xml label paths")
    parser.add_argument("--dir", help="Folder to search recursively for .xml labels")
    parser.add_argument(
        "--out", default="data/ch2_inventory.csv", help="Output CSV path"
    )
    args = parser.parse_args()

    xml_paths = list(args.xml_paths)
    if args.dir:
        xml_paths.extend(
            glob.glob(os.path.join(args.dir, "**", "*.xml"), recursive=True)
        )

    if not xml_paths:
        parser.error("Provide one or more .xml paths, or --dir to search a folder.")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    rows_written = 0
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for xml_path in xml_paths:
            try:
                writer.writerow(build_row(xml_path))
                rows_written += 1
                print(f"OK   {xml_path}")
            except Exception as e:
                print(f"FAIL {xml_path}: {e}")

    print(f"\nWrote {rows_written} row(s) to {args.out}")


if __name__ == "__main__":
    main()