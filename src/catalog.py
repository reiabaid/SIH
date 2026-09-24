# src/catalog.py — "what overlaps this image?" answered from footprints only.
#
# The UI used to answer that by fully decoding both rasters (api.py's
# /overlap called load_product on each -- a multi-GB CH2 decode, uncropped,
# on every pair selection) and by a hard-coded list of pair cards. Footprint
# overlap needs only four corner coordinates per product, so this module
# reads those and never touches pixels:
#   - CH2: parsed straight from the PDS4 label XML (cheap, exact).
#   - LRO: corners come from SPICE geometry that is only known after the
#     product has been loaded once, so they are recorded in a small JSON
#     sidecar at that point (io_lro.load_product does this) and read from
#     there afterwards.

import hashlib
import json
import os
import xml.etree.ElementTree as ET

from shapely.geometry import Polygon

FOOTPRINT_DIR = os.environ.get("LUNARMATCH_FOOTPRINT_DIR", "data/cache/footprints")
_ORDER = ("ul", "ur", "lr", "ll")  # walked in this order so the polygon never self-intersects


def is_ch2(product_id: str) -> bool:
    return "ch2" in (product_id or "").lower()


def _sidecar_path(data_path: str) -> str:
    st = os.stat(data_path)
    key = hashlib.sha256(f"{os.path.abspath(data_path)}:{st.st_mtime_ns}:{st.st_size}".encode()).hexdigest()
    return os.path.join(FOOTPRINT_DIR, f"{key}.json")


def _degenerate(corners: dict) -> bool:
    """LRO geometry that failed to resolve comes back as all-(0,0) corners."""
    return all(abs(v[0]) < 1e-9 and abs(v[1]) < 1e-9 for v in corners.values())


def record_footprint(data_path: str, product) -> None:
    """Store a loaded product's footprint (and the metadata resolved with it)
    next to the caches, keyed by the file's path/mtime/size. Skips degenerate
    (0,0) corners so a load done while geometry was unavailable doesn't
    poison the sidecar -- it stays absent and is recorded on a later good load.
    """
    if _degenerate(product.corners):
        return
    path = _sidecar_path(data_path)
    if os.path.exists(path):
        return
    os.makedirs(FOOTPRINT_DIR, exist_ok=True)
    payload = {
        "corners": {k: list(v) for k, v in product.corners.items()},
        "gsd_m": product.gsd_m,
        "incidence_deg": product.incidence_deg,
        "subsolar_azimuth_deg": product.subsolar_azimuth_deg,
        "acquired_utc": product.acquired_utc,
    }
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.replace(tmp, path)


def _ch2_label_corners(label_path: str):
    from src.io_ch2 import _parse_corners
    return _parse_corners(ET.parse(label_path).getroot(), label_path)


def footprint(product_id: str, path: str):
    """{"corners": {ul,ur,lr,ll: (lat, lon)}, ...metadata} or None if this
    product's footprint isn't known yet (an LRO product not loaded once)."""
    try:
        if is_ch2(product_id):
            return {"corners": _ch2_label_corners(path)}
        sidecar = _sidecar_path(path)
        if not os.path.exists(sidecar):
            return None
        with open(sidecar) as f:
            info = json.load(f)
        info["corners"] = {k: tuple(v) for k, v in info["corners"].items()}
        return info
    except (OSError, ET.ParseError, KeyError, ValueError):
        return None


def _polygon(corners: dict) -> Polygon:
    return Polygon([(corners[k][1], corners[k][0]) for k in _ORDER])  # (lon, lat)


def overlap_fractions(corners_a: dict, corners_b: dict):
    """(fraction of A covered by B, fraction of B covered by A), each in [0, 1]."""
    pa, pb = _polygon(corners_a), _polygon(corners_b)
    if not pa.is_valid or not pb.is_valid or pa.area == 0 or pb.area == 0:
        return 0.0, 0.0
    inter = pa.intersection(pb).area
    return inter / pa.area, inter / pb.area


def rank_candidates(product_id: str, inventory: dict, min_overlap: float = 0.0):
    """Rank products of the OTHER instrument by footprint overlap with
    `product_id`. `inventory` maps product_id -> {"path": ..., **row metadata}.

    Returns (candidates, not_ingested): candidates sorted by the fraction of
    the query product they cover, best first; not_ingested counts products
    whose footprint isn't known yet, so a caller can say so instead of
    silently presenting a shorter list as if it were complete.
    """
    query = inventory.get(product_id)
    if query is None:
        raise KeyError(product_id)
    query_fp = footprint(product_id, query["path"])
    if query_fp is None:
        return [], 0

    want_ch2 = not is_ch2(product_id)
    candidates, not_ingested = [], 0
    for pid, entry in inventory.items():
        if pid.startswith("synthetic_") or is_ch2(pid) != want_ch2:
            continue
        fp = footprint(pid, entry["path"])
        if fp is None or _degenerate(fp["corners"]):
            not_ingested += 1
            continue
        covers_query, covers_candidate = overlap_fractions(query_fp["corners"], fp["corners"])
        if covers_query <= min_overlap:
            continue
        meta = {**{k: v for k, v in entry.items() if k != "path"}, **{k: v for k, v in fp.items() if k != "corners"}}
        candidates.append({
            "product_id": pid,
            "overlap_percent": round(covers_query * 100, 1),          # of the query image
            "candidate_covered_percent": round(covers_candidate * 100, 1),
            "acquired_utc": meta.get("acquired_utc"),
            "incidence_deg": meta.get("incidence_deg"),
            "gsd_m": meta.get("gsd_m"),
        })
    candidates.sort(key=lambda c: c["overlap_percent"], reverse=True)
    return candidates, not_ingested
