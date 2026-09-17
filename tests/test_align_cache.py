# tests/test_align_cache.py — align_cache.cached_align_pair against synthetic
# products with known geometry. Formalizes the ad hoc checks from Phase 1
# (docs/work_Riddhi.md) into a committed test file, per the plan's own
# methodology note: a stale or wrongly-keyed cache is worse than no cache,
# so this must exist and pass before anything real (src/pipeline.py) uses it.

import os
import pickle

import numpy as np
import pytest

import src.align_cache as align_cache
from src.align_cache import cached_align_pair, _cache_key
from src.geo import align_pair
from src.types import Product


def _product(pid, seed, gsd_m=10.0, size=32, corners=None):
    rng = np.random.default_rng(seed)
    arr = rng.random((size, size)).astype(np.float32)
    if corners is None:
        corners = {"ul": (1.0, 0.0), "ur": (1.0, 1.0), "ll": (0.0, 0.0), "lr": (0.0, 1.0)}
    return Product(array=arr, gsd_m=gsd_m, corners=corners, source="SYNTH", product_id=pid)


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    """Every test gets its own empty cache dir -- never touch the real
    data/cache/align_pairs/ dir or leak state between tests.
    """
    import src.align_cache as align_cache
    monkeypatch.setattr(align_cache, "CACHE_DIR", str(tmp_path / "align_pairs"))
    return align_cache


def test_cold_then_warm_call_return_identical_output(isolated_cache_dir):
    a, b = _product("a", 1), _product("b", 2)

    cold = cached_align_pair(a, b)
    warm = cached_align_pair(a, b)

    assert np.array_equal(cold[0].array, warm[0].array)
    assert np.array_equal(cold[1].array, warm[1].array)
    assert cold[0].corners == warm[0].corners
    assert cold[0].gsd_m == warm[0].gsd_m
    assert cold[0].product_id == warm[0].product_id


def test_cached_result_matches_uncached_align_pair(isolated_cache_dir):
    """The cache must never change *what* is returned, only how fast."""
    a, b = _product("a", 1), _product("b", 2)

    cached = cached_align_pair(a, b)
    uncached = align_pair(a, b)

    assert np.array_equal(cached[0].array, uncached[0].array)
    assert np.array_equal(cached[1].array, uncached[1].array)
    assert cached[0].corners == uncached[0].corners


def test_argument_order_is_not_collapsed_by_the_cache(isolated_cache_dir):
    """align_pair(a, b) != align_pair(b, a) in general (different tuple order,
    different _aligned product-id suffixes -- see
    tests/test_geo_align.py::test_align_pair_common_gsd_is_independent_of_argument_order).
    The cache must key on call order, not treat the pair as unordered.
    """
    a, b = _product("a", 1), _product("b", 2)

    assert _cache_key(a, b) != _cache_key(b, a)

    r_ab = cached_align_pair(a, b)
    r_ba = cached_align_pair(b, a)
    u_ab = align_pair(a, b)
    u_ba = align_pair(b, a)

    assert np.array_equal(r_ab[0].array, u_ab[0].array)
    assert np.array_equal(r_ba[0].array, u_ba[0].array)
    assert not np.array_equal(r_ab[0].array, r_ba[0].array)


def test_cache_key_changes_with_gsd(isolated_cache_dir):
    a, b = _product("a", 1, gsd_m=10.0), _product("b", 2)
    a_diff_gsd = _product("a", 1, gsd_m=20.0)

    assert _cache_key(a, b) != _cache_key(a_diff_gsd, b)


def test_cache_key_changes_with_shape_even_when_product_id_is_unchanged(isolated_cache_dir):
    """product_id alone (the plan's literal wording) isn't guaranteed to change
    if a source file were ever reprocessed under the same id -- array shape is
    folded into the key as a cheap guard against that silently serving a stale
    resample. This is the one behavior in align_cache.py that goes beyond the
    plan's literal key and must be locked down by a test.
    """
    a, b = _product("a", 1, size=32), _product("b", 2)
    a_resized = _product("a", 1, size=48)  # same product_id, different array shape

    assert _cache_key(a, b) != _cache_key(a_resized, b)


def test_non_overlapping_products_are_not_cached_and_keep_raising(isolated_cache_dir):
    a = _product("a", 1)
    far = _product("far", 3, corners={
        "ul": (91.0, 90.0), "ur": (91.0, 91.0), "ll": (90.0, 90.0), "lr": (90.0, 91.0),
    })

    key = _cache_key(a, far)
    cache_path = os.path.join(isolated_cache_dir.CACHE_DIR, f"{key}.pkl")

    with pytest.raises(ValueError):
        cached_align_pair(a, far)
    assert not os.path.exists(cache_path)

    # must raise again on a second call, never return a stale/wrong success
    with pytest.raises(ValueError):
        cached_align_pair(a, far)


def test_non_positive_gsd_is_not_cached(isolated_cache_dir):
    a = _product("a", 1)
    zero_gsd = _product("zero", 4, gsd_m=0.0)

    with pytest.raises(ValueError):
        cached_align_pair(a, zero_gsd)
    with pytest.raises(ValueError):
        cached_align_pair(a, zero_gsd)


def test_cache_dir_is_created_when_missing_including_nested_path(isolated_cache_dir, tmp_path):
    import src.align_cache as align_cache
    nested = tmp_path / "does" / "not" / "exist" / "yet"
    align_cache.CACHE_DIR = str(nested)
    assert not nested.exists()

    a, b = _product("a", 1), _product("b", 2)
    cached_align_pair(a, b)

    assert nested.is_dir()


