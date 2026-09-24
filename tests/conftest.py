# tests/conftest.py — keep the test suite from writing into the real
# data/cache/ directory.
#
# Found while validating Phase 3 (docs/work_Riddhi.md): src/pipeline.py's
# run_pipeline(align=True) now goes through src/align_cache.py's on-disk
# cache. tests/test_match.py's pre-existing
# test_pipeline_align_true_returns_points_in_each_products_own_pixel_space
# calls run_pipeline(align=True) directly without isolating the cache dir --
# harmless before Phase 3 (align_pair was uncached), but after it, every
# full-suite run silently wrote a .pkl into the real
# data/cache/align_pairs/. Not a git risk (data/ is gitignored) but a real
# hermeticity bug: repeated test runs accumulate stray state in the working
# tree instead of a clean run leaving no trace. Isolating this at the
# conftest level (autouse, session-wide) rather than patching that one test
# so no *future* align=True test can reintroduce the same leak.

import pytest

import src.align_cache as align_cache
import src.catalog as catalog
import src.product_cache as product_cache


@pytest.fixture(autouse=True)
def isolate_disk_caches(tmp_path, monkeypatch):
    """Every test gets its own empty, disposable cache directories for both
    on-disk caches (align_cache and product_cache) -- never the real
    data/cache/ tree. Tests that want to assert something about caching
    behavior itself (tests/test_align_cache.py, tests/test_pipeline_align_cache.py)
    already set up their own isolation on top of this; this fixture's job is
    just to make sure no test, present or future, can leak a cache file into
    the working tree by omission.
    """
    monkeypatch.setattr(align_cache, "CACHE_DIR", str(tmp_path / "align_pairs"))
    monkeypatch.setattr(product_cache, "CACHE_DIR", str(tmp_path / "products"))
    monkeypatch.setattr(catalog, "FOOTPRINT_DIR", str(tmp_path / "footprints"))
