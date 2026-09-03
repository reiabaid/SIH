# tests/test_cnet.py — cnet.py's PVL control network writer, validated by
# actually parsing the output back with `pvl` (an independent library used
# by real planetary-science tooling to read ISIS labels) rather than only
# checking our own string output by eye.

import datetime

import numpy as np
import pvl
import pytest

from src.cnet import build_control_network_pvl, write_control_network, _serial_number, _pvl_value
from src.types import MatchResult, Product

FIXED_TIME = "2026-09-04T00:00:00"


def _product(pid="ch2_0001", source="OHRC", acquired_utc=None):
    return Product(
        array=np.zeros((4, 4), dtype=np.float32),
        gsd_m=1.0,
        corners={"ul": (1.0, 1.0), "ur": (1.0, 2.0), "ll": (0.0, 1.0), "lr": (0.0, 2.0)},
        source=source,
        product_id=pid,
        acquired_utc=acquired_utc,
    )


def _match_result(pts_a, pts_b, inlier_mask, scores=None):
    n = len(pts_a)
    return MatchResult(
        pts_a=np.asarray(pts_a, dtype=np.float32),
        pts_b=np.asarray(pts_b, dtype=np.float32),
        scores=np.asarray(scores if scores is not None else [1.0] * n, dtype=np.float32),
        inlier_mask=np.asarray(inlier_mask, dtype=bool),
        transform=np.eye(3, dtype=np.float64),
        matcher="synth",
        shape_a=(100, 100),
        shape_b=(100, 100),
        runtime_s=0.0,
    )


# ---- structural correctness, verified by an independent PVL parser ---------

def test_basic_network_parses_and_has_correct_structure():
    pts_a = [[10.0, 20.0], [30.0, 40.0]]
    pts_b = [[11.0, 21.0], [31.0, 41.0]]
    mr = _match_result(pts_a, pts_b, [True, False], scores=[0.9, 0.4])
    a = _product("ch2_0001", "OHRC")
    b = _product("lro_0007", "NAC")

    text = build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME)
    net = pvl.loads(text)["ControlNetwork"]

    assert net["NetworkId"] == "SIH26166"
    assert net["TargetName"] == "Moon"
    assert net["Version"] == 5

    points = net.getall("ControlPoint")
    assert len(points) == 2

    p0 = points[0]
    assert p0["PointId"] == "pt_00000"
    assert p0["PointType"] == "Free"
    measures = p0.getall("ControlMeasure")
    assert len(measures) == 2
    assert measures[0]["SerialNumber"] == "OHRC/ch2_0001"
    assert measures[0]["Sample"] == pytest.approx(10.0)
    assert measures[0]["Line"] == pytest.approx(20.0)
    assert measures[0]["Ignore"] is False  # point 0 is an inlier
    assert measures[1]["SerialNumber"] == "NAC/lro_0007"
    assert measures[1]["Sample"] == pytest.approx(11.0)
    assert measures[1]["Line"] == pytest.approx(21.0)

    p1 = points[1]
    m1 = p1.getall("ControlMeasure")
    assert m1[0]["Ignore"] is True  # point 1 is an outlier
    assert m1[0]["GoodnessOfFit"] == pytest.approx(0.4)


def test_empty_match_result_is_a_valid_network_with_zero_points():
    empty = np.zeros((0, 2), dtype=np.float32)
    mr = _match_result(empty, empty, np.zeros(0, dtype=bool))
    a, b = _product("a"), _product("b")

    text = build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME)
    net = pvl.loads(text)["ControlNetwork"]  # must not raise

    assert "ControlPoint" not in net  # getall() raises KeyError when absent, by design
    assert net["NetworkId"] == "SIH26166"


def test_single_point_network():
    mr = _match_result([[5.0, 5.0]], [[6.0, 6.0]], [True])
    a, b = _product("a"), _product("b")

    text = build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME)
    net = pvl.loads(text)["ControlNetwork"]

    points = net.getall("ControlPoint")
    assert len(points) == 1
    assert points[0]["PointId"] == "pt_00000"


