# tests/test_geo.py — footprint_overlap against hand-checkable square footprints.

import numpy as np
import pytest

from src.geo import footprint_overlap, _corners_to_polygon
from src.types import Product


def _square_product(lat0, lat1, lon0, lon1, pid="test"):
    """A Product whose footprint is the rectangle [lat0,lat1] x [lon0,lon1].
    The array is a dummy — footprint_overlap only reads `corners`.
    """
    corners = {
        "ul": (lat1, lon0),
        "ur": (lat1, lon1),
        "ll": (lat0, lon0),
        "lr": (lat0, lon1),
    }
    return Product(
        array=np.zeros((4, 4), dtype=np.float32),
        gsd_m=1.0,
        corners=corners,
        source="SYNTH",
        product_id=pid,
    )


def test_identical_footprints_overlap_fully():
    a = _square_product(0, 1, 0, 1)
    assert footprint_overlap(a, a) == pytest.approx(1.0)


def test_disjoint_footprints_do_not_overlap():
    a = _square_product(0, 1, 0, 1)
    b = _square_product(5, 6, 5, 6)
    assert footprint_overlap(a, b) == pytest.approx(0.0)


def test_half_overlap_is_symmetric_when_areas_match():
    a = _square_product(0, 1, 0, 1)
    c = _square_product(0.5, 1.5, 0, 1)
    assert footprint_overlap(a, c) == pytest.approx(0.5)
    assert footprint_overlap(c, a) == pytest.approx(0.5)


def test_overlap_is_not_symmetric_when_areas_differ():
    a = _square_product(0, 1, 0, 1)          # area 1
    b = _square_product(-1, 2, -1, 2)         # area 9, fully contains a

    assert footprint_overlap(a, b) == pytest.approx(1.0)   # all of a is covered
    assert footprint_overlap(b, a) == pytest.approx(1.0 / 9.0)  # only 1/9 of b is


def test_touching_footprints_do_not_overlap():
    # share only the boundary edge lon=1 -> intersection is a line, area 0
    a = _square_product(0, 1, 0, 1)
    b = _square_product(0, 1, 1, 2)
    assert footprint_overlap(a, b) == pytest.approx(0.0)


def test_small_overlap_computes_correctly():
    a = _square_product(0, 10, 0, 10)   # area 100
    b = _square_product(9, 11, 9, 11)   # area 4, clips a's corner by 1x1 = area 1
    assert footprint_overlap(a, b) == pytest.approx(1.0 / 100.0)


def test_non_square_rectangles():
    a = _square_product(0, 5, 0, 10)   # 5 x 10 = area 50
    b = _square_product(1, 5, 2, 10)   # 4 x 8 = area 32, fully inside a
    assert footprint_overlap(a, b) == pytest.approx(32.0 / 50.0)
    assert footprint_overlap(b, a) == pytest.approx(1.0)  # all of b is covered by a


def test_degenerate_zero_area_footprint_returns_zero_not_nan():
    a = _square_product(0, 1, 0, 1)
    degenerate = _square_product(0, 0, 0, 1)  # zero height -> a line, area 0
    result = footprint_overlap(a, degenerate)
    assert result == pytest.approx(0.0)
    assert not np.isnan(result)


def test_corner_ordering_produces_a_valid_non_self_intersecting_polygon():
    a = _square_product(0, 1, 0, 1)
    poly = _corners_to_polygon(a)
    assert poly.is_valid
    assert poly.area == pytest.approx(1.0)
