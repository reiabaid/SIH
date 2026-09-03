"""
scripts/build_lro_inventory.py

Scans data/lro_nac/ for .IMG products, loads each with src.io_lro.load_product,
and writes data/lro_inventory.csv.

Run from repo root:
    python scripts/build_lro_inventory.py
"""

import csv
import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.io_lro import load_product, LROReadError

DATA_DIR = "data/lro_nac"
OUT_CSV = "data/lro_inventory.csv"


def main():
    paths = sorted(glob.glob(os.path.join(DATA_DIR, "*.IMG"))) + \
            sorted(glob.glob(os.path.join(DATA_DIR, "*.img")))
    paths = sorted(set(paths))

    if not paths:
        print(f"No .IMG files found in {DATA_DIR}/ — nothing to do.")
        return

    rows = []
    for path in paths:
        print(f"Loading {path} ...")
        try:
            p = load_product(path)
        except LROReadError as e:
            print(f"  FAILED: {e}")
            continue

        lats = [c[0] for c in p.corners.values()]
        lons = [c[1] for c in p.corners.values()]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)

        rows.append({
            "product_id": p.product_id,
            "center_lat": center_lat,
            "center_lon": center_lon,
            "gsd_m": p.gsd_m,
            "incidence_deg": p.incidence_deg,
            "subsolar_azimuth_deg": p.subsolar_azimuth_deg,
            "acquired_utc": p.acquired_utc,
            "path": path,
        })
        inc_str = f"{p.incidence_deg:.1f}" if p.incidence_deg is not None else "N/A"
        print(f"  OK — incidence={inc_str} deg, gsd={p.gsd_m:.2f} m")

    os.makedirs("data", exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "product_id", "center_lat", "center_lon", "gsd_m",
            "incidence_deg", "subsolar_azimuth_deg", "acquired_utc", "path",
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} rows to {OUT_CSV}")


if __name__ == "__main__":
    main()