def test_all_outliers_are_kept_by_default_but_flagged_ignored():
    mr = _match_result([[1.0, 1.0], [2.0, 2.0]], [[1.0, 1.0], [2.0, 2.0]], [False, False])
    a, b = _product("a"), _product("b")

    text = build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME)
    net = pvl.loads(text)["ControlNetwork"]

    points = net.getall("ControlPoint")
    assert len(points) == 2  # kept, not dropped
    for p in points:
        for m in p.getall("ControlMeasure"):
            assert m["Ignore"] is True


def test_realistic_mixed_ratio_keeps_all_ten_with_correct_ignore_flags():
    """10 matches, 7 inliers, 3 outliers -- a realistic split, not just the
    all-or-nothing cases above. Default behaviour keeps all 10 as
    ControlPoints (this writer's own documented design: Ignore marks a
    match as excluded from processing without removing the record of it),
    with exactly the right 7 flagged False and 3 flagged True.
    """
    n = 10
    pts = [[float(i), float(i)] for i in range(n)]
    inlier_mask = [True] * 7 + [False] * 3
    mr = _match_result(pts, pts, inlier_mask)
    a, b = _product("a"), _product("b")

    text = build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME)
    net = pvl.loads(text)["ControlNetwork"]

    points = net.getall("ControlPoint")
    assert len(points) == n  # nothing silently dropped

    ignore_flags = [p.getall("ControlMeasure")[0]["Ignore"] for p in points]
    assert ignore_flags == [False] * 7 + [True] * 3


def test_duplicate_correspondences_are_written_as_separate_points_not_deduplicated():
    """This function transcribes MatchResult faithfully; deduplication (if
    ever needed) is match.py/RANSAC's job, not the writer's.
    """
    mr = _match_result(
        [[100.0, 200.0], [100.0, 200.0]],
        [[120.0, 220.0], [120.0, 220.0]],
        [True, True],
    )
    a, b = _product("a"), _product("b")

    text = build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME)
    net = pvl.loads(text)["ControlNetwork"]

    points = net.getall("ControlPoint")
    assert len(points) == 2  # both kept, not merged into one
    assert points[0]["PointId"] != points[1]["PointId"]  # still uniquely identified
    for p in points:
        m = p.getall("ControlMeasure")[0]
        assert m["Sample"] == pytest.approx(100.0)
        assert m["Line"] == pytest.approx(200.0)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_coordinates_raise_a_clear_error_instead_of_writing_garbage(bad_value):
    """pvl itself happily parses `Sample = nan` back into a real float -- so
    the format wouldn't catch this for us. A non-finite pixel coordinate
    means something upstream is broken (bad sub-pixel refinement, a
    corrupted MatchResult); it should fail loudly here, not produce a file
    that's syntactically valid but semantically meaningless to whatever
    bundle-adjustment tool eventually reads it.
    """
    mr = _match_result([[1.0, 2.0], [bad_value, 4.0]], [[5.0, 6.0], [7.0, 8.0]], [True, True])
    a, b = _product("a"), _product("b")

    with pytest.raises(ValueError, match="non-finite|NaN|inf"):
        build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME)


def test_non_finite_coordinates_in_a_filtered_out_outlier_do_not_raise():
    """A NaN in a match that inliers_only=True will drop anyway shouldn't
    block the ones that are actually being written.
    """
    mr = _match_result(
        [[1.0, 2.0], [float("nan"), 4.0]],
        [[5.0, 6.0], [7.0, 8.0]],
        [True, False],  # the NaN one is the outlier being filtered out
    )
    a, b = _product("a"), _product("b")

    text = build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME, inliers_only=True)
    net = pvl.loads(text)["ControlNetwork"]
    assert len(net.getall("ControlPoint")) == 1


