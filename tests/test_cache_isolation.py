# tests/test_cache_isolation.py — proves tests/conftest.py's
# isolate_disk_caches fixture actually does its job.
#
# Phase 4 (docs/work_Riddhi.md) found that once src/pipeline.py started
# routing through src/align_cache.py, a pre-existing test in
# tests/test_match.py silently wrote a .pkl into the real
# data/cache/align_pairs/ on every full-suite run -- a hermeticity bug, not
# a git risk (data/ is gitignored) but real state leaking into the working
# tree on every test run. Fixed with an autouse conftest fixture. That fix
# was only verified by hand (`ls` before/after a full suite run) -- this
# file turns it into a committed regression test, and pushes on a few more
# edge cases: does the isolation hold with NO test-level opt-in at all
# (conftest alone, not test_align_cache.py's own extra fixture), does it
# cover product_cache.py too (the other on-disk cache conftest touches, with
# no real LRO data available to exercise it via the normal path), and does
# it survive the real cache directories not existing at all.

import glob
import os

import numpy as np

import src.align_cache as align_cache
import src.product_cache as product_cache
from src.align_cache import cached_align_pair
from src.types import Product

REAL_ALIGN_CACHE_DIR = "data/cache/align_pairs"
REAL_PRODUCT_CACHE_DIR = "data/cache/products"


def _snapshot(directory):
    return set(glob.glob(os.path.join(directory, "**", "*"), recursive=True))


def _product(pid, seed, size=16):
    rng = np.random.default_rng(seed)
    arr = rng.random((size, size)).astype(np.float32)
    corners = {"ul": (1.0, 0.0), "ur": (1.0, 1.0), "ll": (0.0, 0.0), "lr": (0.0, 1.0)}
    return Product(array=arr, gsd_m=10.0, corners=corners, source="SYNTH", product_id=pid)


def test_align_cache_dir_is_isolated_with_conftests_fixture_alone():
    """No test-level opt-in here (unlike tests/test_align_cache.py's own
    isolated_cache_dir fixture) -- relies purely on conftest.py's autouse
    fixture, proving that isolation doesn't depend on each test file
    remembering to ask for it.
    """
    assert align_cache.CACHE_DIR != REAL_ALIGN_CACHE_DIR, (
        "conftest's autouse fixture should already have repointed CACHE_DIR "
        "away from the real data/cache/align_pairs/ before this test runs"
    )

    before = _snapshot(REAL_ALIGN_CACHE_DIR) if os.path.isdir(REAL_ALIGN_CACHE_DIR) else set()
    cached_align_pair(_product("iso_a", 1), _product("iso_b", 2))
    after = _snapshot(REAL_ALIGN_CACHE_DIR) if os.path.isdir(REAL_ALIGN_CACHE_DIR) else set()

    assert before == after, "a cache write must never land in the real data/cache/align_pairs/"
    assert glob.glob(os.path.join(align_cache.CACHE_DIR, "*.pkl")), \
        "the write should still have happened, just into the isolated dir"


def test_product_cache_dir_is_isolated_with_conftests_fixture_alone(tmp_path):
    """product_cache.py's normal trigger (io_lro.load_product on a real
    .IMG file) has no real data to exercise in this environment -- but
    cached_load(path, loader) only needs `path` to exist for its mtime/size
    key, so its isolation can still be proven directly without any LRO data.
    """
    assert product_cache.CACHE_DIR != REAL_PRODUCT_CACHE_DIR

    dummy_input = tmp_path / "not_a_real_product.bin"
    dummy_input.write_bytes(b"whatever")

    before = _snapshot(REAL_PRODUCT_CACHE_DIR) if os.path.isdir(REAL_PRODUCT_CACHE_DIR) else set()
    result = product_cache.cached_load(str(dummy_input), loader=lambda: {"ok": True})
    after = _snapshot(REAL_PRODUCT_CACHE_DIR) if os.path.isdir(REAL_PRODUCT_CACHE_DIR) else set()

    assert result == {"ok": True}
    assert before == after, "a cache write must never land in the real data/cache/products/"
    assert glob.glob(os.path.join(product_cache.CACHE_DIR, "*.pkl")), \
        "the write should still have happened, just into the isolated dir"


def test_a_realistic_burst_of_cache_activity_leaves_both_real_directories_untouched(tmp_path):
    """Formalizes the manual check done while fixing this bug (`ls` on both
    real cache dirs before/after a full `pytest tests/ -q` run) into an
    automated regression test, so a future test that reintroduces the same
    leak fails loudly instead of needing another manual before/after `ls`.
    Exercises both caches several times over, several distinct keys each, to
    look more like a real suite run than a single isolated call.
    """
    align_before = _snapshot(REAL_ALIGN_CACHE_DIR) if os.path.isdir(REAL_ALIGN_CACHE_DIR) else set()
    product_before = _snapshot(REAL_PRODUCT_CACHE_DIR) if os.path.isdir(REAL_PRODUCT_CACHE_DIR) else set()

    for i in range(3):
        cached_align_pair(_product(f"burst_a{i}", i), _product(f"burst_b{i}", i + 100))
    for i in range(3):
        dummy = tmp_path / f"dummy_{i}.bin"
        dummy.write_bytes(f"dummy-{i}".encode())
        product_cache.cached_load(str(dummy), loader=lambda i=i: {"i": i})

    align_after = _snapshot(REAL_ALIGN_CACHE_DIR) if os.path.isdir(REAL_ALIGN_CACHE_DIR) else set()
    product_after = _snapshot(REAL_PRODUCT_CACHE_DIR) if os.path.isdir(REAL_PRODUCT_CACHE_DIR) else set()

    assert align_before == align_after, "real data/cache/align_pairs/ must be untouched by a test run"
    assert product_before == product_after, "real data/cache/products/ must be untouched by a test run"
