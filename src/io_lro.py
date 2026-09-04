"""
src/io_lro.py

Reads LRO NAC EDR/CDR products (PDS3 .IMG with attached label) into
the shared Product dataclass defined in src/types.py.

Primary path: pdr.read() (handles PDS3 labels reliably for LROC NAC).
Fallback path: gdal.Open() if pdr fails and GDAL happens to be available.

Usage:
    from src.io_lro import load_product
    p = load_product("data/lro_nac/M1262183951LC.IMG")

Label notes
-----------
pdr 1.4.x returns data.LABEL as a raw PDS3 ASCII string, not a parsed dict.
We parse it with a lightweight regex extractor (_parse_label) so no pvl
dependency is needed.

Geometry notes
--------------
LROC NAC CDR/EDR labels do NOT carry geographic geometry (INCIDENCE_ANGLE,
CENTER_LATITUDE, SUB_SOLAR_AZIMUTH, etc.) — those come from SPICE kernels.
We query the NAIF WebGeocalc REST API (kernel set 21 = Lunar Reconnaissance
Orbiter) at each product's START_TIME to obtain real geometry.  When offline
or when kernels are not yet available (e.g. very recent orbits), all geometry
fields gracefully degrade to None; the Product dataclass already declares them
Optional[float].

GSD
---
Derived from CROSSTRACK_SUMMING using published NAC physical constants
(LROC EDR/CDR SIS, Table 2):
  focal length = 699.62 mm, pixel pitch = 7.0 µm, nominal orbit = 50 km
→ ~0.50 m/px at summing=1, ~1.00 m/px at summing=2.
"""

from __future__ import annotations

import math
import os
import re
import numpy as np

from src.types import Product


class LROReadError(Exception):
    """Raised when an LRO NAC product cannot be parsed."""
    pass


# ---------------------------------------------------------------------------
# PDS3 label parsing  (data.LABEL is a raw ASCII string in pdr 1.4.x)
# ---------------------------------------------------------------------------

def _parse_label(label_str: str) -> dict:
    """
    Parse a raw PDS3 label string into a flat {KEY: value_str} dict.

    Handles: unquoted scalars, values with units (<ms>, <degC>),
    double-quoted strings, parenthesised tuples, LRO:-prefixed keys.
    Structural keywords (OBJECT/END_OBJECT/GROUP/END_GROUP) are skipped.
    """
    SKIP = frozenset({"OBJECT", "END_OBJECT", "GROUP", "END_GROUP", "PDS_VERSION_ID"})
    result: dict = {}
    pattern = re.compile(
        r'^\s*([A-Z][A-Z0-9_:]*)\s*=\s*'
        r'(?:"([^"\n]*)"'        # group 2: double-quoted string
        r'|(\([^\)\n]*\))'       # group 3: parenthesised tuple
        r'|([^\r\n<"(]+?))'      # group 4: bare value (stop before unit/EOL)
        r'(?:\s*<[^>\n]+>)?\s*$',
        re.MULTILINE,
    )
    for m in pattern.finditer(label_str):
        key = m.group(1)
        if key in SKIP:
            continue
        val = m.group(2)
        if val is None:
            val = m.group(3)
        if val is None:
            val = (m.group(4) or "").strip()
        result[key] = val
    return result


def _read_attached_pds3_label(path: str) -> str:
    """Read the ASCII PDS3 label at the front of an attached .IMG file."""
    with open(path, "rb") as handle:
        header = handle.read(1024 * 1024)
    text = header.decode("ascii", errors="ignore")
    end_match = re.search(r"^\s*END\s*$", text, flags=re.MULTILINE)
    return text[:end_match.end()] if end_match else text


def _get(parsed: dict, *candidates: str):
    """Return the first matching value from a parsed label dict, or None."""
    for cand in candidates:
        v = parsed.get(cand)
        if v is not None:
            return v
    return None


