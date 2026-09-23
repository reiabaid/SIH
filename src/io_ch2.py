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


def _crop_window_for_overlap(corners: dict, shape: tuple, hint_corners: dict,
                              margin_px: int = 200) -> "tuple[int, int, int, int] | None":
    """Pixel window (row_start, row_end, col_start, col_end), inclusive, that
    covers the intersection of this product's own footprint (`corners`,
    `shape`) with another product's footprint (`hint_corners`), expanded by
    `margin_px` on each side and clipped to the array bounds. Returns None
    if the two footprints don't overlap at all, or the resulting window is
    degenerate -- callers should fall back to a full decode in that case
    (this is a best-effort speed optimization, not where a real
    "products don't overlap" error should be raised).

    Uses the same single 4-corner perspective-fit approximation
    src/geo.py's `_pixel_to_geo_transform` already applies to CH2 products
    throughout the rest of the pipeline (align_pair, footprint_overlap) --
    CH2 has no per-line SPICE geometry to do better with (the piecewise fit
    in src/geo.py is LRO-only, see that function's own docstring), so this
    doesn't introduce a new approximation, only reuses the one already
    trusted elsewhere for this same product type.
    """
    import cv2
    from shapely.geometry import Polygon

    h, w = shape[:2]
    order = ("ul", "ur", "lr", "ll")
    pixel_corners = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
    geo_corners = np.float32([[corners[k][1], corners[k][0]] for k in order])  # (lon, lat)
    pix2geo = cv2.getPerspectiveTransform(pixel_corners, geo_corners)

    poly_self = Polygon([(corners[k][1], corners[k][0]) for k in order])
    poly_hint = Polygon([(hint_corners[k][1], hint_corners[k][0]) for k in order])
    if not poly_self.is_valid or not poly_hint.is_valid:
        return None
    inter = poly_self.intersection(poly_hint)
    if inter.is_empty or inter.area == 0:
        return None

    min_lon, min_lat, max_lon, max_lat = inter.bounds
    geo2pix = np.linalg.inv(pix2geo)
    geo_box = np.float32([
        [min_lon, min_lat], [max_lon, min_lat], [max_lon, max_lat], [min_lon, max_lat],
    ]).reshape(-1, 1, 2)
    pix_box = cv2.perspectiveTransform(geo_box, geo2pix).reshape(-1, 2)

    col_start = int(np.floor(pix_box[:, 0].min())) - margin_px
    col_end = int(np.ceil(pix_box[:, 0].max())) + margin_px
    row_start = int(np.floor(pix_box[:, 1].min())) - margin_px
    row_end = int(np.ceil(pix_box[:, 1].max())) + margin_px

    col_start, row_start = max(0, col_start), max(0, row_start)
    col_end, row_end = min(w - 1, col_end), min(h - 1, row_end)
    if col_end <= col_start or row_end <= row_start:
        return None
    return row_start, row_end, col_start, col_end


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


def load_product(xml_path: str, overlap_hint: "Product | dict | None" = None) -> Product:
    """Load a Chandrayaan-2 OHRC product.

    Deliberately NOT using src/product_cache.py's on-disk cache here, unlike
    io_lro.load_product. Tried it (2026-09-16): an OHRC strip's array is
    large enough that the pickled cache file hit 4.49GB for one product, and
    reading that back only cut load_ch2's ~17-21s cost to ~4-16s, not the
    near-zero win the same approach gave LRO (whose cost is genuinely
    network-bound, not I/O-bound). Fixed differently, via `overlap_hint`
    below: crop to the actual overlap region before decoding, rather than
    caching the whole raster.
    """
    return _load_product_uncached(xml_path, overlap_hint=overlap_hint)


