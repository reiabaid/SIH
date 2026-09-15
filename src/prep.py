# src/prep.py — illumination-robust representation, tiling for large rasters

import numpy as np
import cv2
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

    truncate=2.0 limits the Gaussian kernel to 2*sigma+1 pixels (61px at sigma=15)
    instead of the scipy default of 4*sigma+1 (121px). The tails beyond 2σ contribute
    <2% of the kernel weight, so the output is numerically near-identical but the
    convolution is ~4× cheaper on large rasters — the single biggest wall-clock win
    in the entire pipeline.
    """
    a = arr.astype(np.float32)
    low = gaussian_filter(a, sigma=sigma, truncate=2.0)
    high = a - low
    local_var = gaussian_filter(high * high, sigma=sigma, truncate=2.0)
    local_std = np.sqrt(np.maximum(local_var, 0.0)) + eps
    return (high / local_std).astype(np.float32)


def log_gabor_max_index_map(arr: np.ndarray, nscale: int = 4, norient: int = 6,
                             min_wavelength: float = 3.0, mult: float = 1.6,
                             sigma_onf: float = 0.75, downsample: int = 1):
    """RIFT-style Maximum Index Map: for each pixel, which of `norient` log-Gabor
    orientation channels carries the most energy, plus that channel's energy as
    a magnitude-like confidence.

    This replaces raw-gradient orientation (see gradient_orientation_mod_pi) as
    the basis for rung 1's descriptor. A Sobel gradient's direction and
    magnitude are sensitive to *local contrast*, not just polarity -- two
    independently-sensed rasters (different optics, noise, dynamic range, a
    real non-uniform illumination difference) can attenuate or amplify local
    contrast at the same physical edge in ways a sign flip alone doesn't
    capture, which is why rung 1's original mod-pi descriptor was verified
    (2026-09-15 session) to carry ~zero discriminative signal at genuine
    correspondences on real CH2xLRO pairs despite passing a pure-inversion
    synthetic test.

    Log-Gabor filters respond to phase structure in a band of spatial
    frequencies rather than raw intensity derivatives, and here we only need
    *which orientation dominates* at each pixel (an ordinal, ranking-based
    quantity), not the raw response scale -- exactly the same intuition behind
    RIFT/HAPCG's radiation-invariance claims in the literature (see
    docs/research/reia.md), and unlike absolute gradient magnitude, "which
    orientation wins" is far more stable under independent per-sensor
    contrast/gain differences.

    downsample: compute the filter bank on a downscaled copy of `arr` (an FFT
    over every pixel of a full ~1024px tile is the dominant cost of rung 1 --
    measured at ~2.6s/call at 1024x1024 with the defaults below, ~5.6s per
    real tile-pair once doubled for both images plus SIFT/matching overhead),
    then upsample the resulting maps back to `arr`'s original size with
    nearest-neighbour resize (mim is a category label, energy a magnitude --
    neither should be interpolated). FFT cost scales with pixel count, so
    downsample=2 cuts it ~4x; combined with a lower nscale this is what makes
    rung 1 practical at tile scale rather than a multi-minute-per-tile cost.

    Returns (mim, energy): mim is int32 in [0, norient), energy is float32 the
    winning orientation's summed-over-scale filter response magnitude (used to
    weight the descriptor histogram the same way gradient magnitude does for
    rung 1's predecessor).
    """
    if downsample > 1:
        h0, w0 = arr.shape[:2]
        small = cv2.resize(arr.astype(np.float32), (max(1, w0 // downsample), max(1, h0 // downsample)),
                            interpolation=cv2.INTER_AREA)
        mim_small, energy_small = log_gabor_max_index_map(
            small, nscale=nscale, norient=norient, min_wavelength=min_wavelength,
            mult=mult, sigma_onf=sigma_onf, downsample=1,
        )
        mim = cv2.resize(mim_small.astype(np.float32), (w0, h0), interpolation=cv2.INTER_NEAREST).astype(np.int32)
        energy = cv2.resize(energy_small, (w0, h0), interpolation=cv2.INTER_NEAREST)
        return mim, energy

    h, w = arr.shape[:2]
    a = arr.astype(np.float64)

    # Frequency-domain radius/angle grids, DC at (0,0) (i.e. not fftshifted) so
    # they line up directly with np.fft.fft2's output layout.
    fy = np.fft.fftfreq(h).reshape(h, 1)
    fx = np.fft.fftfreq(w).reshape(1, w)
    radius = np.sqrt(fx * fx + fy * fy)
    radius[0, 0] = 1.0  # avoid log(0) at DC; DC is excluded from every filter anyway
    theta = np.arctan2(-fy, fx)  # image-space y grows downward; negate for a standard math angle
    sin_theta, cos_theta = np.sin(theta), np.cos(theta)

    fft_a = np.fft.fft2(a)

    energy_per_orient = np.zeros((norient, h, w), dtype=np.float64)
    theta_sigma = np.pi / norient / 1.2

    for o in range(norient):
        angle_o = o * np.pi / norient
        ds = sin_theta * np.cos(angle_o) - cos_theta * np.sin(angle_o)
        dc = cos_theta * np.cos(angle_o) + sin_theta * np.sin(angle_o)
        dtheta = np.abs(np.arctan2(ds, dc))
        angular_spread = np.exp(-(dtheta ** 2) / (2.0 * theta_sigma ** 2))

        for s in range(nscale):
            wavelength = min_wavelength * (mult ** s)
            f0 = 1.0 / wavelength
            radial = np.exp(-(np.log(radius / f0) ** 2) / (2.0 * np.log(sigma_onf) ** 2))
            radial[0, 0] = 0.0  # zero out DC explicitly

            response = np.fft.ifft2(fft_a * radial * angular_spread)
            energy_per_orient[o] += np.abs(response)

    mim = np.argmax(energy_per_orient, axis=0).astype(np.int32)
    energy = np.take_along_axis(
        energy_per_orient, mim[None, :, :], axis=0
    )[0].astype(np.float32)
    return mim, energy


def gradient_orientation_mod_pi(arr: np.ndarray, ksize: int = 3):
    """Per-pixel gradient orientation, folded to [0, pi), plus its magnitude.

    When the sun moves, a slope that was bright-on-the-left becomes bright-on-the-
    right — the gradient *direction* at that edge reverses by exactly 180 degrees.
    A descriptor built on full 0-360 degree direction (like plain SIFT's) sees a
    completely different feature. Folding the angle modulo pi collapses direction
    into orientation — which way the edge runs, ignoring which side is lit — so
    both lightings map to the same value. This is the "rung 1" representation.
    """
    a = arr.astype(np.float32)
    gx = cv2.Sobel(a, cv2.CV_32F, 1, 0, ksize=ksize)
    gy = cv2.Sobel(a, cv2.CV_32F, 0, 1, ksize=ksize)
    theta = np.arctan2(gy, gx)          # -pi .. pi
    theta_mod = np.mod(theta, np.pi)    # 0 .. pi, illumination-polarity invariant
    magnitude = np.sqrt(gx * gx + gy * gy)
    return theta_mod, magnitude


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