def _as_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = re.sub(r"\s*<[^>]+>\s*$", "", str(value)).strip()
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _as_str(value) -> str | None:
    if value is None:
        return None
    return str(value).strip().strip('"')


# ---------------------------------------------------------------------------
# Array loaders
# ---------------------------------------------------------------------------

def _load_with_pdr(path: str):
    import pdr

    data = pdr.read(path)
    if "IMAGE" not in data.keys():
        raise LROReadError(f"{path}: pdr found no IMAGE data object")

    array = np.asarray(data["IMAGE"])
    label_str = data.LABEL
    if not isinstance(label_str, str):
        label_str = str(label_str)
    return array, label_str


def _load_with_gdal_fallback(path: str):
    from osgeo import gdal

    ds = gdal.Open(path)
    if ds is None:
        raise LROReadError(f"{path}: GDAL could not open file")

    array = ds.ReadAsArray()
    meta_dict = ds.GetMetadata() or {}
    # GDAL exposes only a subset of PDS3 keywords for these EDR products;
    # recover the attached label so fields such as CROSSTRACK_SUMMING survive.
    label_str = _read_attached_pds3_label(path)
    if not label_str.strip():
        label_str = "\n".join(f"{k} = {v}" for k, v in meta_dict.items())
    return array, label_str


# ---------------------------------------------------------------------------
# Array normalisation
# ---------------------------------------------------------------------------

def _normalize_to_float01(
    array: np.ndarray, scaling_factor: float | None = None
) -> np.ndarray:
    """
    Normalise pixel values to [0, 1] float32.

    For CDR products a SCALING_FACTOR converts DN → Scaled I/F reflectance
    before stretching.  NULL/fill pixels (< -32752 in CDR) are masked out.
    """
    array = np.asarray(array, dtype=np.float32)
    if array.ndim == 3:
        array = array[0] if array.shape[0] == 1 else array.mean(axis=0)

    if scaling_factor is not None and scaling_factor != 0.0:
        valid = array > -32752
        array = np.where(valid, array * scaling_factor, np.nan)

    finite = array[np.isfinite(array)]
    if finite.size == 0:
        raise LROReadError("image array has no finite pixel values")

    lo, hi = np.percentile(finite, [0.5, 99.5])
    if hi <= lo:
        lo, hi = float(finite.min()), float(finite.max())
    if hi <= lo:
        return np.zeros_like(array, dtype=np.float32)

    return np.clip((array - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)


# ---------------------------------------------------------------------------
# GSD extraction
# ---------------------------------------------------------------------------

_NAC_FOCAL_LENGTH_MM = 699.62   # LROC EDR/CDR SIS Table 2
_NAC_PIXEL_PITCH_UM  = 7.0      # µm per pixel (at summing=1)
_NAC_NOMINAL_ALT_M   = 50_000.0 # nominal LRO 50 km orbit


def _extract_gsd_m(parsed: dict) -> float:
    """
    Derive ground sample distance in m/px.

    Priority:
      1. Explicit map-scale keyword (projected products)
      2. Camera geometry from label (SPACECRAFT_ALTITUDE + optics)
      3. CROSSTRACK_SUMMING × NAC physical constants  ← standard CDR/EDR path
    """
    for key in ("MAP_SCALE", "PIXEL_RESOLUTION", "GSD", "SPATIAL_RESOLUTION"):
        val = _as_float(_get(parsed, key))
        if val is not None and val > 0:
            return val

    alt   = _as_float(_get(parsed, "SPACECRAFT_ALTITUDE"))
    fl_mm = _as_float(_get(parsed, "FOCAL_LENGTH"))
    pp_um = _as_float(_get(parsed, "PIXEL_SIZE", "DETECTOR_PIXEL_WIDTH"))
    if alt and fl_mm and pp_um:
        return (alt * (pp_um / 1e6)) / (fl_mm / 1e3)

    summing = _as_float(_get(parsed, "CROSSTRACK_SUMMING"))
    if summing is not None and summing >= 1:
        base = (_NAC_NOMINAL_ALT_M * (_NAC_PIXEL_PITCH_UM / 1e6)) / (_NAC_FOCAL_LENGTH_MM / 1e3)
        return base * summing   # ~0.50 m/px (sum=1)  ~1.00 m/px (sum=2)

    raise LROReadError(
        "no map scale/resolution field and insufficient geometry to derive GSD"
    )


# ---------------------------------------------------------------------------
# NAIF WebGeocalc geometry query
# ---------------------------------------------------------------------------

_MOON_RADIUS_M = 1_737_400.0
_LRO_KERNEL_SET = 21           # NAIF WebGeocalc kernel set 21 = LRO


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle bearing from (lat1, lon1) to (lat2, lon2) in degrees [0, 360).
    All angles in degrees.  Bearing is measured clockwise from North.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dl)
    return math.degrees(math.atan2(x, y)) % 360.0


