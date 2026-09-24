"""Write a registered raster and human-readable match-point deliverables."""

from __future__ import annotations

import csv
import json
import math
import os

import cv2
import numpy as np
from PIL import Image

from src.metrics import coverage, fit_reliability, inlier_stats, rmse
from src.types import MatchResult, Product


def _pixel_to_geo(product: Product, points: np.ndarray) -> np.ndarray:
    """Map image (x, y) points to lon/lat using the four product corners."""
    order = ("ul", "ur", "lr", "ll")
    src = np.float32([[0, 0], [product.array.shape[1] - 1, 0],
                      [product.array.shape[1] - 1, product.array.shape[0] - 1],
                      [0, product.array.shape[0] - 1]])
    dst = np.float32([[product.corners[k][1], product.corners[k][0]] for k in order])
    transform = cv2.getPerspectiveTransform(src, dst)
    points = np.asarray(points, dtype=np.float32).reshape(-1, 1, 2)
    if len(points) == 0:  # cv2.perspectiveTransform returns None for no points
        return np.empty((0, 2), dtype=np.float32)
    return cv2.perspectiveTransform(points, transform).reshape(-1, 2)


def _write_geotiff(path: str, array: np.ndarray, product: Product) -> None:
    height, width = array.shape
    ul_lat, ul_lon = product.corners["ul"]
    ur_lat, ur_lon = product.corners["ur"]
    ll_lat, ll_lon = product.corners["ll"]
    pixel_lon = (ur_lon - ul_lon) / max(width - 1, 1)
    pixel_lat = (ll_lat - ul_lat) / max(height - 1, 1)

    try:
        from osgeo import gdal, osr
        driver = gdal.GetDriverByName("GTiff")
        dataset = driver.Create(path, width, height, 1, gdal.GDT_Float32,
                                options=["COMPRESS=NONE"])
        if dataset is None:
            raise RuntimeError(f"GDAL could not create {path}")

        dataset.SetGeoTransform((ul_lon, pixel_lon, 0.0, ul_lat, 0.0, pixel_lat))
        spatial_ref = osr.SpatialReference()
        spatial_ref.ImportFromEPSG(4326)
        dataset.SetProjection(spatial_ref.ExportToWkt())
        dataset.GetRasterBand(1).WriteArray(array.astype(np.float32))
        dataset.FlushCache()
        dataset = None
        return
    except ImportError:
        pass

    try:
        import rasterio
        from rasterio.transform import from_origin
        transform = from_origin(ul_lon, ul_lat, pixel_lon, abs(pixel_lat))
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype=np.float32,
            crs="EPSG:4326",
            transform=transform,
            # Uncompressed on purpose: LZW on float32 pixel data barely
            # compresses (measured 2026-09-24 on a real 52224x2532 registered
            # raster: 529 MB raw -> 516 MB with LZW, a 2.5% saving) yet cost
            # ~4.5s of single-threaded encode time -- about a quarter of
            # build_deliverable. Pixel values are identical either way.
            compress="none",
        ) as dst:
            dst.write(array.astype(np.float32), 1)
        return
    except ImportError as exc:
        raise RuntimeError("Neither GDAL nor rasterio is available to write GeoTIFF") from exc


def write_match_points(path: str, match_result: MatchResult, product_a: Product,
                       product_b: Product) -> None:
    geo_a = _pixel_to_geo(product_a, match_result.pts_a)
    geo_b = _pixel_to_geo(product_b, match_result.pts_b)
    fields = ["point_id", "x_a", "y_a", "x_b", "y_b", "lon_a", "lat_a",
              "lon_b", "lat_b", "score", "inlier"]
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(len(match_result.pts_a)):
            writer.writerow({
                "point_id": index,
                "x_a": float(match_result.pts_a[index, 0]),
                "y_a": float(match_result.pts_a[index, 1]),
                "x_b": float(match_result.pts_b[index, 0]),
                "y_b": float(match_result.pts_b[index, 1]),
                "lon_a": float(geo_a[index, 0]),
                "lat_a": float(geo_a[index, 1]),
                "lon_b": float(geo_b[index, 0]),
                "lat_b": float(geo_b[index, 1]),
                "score": float(match_result.scores[index]),
                "inlier": bool(match_result.inlier_mask[index]),
            })


def write_match_geojson(path: str, match_result: MatchResult, product_a: Product,
                        product_b: Product) -> None:
    geo_a = _pixel_to_geo(product_a, match_result.pts_a)
    geo_b = _pixel_to_geo(product_b, match_result.pts_b)
    features = []
    for index in range(len(geo_a)):
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [
                [float(geo_a[index, 0]), float(geo_a[index, 1])],
                [float(geo_b[index, 0]), float(geo_b[index, 1])],
            ]},
            "properties": {"point_id": index, "inlier": bool(match_result.inlier_mask[index]),
                           "score": float(match_result.scores[index])},
        })
    with open(path, "w") as handle:
        json.dump({"type": "FeatureCollection", "features": features}, handle, indent=2)


