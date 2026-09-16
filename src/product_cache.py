# src/product_cache.py — on-disk cache for loaded Product objects.
#
# Reia's speed work (docs/WORK_DIVISION_PLAN.md): profiling
# (scripts/profile_pipeline.py, docs/research/pipeline_time_breakdown.json)
# found that loading the two input products dominates a default job's wall
# time -- 67-72% measured on real pairs. io_ch2.load_product decodes a large
# raster from scratch every call (~17-21s), and io_lro.load_product
# additionally hits NAIF WebGeocalc over the network for geometry
# (~35-48s). Neither result changes for a fixed input file, so caching the
# fully-loaded Product on disk, keyed by the input path's own mtime/size
# (so an edited or replaced file invalidates the cache instead of silently
# serving stale data), removes that cost entirely on a repeat load.

import hashlib
import os
import pickle

CACHE_DIR = os.environ.get("LUNARMATCH_PRODUCT_CACHE_DIR", "data/cache/products")


def _cache_key(path: str) -> str:
    st = os.stat(path)
    raw = f"{os.path.abspath(path)}:{st.st_mtime_ns}:{st.st_size}"
    return hashlib.sha256(raw.encode()).hexdigest()


def cached_load(path: str, loader):
    """Return loader() for `path`, from an on-disk cache keyed by `path`'s
    own mtime/size when available, else compute it once and cache it.

    `path` should be the primary input file the caller already treats as
    the identity of the product (e.g. a CH2 product's .xml label, an LRO
    product's .IMG file) -- a companion file changing without that primary
    file's mtime changing (e.g. a paired .img next to an untouched .xml)
    won't be caught by this key. Acceptable here since these are immutable,
    paired-at-download product files, not files edited independently later.

    A `path` that doesn't exist (or can't be stat'd) skips caching entirely
    and calls `loader()` directly, so callers' own existence checks still
    run and raise their own domain-specific error (LabelParseError,
    LROReadError, ...) instead of a raw FileNotFoundError from os.stat here.
    """
    try:
        key = _cache_key(path)
    except OSError:
        return loader()

    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"{key}.pkl")

    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    product = loader()

    tmp_path = f"{cache_path}.{os.getpid()}.tmp"
    with open(tmp_path, "wb") as f:
        pickle.dump(product, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp_path, cache_path)  # atomic on both POSIX and Windows
    return product
