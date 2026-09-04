# src/geo.py — footprint overlap and common-grid resampling for Product pairs
# Owner: Riddhi

import numpy as np
import cv2
from shapely.geometry import Polygon

from src.types import Product

MOON_RADIUS_M = 1_737_400.0  # mean lunar radius, metres — used only to convert
                              # a GSD in metres/pixel into degrees/pixel


def _corners_to_polygon(product: Product) -> Polygon:
    """Build a shapely polygon from a Product's corner lat/lons.

    Coordinates are (lon, lat) so the polygon is planar-Euclidean, not geodesic —
    fine at the tile/strip sizes here, and doesn't handle the antimeridian.
    Corners are walked ul -> ur -> lr -> ll so the boundary doesn't self-intersect
    (walking ul -> ur -> ll -> lr would cross itself into a bowtie).
    """
    order = ("ul", "ur", "lr", "ll")
    coords = [(product.corners[k][1], product.corners[k][0]) for k in order]
    return Polygon(coords)


def footprint_overlap(a: Product, b: Product) -> float:
    """Fraction of `a`'s footprint covered by `b`, in [0, 1].

    Not symmetric: footprint_overlap(a, b) != footprint_overlap(b, a) in general
    (a small product fully inside a large one scores 1.0 one way, a small
    fraction the other way).
    """
    poly_a = _corners_to_polygon(a)
    poly_b = _corners_to_polygon(b)

    if not poly_a.is_valid or not poly_b.is_valid or poly_a.area == 0:
        return 0.0

    intersection = poly_a.intersection(poly_b)
    return intersection.area / poly_a.area


def _pixel_corners(shape: tuple) -> np.ndarray:
    h, w = shape[:2]
    return np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])  # ul,ur,lr,ll


def _geo_corners(product: Product) -> np.ndarray:
    order = ("ul", "ur", "lr", "ll")
    return np.float32([[product.corners[k][1], product.corners[k][0]] for k in order])  # (lon,lat)


def _pixel_to_geo_transform(product: Product) -> np.ndarray:
    """3x3 homography mapping (col, row) pixel coords -> (lon, lat) planar coords,
    fit from the product's four corners. Same planar approximation as
    `_corners_to_polygon`; reduces to a plain affine transform whenever the
    corners form an axis-aligned rectangle.
    """
    return cv2.getPerspectiveTransform(_pixel_corners(product.array.shape), _geo_corners(product))


def _meters_per_degree(lat_deg: float) -> "tuple[float, float]":
    """(metres per degree latitude, metres per degree longitude) at a given
    latitude on a spherical Moon. Longitude degrees shrink toward the poles
    by a factor of cos(lat); latitude degrees don't.
    """
    m_per_deg_lat = MOON_RADIUS_M * np.pi / 180.0
    m_per_deg_lon = m_per_deg_lat * np.cos(np.deg2rad(lat_deg))
    return m_per_deg_lat, m_per_deg_lon


def _resample_onto_grid(product: Product, dst_geo2pix: np.ndarray, dsize: tuple) -> np.ndarray:
    src_pix2geo = _pixel_to_geo_transform(product)
    m = dst_geo2pix @ src_pix2geo  # src pixel -> dst pixel, forward map
    m = (m / m[2, 2]).astype(np.float64)
    return cv2.warpPerspective(
        product.array.astype(np.float32), m, dsize,
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0.0,
    )


