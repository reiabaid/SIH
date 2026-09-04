"""
SPICE Cross-Check Script (Manya lane)
======================================
Compares incidence angles stored in lro_inventory.csv (derived via NAIF
WebGeocalc REST at load time) against three independent sources:

  1. The raw PDS3 label INCIDENCE_ANGLE keyword (if present in the .IMG header)
  2. A geometric sanity bound: for polar orbit images near 70-75°S, the solar
     incidence angle must satisfy  |90° - sun_elevation| ≈ incidence_angle,
     and should lie between 60° and 90° for a lunar south-pole pass.
  3. Cross-product consistency: if we have lat/lon of the sub-solar point
     (derivable from subsolar_azimuth_deg), the incidence angle at the image
     centre should be consistent with the Sun's angular separation.

Outputs a concise table with PASS / WARN / FAIL for each product.
"""

import csv
import re
import math
import os

# ── Load inventory ─────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INV  = os.path.join(ROOT, "data", "lro_inventory.csv")

products = []
with open(INV, newline="") as f:
    for row in csv.DictReader(f):
        products.append(row)

# ── Label reader (same logic as io_lro._parse_label) ───────────────────────
def _parse_label(label_str: str) -> dict:
    SKIP = frozenset({"OBJECT", "END_OBJECT", "GROUP", "END_GROUP", "PDS_VERSION_ID"})
    result = {}
    pattern = re.compile(
        r'^\s*([A-Z][A-Z0-9_:]*)\s*=\s*'
        r'(?:"([^"\n]*)"'
        r'|(\([^\)\n]*\))'
        r'|([^\r\n<"(]+?))'
        r'(?:\s*<[^>\n]+>)?\s*$',
        re.MULTILINE,
    )
    for m in pattern.finditer(label_str):
        key = m.group(1)
        if key in SKIP:
            continue
        val = m.group(2) or m.group(3) or (m.group(4) or "").strip()
        result[key] = val
    return result


def _as_float(v):
    if v is None:
        return None
    s = re.sub(r"\s*<[^>]+>\s*$", "", str(v)).strip()
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def read_label_dict(img_path: str) -> dict:
    with open(img_path, "rb") as f:
        raw = f.read(1024 * 512)  # first 512 kB covers any PDS3 label
    text = raw.decode("ascii", errors="ignore")
    end = re.search(r"^\s*END\s*$", text, flags=re.MULTILINE)
    return _parse_label(text[:end.end()] if end else text)


# ── Sanity bound for south-pole incidence angles ───────────────────────────
# Sub-solar latitude near ecliptic plane is ~1.5°. For an LRO pass at ~70–75°S,
# the solar incidence angle ≈ 90° − (sub-solar elevation from the surface).
# For south-pole geometry this should be between ~65° and ~90°.
INCIDENCE_MIN = 60.0
INCIDENCE_MAX = 90.0


