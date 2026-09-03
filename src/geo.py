# src/geo.py — footprint overlap and common-grid resampling for Product pairs
# Owner: Riddhi

from shapely.geometry import Polygon

from src.types import Product


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