def test_finite_out_of_range_coordinates_pass_through_unchanged():
    """Negative or larger-than-image-bounds coordinates are still *finite*
    -- sub-pixel refinement can legitimately produce these near an image
    edge (see scripts/report.py's equivalent boundary test). Only
    non-finite values are rejected; this is not one of them.
    """
    mr = _match_result([[-5.5, 1000.25]], [[-3.0, 2000.0]], [True])
    a, b = _product("a"), _product("b")

    text = build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME)  # must not raise
    net = pvl.loads(text)["ControlNetwork"]
    m = net.getall("ControlPoint")[0].getall("ControlMeasure")[0]
    assert m["Sample"] == pytest.approx(-5.5)
    assert m["Line"] == pytest.approx(1000.25)


def test_two_separate_pair_networks_do_not_collide_and_reset_point_ids():
    """MatchResult is frozen to exactly one image pair (see types.py), so a
    genuine multi-image network is out of scope here -- but confirms two
    independent per-pair calls (e.g. for two different image pairs in the
    same session) don't leak state into each other: PointIds restart from
    pt_00000 each time (there's nothing shared to collide), and each
    network correctly names its own two images, not the other call's.
    """
    mr1 = _match_result([[1.0, 1.0]], [[2.0, 2.0]], [True])
    net1_text = build_control_network_pvl(mr1, _product("ch2_a"), _product("lro_a"), created_utc=FIXED_TIME)

    mr2 = _match_result([[9.0, 9.0]], [[8.0, 8.0]], [True])
    net2_text = build_control_network_pvl(mr2, _product("ch2_b"), _product("lro_b"), created_utc=FIXED_TIME)

    net1 = pvl.loads(net1_text)["ControlNetwork"]
    net2 = pvl.loads(net2_text)["ControlNetwork"]

    assert net1.getall("ControlPoint")[0]["PointId"] == "pt_00000"
    assert net2.getall("ControlPoint")[0]["PointId"] == "pt_00000"  # independent, not continuing

    m1 = net1.getall("ControlPoint")[0].getall("ControlMeasure")[0]
    m2 = net2.getall("ControlPoint")[0].getall("ControlMeasure")[0]
    assert m1["SerialNumber"] == "OHRC/ch2_a"
    assert m2["SerialNumber"] == "OHRC/ch2_b"  # no cross-talk between the two calls


def test_inliers_only_flag_drops_outliers_entirely():
    mr = _match_result(
        [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]],
        [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]],
        [True, False, True],
    )
    a, b = _product("a"), _product("b")

    text = build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME, inliers_only=True)
    net = pvl.loads(text)["ControlNetwork"]

    points = net.getall("ControlPoint")
    assert len(points) == 2  # only the two inliers


def test_point_and_measure_counts_are_structurally_balanced():
    """Explicit count of Object=/End_Object and Group=/End_Group pairs, on
    top of the parser accepting it -- a stronger, hand-checkable guarantee
    than "the parser didn't complain."
    """
    n = 10
    pts = [[float(i), float(i)] for i in range(n)]
    mr = _match_result(pts, pts, [True] * n)
    a, b = _product("a"), _product("b")

    text = build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME)

    assert text.count("Object = ControlNetwork") == 1
    assert text.count("Object = ControlPoint") == n
    assert text.count("End_Object") == n + 1  # n points + the network itself
    assert text.count("Group = ControlMeasure") == 2 * n
    assert text.count("End_Group") == 2 * n


def test_point_ids_are_unique_and_sequential():
    n = 12
    pts = [[float(i), float(i)] for i in range(n)]
    mr = _match_result(pts, pts, [True] * n)
    a, b = _product("a"), _product("b")

    text = build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME)
    net = pvl.loads(text)["ControlNetwork"]
    ids = [p["PointId"] for p in net.getall("ControlPoint")]

    assert ids == [f"pt_{i:05d}" for i in range(n)]
    assert len(set(ids)) == n  # all unique