def _fetch_geometry(utc_time: str, instrument: str) -> dict:
    """
    Query NAIF WebGeocalc (kernel set 21 = LRO) for geometry at utc_time.

    Returns a dict with keys:
        center_lat, center_lon   — surface intercept of the camera boresight
        incidence_deg            — solar incidence angle at intercept
        subsolar_azimuth_deg     — azimuth of Sun from intercept, CW from North

    Returns an empty dict on any failure (offline, kernels unavailable, etc.).
    Any missing fields stay None in the caller.
    """
    try:
        from webgeocalc import SurfaceInterceptPoint, SubObserverPoint, SubSolarPoint
    except ImportError:
        return {}

    # --- Surface Intercept (camera boresight footprint on the Moon) ---
    try:
        obs = SurfaceInterceptPoint(
            kernels=_LRO_KERNEL_SET,
            times=[utc_time],
            target="MOON",
            target_frame="IAU_MOON",
            observer="LRO",
            direction_vector_type="INSTRUMENT_BORESIGHT",
            direction_instrument=instrument,
            aberration_correction="LT+S",
            state_representation="LATITUDINAL",
        ).run()
    except Exception as e:
        return {"_error_obs": str(e)}

    center_lat    = float(obs["LATITUDE"])
    center_lon    = float(obs["LONGITUDE"])
    incidence_deg = float(obs["INCIDENCE_ANGLE"])

    # --- Sub-solar point (for azimuth computation) ---
    try:
        sol = SubSolarPoint(
            kernels=_LRO_KERNEL_SET,
            times=[utc_time],
            target="MOON",
            target_frame="IAU_MOON",
            observer="LRO",
            aberration_correction="LT+S",
            state_representation="LATITUDINAL",
        ).run()
        solar_lat = float(sol["LATITUDE"])
        solar_lon = float(sol["LONGITUDE"])
        subsolar_azimuth_deg = _bearing_deg(center_lat, center_lon, solar_lat, solar_lon)
    except Exception:
        subsolar_azimuth_deg = None

    return {
        "center_lat":          center_lat,
        "center_lon":          center_lon,
        "incidence_deg":       incidence_deg,
        "subsolar_azimuth_deg": subsolar_azimuth_deg,
    }


# ---------------------------------------------------------------------------
# Corner computation from SPICE centre + swath geometry
# ---------------------------------------------------------------------------

def _compute_corners(
    center_lat: float,
    center_lon: float,
    n_lines: int,
    n_samples: int,
    gsd_m: float,
) -> dict:
    """
    Approximate image corners from the SPICE-derived centre.

    Assumes nadir-pointing and that along-track ≈ meridional (valid for
    LRO's near-polar orbit).  Errors are <0.5° near the poles.
    """
    half_lat_m  = (n_lines   * gsd_m) / 2.0
    half_lon_m  = (n_samples * gsd_m) / 2.0

    cos_lat = math.cos(math.radians(center_lat))
    if abs(cos_lat) < 1e-6:
        cos_lat = 1e-6   # avoid divide-by-zero exactly at poles

    half_lat_deg = math.degrees(half_lat_m / _MOON_RADIUS_M)
    half_lon_deg = math.degrees(half_lon_m / (_MOON_RADIUS_M * cos_lat))

    c_lon = center_lon % 360.0
    return {
        "ul": (center_lat + half_lat_deg, (c_lon - half_lon_deg) % 360.0),
        "ur": (center_lat + half_lat_deg, (c_lon + half_lon_deg) % 360.0),
        "ll": (center_lat - half_lat_deg, (c_lon - half_lon_deg) % 360.0),
        "lr": (center_lat - half_lat_deg, (c_lon + half_lon_deg) % 360.0),
    }