def test_cache_key_changes_with_bs_shape_too(isolated_cache_dir):
    """Symmetric case of the shape-guard test above -- the guard must catch a
    changed *second* argument's shape as well as the first's, since align_pair
    resamples both products and either one's staleness matters equally.
    """
    a, b = _product("a", 1), _product("b", 2, size=32)
    b_resized = _product("b", 2, size=48)

    assert _cache_key(a, b) != _cache_key(a, b_resized)


def test_distinct_pairs_coexist_in_the_cache_without_collision(isolated_cache_dir):
    """Two different pairs cached into the same directory must each be
    retrievable on their own terms, not clobber or shadow one another.
    """
    a, b = _product("a", 1), _product("b", 2)
    c, d = _product("c", 3), _product("d", 4)

    r_ab = cached_align_pair(a, b)
    r_cd = cached_align_pair(c, d)

    # warm reads must still return each pair's own result, not the other's
    assert np.array_equal(cached_align_pair(a, b)[0].array, r_ab[0].array)
    assert np.array_equal(cached_align_pair(c, d)[0].array, r_cd[0].array)
    assert not np.array_equal(r_ab[0].array, r_cd[0].array)


def test_cached_sliver_overlap_matches_uncached_align_pair(isolated_cache_dir):
    """Mirrors test_geo_align.py's own edge case (an overlap smaller than one
    output pixel, near-singular grid sizing) through the cache wrapper, since
    align_cache's key computation (max(gsd) etc.) must not choke on the same
    inputs align_pair itself is already proven to handle.
    """
    size = 64
    a = _product("a", 21, gsd_m=1.0, size=size, corners={
        "ul": (1.0, 0.0), "ur": (1.0, 1.0), "ll": (0.0, 0.0), "lr": (0.0, 1.0),
    })
    b = _product("b", 22, gsd_m=1.0, size=size, corners={
        "ul": (1.999, 0.999), "ur": (1.999, 1.999), "ll": (0.999, 0.999), "lr": (0.999, 1.999),
    })

    cached = cached_align_pair(a, b)
    uncached = align_pair(a, b)

    assert cached[0].array.shape == uncached[0].array.shape
    assert np.array_equal(cached[0].array, uncached[0].array)
    assert np.all(np.isfinite(cached[0].array))


def test_pickled_round_trip_preserves_every_product_field(isolated_cache_dir):
    """The cache must not silently drop or alter any field of the aligned
    Product on the way through pickle -- dtype, meta (incl. aligned_from),
    source, and the optional metadata fields real CH2/LRO products carry.
    """
    a = Product(
        array=np.random.default_rng(1).random((16, 16)).astype(np.float32),
        gsd_m=10.0, corners={"ul": (1.0, 0.0), "ur": (1.0, 1.0), "ll": (0.0, 0.0), "lr": (0.0, 1.0)},
        source="OHRC", product_id="a", acquired_utc="2026-01-01T00:00:00Z",
        incidence_deg=42.0, subsolar_azimuth_deg=88.0, meta={"note": "real-product-like"},
    )
    b = _product("b", 2)

    cold = cached_align_pair(a, b)
    warm = cached_align_pair(a, b)

    for field in ("gsd_m", "corners", "source", "product_id", "acquired_utc",
                  "incidence_deg", "subsolar_azimuth_deg", "meta"):
        assert getattr(cold[0], field) == getattr(warm[0], field), field
    assert cold[0].array.dtype == warm[0].array.dtype == np.float32
    assert cold[0].meta.get("aligned_from") == "a"  # align_pair's own provenance tag survives


def test_a_crashed_write_never_leaves_a_readable_partial_cache_file(isolated_cache_dir, monkeypatch):
    """If pickling raises mid-write (disk full, killed process, whatever), the
    tmp-file-then-os.replace pattern must guarantee the *final* cache_path
    never exists in a partial state -- otherwise a later call could read back
    truncated/corrupt data as if it were a legitimate hit. This is the actual
    safety argument for using os.replace instead of writing cache_path
    directly, so it needs to be locked down by a test, not just asserted in
    a comment.
    """
    a, b = _product("a", 1), _product("b", 2)
    key = _cache_key(a, b)
    cache_path = os.path.join(align_cache.CACHE_DIR, f"{key}.pkl")

    class ExplodingPickle:
        HIGHEST_PROTOCOL = pickle.HIGHEST_PROTOCOL

        @staticmethod
        def dump(obj, f, protocol=None):
            f.write(b"\x00")  # simulate a partial write before the crash
            raise RuntimeError("simulated crash mid-write")

        load = staticmethod(pickle.load)

    monkeypatch.setattr(align_cache, "pickle", ExplodingPickle)

    with pytest.raises(RuntimeError):
        cached_align_pair(a, b)

    assert not os.path.exists(cache_path), "a failed write must never promote to the final cache path"


def test_a_corrupted_existing_cache_file_fails_loudly_instead_of_silently(isolated_cache_dir):
    """If the on-disk cache file is corrupt (bit rot, manual tampering, a
    pickle-protocol mismatch across a Python upgrade), cached_align_pair must
    not silently swallow the error and return garbage -- it should raise, the
    same "fail loud beats fail wrong" stance the plan's methodology note
    takes for staleness generally. Locks in current behavior so a future
    change doesn't accidentally start returning corrupted data instead.
    """
    a, b = _product("a", 1), _product("b", 2)
    key = _cache_key(a, b)
    os.makedirs(align_cache.CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(align_cache.CACHE_DIR, f"{key}.pkl")
    with open(cache_path, "wb") as f:
        f.write(b"not a valid pickle stream")

    with pytest.raises(Exception):
        cached_align_pair(a, b)
