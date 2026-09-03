# src/cnet.py — write matches out as an ISIS control network (PVL format)
# Owner: Riddhi
#
# Format verified against USGS's public spec (isis.astrogeology.usgs.gov/.../
# ControlNetworks) and cross-checked by round-tripping through the independent
# `pvl` parser (the same library planetary-science Python tooling uses to read
# real ISIS labels) -- not just written to look right by eye.
#
# Deliberately scoped: every ControlPoint is written as "Free" (a tie point
# whose ground position is determined later by whoever runs the bundle
# adjustment) with no a-priori XYZ. We only have pixel correspondences, not a
# triangulated 3D ground position, so writing AprioriXYZ would be fabricating
# a number we have no basis for -- "Free" is the type that's correct to use
# when you only have image measures. No ISIS install needed to write this;
# only to consume it downstream, which is out of scope here.

import datetime

import numpy as np

from src.types import MatchResult, Product

PVL_VERSION = 5
_PVL_SPECIAL_CHARS = set(' \t()=<>{}#"\'')


def _pvl_value(value) -> str:
    """Format one Python value as a PVL right-hand side."""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        return f"{value:.6f}"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if text == "" or any(ch in _PVL_SPECIAL_CHARS for ch in text):
        # PVL's quoted-string grammar has no escape for an embedded double
        # quote (backslash-escaping it produces invalid PVL, confirmed by
        # round-tripping through the independent `pvl` parser) -- swap any
        # embedded double quote for a single quote rather than write
        # unparseable output.
        return f'"{text.replace(chr(34), chr(39))}"'
    return text


def _serial_number(product: Product) -> str:
    """A stand-in for ISIS's own generated serial number (spacecraft/instrument/
    start-time), since that's produced by ISIS itself from a real cube label.
    Built from what Product actually carries; the only property that matters
    for a control network is that it's consistent for the same image
    throughout the file, which this is.
    """
    parts = [product.source, product.product_id]
    if product.acquired_utc:
        parts.append(product.acquired_utc)
    return "/".join(parts)


def build_control_network_pvl(
    match_result: MatchResult,
    product_a: Product,
    product_b: Product,
    network_id: str = "SIH26166",
    target_name: str = "Moon",
    user_name: str = "riddhi",
    chooser_name: str = "sih26166_cnet_writer",
    created_utc: "str | None" = None,
    measure_type: str = "RegisteredSubPixel",
    inliers_only: bool = False,
) -> str:
    """Build a PVL-format ISIS control network from a MatchResult, as text.

    Every match becomes one ControlPoint with two ControlMeasures (one per
    image). Outliers are kept by default with `Ignore = True` (ISIS's own
    documented meaning for that flag) rather than silently dropped, so the
    file still records what the matcher found; pass `inliers_only=True` to
    omit them instead.

    `created_utc` is injectable so this function is deterministic and
    testable -- pass a fixed string in tests; a real caller can leave it as
    the current UTC time.

    Scoped to exactly one image pair, matching `MatchResult`'s own frozen
    contract in types.py (a pair, not an N-image network) -- not an
    oversight. A real multi-image control network needs to know which
    points in *different* pairs represent the same physical ground
    feature, information a set of independent pairwise MatchResults
    doesn't carry; merging several of this function's outputs into one
    true multi-image network is a separate, harder problem than writing
    the file format, and out of scope here. Duplicate (pts_a[i], pts_b[i])
    rows are written as separate ControlPoints, not deduplicated -- this
    function transcribes MatchResult faithfully, it doesn't clean it.
    """
    created = created_utc or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    serial_a = _serial_number(product_a)
    serial_b = _serial_number(product_b)

    n = len(match_result.pts_a)
    indices = range(n)
    if inliers_only:
        indices = [i for i in indices if match_result.inlier_mask[i]]

    if not np.all(np.isfinite(match_result.pts_a[list(indices)])) or not np.all(
        np.isfinite(match_result.pts_b[list(indices)])
    ):
        bad = [i for i in indices if not (np.all(np.isfinite(match_result.pts_a[i])) and np.all(np.isfinite(match_result.pts_b[i])))]
        raise ValueError(
            f"build_control_network_pvl: non-finite coordinate (NaN/inf) at match index(es) {bad} "
            "-- a control network with a NaN/inf Sample or Line is meaningless to any real "
            "bundle-adjustment tool, even though it happens to be syntactically valid PVL."
        )

    lines = [
        "Object = ControlNetwork",
        f"  NetworkId    = {_pvl_value(network_id)}",
        f"  TargetName   = {_pvl_value(target_name)}",
        f"  UserName     = {_pvl_value(user_name)}",
        f"  Created      = {_pvl_value(created)}",
        '  Description  = "Correspondences from src/match.py; Free-type tie points, no a priori ground coordinates"',
        f"  Version      = {PVL_VERSION}",
        "",
    ]

    for i in indices:
        is_inlier = bool(match_result.inlier_mask[i])
        score = float(match_result.scores[i])
        point_id = f"pt_{i:05d}"

        lines.append("  Object = ControlPoint")
        lines.append("    PointType   = Free")
        lines.append(f"    PointId     = {_pvl_value(point_id)}")
        lines.append(f"    ChooserName = {_pvl_value(chooser_name)}")
        lines.append(f"    DateTime    = {_pvl_value(created)}")
        lines.append("")

        for serial, pt in ((serial_a, match_result.pts_a[i]), (serial_b, match_result.pts_b[i])):
            lines.append("    Group = ControlMeasure")
            lines.append(f"      SerialNumber  = {_pvl_value(serial)}")
            lines.append(f"      MeasureType   = {_pvl_value(measure_type)}")
            lines.append(f"      ChooserName   = {_pvl_value(chooser_name)}")
            lines.append(f"      DateTime      = {_pvl_value(created)}")
            lines.append(f"      Sample        = {_pvl_value(float(pt[0]))}")
            lines.append(f"      Line          = {_pvl_value(float(pt[1]))}")
            lines.append(f"      GoodnessOfFit = {_pvl_value(score)}")
            lines.append(f"      Ignore        = {_pvl_value(not is_inlier)}")
            lines.append("    End_Group")

        lines.append("  End_Object")
        lines.append("")

    lines.append("End_Object")
    return "\n".join(lines) + "\n"


def write_control_network(
    match_result: MatchResult,
    product_a: Product,
    product_b: Product,
    output_path: str,
    **kwargs,
) -> None:
    """Build the control network and write it to `output_path`."""
    text = build_control_network_pvl(match_result, product_a, product_b, **kwargs)
    with open(output_path, "w") as f:
        f.write(text)