def _load_product_uncached(xml_path: str, overlap_hint: "Product | dict | None" = None) -> Product:
    """
    Load a Chandrayaan-2 OHRC product into the shared Product dataclass.

    Parameters
    ----------
    xml_path : str
        Path to the product's .xml PDS4 label. The paired .img file must
        sit in the same directory with the same stem.
    overlap_hint : Product or corners dict, optional
        Another product (or just its `.corners` dict) this one is about to
        be matched against. When given, only the pixel window covering their
        footprint intersection (plus a safety margin) is decoded from disk,
        via a windowed rasterio read, instead of the full raster --
        `_crop_window_for_overlap`'s docstring covers the geometry
        assumptions this relies on. Falls back to a full decode (unchanged
        behaviour) if the hint is absent, the footprints don't overlap, or
        GDAL (rather than rasterio) ends up being the reader used, since
        GDAL's `ReadAsArray()` doesn't offer an equally simple windowed path
        here -- in that case the crop still gets applied in-memory after a
        full read, which saves the returned array's size but not the I/O.

        Known behavioural difference from an un-hinted load: contrast
        normalisation below is fit to the *cropped* array's own min/max, not
        the full raster's, so a cropped and an uncropped load of the same
        product can differ slightly in overall brightness/contrast scaling
        even where both cover the same physical ground. Validate against the
        full real-pair inventory before relying on this for anything beyond
        the two products actually being registered against each other.

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

    # Corners are needed up front now (to compute a crop window before
    # deciding how to read the array), not just for the returned Product.
    full_corners = _parse_corners(root, xml_path)
    hint_corners = overlap_hint.corners if isinstance(overlap_hint, Product) else overlap_hint

    # --- read the array ---
    # Prefer osgeo.gdal directly if installed; fall back to rasterio, which
    # bundles its own GDAL build (PDS4 driver included) and doesn't need the
    # separate osgeo package — osgeo's wheel requires a C++ build toolchain
    # on Windows, which isn't something to assume is available.
    array = None
    read_errors = []
    crop_window = None  # (row_start, row_end, col_start, col_end) in FULL-image pixel space, or None
    full_shape = None   # the un-cropped array's own (h, w), needed later to re-derive crop corners

    if _HAVE_GDAL:
        try:
            ds = gdal.Open(xml_path)  # GDAL's PDS4 driver reads via the label
            if ds is None:
                raise LabelParseError(
                    f"GDAL could not open label (returned None): {xml_path}"
                )
            array = ds.ReadAsArray()
            full_shape = array.shape[:2]
            if hint_corners is not None:
                crop_window = _crop_window_for_overlap(full_corners, full_shape, hint_corners)
                if crop_window is not None:
                    row_start, row_end, col_start, col_end = crop_window
                    array = array[row_start:row_end + 1, col_start:col_end + 1]
        except Exception as e:
            read_errors.append(f"gdal: {e}")

    if array is None:
        try:
            import rasterio
            with rasterio.open(xml_path) as ds:
                full_shape = (ds.height, ds.width)
                if hint_corners is not None:
                    crop_window = _crop_window_for_overlap(full_corners, full_shape, hint_corners)
                if crop_window is not None:
                    from rasterio.windows import Window
                    row_start, row_end, col_start, col_end = crop_window
                    window = Window.from_slices(
                        (row_start, row_end + 1), (col_start, col_end + 1)
                    )
                    array = ds.read(1, window=window) if ds.count == 1 else ds.read(window=window)
                else:
                    array = ds.read(1) if ds.count == 1 else ds.read()
        except Exception as e:
            read_errors.append(f"rasterio: {e}")

    if array is None:
        raise LabelParseError(
            f"{xml_path}: could not be read by GDAL or rasterio. "
            f"Errors: {'; '.join(read_errors) if read_errors else 'neither is installed'}"
        )

    if array is None or array.size == 0:
        raise LabelParseError(f"Read an empty array from: {img_path}")

    array = array.astype(np.float32, copy=False)
    # normalise to 0..1 using the array's own min/max (raw DN range varies).
    #
    # In-place (-=, /=) rather than `array = (array - arr_min) / (arr_max - arr_min)`:
    # that expression allocates two full-size temporary arrays (one for the
    # subtraction, one for the division) that briefly coexist with the
    # original -- on a real ~4.2GB OHRC-strip-sized float32 array this alone
    # peaks around 8-9GB, which OOM-killed a real registration inside a
    # memory-constrained container (confirmed via resource.getrusage
    # profiling: the crash happened during this function). In-place ops
    # mutate the existing buffer with no extra allocation, so peak memory
    # here stays at the one array's own size.
    arr_min, arr_max = float(array.min()), float(array.max())
    if arr_max > arr_min:
        array -= arr_min
        array /= (arr_max - arr_min)
    else:
        raise LabelParseError(
            f"Array has no dynamic range (min == max) in: {img_path}"
        )

    # --- geometry & metadata from the label ---
    if crop_window is not None:
        # Re-derive corners for the CROPPED array from the same pixel<->geo
        # transform the full image's corners were fit from -- evaluated at
        # the crop window's own pixel corners (in FULL-image pixel space),
        # not the original 4. Every downstream consumer (align_pair,
        # footprint_overlap, ...) assumes `product.corners` describes the
        # actual array's footprint, so this must track the crop, not the
        # original image.
        import cv2
        row_start, row_end, col_start, col_end = crop_window
        order = ("ul", "ur", "lr", "ll")
        full_h, full_w = full_shape
        full_pixel_corners = np.float32(
            [[0, 0], [full_w - 1, 0], [full_w - 1, full_h - 1], [0, full_h - 1]]
        )
        full_geo_corners = np.float32([[full_corners[k][1], full_corners[k][0]] for k in order])
        pix2geo = cv2.getPerspectiveTransform(full_pixel_corners, full_geo_corners)

        crop_pixel_corners = np.float32([
            [col_start, row_start], [col_end, row_start],
            [col_end, row_end], [col_start, row_end],
        ]).reshape(-1, 1, 2)
        crop_geo_corners = cv2.perspectiveTransform(crop_pixel_corners, pix2geo).reshape(-1, 2)
        corners = {
            k: (float(lat), float(lon))
            for k, (lon, lat) in zip(order, crop_geo_corners)
        }
        meta_crop_info = {"cropped_from_shape": full_shape, "cropped_window": crop_window}
    else:
        corners = full_corners
        meta_crop_info = {}

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
    meta.update(meta_crop_info)

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