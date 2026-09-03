# src/prep.py — illumination-robust representation, tiling for large rasters

import numpy as np
from scipy.ndimage import gaussian_filter


def to_gray_float(arr: np.ndarray) -> np.ndarray:
    """Convert an array to 2D grayscale float32 in 0..1."""
    a = np.asarray(arr)
    if a.ndim == 3:
        # assume last axis is channels; weighted per ITU-R BT.601
        weights = np.array([0.299, 0.587, 0.114])[: a.shape[-1]]
        weights = weights / weights.sum()
        a = np.tensordot(a, weights, axes=([-1], [0]))
    a = a.astype(np.float32)
    lo, hi = float(a.min()), float(a.max())
    if hi > lo:
        a = (a - lo) / (hi - lo)
    else:
        a = np.zeros_like(a)
    return a.astype(np.float32)


def local_contrast_norm(arr: np.ndarray, sigma: float = 15.0, eps: float = 1e-6) -> np.ndarray:
    """Remove the low-frequency shading gradient (sun angle) while keeping local structure.

    Subtracts a large-sigma Gaussian blur (the illumination gradient), then divides by
    the local standard deviation to normalise contrast. What survives is the
    illumination-invariant, high-frequency structure — crater rims, not shading.
    """
    a = arr.astype(np.float32)
    low = gaussian_filter(a, sigma=sigma)
    high = a - low
    local_var = gaussian_filter(high * high, sigma=sigma)
    local_std = np.sqrt(np.maximum(local_var, 0.0)) + eps
    return (high / local_std).astype(np.float32)


def tile(arr: np.ndarray, size: int, overlap: int) -> "list[tuple[np.ndarray, tuple[int, int]]]":
    """Split a large raster into overlapping tiles.

    Returns a list of (tile_array, (row_offset, col_offset)) pairs. row_offset/col_offset
    are the top-left coordinates of the tile in the original array — pass them to
    untile_points to map tile-local match coordinates back to global coordinates.
    """
    h, w = arr.shape[:2]
    stride = size - overlap
    if stride <= 0:
        raise ValueError("overlap must be smaller than size")

    tiles = []
    row_starts = list(range(0, max(h - size, 0) + 1, stride))
    if not row_starts or row_starts[-1] + size < h:
        row_starts.append(max(h - size, 0))
    col_starts = list(range(0, max(w - size, 0) + 1, stride))
    if not col_starts or col_starts[-1] + size < w:
        col_starts.append(max(w - size, 0))

    for r in sorted(set(row_starts)):
        for c in sorted(set(col_starts)):
            r_end = min(r + size, h)
            c_end = min(c + size, w)
            tiles.append((arr[r:r_end, c:c_end], (r, c)))
    return tiles


def untile_points(pts: np.ndarray, offset: "tuple[int, int]") -> np.ndarray:
    """Map tile-local (x, y) points back to global coordinates.

    offset is (row_offset, col_offset) as returned by tile(); points are (x, y) i.e.
    (col, row), matching OpenCV/image convention.
    """
    row_off, col_off = offset
    pts = np.asarray(pts, dtype=np.float32).copy()
    pts[:, 0] += col_off
    pts[:, 1] += row_off
    return pts
