# src/align_cache.py — on-disk cache for geo.align_pair's output.
#
# Riddhi's speed work (docs/WORK_DIVISION_PLAN.md, docs/work_Riddhi.md):
# align_pair resamples both input products onto a shared geo grid via
# full-raster warps (cv2.warpPerspective per line-geometry segment) --
# deterministic for a given pair of products at a given GSD, and currently
# recomputed from scratch on every single /register call for the same pair
# (measured ~9-17s). Same on-disk-pickle pattern as src/product_cache.py's
# already-validated product-load cache, applied one stage later in the
# pipeline.

import hashlib
import os
import pickle

from src.geo import align_pair

CACHE_DIR = os.environ.get("LUNARMATCH_ALIGN_CACHE_DIR", "data/cache/align_pairs")


def _cache_key(a, b) -> str:
    """Hash of everything align_pair's output actually depends on for a given
    call: which two products (in this order -- align_pair is not symmetric,
    see test_align_pair_common_gsd_is_independent_of_argument_order), and the
    common GSD it resamples onto (max of the two inputs' own GSDs, mirroring
    align_pair's own `gsd_common` computation).

    product_id alone would be the natural key (docs/WORK_DIVISION_PLAN.md's
    own wording), but it's sourced from label metadata (CH2 logical_identifier
    / LRO PRODUCT_ID) that isn't guaranteed to change if a source file were
    ever reprocessed under the same ID. Each input's array shape is folded in
    too as a cheap extra guard -- free to compute, and turns that scenario
    into a cache miss instead of a silently stale resample.
    """
    gsd_common = max(a.gsd_m, b.gsd_m)
    raw = (
        f"{a.product_id}:{a.array.shape}:"
        f"{b.product_id}:{b.array.shape}:"
        f"{gsd_common!r}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def cached_align_pair(a, b) -> "tuple":
    """Return align_pair(a, b), from an on-disk cache keyed by the two
    products' identity and the common GSD when available, else compute it
    once and cache it.

    Errors from align_pair itself (e.g. non-overlapping products, non-positive
    GSD) are not cached and propagate on every call, same as an uncached
    align_pair -- only a successful result is written through.
    """
    key = _cache_key(a, b)
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"{key}.pkl")

    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    result = align_pair(a, b)

    tmp_path = f"{cache_path}.{os.getpid()}.tmp"
    with open(tmp_path, "wb") as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp_path, cache_path)  # atomic on both POSIX and Windows
    return result
