"""tests/test_catalog.py -- footprint-only overlap ranking (src/catalog.py) and
the API endpoints built on it. None of these decode a raster."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import src.api as api
import src.catalog as catalog


def _rect(min_lon, min_lat, max_lon, max_lat):
    return {"ul": (max_lat, min_lon), "ur": (max_lat, max_lon),
            "lr": (min_lat, max_lon), "ll": (min_lat, min_lon)}


def test_overlap_fractions_identical_half_and_disjoint():
    a = _rect(0, 0, 2, 2)
    assert catalog.overlap_fractions(a, a) == (1.0, 1.0)
    # B covers the right half of A, and is itself entirely inside A's span
    half = catalog.overlap_fractions(a, _rect(1, 0, 2, 2))
    assert half == pytest.approx((0.5, 1.0))
    assert catalog.overlap_fractions(a, _rect(10, 10, 11, 11)) == (0.0, 0.0)


def test_overlap_fractions_degenerate_footprint_is_zero_not_an_error():
    zero = {k: (0.0, 0.0) for k in ("ul", "ur", "lr", "ll")}
    assert catalog.overlap_fractions(_rect(0, 0, 1, 1), zero) == (0.0, 0.0)


def test_record_then_read_lro_footprint_roundtrip(tmp_path):
    img = tmp_path / "M1LE.IMG"
    img.write_bytes(b"x")
    product = SimpleNamespace(corners=_rect(1, 1, 2, 2), gsd_m=1.0, incidence_deg=70.0,
                              subsolar_azimuth_deg=10.0, acquired_utc="2025-01-01")

    assert catalog.footprint("M1LE", str(img)) is None  # not recorded yet
    catalog.record_footprint(str(img), product)
    fp = catalog.footprint("M1LE", str(img))
    assert fp["corners"] == product.corners
    assert fp["incidence_deg"] == 70.0 and fp["acquired_utc"] == "2025-01-01"


def test_degenerate_lro_corners_are_never_recorded(tmp_path):
    """A load done while SPICE geometry was unavailable returns all-(0,0)
    corners; recording them would make the product look ingested forever."""
    img = tmp_path / "M2LE.IMG"
    img.write_bytes(b"x")
    bad = SimpleNamespace(corners={k: (0.0, 0.0) for k in ("ul", "ur", "lr", "ll")}, gsd_m=1.0,
                          incidence_deg=None, subsolar_azimuth_deg=None, acquired_utc=None)

    catalog.record_footprint(str(img), bad)

    assert catalog.footprint("M2LE", str(img)) is None


def test_ch2_footprint_comes_from_the_label_without_touching_pixels(tmp_path):
    label = tmp_path / "ch2_x.xml"
    label.write_text(
        "<Product><Refined_Corner_Coordinates>"
        "<upper_left_latitude>-73.0</upper_left_latitude><upper_left_longitude>42.0</upper_left_longitude>"
        "<upper_right_latitude>-73.0</upper_right_latitude><upper_right_longitude>43.0</upper_right_longitude>"
        "<lower_left_latitude>-74.0</lower_left_latitude><lower_left_longitude>42.0</lower_left_longitude>"
        "<lower_right_latitude>-74.0</lower_right_latitude><lower_right_longitude>43.0</lower_right_longitude>"
        "</Refined_Corner_Coordinates></Product>")

    fp = catalog.footprint("urn:isro:isda:ch2_cho.ohr:x", str(label))  # no .img exists next to it

    assert fp["corners"]["ul"] == (-73.0, 42.0) and fp["corners"]["lr"] == (-74.0, 43.0)


def _fake_footprints(monkeypatch, table):
    monkeypatch.setattr(catalog, "footprint",
                        lambda pid, path: ({"corners": table[pid]} if pid in table else None))


INVENTORY = {
    "urn:ch2:a": {"path": "a.xml"},
    "M_good": {"path": "g.IMG", "gsd_m": "1.0"},
    "M_partial": {"path": "p.IMG"},
    "M_far": {"path": "f.IMG"},
    "M_unknown": {"path": "u.IMG"},
    "synthetic_a": {"path": "SYNTHETIC"},
}


def test_rank_candidates_orders_by_overlap_filters_and_counts_unknown(monkeypatch):
    _fake_footprints(monkeypatch, {
        "urn:ch2:a": _rect(0, 0, 4, 4),
        "M_good": _rect(0, 0, 4, 3),      # covers 75% of the CH2 image
        "M_partial": _rect(0, 0, 4, 1),   # covers 25%
        "M_far": _rect(50, 50, 51, 51),   # no overlap -> filtered out
        # M_unknown deliberately has no footprint
    })

    cands, not_ingested = catalog.rank_candidates("urn:ch2:a", INVENTORY)

    assert [c["product_id"] for c in cands] == ["M_good", "M_partial"]
    assert cands[0]["overlap_percent"] == 75.0 and cands[1]["overlap_percent"] == 25.0
    assert cands[0]["candidate_covered_percent"] == 100.0  # the whole LRO frame lies inside the CH2 strip
    assert not_ingested == 1                                # M_unknown; synthetic_a is not counted


def test_rank_candidates_works_in_the_reverse_direction_and_rejects_unknown_ids(monkeypatch):
    _fake_footprints(monkeypatch, {"urn:ch2:a": _rect(0, 0, 4, 4), "M_good": _rect(0, 0, 4, 3)})

    cands, _ = catalog.rank_candidates("M_good", INVENTORY)  # LRO query -> CH2 candidates

    assert [c["product_id"] for c in cands] == ["urn:ch2:a"]
    with pytest.raises(KeyError):
        catalog.rank_candidates("nope", INVENTORY)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "PRODUCT_CACHE", {pid: e["path"] for pid, e in INVENTORY.items()})
    monkeypatch.setattr(api, "PRODUCT_META", {pid: {k: v for k, v in e.items() if k != "path"}
                                              for pid, e in INVENTORY.items()})
    _fake_footprints(monkeypatch, {"urn:ch2:a": _rect(0, 0, 4, 4), "M_good": _rect(0, 0, 4, 3)})
    return TestClient(api.app)  # not entered as a context manager: skips startup/DB init


def test_candidates_endpoint_returns_ranked_list_and_ingest_count(client):
    body = client.get("/candidates", params={"product_id": "urn:ch2:a"}).json()

    assert [c["product_id"] for c in body["candidates"]] == ["M_good"]
    # only the CH2 image and M_good have footprints in this fixture, so
    # M_partial, M_far and M_unknown all count as not yet ingested
    assert body["not_ingested"] == 3


def test_candidates_endpoint_404s_for_unknown_and_synthetic_ids(client):
    assert client.get("/candidates", params={"product_id": "nope"}).status_code == 404
    assert client.get("/candidates", params={"product_id": "synthetic_a"}).status_code == 404


def test_overlap_endpoint_uses_footprints_and_never_loads_a_raster(client, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("/overlap decoded a raster although both footprints were known")
    monkeypatch.setattr(api, "load_product_dynamically", boom)

    body = client.post("/overlap", json={"product_a": "urn:ch2:a", "product_b": "M_good"}).json()

    assert body["overlap_percent"] == 75.0
