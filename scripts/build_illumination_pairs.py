"""
scripts/build_illumination_pairs.py

Reads data/lro_inventory.csv, enumerates every pair of products, and writes
demo/illumination_pairs.csv sorted by incidence-angle difference ascending.

Run from repo root, after build_lro_inventory.py:
    python scripts/build_illumination_pairs.py
"""

import csv
import itertools
import os

IN_CSV = "data/lro_inventory.csv"
OUT_CSV = "demo/illumination_pairs.csv"


def main():
    if not os.path.exists(IN_CSV):
        print(f"{IN_CSV} not found — run scripts/build_lro_inventory.py first.")
        return

    with open(IN_CSV, newline="") as f:
        rows = list(csv.DictReader(f))

    if len(rows) < 2:
        print(f"Only {len(rows)} product(s) in inventory — need at least 2 to form a pair.")
        return

    pairs = []
    for a, b in itertools.combinations(rows, 2):
        inc_a = float(a["incidence_deg"]) if a["incidence_deg"] not in ("", "None", None) else 0.0
        inc_b = float(b["incidence_deg"]) if b["incidence_deg"] not in ("", "None", None) else 0.0
        pairs.append({
            "pair_id": f"{a['product_id']}__{b['product_id']}",
            "product_a": a["product_id"],
            "product_b": b["product_id"],
            "path_a": a["path"],
            "path_b": b["path"],
            "incidence_a_deg": inc_a,
            "incidence_b_deg": inc_b,
            "incidence_diff_deg": abs(inc_a - inc_b),
        })

    pairs.sort(key=lambda r: r["incidence_diff_deg"])

    os.makedirs("demo", exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "pair_id", "product_a", "product_b", "path_a", "path_b",
            "incidence_a_deg", "incidence_b_deg", "incidence_diff_deg",
        ])
        writer.writeheader()
        writer.writerows(pairs)

    print(f"Wrote {len(pairs)} pairs to {OUT_CSV}")
    print("Smallest incidence gap:", pairs[0]["pair_id"], f"{pairs[0]['incidence_diff_deg']:.1f} deg")
    print("Largest incidence gap: ", pairs[-1]["pair_id"], f"{pairs[-1]['incidence_diff_deg']:.1f} deg")


if __name__ == "__main__":
    main()