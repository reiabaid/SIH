# tests/test_pipeline_align_cache.py — Phase 3 integration: does
# run_pipeline(align=True) actually use align_cache.cached_align_pair
# correctly, not just "does align_cache work in isolation" (that's Phase 2's
# job, tests/test_align_cache.py). Per docs/work_Riddhi.md's Phase 3 note,
# comparing run_pipeline's final match output directly across cold/warm runs
# is unreliable on synthetic input -- match()'s own SIFT/RANSAC behavior
# showed run-to-run count variation on featureless random noise, independent
# of alignment entirely. So most tests here replace the matcher with a fixed
# deterministic stub, isolating "did the cache wiring behave correctly" from
# "is SIFT deterministic on this input" (a different, already-flagged
# question that belongs to Reia's match.py, not this integration).

import glob
import os

import numpy as np
import pytest

import src.align_cache as align_cache
import src.geo as geo
import src.pipeline as pipeline
from src.pipeline import run_pipeline
from src.types import MatchResult, Product


def _product_for_square_deg(size, lat0, lat1, lon0, lon1, gsd_m, pid, seed):
    rng = np.random.default_rng(seed)
    arr = rng.random((size, size)).astype(np.float32)
    corners = {"ul": (lat1, lon0), "ur": (lat1, lon1), "ll": (lat0, lon0), "lr": (lat0, lon1)}
    return Product(array=arr, gsd_m=gsd_m, corners=corners, source="SYNTH", product_id=pid)


def _pair(pid_a="a", pid_b="b", size=64):
    """A degree-span picked to match `size` at a sane GSD (same self-consistent
    pattern as tests/test_geo_align.py) -- an arbitrary gsd_m against a whole
    degree of lat/lon would make align_pair resample onto a many-thousand-pixel
    grid (a 1deg span is ~30km on the Moon; at a real few-m/px GSD that's
    thousands of output pixels), which is both pointlessly slow for a unit
    test and not what any real CH2/LRO product's footprint looks like.
    """
    m_per_deg_lat = geo.MOON_RADIUS_M * np.pi / 180.0
    lat0, lat1, lon0, lon1 = 0.0, 0.001, 0.0, 0.001
    gsd_m = (lat1 - lat0) / (size - 1) * m_per_deg_lat
    return (
        _product_for_square_deg(size, lat0, lat1, lon0, lon1, gsd_m, pid_a, seed=1),
        _product_for_square_deg(size, lat0, lat1, lon0, lon1, gsd_m, pid_b, seed=2),
    )


def _stub_match(a, b, matcher="sift", rung=0):
    """Fixed-output stand-in for src.match.match -- removes matcher-level
    randomness entirely so these tests isolate the align-cache wiring.
    """
    return MatchResult(
        pts_a=np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
        pts_b=np.array([[1.5, 2.5], [3.5, 4.5]], dtype=np.float32),
        scores=np.array([0.9, 0.8], dtype=np.float32),
        inlier_mask=np.array([True, True]),
        transform=np.eye(3, dtype=np.float64),
        matcher=matcher, shape_a=a.shape, shape_b=b.shape, runtime_s=0.0,
    )


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(align_cache, "CACHE_DIR", str(tmp_path / "align_pairs"))
    return align_cache


@pytest.fixture(autouse=True)
def stub_matcher(monkeypatch):
    monkeypatch.setattr(pipeline, "run_match", _stub_match)


@pytest.fixture()
def counted_align_pair(monkeypatch):
    """Wrap the real geo.align_pair (the function align_cache falls through
    to on a miss) with a call counter, so tests can assert exactly how many
    times real alignment work happened -- the only reliable signal for
    "was this a cache hit", since a hit and a miss otherwise look identical
    from the outside by design (Phase 1's whole point).
    """
    real_align_pair = geo.align_pair
    counter = {"n": 0}

    def counting(a, b):
        counter["n"] += 1
        return real_align_pair(a, b)

    monkeypatch.setattr(align_cache, "align_pair", counting)
    return counter


def test_second_align_true_call_is_a_genuine_cache_hit(counted_align_pair):
    a, b = _pair()

    run_pipeline(a, b, matcher="sift", rung=0, align=True)
    assert counted_align_pair["n"] == 1

    run_pipeline(a, b, matcher="sift", rung=0, align=True)
    assert counted_align_pair["n"] == 1, "second call must not recompute alignment"


def test_align_false_never_touches_align_pair_or_the_cache(counted_align_pair):
    a, b = _pair()

    run_pipeline(a, b, matcher="sift", rung=0, align=False)
    run_pipeline(a, b, matcher="sift", rung=0, align=False)

    assert counted_align_pair["n"] == 0
    assert not glob.glob(os.path.join(align_cache.CACHE_DIR, "*.pkl"))


