"""
io_ch2.py — Chandrayaan-2 OHRC PDS4 product reader.

Reads a Chandrayaan-2 OHRC product (a .xml PDS4 label + its paired .img
binary) into the shared `Product` dataclass defined in src/types.py.

Usage:
    from io_ch2 import load_product
    p = load_product("data/calibrated/20200229/ch2_ohr_ncp_..._d32.xml")

Notes on this specific label format (confirmed against a real ISRO OHRC
calibrated-product label):
- Corner coordinates and most instrument parameters live under an
  `isda:` namespace prefix (e.g. <isda:upper_left_latitude>), NOT plain
  tag names. We strip namespaces when parsing so this is robust to the
  exact URI ISRO uses.
- The label conveniently ships `isda:pixel_resolution` (m/pixel)
  directly — we use that as ground sample distance rather than deriving
  it from spacecraft altitude and focal length.
- Two corner sets exist: `System_Level_Coordinates` and
  `Refined_Corner_Coordinates`. We prefer the refined set and fall back
  to system-level if refined is missing.
- Chandrayaan-2 OHRC labels do not carry sun-angle geometry. incidence_deg
  and subsolar_azimuth_deg are always set to None here — do NOT guess or
  backfill these; LRO NAC labels are where that field gets populated.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import asdict

import numpy as np

try:
    from osgeo import gdal
    gdal.UseExceptions()
    _HAVE_GDAL = True
except ImportError:
    _HAVE_GDAL = False

from src.types import Product  # run this module as `python -m src.io_ch2 ...`
                                # from the repo root so this import resolves.


class LabelParseError(Exception):
    """Raised when a PDS4 label is missing a field we need, is malformed,
    or otherwise can't be parsed. Always includes the offending file path."""
    pass


def _strip_ns(tag: str) -> str:
    """'{http://...}upper_left_latitude' -> 'upper_left_latitude'"""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _local_findall(root: ET.Element, local_name: str):
    """Find all descendant elements by local tag name, ignoring namespace."""
    return [el for el in root.iter() if _strip_ns(el.tag) == local_name]


def _local_find_text(root: ET.Element, local_name: str, xml_path: str) -> str:
    matches = _local_findall(root, local_name)
    if not matches or matches[0].text is None:
        raise LabelParseError(
            f"Missing required field <{local_name}> in label: {xml_path}"
        )
    return matches[0].text.strip()


def _local_find_float(root: ET.Element, local_name: str, xml_path: str) -> float:
    text = _local_find_text(root, local_name, xml_path)
    try:
        return float(text)
    except ValueError as e:
        raise LabelParseError(
            f"Field <{local_name}> in {xml_path} is not a valid number: {text!r}"
        ) from e


def _parse_corners(root: ET.Element, xml_path: str) -> dict:
    """
    Returns {"ul": (lat, lon), "ur": (lat, lon), "ll": (lat, lon), "lr": (lat, lon)}
    Prefers Refined_Corner_Coordinates; falls back to System_Level_Coordinates.
    """
    corner_block = None
    for block_name in ("Refined_Corner_Coordinates", "System_Level_Coordinates"):
        matches = _local_findall(root, block_name)
        if matches:
            corner_block = matches[0]
            break

    if corner_block is None:
        raise LabelParseError(
            f"No corner coordinate block (Refined_Corner_Coordinates or "
            f"System_Level_Coordinates) found in label: {xml_path}"
        )

    key_map = {
        "ul": ("upper_left_latitude", "upper_left_longitude"),
        "ur": ("upper_right_latitude", "upper_right_longitude"),
        "ll": ("lower_left_latitude", "lower_left_longitude"),
        "lr": ("lower_right_latitude", "lower_right_longitude"),
    }

    corners = {}
    for key, (lat_tag, lon_tag) in key_map.items():
        lat_el = _local_findall(corner_block, lat_tag)
        lon_el = _local_findall(corner_block, lon_tag)
        if not lat_el or not lon_el:
            raise LabelParseError(
                f"Missing corner field {lat_tag}/{lon_tag} in label: {xml_path}"
            )
        corners[key] = (float(lat_el[0].text), float(lon_el[0].text))

    return corners


