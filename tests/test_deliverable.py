import json

import numpy as np

from PIL import Image

from src.deliverable import _overlap_bbox, build_deliverable, write_overlay
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

def test_overlap_bbox_covers_only_where_the_registered_image_landed():
    registered = np.zeros((1000, 200), dtype=np.float32)
    registered[300:500, 50:150] = 0.7  # A only landed in this block of B's frame

    r0, r1, c0, c1 = _overlap_bbox(registered, margin_frac=0.0)
    assert (r0, r1, c0, c1) == (300, 500, 50, 150)

    # a margin pads outward but never past the array
    r0, r1, c0, c1 = _overlap_bbox(registered, margin_frac=0.05)
    assert r0 < 300 and r1 > 500 and c0 < 50 and c1 > 150
    assert r0 >= 0 and r1 <= 1000 and c0 >= 0 and c1 <= 200


def test_overlap_bbox_is_none_when_nothing_landed():
    assert _overlap_bbox(np.zeros((50, 50), dtype=np.float32)) is None


def test_write_overlay_crops_to_the_overlap_and_caps_the_longest_side(tmp_path):
    # tall strip like a real LRO NAC frame, registered content only in the middle
    target = np.full((6000, 300), 0.5, dtype=np.float32)
    registered = np.zeros_like(target)
    registered[2000:4000, 20:280] = 0.9
    out = tmp_path / "overlay.png"

    write_overlay(str(out), registered, target, max_side=1000)

    width, height = Image.open(out).size
    assert max(width, height) <= 1000
    # cropped: far shorter than the 6000-row frame would scale to (1000 x 50)
    assert height >= 300 and width > 50
    assert width < height  # still portrait: not cropped/stretched into a square


def test_write_overlay_keeps_the_full_frame_when_nothing_landed(tmp_path):
    target = np.full((400, 100), 0.5, dtype=np.float32)
    out = tmp_path / "overlay.png"

    write_overlay(str(out), np.zeros_like(target), target)

    assert Image.open(out).size == (100, 400)  # no crop, under max_side: untouched