def test_special_characters_in_product_id_round_trip_through_quoting():
    """product_id containing PVL-special characters (space, '#') must still
    produce a file the independent parser accepts. A literal embedded
    double-quote can't be represented in PVL's quoted-string grammar at all
    (confirmed by the parser rejecting a backslash-escaped attempt) -- it's
    swapped for a single quote rather than corrupting the file.
    """
    mr = _match_result([[1.0, 2.0]], [[3.0, 4.0]], [True])
    a = _product('weird id #1 with "quotes"', "OHRC")
    b = _product("b")

    text = build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME)
    net = pvl.loads(text)["ControlNetwork"]  # must not raise

    measures = net.getall("ControlPoint")[0].getall("ControlMeasure")
    assert measures[0]["SerialNumber"] == "OHRC/weird id #1 with 'quotes'"


def test_sample_and_line_use_fixed_precision_not_raw_float_noise():
    mr = _match_result([[1.0 / 3.0, 2.0 / 3.0]], [[0.1, 0.2]], [True])
    a, b = _product("a"), _product("b")

    text = build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME)

    assert "0.333333" in text  # 6 fixed decimals, not float64 repr noise
    assert "0.100000" in text

    net = pvl.loads(text)["ControlNetwork"]
    m = net.getall("ControlPoint")[0].getall("ControlMeasure")[0]
    assert m["Sample"] == pytest.approx(1.0 / 3.0, abs=1e-6)


def test_created_utc_is_injectable_for_determinism():
    """`pvl` recognises an ISO-8601-looking bare value as a real PVL
    date-time literal and parses it into a `datetime.datetime`, not a
    string -- which is correct PVL behaviour, and confirms Created/DateTime
    are written as proper date-time values rather than opaque strings.
    """
    mr = _match_result([[1.0, 1.0]], [[1.0, 1.0]], [True])
    a, b = _product("a"), _product("b")

    text = build_control_network_pvl(mr, a, b, created_utc=FIXED_TIME)
    net = pvl.loads(text)["ControlNetwork"]

    expected = datetime.datetime(2026, 9, 4, 0, 0, 0)
    assert net["Created"].replace(tzinfo=None) == expected
    point = net.getall("ControlPoint")[0]
    assert point["DateTime"].replace(tzinfo=None) == expected


def test_created_utc_defaults_to_something_when_not_provided():
    mr = _match_result([[1.0, 1.0]], [[1.0, 1.0]], [True])
    a, b = _product("a"), _product("b")

    text = build_control_network_pvl(mr, a, b)  # no created_utc passed
    net = pvl.loads(text)["ControlNetwork"]  # must not raise
    assert net["Created"]  # non-empty


# ---- _serial_number ----------------------------------------------------------

def test_serial_number_includes_acquired_utc_when_present():
    p = _product("ch2_0001", "OHRC", acquired_utc="2021-05-01T12:00:00")
    assert _serial_number(p) == "OHRC/ch2_0001/2021-05-01T12:00:00"


def test_serial_number_omits_acquired_utc_when_absent():
    p = _product("ch2_0001", "OHRC", acquired_utc=None)
    assert _serial_number(p) == "OHRC/ch2_0001"


# ---- write_control_network / file output ------------------------------------

def test_write_control_network_produces_a_file_readable_by_an_independent_parser(tmp_path):
    mr = _match_result([[1.0, 2.0], [3.0, 4.0]], [[5.0, 6.0], [7.0, 8.0]], [True, True])
    a, b = _product("a"), _product("b")

    output_path = tmp_path / "network.pvl"
    write_control_network(mr, a, b, str(output_path), created_utc=FIXED_TIME)

    assert output_path.exists()
    net = pvl.load(str(output_path))["ControlNetwork"]  # independent file-based parse
    assert len(net.getall("ControlPoint")) == 2


# ---- _pvl_value --------------------------------------------------------------

def test_pvl_value_formats_each_python_type_correctly():
    assert _pvl_value(True) == "True"
    assert _pvl_value(False) == "False"
    assert _pvl_value(5) == "5"
    assert _pvl_value(3.14159265) == "3.141593"
    assert _pvl_value("plain_identifier") == "plain_identifier"
    assert _pvl_value("has space") == '"has space"'
    assert _pvl_value("") == '""'
    assert _pvl_value('has "quotes"') == "\"has 'quotes'\""