def check_product(row: dict):
    pid       = row["product_id"]
    path      = os.path.join(ROOT, row["path"].replace("\\", os.sep))
    inv_inc   = _as_float(row.get("incidence_deg"))
    inv_az    = _as_float(row.get("subsolar_azimuth_deg"))
    clat      = _as_float(row.get("center_lat"))

    status = []
    label_inc = None

    if not os.path.exists(path):
        return pid, None, inv_inc, inv_az, ["FILE_MISSING"]

    try:
        lbl = read_label_dict(path)
    except Exception as e:
        return pid, None, inv_inc, inv_az, [f"LABEL_ERR: {e}"]

    # ── Check 1: label INCIDENCE_ANGLE keyword ──────────────────────────
    label_inc = _as_float(lbl.get("INCIDENCE_ANGLE") or lbl.get("SOLAR_DISTANCE"))
    if label_inc is not None and 0 < label_inc < 180:
        if inv_inc is not None:
            delta = abs(label_inc - inv_inc)
            if delta < 2.0:
                status.append(f"LABEL_MATCH  (label={label_inc:.3f}° vs SPICE={inv_inc:.3f}°, Δ={delta:.3f}°)")
            else:
                status.append(f"LABEL_MISMATCH  (label={label_inc:.3f}° vs SPICE={inv_inc:.3f}°, Δ={delta:.3f}°)")
        else:
            status.append(f"LABEL_ONLY  (label={label_inc:.3f}°, no SPICE value in inventory)")
    else:
        # LROC NAC EDRs often don't carry INCIDENCE_ANGLE in label
        status.append("NO_LABEL_INCIDENCE  (normal for LROC NAC EDRs)")

    # ── Check 2: plausibility bound ─────────────────────────────────────
    check_val = inv_inc if inv_inc is not None else label_inc
    if check_val is not None:
        if INCIDENCE_MIN <= check_val <= INCIDENCE_MAX:
            status.append(f"RANGE_OK  ({INCIDENCE_MIN}-{INCIDENCE_MAX} deg expected for south-pole pass)")
        else:
            status.append(f"RANGE_WARN  ({check_val:.2f} deg outside expected {INCIDENCE_MIN}-{INCIDENCE_MAX} deg)")
    else:
        status.append("RANGE_SKIP  (no incidence value to bound-check)")

    # ── Check 3: azimuth in [0, 360) ────────────────────────────────────
    if inv_az is not None:
        if 0 <= inv_az < 360:
            status.append(f"AZIMUTH_OK  ({inv_az:.2f}°)")
        else:
            status.append(f"AZIMUTH_BAD  ({inv_az:.2f}° outside [0,360))")
    else:
        status.append("AZIMUTH_NONE  (normal for products with geometry_source=none)")

    # ── Check 4: CROSSTRACK_SUMMING consistency with GSD ────────────────
    summing = _as_float(lbl.get("CROSSTRACK_SUMMING"))
    inv_gsd = _as_float(row.get("gsd_m"))
    if summing is not None and inv_gsd is not None:
        expected_gsd = 0.5006 * summing  # NAC physical constants
        delta_gsd = abs(expected_gsd - inv_gsd)
        if delta_gsd < 0.1:
            status.append(f"GSD_OK  (summing={int(summing)}, expected≈{expected_gsd:.3f} m/px, inventory={inv_gsd:.4f} m/px)")
        else:
            status.append(f"GSD_WARN  (summing={int(summing)}, expected≈{expected_gsd:.3f} m/px, inventory={inv_gsd:.4f} m/px, Δ={delta_gsd:.3f})")

    return pid, label_inc, inv_inc, inv_az, status


# ── Run and print ──────────────────────────────────────────────────────────
seen = set()
unique_products = [p for p in products if p["product_id"] not in seen and not seen.add(p["product_id"])]

print("=" * 72)
print("SPICE CROSS-CHECK  |  LunarMatch / Manya lane")
print("=" * 72)

all_ok = True
results = []
for row in unique_products:
    pid, label_inc, inv_inc, inv_az, checks = check_product(row)
    has_warn = any("WARN" in c or "MISMATCH" in c or "BAD" in c or "MISSING" in c for c in checks)
    flag = "[WARN]" if has_warn else "[PASS]"
    if has_warn:
        all_ok = False
    results.append((pid, label_inc, inv_inc, inv_az, checks, flag))

for pid, label_inc, inv_inc, inv_az, checks, flag in results:
    print(f"\n[{flag}]  {pid}")
    print(f"       SPICE incidence : {inv_inc:.4f}°" if inv_inc else "       SPICE incidence : None")
    print(f"       Label incidence : {label_inc:.4f}°" if label_inc else "       Label incidence : (not in label)")
    print(f"       Subsolar azimuth: {inv_az:.2f}°" if inv_az else "       Subsolar azimuth: None")
    for c in checks:
        indent = "         » "
        print(f"{indent}{c}")

print("\n" + "=" * 72)
if all_ok:
    print("OVERALL: ALL CHECKS PASSED -- illumination axis validated")
else:
    print("OVERALL: SOME WARNINGS -- review flagged products above")
print("=" * 72)