def align_pair(a: Product, b: Product) -> "tuple[Product, Product]":
    """Resample both Products onto one common grid, at the coarser of the two
    GSDs, over the region where their footprints overlap.

    Returns two new Products of identical array shape and identical corners,
    so a scale-invariant descriptor is never needed downstream in match.py —
    the scale gap is closed here.
    """
    if a.gsd_m <= 0 or b.gsd_m <= 0:
        raise ValueError(
            f"align_pair: gsd_m must be positive (got a.gsd_m={a.gsd_m!r} for "
            f"'{a.product_id}', b.gsd_m={b.gsd_m!r} for '{b.product_id}')"
        )

    poly_a = _corners_to_polygon(a)
    poly_b = _corners_to_polygon(b)
    overlap = poly_a.intersection(poly_b)

    if overlap.is_empty or overlap.area == 0:
        raise ValueError(
            f"align_pair: '{a.product_id}' and '{b.product_id}' do not overlap — "
            "nothing to resample onto a common grid."
        )

    min_lon, min_lat, max_lon, max_lat = overlap.bounds
    lat_range, lon_range = max_lat - min_lat, max_lon - min_lon
    center_lat = (min_lat + max_lat) / 2.0

    gsd_common = max(a.gsd_m, b.gsd_m)
    m_per_deg_lat, m_per_deg_lon = _meters_per_degree(center_lat)
    target_deg_per_px_lat = gsd_common / m_per_deg_lat
    target_deg_per_px_lon = gsd_common / m_per_deg_lon

    # Pixel count for a corner-to-corner span of N-1 steps (matching
    # _pixel_to_geo_transform's own corner-fit convention below), not N steps —
    # otherwise the destination grid and the source corner-fit disagree on how
    # many pixels a given angular range spans, and warping isn't a true identity
    # even when both products already share one grid.
    out_h = max(1, int(round(lat_range / target_deg_per_px_lat)) + 1)
    out_w = max(1, int(round(lon_range / target_deg_per_px_lon)) + 1)

    # When the overlap is smaller than one output pixel, out_h/out_w clamp to 1
    # and there's no real "span" to divide by — fall back to the target step so
    # dst_pix2geo stays invertible (a literal 0 step makes it singular). The
    # fallback value doesn't affect the sampled output: with only row/col 0 to
    # place, its coordinate is min_lon/max_lat regardless of the step size.
    deg_per_px_lat = lat_range / (out_h - 1) if out_h > 1 else target_deg_per_px_lat
    deg_per_px_lon = lon_range / (out_w - 1) if out_w > 1 else target_deg_per_px_lon

    # destination grid: pixel (col,row) -> (lon,lat); row 0 is the north edge (max_lat)
    dst_pix2geo = np.array([
        [deg_per_px_lon, 0, min_lon],
        [0, -deg_per_px_lat, max_lat],
        [0, 0, 1],
    ], dtype=np.float64)
    dst_geo2pix = np.linalg.inv(dst_pix2geo)

    out_a = _resample_onto_grid(a, dst_geo2pix, (out_w, out_h))
    out_b = _resample_onto_grid(b, dst_geo2pix, (out_w, out_h))

    common_corners = {
        "ul": (max_lat, min_lon), "ur": (max_lat, max_lon),
        "ll": (min_lat, min_lon), "lr": (min_lat, max_lon),
    }

    aligned_a = Product(
        array=out_a, gsd_m=gsd_common, corners=dict(common_corners), source=a.source,
        product_id=f"{a.product_id}_aligned", acquired_utc=a.acquired_utc,
        incidence_deg=a.incidence_deg, subsolar_azimuth_deg=a.subsolar_azimuth_deg,
        meta={**a.meta, "aligned_from": a.product_id},
    )
    aligned_b = Product(
        array=out_b, gsd_m=gsd_common, corners=dict(common_corners), source=b.source,
        product_id=f"{b.product_id}_aligned", acquired_utc=b.acquired_utc,
        incidence_deg=b.incidence_deg, subsolar_azimuth_deg=b.subsolar_azimuth_deg,
        meta={**b.meta, "aligned_from": b.product_id},
    )
    return aligned_a, aligned_b


def original_pixel_transform(aligned_product: Product, original_product: Product) -> np.ndarray:
    """3x3 homography mapping `aligned_product`'s common-grid pixel coords (as
    produced by `align_pair`) to `original_product`'s own raw pixel coords.

    Composes the aligned grid's pixel->geo transform with the inverse of the
    original product's own pixel->geo transform; both are the same corner-fit
    approximation `align_pair` itself uses, so this exactly undoes its
    resampling. Exposed separately from `to_original_pixels` so a caller can
    also carry a homography *fit on the aligned grid* (e.g. a MatchResult's
    A->B transform) into original-pixel space by composing on both sides,
    rather than only transforming points.
    """
    aligned_pix2geo = _pixel_to_geo_transform(aligned_product)
    orig_geo2pix = np.linalg.inv(_pixel_to_geo_transform(original_product))
    m = orig_geo2pix @ aligned_pix2geo
    return (m / m[2, 2]).astype(np.float64)


def to_original_pixels(aligned_product: Product, original_product: Product,
                        points: np.ndarray) -> np.ndarray:
    """Map (x, y) pixel points from `aligned_product`'s common-grid frame (as
    produced by `align_pair`) back to `original_product`'s own raw pixel frame.

    Needed because match() runs on the aligned grid, so its output points are
    in that shared frame -- not in either product's original raster, which is
    what downstream consumers (cnet.py Sample/Line, a registered-raster export
    against the untouched source image) actually need.
    """
    points = np.asarray(points, dtype=np.float32)
    if len(points) == 0:
        # cv2.perspectiveTransform returns None on an empty input rather than an
        # empty array -- match_tiled legitimately produces zero points when a
        # rung finds no matches at all, and that's not an error here.
        return points.reshape(-1, 2)

    m = original_pixel_transform(aligned_product, original_product).astype(np.float32)
    pts = points.reshape(-1, 1, 2)
    out = cv2.perspectiveTransform(pts, m)
    return out.reshape(-1, 2)