def test_pipeline_output_is_identical_across_cold_and_warm_cache():
    """With the matcher stubbed to a fixed output, the only thing that can
    differ between a cold and a warm run is the align-cache wiring itself --
    if the coordinate-inversion math (original_pixel_transform,
    to_original_pixels) or shape bookkeeping behaved differently against a
    freshly-computed vs. a pickled-and-reloaded aligned Product, this would
    catch it.
    """
    a, b = _pair()

    cold = run_pipeline(a, b, matcher="sift", rung=0, align=True)
    warm = run_pipeline(a, b, matcher="sift", rung=0, align=True)

    np.testing.assert_array_equal(cold["match_result"]["pts_a"], warm["match_result"]["pts_a"])
    np.testing.assert_array_equal(cold["match_result"]["pts_b"], warm["match_result"]["pts_b"])
    np.testing.assert_array_equal(cold["match_result"]["transform"], warm["match_result"]["transform"])
    assert cold["match_result"]["shape_a"] == warm["match_result"]["shape_a"]
    assert cold["match_result"]["shape_b"] == warm["match_result"]["shape_b"]
    assert cold["product_a_id"] == warm["product_a_id"] == "a"
    assert cold["product_b_id"] == warm["product_b_id"] == "b"


def test_align_true_still_raises_on_non_overlapping_products(counted_align_pair):
    """The cache wiring must not swallow or alter align_pair's own error --
    same behavior as calling align_pair directly, just routed through the
    cache first."""
    a = _product_for_square_deg(32, 0.0, 1.0, 0.0, 1.0, 10.0, "a", seed=1)
    far = _product_for_square_deg(32, 50.0, 51.0, 50.0, 51.0, 10.0, "far", seed=2)

    with pytest.raises(ValueError):
        run_pipeline(a, far, matcher="sift", rung=0, align=True)

    # must keep raising on a second call too, not cache a partial/wrong result
    with pytest.raises(ValueError):
        run_pipeline(a, far, matcher="sift", rung=0, align=True)
    assert counted_align_pair["n"] == 2


def test_tiling_decision_is_consistent_across_cold_and_warm_cache(monkeypatch):
    """run_pipeline picks match_tiled vs. match based on the *aligned*
    product's shape (TILE_THRESHOLD_PX). That shape has to come out of the
    cache identically to a freshly-computed align_pair for this branch to
    stay stable across cold/warm calls -- lowers TILE_THRESHOLD_PX so a small
    synthetic pair exercises the tiled path cheaply, and stubs match_tiled
    itself (real tiled SIFT is neither fast nor the thing under test here).
    """
    tiled_calls = []

    def stub_tiled(a, b, matcher="sift", rung=0, tile_size=None, overlap=None):
        tiled_calls.append(a.shape)
        return _stub_match(a, b, matcher=matcher, rung=rung)

    monkeypatch.setattr(pipeline, "TILE_THRESHOLD_PX", 8)
    monkeypatch.setattr(pipeline, "match_tiled", stub_tiled)

    a, b = _pair(size=32)  # aligned output will exceed the lowered 8px threshold

    run_pipeline(a, b, matcher="sift", rung=0, align=True)
    run_pipeline(a, b, matcher="sift", rung=0, align=True)

    assert len(tiled_calls) == 2, "both calls should take the tiled path"
    assert tiled_calls[0] == tiled_calls[1], "aligned shape must match between cold and warm cache"


def test_two_different_pairs_do_not_cross_contaminate_through_the_pipeline(counted_align_pair):
    a, b = _pair(pid_a="a", pid_b="b")
    c, d = _pair(pid_a="c", pid_b="d")

    out_ab = run_pipeline(a, b, matcher="sift", rung=0, align=True)
    out_cd = run_pipeline(c, d, matcher="sift", rung=0, align=True)
    assert counted_align_pair["n"] == 2, "two distinct pairs are two distinct cache misses"

    # re-running each must hit its own cache entry, not the other pair's
    out_ab_warm = run_pipeline(a, b, matcher="sift", rung=0, align=True)
    out_cd_warm = run_pipeline(c, d, matcher="sift", rung=0, align=True)
    assert counted_align_pair["n"] == 2, "warm re-runs of both pairs must not recompute either"

    assert out_ab_warm["product_a_id"] == out_ab["product_a_id"] == "a"
    assert out_cd_warm["product_a_id"] == out_cd["product_a_id"] == "c"
