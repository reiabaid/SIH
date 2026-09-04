import json

import numpy as np

from src.deliverable import build_deliverable
from src.match import match
from src.types import Product
from tests.test_match import _synthetic_crater_field
from tests.make_synthetic import make_synthetic_pair


def _product(array, product_id):
    return Product(
        array=array, gsd_m=1.0,
        corners={"ul": (10.0, 20.0), "ur": (10.0, 21.0),
                 "ll": (9.0, 20.0), "lr": (9.0, 21.0)},
        source="SYNTH", product_id=product_id,
    )


def test_build_deliverable_writes_registered_raster_and_points(tmp_path):
    source = _synthetic_crater_field(size=256, seed=10)
    warped, _ = make_synthetic_pair(source, seed=12, rotation_deg=3.0,
                                    scale_range=(0.99, 1.01), translation_frac=0.01)
    product_a, product_b = _product(source, "a"), _product(warped, "b")
    result = match(source, warped, matcher="sift")

    metrics = build_deliverable(product_a, product_b, result, str(tmp_path))

    assert (tmp_path / "registered_a_to_b.tif").exists()
    assert (tmp_path / "match_points.csv").exists()
    assert (tmp_path / "match_points.geojson").exists()
    assert (tmp_path / "overlay_rgb.png").exists()
    assert metrics["total_matches"] >= metrics["inlier_count"]
    saved = json.loads((tmp_path / "metrics.json").read_text())
    assert saved["product_a"] == "a"