# ---------------------------------------------------------------------------
# Fallback corner extraction from label (CDR/RDR projected products)
# ---------------------------------------------------------------------------

def _extract_corners_from_label(parsed: dict, n_lines: int, n_samples: int,
                                 gsd_m: float) -> tuple[dict, str]:
    """
    Try to build corners from label fields.  Returns (corners_dict, source_str).
    source_str is 'explicit' | 'center_approx' | 'none' | 'spice_approx'.
    SPICE-based corners are built by _compute_corners() after geometry query.
    """
    # Explicit corner keywords
    clat = {
        "ul": ("UL_LATITUDE",  "UPPER_LEFT_LATITUDE"),
        "ur": ("UR_LATITUDE",  "UPPER_RIGHT_LATITUDE"),
        "ll": ("LL_LATITUDE",  "LOWER_LEFT_LATITUDE"),
        "lr": ("LR_LATITUDE",  "LOWER_RIGHT_LATITUDE"),
    }
    clon = {
        "ul": ("UL_LONGITUDE", "UPPER_LEFT_LONGITUDE"),
        "ur": ("UR_LONGITUDE", "UPPER_RIGHT_LONGITUDE"),
        "ll": ("LL_LONGITUDE", "LOWER_LEFT_LONGITUDE"),
        "lr": ("LR_LONGITUDE", "LOWER_RIGHT_LONGITUDE"),
    }
    corners: dict = {}
    for c in ("ul", "ur", "ll", "lr"):
        lat = _as_float(_get(parsed, *clat[c]))
        lon = _as_float(_get(parsed, *clon[c]))
        if lat is None or lon is None:
            break
        corners[c] = (lat, lon % 360.0)
    else:
        return corners, "explicit"

    # Centre-based approximation from label
    clat_val = _as_float(_get(parsed, "CENTER_LATITUDE"))
    clon_val = _as_float(_get(parsed, "CENTER_LONGITUDE"))
    if clat_val is not None and clon_val is not None:
        return _compute_corners(clat_val, clon_val, n_lines, n_samples, gsd_m), "center_approx"

    # Will be replaced by SPICE-derived corners in load_product()
    return {}, "none"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_product(path: str) -> Product:
    """
    Load an LRO NAC EDR or CDR .IMG file and return a Product.

    Geometry (center_lat, center_lon, incidence_deg, subsolar_azimuth_deg)
    is obtained from the NAIF WebGeocalc REST API at each product's
    START_TIME.  If the API is unreachable or the kernels don't yet cover
    the observation epoch, those fields are None.
    """
    if not os.path.exists(path):
        raise LROReadError(f"{path}: file does not exist")

    # --- Load raw array and label string ---
    array = None
    label_str = None
    read_errors: list[str] = []

    try:
        array, label_str = _load_with_pdr(path)
    except Exception as e:
        read_errors.append(f"pdr: {e}")

    if array is None:
        try:
            array, label_str = _load_with_gdal_fallback(path)
        except Exception as e:
            read_errors.append(f"gdal: {e}")

    if array is None or label_str is None:
        raise LROReadError(
            f"{path}: could not be read by pdr or GDAL. "
            f"Errors: {'; '.join(read_errors)}"
        )

    # --- Parse label ---
    parsed = _parse_label(label_str)

    n_lines   = int(array.shape[0])
    n_samples = int(array.shape[1]) if array.ndim >= 2 else 1

    # --- GSD ---
    try:
        gsd_m = _extract_gsd_m(parsed)
    except LROReadError as e:
        raise LROReadError(f"{path}: {e}") from e

    # --- Normalise array (apply CDR SCALING_FACTOR if present) ---
    scaling_factor = _as_float(_get(parsed, "SCALING_FACTOR"))
    try:
        norm_array = _normalize_to_float01(array, scaling_factor=scaling_factor)
    except LROReadError as e:
        raise LROReadError(f"{path}: {e}") from e

    # --- Scalar metadata from label ---
    product_id   = _as_str(_get(parsed, "PRODUCT_ID")) or os.path.splitext(os.path.basename(path))[0]
    
    start_utc = _as_str(_get(parsed, "START_TIME", "IMAGE_TIME"))
    stop_utc = _as_str(_get(parsed, "STOP_TIME"))
    
    # Estimate midpoint time for true image center geometry
    acquired_utc = start_utc
    if start_utc and stop_utc and "T" in start_utc and "T" in stop_utc:
        try:
            from datetime import datetime
            t1 = datetime.fromisoformat(start_utc.replace("Z", ""))
            t2 = datetime.fromisoformat(stop_utc.replace("Z", ""))
            mid = t1 + (t2 - t1) / 2
            acquired_utc = mid.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        except ValueError:
            pass

    # Determine instrument frame (LRO_LROCNACL or LRO_LROCNACR)
    frame_id = _as_str(_get(parsed, "FRAME_ID"))
    if frame_id and frame_id.upper().startswith("R"):
        instrument = "LRO_LROCNACR"
    elif frame_id and frame_id.upper().startswith("L"):
        instrument = "LRO_LROCNACL"
    elif "R" in product_id[-2:].upper():
        instrument = "LRO_LROCNACR"
    else:
        instrument = "LRO_LROCNACL"

    # --- Geometry from NAIF WebGeocalc ---
    geo = _fetch_geometry(acquired_utc, instrument) if acquired_utc else {}

    center_lat           = geo.get("center_lat")
    center_lon           = geo.get("center_lon")
    incidence_deg        = geo.get("incidence_deg")
    subsolar_azimuth_deg = geo.get("subsolar_azimuth_deg")

    # --- Corners ---
    # Prefer label-explicit → SPICE-derived centre → sentinel zeros
    corners, corners_src = _extract_corners_from_label(parsed, n_lines, n_samples, gsd_m)

    if not corners:
        if center_lat is not None and center_lon is not None:
            corners = _compute_corners(center_lat, center_lon, n_lines, n_samples, gsd_m)
            corners_src = "spice_approx"
        else:
            corners = {"ul": (0.0, 0.0), "ur": (0.0, 0.0),
                       "ll": (0.0, 0.0), "lr": (0.0, 0.0)}
            corners_src = "none"

    meta = {
        "raw_shape":          (n_lines, n_samples),
        "read_errors":        read_errors,
        "corners_source":     corners_src,
        "scaling_factor":     scaling_factor,
        "crosstrack_summing": _as_float(_get(parsed, "CROSSTRACK_SUMMING")),
        "data_set_id":        _as_str(_get(parsed, "DATA_SET_ID")),
        "product_type":       _as_str(_get(parsed, "PRODUCT_TYPE")),
        "orbit_number":       _as_float(_get(parsed, "ORBIT_NUMBER")),
        "geometry_source":    "naif_webgeocalc" if geo.get("center_lat") is not None else "none",
        "geo_error":          geo.get("_error_obs"),
    }

    return Product(
        array=norm_array,
        gsd_m=float(gsd_m),
        corners=corners,
        source="NAC",
        product_id=product_id,
        acquired_utc=acquired_utc,
        incidence_deg=float(incidence_deg) if incidence_deg is not None else None,
        subsolar_azimuth_deg=float(subsolar_azimuth_deg) if subsolar_azimuth_deg is not None else None,
        meta=meta,
    )