def _find_img_path(xml_path: str) -> str:
    """The .img file sits alongside its .xml label with a matching stem."""
    base = os.path.splitext(xml_path)[0]
    img_path = base + ".img"
    if not os.path.exists(img_path):
        # try uppercase extension too — ISRO's zips sometimes vary
        alt = base + ".IMG"
        if os.path.exists(alt):
            return alt
        raise LabelParseError(
            f"Expected matching .img file not found next to label: {xml_path} "
            f"(looked for {img_path})"
        )
    return img_path


def load_product(xml_path: str) -> Product:
    """
    Load a Chandrayaan-2 OHRC product into the shared Product dataclass.

    Parameters
    ----------
    xml_path : str
        Path to the product's .xml PDS4 label. The paired .img file must
        sit in the same directory with the same stem.

    Raises
    ------
    LabelParseError
        If the label is missing required fields, is malformed, or the
        paired .img file can't be found/opened.
    """
    if not os.path.exists(xml_path):
        raise LabelParseError(f"Label file does not exist: {xml_path}")

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise LabelParseError(f"Malformed XML in label: {xml_path} ({e})") from e

    img_path = _find_img_path(xml_path)

    # --- read the array ---
    if _HAVE_GDAL:
        try:
            ds = gdal.Open(xml_path)  # GDAL's PDS4 driver reads via the label
            if ds is None:
                raise LabelParseError(
                    f"GDAL could not open label (returned None): {xml_path}"
                )
            array = ds.ReadAsArray()
        except Exception as e:
            raise LabelParseError(
                f"GDAL failed to read product for label {xml_path}: {e}"
            ) from e
    else:
        raise LabelParseError(
            "GDAL (osgeo) is not installed — install it to read PDS4 products. "
            "Try: conda install -c conda-forge gdal"
        )

    if array is None or array.size == 0:
        raise LabelParseError(f"Read an empty array from: {img_path}")

    array = array.astype(np.float32)
    # normalise to 0..1 using the array's own min/max (raw DN range varies)
    arr_min, arr_max = float(array.min()), float(array.max())
    if arr_max > arr_min:
        array = (array - arr_min) / (arr_max - arr_min)
    else:
        raise LabelParseError(
            f"Array has no dynamic range (min == max) in: {img_path}"
        )

    # --- geometry & metadata from the label ---
    corners = _parse_corners(root, xml_path)

    # GSD: prefer the label's own pixel_resolution (m/pixel) directly
    pixel_res_matches = _local_findall(root, "pixel_resolution")
    if pixel_res_matches and pixel_res_matches[0].text:
        gsd_m = float(pixel_res_matches[0].text)
    else:
        raise LabelParseError(
            f"No isda:pixel_resolution field found in label: {xml_path}"
        )

    product_id_matches = _local_findall(root, "logical_identifier")
    product_id = (
        product_id_matches[0].text.strip()
        if product_id_matches and product_id_matches[0].text
        else os.path.splitext(os.path.basename(xml_path))[0]
    )

    start_time_matches = _local_findall(root, "start_date_time")
    acquired_utc = (
        start_time_matches[0].text.strip()
        if start_time_matches and start_time_matches[0].text
        else None
    )

    # optional extras, stashed in meta rather than promoted to top-level
    # fields, since the frozen contract doesn't name them explicitly
    meta = {}
    for optional_field in (
        "focal_length",
        "detector_pixel_width",
        "spacecraft_altitude",
        "orbit_limb_direction",
        "reference_data_used",
    ):
        matches = _local_findall(root, optional_field)
        if matches and matches[0].text:
            meta[optional_field] = matches[0].text.strip()

    return Product(
        array=array,
        gsd_m=gsd_m,
        corners=corners,
        source="OHRC",
        product_id=product_id,
        acquired_utc=acquired_utc,
        incidence_deg=None,           # CH-2 labels never carry this — see module docstring
        subsolar_azimuth_deg=None,    # same
        meta=meta,
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python io_ch2.py <path_to_label.xml>")
        sys.exit(1)
    p = load_product(sys.argv[1])
    print(f"Loaded product: {p.product_id}")
    print(f"  shape: {p.array.shape}, dtype: {p.array.dtype}")
    print(f"  gsd_m: {p.gsd_m}")
    print(f"  corners: {p.corners}")
    print(f"  acquired_utc: {p.acquired_utc}")
    print(f"  meta: {p.meta}")