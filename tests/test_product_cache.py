"""tests/test_product_cache.py

Unit and regression tests for src/product_cache.py (Shivani's secondary test coverage
for the ingestion caching layer landed by Riddhi and Manya).

Verifies:
- Cache miss calls loader and stores result atomically on disk.
- Cache hit returns identical result without re-invoking loader.
- Byte-identical preservation of all Product fields across pickle serialization.
- Cache miss falls back correctly when file does not exist (skips caching, calls loader).
- Loader exceptions are not cached and propagate properly.
- Cache key invalidation when file mtime or file size changes.
- Atomic write safety: simulated crash during write leaves no partial cache files.
- Corrupted cache files fail loudly rather than returning silent errors.
- Distinct paths produce isolated cache keys without collision.
"""

import os
import pickle
import time
import numpy as np
import pytest

from src.geo import Product
from src.product_cache import cached_load, _cache_key, CACHE_DIR


def _make_dummy_product(product_id="test_prod_1", size=32):
    array = np.arange(size * size, dtype=np.float32).reshape(size, size)
    corners = {
        "ul": (-73.45, 42.70), "ur": (-73.45, 42.80),
        "ll": (-73.55, 42.70), "lr": (-73.55, 42.80),
    }
    meta = {
        "incidence_deg": 45.0,
        "subsolar_azimuth_deg": 120.0,
        "acquired_utc": "2024-01-01T00:00:00Z",
    }
    return Product(
        array=array,
        gsd_m=2.5,
        corners=corners,
        source="TEST_LRO",
        product_id=product_id,
        meta=meta,
    )


def test_product_cache_miss_calls_loader_and_writes_cache(tmp_path):
    target_file = tmp_path / "product_source.img"
    target_file.write_bytes(b"sample product payload 12345")
    
    loader_calls = 0
    expected_product = _make_dummy_product("prod_miss")

    def dummy_loader():
        nonlocal loader_calls
        loader_calls += 1
        return expected_product

    result = cached_load(str(target_file), dummy_loader)

    assert loader_calls == 1
    assert result.product_id == "prod_miss"
    assert np.array_equal(result.array, expected_product.array)

    # Check cache directory contains exactly one cache entry
    key = _cache_key(str(target_file))
    cache_file = tmp_path / "products" / f"{key}.pkl"
    # Note: tmp_path / "products" is configured by tests/conftest.py fixture
    assert cache_file.exists() or os.path.exists(os.path.join(CACHE_DIR, f"{key}.pkl"))


def test_product_cache_hit_returns_same_result_without_reinvoking_loader(tmp_path):
    target_file = tmp_path / "product_hit.img"
    target_file.write_bytes(b"sample product payload hit")

    loader_calls = 0
    expected_product = _make_dummy_product("prod_hit")

    def dummy_loader():
        nonlocal loader_calls
        loader_calls += 1
        return expected_product

    # First call: cache miss
    first_res = cached_load(str(target_file), dummy_loader)
    assert loader_calls == 1

    # Second call: cache hit
    second_res = cached_load(str(target_file), dummy_loader)
    assert loader_calls == 1  # Loader must not have been invoked again
    assert np.array_equal(first_res.array, second_res.array)
    assert first_res.product_id == second_res.product_id
    assert first_res.gsd_m == second_res.gsd_m
    assert first_res.corners == second_res.corners


def test_product_cache_hit_preserves_all_product_attributes_byte_identical(tmp_path):
    target_file = tmp_path / "product_roundtrip.img"
    target_file.write_bytes(b"content for roundtrip")

    original = _make_dummy_product("prod_full_fidelity")
    cached = cached_load(str(target_file), lambda: original)
    from_cache = cached_load(str(target_file), lambda: None)

    assert np.array_equal(from_cache.array, original.array)
    assert from_cache.array.dtype == original.array.dtype
    assert from_cache.gsd_m == original.gsd_m
    assert from_cache.corners == original.corners
    assert from_cache.source == original.source
    assert from_cache.product_id == original.product_id
    assert from_cache.meta == original.meta


def test_product_cache_miss_falls_back_correctly_on_nonexistent_file():
    missing_file = "data/nonexistent_file_xyz_12345.IMG"
    loader_calls = 0

    def failing_loader():
        nonlocal loader_calls
        loader_calls += 1
        raise FileNotFoundError(f"Underlying loader cannot find {missing_file}")

    with pytest.raises(FileNotFoundError, match="Underlying loader cannot find"):
        cached_load(missing_file, failing_loader)

    assert loader_calls == 1


