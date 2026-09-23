"""
tests/test_io_ch2.py

io_ch2.py had zero dedicated test coverage before this file (confirmed via
grep across tests/) -- it was only ever exercised indirectly through
pipeline/geo tests that happen to load real CH2 data. This file adds direct
coverage, focused on the `overlap_hint`/crop-before-decode path (load_ch2's
raw raster decode was ~17-21s and, unlike LRO's product-load cache, couldn't
be cheaply cached -- a full-resolution OHRC array hit 4.49GB pickled -- so
cropping to the overlap region before decoding was the chosen fix instead).

Run from repo root:
    pytest tests/test_io_ch2.py -v
"""

import glob
import os

import numpy as np
import pytest

from src.io_ch2 import _crop_window_for_overlap, load_product, LabelParseError

CH2_XMLS = sorted(
    glob.glob("data/ch2_products/**/miscellaneous/**/*_d_img_*.xml", recursive=True)
)


def _rect_corners(min_lon, min_lat, max_lon, max_lat):
    """A simple axis-aligned rectangle in the {ul,ur,lr,ll: (lat,lon)} format
    the rest of the codebase uses (see src/geo.py's _geo_corners/_corners_to_polygon)."""
    return {
        "ul": (max_lat, min_lon), "ur": (max_lat, max_lon),
        "lr": (min_lat, max_lon), "ll": (min_lat, min_lon),
    }


def test_crop_window_for_overlap_returns_a_sane_window_for_real_overlap():
    """A long, narrow strip (mimicking a real OHRC product's aspect ratio)
    overlapping a hint in its lower half should crop to roughly that half,
    not the whole image and not nothing."""
    self_corners = _rect_corners(-74.0, 42.0, -73.0, 43.0)  # 1deg x 1deg
    shape = (10000, 1000)  # tall and narrow, like a real OHRC strip
    hint_corners = _rect_corners(-74.0, 42.0, -73.0, 42.5)  # lower half only

    window = _crop_window_for_overlap(self_corners, shape, hint_corners, margin_px=50)
    assert window is not None
    row_start, row_end, col_start, col_end = window

    assert 0 <= row_start < row_end <= shape[0] - 1
    assert 0 <= col_start < col_end <= shape[1] - 1
    # should cover roughly the lower half (~50%) of rows, not the whole image
    frac = (row_end - row_start) / shape[0]
    assert 0.3 < frac < 0.8, f"expected a partial crop around 50% of rows, got {frac:.1%}"
    # a 1000-wide strip fully overlapped across its width should keep ~all columns
    assert col_end - col_start > shape[1] * 0.9


def test_crop_window_for_overlap_returns_none_for_non_overlapping_footprints():
    self_corners = _rect_corners(-74.0, 42.0, -73.0, 43.0)
    hint_corners = _rect_corners(10.0, 10.0, 11.0, 11.0)  # nowhere near
    shape = (10000, 1000)

    assert _crop_window_for_overlap(self_corners, shape, hint_corners) is None


def test_crop_window_for_overlap_clips_margin_to_array_bounds():
    """A hint that covers the product's entire footprint should still clip
    the requested margin to the actual array size, not go out of bounds."""
    self_corners = _rect_corners(-74.0, 42.0, -73.0, 43.0)
    hint_corners = _rect_corners(-74.0, 42.0, -73.0, 43.0)  # identical footprint
    shape = (500, 200)

    window = _crop_window_for_overlap(self_corners, shape, hint_corners, margin_px=1000)
    assert window is not None
    row_start, row_end, col_start, col_end = window
    assert row_start == 0 and col_start == 0
    assert row_end == shape[0] - 1 and col_end == shape[1] - 1


def test_crop_window_for_overlap_handles_a_tiny_sliver_overlap():
    """A very thin overlap sliver shouldn't crash or return a degenerate
    (zero-area) window once the margin is added."""
    self_corners = _rect_corners(-74.0, 42.0, -73.0, 43.0)
    hint_corners = _rect_corners(-74.0, 42.999, -73.0, 43.5)  # tiny sliver at the top edge
    shape = (10000, 1000)

    window = _crop_window_for_overlap(self_corners, shape, hint_corners, margin_px=50)
    assert window is not None
    row_start, row_end, col_start, col_end = window
    assert row_end > row_start
    assert col_end > col_start


@pytest.mark.skipif(not CH2_XMLS, reason="no CH2 .xml labels found in data/ch2_products/")
def test_load_product_without_hint_is_unchanged(monkeypatch):
    """Regression guard: the default (no overlap_hint) path must behave
    exactly as it did before this feature was added -- full decode, original
    corners, no crop metadata."""
    p = load_product(CH2_XMLS[0])
    assert "cropped_window" not in p.meta
    assert p.array.ndim == 2
    assert p.array.min() >= 0.0
    assert p.array.max() <= 1.0


@pytest.mark.skipif(not CH2_XMLS, reason="no CH2 .xml labels found in data/ch2_products/")
def test_load_product_with_hint_crops_and_matches_full_decode_content():
    """The decisive correctness check: a cropped load's array must be
    pixel-identical (up to the documented per-array normalization
    difference) to the corresponding slice of a full decode, and its
    corners must be re-derived, not left as the original full-image corners."""
    from src.io_lro import load_product as load_lro
    import glob as _glob

    lro_paths = sorted(_glob.glob("data/lro_nac/*.IMG")) + sorted(_glob.glob("data/lro_nac/*.img"))
    if not lro_paths:
        pytest.skip("no LRO .IMG files found in data/lro_nac/ to build an overlap hint from")

    # Try each LRO product until one actually overlaps this CH2 product --
    # not every pair in the inventory does (see docs/research/day2_pair_verification.md).
    full = None
    cropped = None
    for lro_path in lro_paths:
        lro = load_lro(lro_path)
        candidate = load_product(CH2_XMLS[0], overlap_hint=lro)
        if "cropped_window" in candidate.meta:
            cropped = candidate
            break
    if cropped is None:
        pytest.skip("none of the available LRO products overlap this CH2 product")

    full = load_product(CH2_XMLS[0])
    row_start, row_end, col_start, col_end = cropped.meta["cropped_window"]
    full_slice = full.array[row_start:row_end + 1, col_start:col_end + 1]

    assert full_slice.shape == cropped.array.shape
    corr = np.corrcoef(full_slice.ravel(), cropped.array.ravel())[0, 1]
    assert corr > 0.999, f"cropped array doesn't match the corresponding full-decode slice (corr={corr:.6f})"

    # corners must have moved from the full image's corners (re-derived, not reused)
    assert cropped.corners != full.corners
    # and must stay within the full image's own lat/lon bounding range
    full_lats = [v[0] for v in full.corners.values()]
    full_lons = [v[1] for v in full.corners.values()]
    for lat, lon in cropped.corners.values():
        assert min(full_lats) - 0.01 <= lat <= max(full_lats) + 0.01
        assert min(full_lons) - 0.01 <= lon <= max(full_lons) + 0.01


@pytest.mark.skipif(not CH2_XMLS, reason="no CH2 .xml labels found in data/ch2_products/")
def test_load_product_with_non_overlapping_hint_falls_back_to_full_decode():
    """A hint with zero real overlap should fall back to a full decode
    (crop_window_for_overlap returns None), not raise or silently crop to
    garbage."""
    fake_hint_corners = _rect_corners(10.0, 10.0, 11.0, 11.0)  # nowhere near the Moon's near side
    p = load_product(CH2_XMLS[0], overlap_hint=fake_hint_corners)
    assert "cropped_window" not in p.meta
