# tests/test_geo_align.py — align_pair against synthetic products with known geometry.

import numpy as np
import cv2
import pytest

from src.geo import align_pair, to_original_pixels, _meters_per_degree
from src.types import Product


def _textured_field(size, seed):
    """Blobby noise field with enough structure for a correlation check to be
    meaningful — not meant to look like a real crater, just non-flat.
    `size` is either an int (square) or an (h, w) tuple.
    """
    h, w = (size, size) if isinstance(size, int) else size
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    img = 0.5 + 0.05 * rng.standard_normal((h, w)).astype(np.float32)
    for _ in range(30):
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.uniform(4, 16)
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        img += 0.4 * np.exp(-((dist - r) ** 2) / (2 * (r * 0.25) ** 2))
    return np.clip(img, 0.0, 1.0).astype(np.float32)


def _product_for_square_deg(array, lat0, lat1, lon0, lon1, gsd_m, pid):
    corners = {
        "ul": (lat1, lon0), "ur": (lat1, lon1),
        "ll": (lat0, lon0), "lr": (lat0, lon1),
    }
    return Product(array=array, gsd_m=gsd_m, corners=corners, source="SYNTH", product_id=pid)


def test_align_pair_recovers_common_shape_and_correlated_content():
    size_hi = 256
    factor = 4
    hi_img = _textured_field(size_hi, seed=7)
    lo_img = cv2.resize(hi_img, (size_hi // factor, size_hi // factor), interpolation=cv2.INTER_AREA)

    lat0, lat1, lon0, lon1 = 0.0, 1.0, 0.0, 1.0
    m_per_deg_lat, _ = _meters_per_degree((lat0 + lat1) / 2.0)
    gsd_hi = (lat1 - lat0) / (size_hi - 1) * m_per_deg_lat
    gsd_lo = (lat1 - lat0) / (size_hi // factor - 1) * m_per_deg_lat

    product_hi = _product_for_square_deg(hi_img, lat0, lat1, lon0, lon1, gsd_hi, "hi")
    product_lo = _product_for_square_deg(lo_img, lat0, lat1, lon0, lon1, gsd_lo, "lo")

    aligned_hi, aligned_lo = align_pair(product_hi, product_lo)

    assert aligned_hi.array.shape == aligned_lo.array.shape
    assert aligned_hi.array.shape[0] == pytest.approx(size_hi // factor, abs=2)
    assert aligned_hi.gsd_m == pytest.approx(gsd_lo)  # coarser GSD wins

    corr = np.corrcoef(aligned_hi.array.ravel(), aligned_lo.array.ravel())[0, 1]
    assert corr > 0.9, f"expected strong correlation after alignment, got {corr:.3f}"


def test_align_pair_raises_a_clear_error_when_products_do_not_overlap():
    a = _product_for_square_deg(np.zeros((32, 32), dtype=np.float32), 0, 1, 0, 1, 10.0, "product_a")
    b = _product_for_square_deg(np.zeros((32, 32), dtype=np.float32), 50, 51, 50, 51, 10.0, "product_b")

    with pytest.raises(ValueError, match="product_a.*product_b|product_b.*product_a"):
        align_pair(a, b)


def test_align_pair_windows_to_the_overlap_region_only():
    size = 128
    lat0, lat1, lon0, lon1 = 0.0, 2.0, 0.0, 2.0
    m_per_deg_lat, _ = _meters_per_degree((lat0 + lat1) / 2.0)
    gsd = (lat1 - lat0) / (size - 1) * m_per_deg_lat

    a = _product_for_square_deg(_textured_field(size, seed=1), lat0, lat1, lon0, lon1, gsd, "a")
    # b is shifted by 1 degree in both lat and lon -> overlap is exactly [1,2]x[1,2]
    b = _product_for_square_deg(_textured_field(size, seed=2), 1.0, 3.0, 1.0, 3.0, gsd, "b")

    aligned_a, aligned_b = align_pair(a, b)

    assert aligned_a.corners == aligned_b.corners
    assert aligned_a.corners["ll"] == pytest.approx((1.0, 1.0))
    assert aligned_a.corners["ur"] == pytest.approx((2.0, 2.0))
    # overlap is a quarter of each original footprint -> roughly half the side length
    assert aligned_a.array.shape[0] == pytest.approx(size // 2, abs=2)
    assert aligned_a.array.shape == aligned_b.array.shape


def test_align_pair_is_near_identity_when_grids_already_match():
    size = 64
    lat0, lat1, lon0, lon1 = 0.0, 1.0, 0.0, 1.0
    m_per_deg_lat, _ = _meters_per_degree((lat0 + lat1) / 2.0)
    gsd = (lat1 - lat0) / (size - 1) * m_per_deg_lat
    img = _textured_field(size, seed=3)

    a = _product_for_square_deg(img, lat0, lat1, lon0, lon1, gsd, "a")
    b = _product_for_square_deg(img.copy(), lat0, lat1, lon0, lon1, gsd, "b")

    aligned_a, aligned_b = align_pair(a, b)

    assert aligned_a.array.shape == img.shape
    corr = np.corrcoef(aligned_a.array.ravel(), img.ravel())[0, 1]
    assert corr > 0.99, f"expected near-identical resampling of an already-aligned grid, got {corr:.3f}"


def test_align_pair_does_not_assume_matching_input_array_shapes():
    """Same physical resolution (GSD), different pixel dimensions — a's
    footprint sits entirely inside b's larger one, from a shared origin.
    """
    gsd = 4.0
    m_per_deg_lat, _ = _meters_per_degree(0.0)
    deg_per_px = gsd / m_per_deg_lat

    size_a, size_b = 128, 256
    lat0, lon0 = 0.0, 0.0
    lat1_a = lon1_a = deg_per_px * (size_a - 1)
    lat1_b = lon1_b = deg_per_px * (size_b - 1)

    a = _product_for_square_deg(np.zeros((size_a, size_a), dtype=np.float32), lat0, lat1_a, lon0, lon1_a, gsd, "a")
    b = _product_for_square_deg(np.zeros((size_b, size_b), dtype=np.float32), lat0, lat1_b, lon0, lon1_b, gsd, "b")

    aligned_a, aligned_b = align_pair(a, b)

    assert aligned_a.array.shape == aligned_b.array.shape
    assert aligned_a.gsd_m == pytest.approx(gsd)
    assert aligned_a.array.shape[0] == pytest.approx(size_a, abs=2)  # overlap == a's own footprint


def test_align_pair_when_one_footprint_fully_contains_the_other():
    m_per_deg_lat, _ = _meters_per_degree(1.5)
    size_small, size_big = 64, 96

    gsd_small = (2.0 - 1.0) / (size_small - 1) * m_per_deg_lat
    gsd_big = (3.0 - 0.0) / (size_big - 1) * m_per_deg_lat

    small = _product_for_square_deg(_textured_field(size_small, seed=11), 1.0, 2.0, 1.0, 2.0, gsd_small, "small")
    big = _product_for_square_deg(_textured_field(size_big, seed=12), 0.0, 3.0, 0.0, 3.0, gsd_big, "big")

    aligned_small, aligned_big = align_pair(small, big)

    # overlap == small's entire footprint, not a partial rectangle
    assert aligned_small.corners == aligned_big.corners
    assert aligned_small.corners["ll"] == pytest.approx((1.0, 1.0))
    assert aligned_small.corners["ur"] == pytest.approx((2.0, 2.0))
    assert aligned_small.array.shape == aligned_big.array.shape


def test_align_pair_handles_a_very_small_overlap_region_without_crashing():
    size = 64
    m_per_deg_lat, _ = _meters_per_degree(0.5)
    gsd = 1.0 / (size - 1) * m_per_deg_lat  # a 1-degree-wide product

    a = _product_for_square_deg(_textured_field(size, seed=21), 0.0, 1.0, 0.0, 1.0, gsd, "a")
    # b overlaps a by a sliver: [0.999, 1] x [0.999, 1] -- smaller than one output pixel
    b = _product_for_square_deg(_textured_field(size, seed=22), 0.999, 1.999, 0.999, 1.999, gsd, "b")

    aligned_a, aligned_b = align_pair(a, b)

    assert aligned_a.array.shape == aligned_b.array.shape
    assert aligned_a.array.shape[0] >= 1 and aligned_a.array.shape[1] >= 1
    assert aligned_a.array.size > 0
    assert np.all(np.isfinite(aligned_a.array))


def test_align_pair_common_gsd_is_independent_of_argument_order():
    lat0, lat1, lon0, lon1 = 0.0, 1.0, 0.0, 1.0
    m_per_deg_lat, _ = _meters_per_degree(0.5)
    size_fine, size_coarse = 128, 32
    gsd_fine = (lat1 - lat0) / (size_fine - 1) * m_per_deg_lat
    gsd_coarse = (lat1 - lat0) / (size_coarse - 1) * m_per_deg_lat

    fine = _product_for_square_deg(_textured_field(size_fine, seed=31), lat0, lat1, lon0, lon1, gsd_fine, "fine")
    coarse = _product_for_square_deg(_textured_field(size_coarse, seed=32), lat0, lat1, lon0, lon1, gsd_coarse, "coarse")

    a1, b1 = align_pair(fine, coarse)
    a2, b2 = align_pair(coarse, fine)

    assert a1.gsd_m == pytest.approx(gsd_coarse)
    assert a2.gsd_m == pytest.approx(gsd_coarse)
    assert a1.array.shape == b1.array.shape == a2.array.shape == b2.array.shape


def test_align_pair_handles_non_square_images():
    h, w = 80, 160
    lat0, lat1, lon0 = 0.0, 1.0, 0.0
    m_per_deg_lat, m_per_deg_lon = _meters_per_degree((lat0 + lat1) / 2.0)
    gsd = (lat1 - lat0) / (h - 1) * m_per_deg_lat
    lon1 = lon0 + (gsd / m_per_deg_lon) * (w - 1)  # keeps lon spacing self-consistent too

    img = np.random.default_rng(41).random((h, w)).astype(np.float32)

    a = _product_for_square_deg(img, lat0, lat1, lon0, lon1, gsd, "a")
    b = _product_for_square_deg(img.copy(), lat0, lat1, lon0, lon1, gsd, "b")

    aligned_a, aligned_b = align_pair(a, b)

    assert aligned_a.array.shape[0] != aligned_a.array.shape[1]  # stayed non-square
    assert aligned_a.array.shape == (h, w)
    corr = np.corrcoef(aligned_a.array.ravel(), img.ravel())[0, 1]
    assert corr > 0.99


def test_align_pair_preserves_a_known_gradient_direction():
    """A more direct check than raw correlation: a horizontal gradient should
    still read low-to-high left-to-right after warping, not flipped or garbled.
    """
    size_hi, factor = 128, 4
    ramp = np.tile(np.linspace(0.0, 1.0, size_hi, dtype=np.float32), (size_hi, 1))
    lo = cv2.resize(ramp, (size_hi // factor, size_hi // factor), interpolation=cv2.INTER_AREA)

    lat0, lat1, lon0, lon1 = 0.0, 1.0, 0.0, 1.0
    m_per_deg_lat, _ = _meters_per_degree(0.5)
    gsd_hi = (lat1 - lat0) / (size_hi - 1) * m_per_deg_lat
    gsd_lo = (lat1 - lat0) / (size_hi // factor - 1) * m_per_deg_lat

    hi_product = _product_for_square_deg(ramp, lat0, lat1, lon0, lon1, gsd_hi, "hi")
    lo_product = _product_for_square_deg(lo, lat0, lat1, lon0, lon1, gsd_lo, "lo")

    aligned_hi, _ = align_pair(hi_product, lo_product)

    row = aligned_hi.array[aligned_hi.array.shape[0] // 2]
    assert np.all(np.diff(row) >= -1e-3), "gradient should stay non-decreasing left to right"
    assert row[0] == pytest.approx(0.0, abs=0.05)
    assert row[-1] == pytest.approx(1.0, abs=0.05)


def test_meters_per_degree_reflects_longitude_compression_at_target_latitude():
    """Real search box (2026-09-03 update): target moved to lat -74.4..-73.1,
    lon 42.4..44.0E (was the equatorial-ish Chandrayaan-3 site). At -73.7 deg,
    a degree of longitude covers cos(73.7 deg) =~ 0.28x the ground distance a
    degree of latitude does -- this is the ratio align_pair's grid-sizing
    depends on to not distort the image at this latitude.
    """
    target_lat = -73.7
    m_per_deg_lat, m_per_deg_lon = _meters_per_degree(target_lat)

    assert m_per_deg_lon < m_per_deg_lat  # longitude degrees are shorter this far south
    ratio = m_per_deg_lon / m_per_deg_lat
    assert ratio == pytest.approx(np.cos(np.deg2rad(target_lat)), rel=1e-6)
    assert ratio == pytest.approx(0.28, abs=0.01)


def test_align_pair_at_the_actual_target_area_does_not_distort_the_grid():
    """Same real search box as above. Runs align_pair's full pipeline (corner
    fit, overlap, grid sizing, warp) at the real target latitude instead of
    the near-equatorial coordinates every earlier test used, to prove the
    cos(lat) correction actually holds together end to end, not just in
    isolation. The array shape is derived from the real box and a chosen GSD
    (not picked arbitrarily square), the same self-consistent pattern as the
    non-square-images test above.
    """
    lat0, lat1 = -74.4, -73.1
    lon0, lon1 = 42.4, 44.0
    center_lat = (lat0 + lat1) / 2.0
    m_per_deg_lat, m_per_deg_lon = _meters_per_degree(center_lat)

    gsd = 300.0  # metres/pixel -- coarse on purpose, keeps the test fast
    deg_per_px_lat = gsd / m_per_deg_lat
    deg_per_px_lon = gsd / m_per_deg_lon
    h = int(round((lat1 - lat0) / deg_per_px_lat)) + 1
    w = int(round((lon1 - lon0) / deg_per_px_lon)) + 1

    img = _textured_field((h, w), seed=51)
    a = _product_for_square_deg(img, lat0, lat1, lon0, lon1, gsd, "ch2_actual")
    b = _product_for_square_deg(img.copy(), lat0, lat1, lon0, lon1, gsd, "lro_actual")

    aligned_a, aligned_b = align_pair(a, b)

    assert np.all(np.isfinite(aligned_a.array))
    assert aligned_a.array.shape == aligned_b.array.shape == img.shape

    corr = np.corrcoef(aligned_a.array.ravel(), img.ravel())[0, 1]
    assert corr > 0.99, f"expected near-identical resampling at target latitude, got {corr:.3f}"

    # the real box is 1.3 deg of latitude by 1.6 deg of longitude -- similar-looking
    # ranges -- but at -73.7 deg a degree of longitude is physically much shorter,
    # so the true ground footprint is markedly taller than it is wide. If the
    # cos(lat) correction were missing (lon treated like lat), the grid would come
    # out roughly square/wide instead.
    assert img.shape[0] > 2 * img.shape[1], (
        f"expected a visibly non-square footprint at this latitude, got {img.shape}"
    )


def test_align_pair_rejects_non_positive_gsd():
    zero_gsd = _product_for_square_deg(np.zeros((16, 16), dtype=np.float32), 0, 1, 0, 1, 0.0, "zero")
    positive_gsd = _product_for_square_deg(np.zeros((16, 16), dtype=np.float32), 0, 1, 0, 1, 10.0, "ok")
    negative_gsd = _product_for_square_deg(np.zeros((16, 16), dtype=np.float32), 0, 1, 0, 1, -5.0, "neg")

    with pytest.raises(ValueError, match="gsd"):
        align_pair(zero_gsd, positive_gsd)

    with pytest.raises(ValueError, match="gsd"):
        align_pair(positive_gsd, negative_gsd)


# ---- to_original_pixels: coordinate inversion out of align_pair's common grid ----

def test_to_original_pixels_round_trips_a_products_own_corners():
    """When the two products share exactly the same footprint (test 1's setup),
    aligned_hi's array covers exactly product_hi's own corners -- so mapping
    aligned_hi's own four pixel corners back through to_original_pixels(aligned_hi,
    product_hi, ...) must land back on product_hi's own four pixel corners
    (0,0)..(w-1,h-1), regardless of the resolution change align_pair applied.
    """
    size_hi = 256
    factor = 4
    hi_img = _textured_field(size_hi, seed=7)
    lo_img = cv2.resize(hi_img, (size_hi // factor, size_hi // factor), interpolation=cv2.INTER_AREA)

    lat0, lat1, lon0, lon1 = 0.0, 1.0, 0.0, 1.0
    m_per_deg_lat, _ = _meters_per_degree((lat0 + lat1) / 2.0)
    gsd_hi = (lat1 - lat0) / (size_hi - 1) * m_per_deg_lat
    gsd_lo = (lat1 - lat0) / (size_hi // factor - 1) * m_per_deg_lat

    product_hi = _product_for_square_deg(hi_img, lat0, lat1, lon0, lon1, gsd_hi, "hi")
    product_lo = _product_for_square_deg(lo_img, lat0, lat1, lon0, lon1, gsd_lo, "lo")
    aligned_hi, aligned_lo = align_pair(product_hi, product_lo)

    ah, aw = aligned_hi.array.shape[:2]
    aligned_corners = np.float32([[0, 0], [aw - 1, 0], [aw - 1, ah - 1], [0, ah - 1]])

    back = to_original_pixels(aligned_hi, product_hi, aligned_corners)

    h, w = product_hi.array.shape[:2]
    expected = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
    np.testing.assert_allclose(back, expected, atol=1.5)


def test_to_original_pixels_maps_the_two_sides_of_a_pair_independently():
    """The same aligned-grid point, inverted against each product's own original
    frame, generally lands at a different pixel location in each -- since
    aligned_a and aligned_b were resampled from different source resolutions.
    Regression check that the function actually uses the `original_product`
    argument rather than always returning the aligned-grid coordinate unchanged.
    """
    size = 128
    lat0, lat1, lon0, lon1 = 0.0, 2.0, 0.0, 2.0
    m_per_deg_lat, _ = _meters_per_degree((lat0 + lat1) / 2.0)
    gsd = (lat1 - lat0) / (size - 1) * m_per_deg_lat

    a = _product_for_square_deg(_textured_field(size, seed=1), lat0, lat1, lon0, lon1, gsd, "a")
    b = _product_for_square_deg(_textured_field(size // 2, seed=2), lat0, lat1, lon0, lon1, gsd * 2, "b")
    aligned_a, aligned_b = align_pair(a, b)

    point = np.float32([[aligned_a.array.shape[1] / 2, aligned_a.array.shape[0] / 2]])
    back_a = to_original_pixels(aligned_a, a, point)
    back_b = to_original_pixels(aligned_b, b, point)

    # both should land near each product's own centre pixel, at each one's own scale
    assert back_a[0, 0] == pytest.approx(a.array.shape[1] / 2, abs=2)
    assert back_b[0, 0] == pytest.approx(b.array.shape[1] / 2, abs=2)


def test_to_original_pixels_handles_zero_points_without_crashing():
    """A rung that finds zero matches (a real, observed outcome -- e.g. rung-1 on
    the real CH2 x LRO pair) must not crash the pipeline's coordinate inversion
    step. cv2.perspectiveTransform returns None (not an empty array) on empty
    input, which crashed here before this guard.
    """
    size = 64
    lat0, lat1, lon0, lon1 = 0.0, 1.0, 0.0, 1.0
    a = _product_for_square_deg(_textured_field(size, seed=1), lat0, lat1, lon0, lon1, 10.0, "a")
    b = _product_for_square_deg(_textured_field(size, seed=2), lat0, lat1, lon0, lon1, 10.0, "b")
    aligned_a, _ = align_pair(a, b)

    empty = np.zeros((0, 2), dtype=np.float32)
    out = to_original_pixels(aligned_a, a, empty)
    assert out.shape == (0, 2)