def test_product_cache_loader_exception_does_not_cache_failure(tmp_path):
    target_file = tmp_path / "flaky_product.img"
    target_file.write_bytes(b"flaky content")

    loader_calls = 0

    def flaky_loader():
        nonlocal loader_calls
        loader_calls += 1
        if loader_calls == 1:
            raise RuntimeError("Temporary network timeout querying WebGeocalc")
        return _make_dummy_product("flaky_recovered")

    # Call 1 fails
    with pytest.raises(RuntimeError, match="Temporary network timeout"):
        cached_load(str(target_file), flaky_loader)

    assert loader_calls == 1

    # Call 2 succeeds, showing failure was not stored as a cache entry
    result = cached_load(str(target_file), flaky_loader)
    assert loader_calls == 2
    assert result.product_id == "flaky_recovered"


def test_product_cache_invalidates_when_mtime_changes(tmp_path):
    target_file = tmp_path / "mtime_test.img"
    target_file.write_bytes(b"original data")

    loader_calls = 0

    def versioned_loader():
        nonlocal loader_calls
        loader_calls += 1
        return _make_dummy_product(f"version_{loader_calls}")

    # First call
    res1 = cached_load(str(target_file), versioned_loader)
    assert loader_calls == 1
    assert res1.product_id == "version_1"

    # Simulate external file update by changing mtime
    st = os.stat(str(target_file))
    future_mtime = st.st_mtime + 5.0
    os.utime(str(target_file), (future_mtime, future_mtime))

    # Second call must invalidate cache and reload
    res2 = cached_load(str(target_file), versioned_loader)
    assert loader_calls == 2
    assert res2.product_id == "version_2"


def test_product_cache_invalidates_when_filesize_changes(tmp_path):
    target_file = tmp_path / "filesize_test.img"
    target_file.write_bytes(b"short data")

    loader_calls = 0

    def versioned_loader():
        nonlocal loader_calls
        loader_calls += 1
        return _make_dummy_product(f"size_v_{loader_calls}")

    res1 = cached_load(str(target_file), versioned_loader)
    assert loader_calls == 1

    # Append data to change file size
    with open(target_file, "ab") as f:
        f.write(b" -- appended extra bytes")

    res2 = cached_load(str(target_file), versioned_loader)
    assert loader_calls == 2
    assert res2.product_id == "size_v_2"


def test_product_cache_atomic_write_prevents_partial_file_on_crash(tmp_path, monkeypatch):
    target_file = tmp_path / "crash_test.img"
    target_file.write_bytes(b"crash simulation payload")

    def crashing_dump(obj, f, protocol=None):
        f.write(b"partial corrupted stream")
        raise IOError("Disk full or process killed mid-dump")

    monkeypatch.setattr(pickle, "dump", crashing_dump)

    product = _make_dummy_product("crash_prod")
    with pytest.raises(IOError, match="Disk full or process killed"):
        cached_load(str(target_file), lambda: product)

    # Key cache path must NOT exist
    key = _cache_key(str(target_file))
    from src.product_cache import CACHE_DIR
    cache_path = os.path.join(CACHE_DIR, f"{key}.pkl")
    assert not os.path.exists(cache_path), "Partial cache file was left behind after crashed write"


def test_product_cache_corrupted_file_fails_loudly(tmp_path):
    target_file = tmp_path / "corrupt_test.img"
    target_file.write_bytes(b"valid source file")

    key = _cache_key(str(target_file))
    from src.product_cache import CACHE_DIR
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"{key}.pkl")

    # Pre-write invalid pickle bytes to simulate disk corruption
    with open(cache_path, "wb") as f:
        f.write(b"GARBAGE_NOT_A_PICKLE_STREAM_12345")

    with pytest.raises((pickle.UnpicklingError, EOFError, AttributeError)):
        cached_load(str(target_file), lambda: _make_dummy_product("unused"))


def test_product_cache_independent_paths_do_not_collide(tmp_path):
    file_a = tmp_path / "path_a.img"
    file_b = tmp_path / "path_b.img"

    file_a.write_bytes(b"content a")
    file_b.write_bytes(b"content b")

    prod_a = _make_dummy_product("prod_a")
    prod_b = _make_dummy_product("prod_b")

    res_a = cached_load(str(file_a), lambda: prod_a)
    res_b = cached_load(str(file_b), lambda: prod_b)

    assert res_a.product_id == "prod_a"
    assert res_b.product_id == "prod_b"
    assert res_a.product_id != res_b.product_id

    # Verify both are independently cached
    hit_a = cached_load(str(file_a), lambda: None)
    hit_b = cached_load(str(file_b), lambda: None)
    assert hit_a.product_id == "prod_a"
    assert hit_b.product_id == "prod_b"