def _overlap_bbox(registered: np.ndarray, margin_frac: float = 0.05):
    """(row_start, row_end, col_start, col_end), exclusive ends, of the region
    where `registered` actually has content, padded by `margin_frac` of each
    extent. cv2.warpPerspective fills everything outside A's footprint with
    exactly 0.0, so non-zero pixels mark where A landed in B's frame. Returns
    None when nothing landed (degenerate registration) -- callers then keep
    the full frame rather than crop to nothing.
    """
    filled = registered != 0
    rows = np.flatnonzero(filled.any(axis=1))
    if rows.size == 0:
        return None
    cols = np.flatnonzero(filled.any(axis=0))
    h, w = registered.shape
    pad_r = int((rows[-1] - rows[0] + 1) * margin_frac)
    pad_c = int((cols[-1] - cols[0] + 1) * margin_frac)
    return (max(0, rows[0] - pad_r), min(h, rows[-1] + 1 + pad_r),
            max(0, cols[0] - pad_c), min(w, cols[-1] + 1 + pad_c))


def write_overlay(path: str, registered: np.ndarray, target: np.ndarray,
                  max_side: int = 4096) -> None:
    """Write the red(target)/green(registered) alignment preview.

    A preview, not a deliverable: the registered GeoTIFF and the match points
    carry the full-resolution result. Cropped to the region where the
    registered image actually landed, then downscaled so the longest side is
    at most `max_side`. Uncropped, a real LRO NAC frame (52224x2532, ~20:1)
    made a 140-220 MB PNG that took ~5-13s to encode and rendered as a
    ~24px-wide sliver in the UI's viewer, so most of that was unusable.
    """
    box = _overlap_bbox(registered)
    if box is not None:
        r0, r1, c0, c1 = box
        registered, target = registered[r0:r1, c0:c1], target[r0:r1, c0:c1]
    longest = max(registered.shape)
    if longest > max_side:
        scale = max_side / longest
        size = (max(1, int(registered.shape[1] * scale)), max(1, int(registered.shape[0] * scale)))
        registered = cv2.resize(registered, size, interpolation=cv2.INTER_AREA)
        target = cv2.resize(target, size, interpolation=cv2.INTER_AREA)
    red = (np.clip(target, 0, 1) * 255).astype(np.uint8)
    green = (np.clip(registered, 0, 1) * 255).astype(np.uint8)
    blue = np.zeros_like(red)
    # compress_level=1: PIL's default (6) spent ~12.9s encoding a real
    # 52224x2532 overlay (measured 2026-09-24, ~70% of build_deliverable).
    # Lossless either way -- PNG is always lossless; the level only trades
    # encode time against file size.
    Image.fromarray(np.stack([red, green, blue], axis=-1), mode="RGB").save(
        path, compress_level=1)


def build_deliverable(product_a: Product, product_b: Product, match_result: MatchResult,
                      out_dir: str) -> dict:
    """Warp A into B's pixel frame and write all hand-off artifacts."""
    os.makedirs(out_dir, exist_ok=True)
    registered = cv2.warpPerspective(product_a.array.astype(np.float32, copy=False),
                                     match_result.transform,
                                     (product_b.array.shape[1], product_b.array.shape[0]))
    registered_path = os.path.join(out_dir, "registered_a_to_b.tif")
    _write_geotiff(registered_path, registered, product_b)
    write_match_points(os.path.join(out_dir, "match_points.csv"), match_result, product_a, product_b)
    write_match_geojson(os.path.join(out_dir, "match_points.geojson"), match_result, product_a, product_b)
    write_overlay(os.path.join(out_dir, "overlay_rgb.png"), registered, product_b.array)

    metrics = {
        "product_a": product_a.product_id,
        "product_b": product_b.product_id,
        "matcher": match_result.matcher,
        "transform_a_to_b": match_result.transform.tolist(),
        "runtime_s": match_result.runtime_s,
        **rmse(match_result),
        **inlier_stats(match_result),
        **coverage(match_result),
        **fit_reliability(match_result),
    }
    # NaN means "nothing to evaluate" (e.g. zero matches); JSON has no NaN, so
    # it is written as null rather than crashing the job.
    metrics = {k: (None if isinstance(v, float) and math.isnan(v) else v)
               for k, v in metrics.items()}
    with open(os.path.join(out_dir, "metrics.json"), "w") as handle:
        json.dump(metrics, handle, indent=2, allow_nan=False)
    return metrics