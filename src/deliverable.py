"""Write a registered raster and human-readable match-point deliverables."""

from __future__ import annotations

import csv
import json
import os

import cv2
import numpy as np
from PIL import Image

from src.metrics import coverage, inlier_stats, rmse
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
                                options=["COMPRESS=LZW"])
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
            compress="lzw",
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


def write_overlay(path: str, registered: np.ndarray, target: np.ndarray) -> None:
    red = (np.clip(target, 0, 1) * 255).astype(np.uint8)
    green = (np.clip(registered, 0, 1) * 255).astype(np.uint8)
    blue = np.zeros_like(red)
    Image.fromarray(np.stack([red, green, blue], axis=-1), mode="RGB").save(path)


def build_deliverable(product_a: Product, product_b: Product, match_result: MatchResult,
                      out_dir: str) -> dict:
    """Warp A into B's pixel frame and write all hand-off artifacts."""
    os.makedirs(out_dir, exist_ok=True)
    registered = cv2.warpPerspective(product_a.array.astype(np.float32),
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
    }
    with open(os.path.join(out_dir, "metrics.json"), "w") as handle:
        json.dump(metrics, handle, indent=2, allow_nan=False)
    return metrics