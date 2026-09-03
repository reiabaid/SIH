# tests/make_synthetic.py — synthetic pairs with a known ground-truth homography.
#
# The key idea: warp an image by a homography we choose, and we know the correct
# answer exactly. Recovered transform vs applied transform gives ground-truth error.
# If RMSE isn't near zero on synthetic pairs, the bug is ours, not the data's.

import numpy as np
import cv2


def make_homography(
    seed: int,
    rotation_deg: float = 15.0,
    scale_range: "tuple[float, float]" = (0.8, 1.25),
    translation_frac: float = 0.05,
    perspective_strength: float = 0.0005,
    image_shape: "tuple[int, int]" = (512, 512),
) -> np.ndarray:
    """Build a random-but-seeded homography: rotation, scale, translation, mild perspective."""
    rng = np.random.default_rng(seed)
    h, w = image_shape[:2]

    theta = np.deg2rad(rng.uniform(-rotation_deg, rotation_deg))
    scale = rng.uniform(*scale_range)
    tx = rng.uniform(-translation_frac, translation_frac) * w
    ty = rng.uniform(-translation_frac, translation_frac) * h
    p1 = rng.uniform(-perspective_strength, perspective_strength)
    p2 = rng.uniform(-perspective_strength, perspective_strength)

    cx, cy = w / 2.0, h / 2.0
    cos_t, sin_t = np.cos(theta), np.sin(theta)

    # rotate + scale about the image centre, then translate, then a mild perspective tilt
    to_origin = np.array([[1, 0, -cx], [0, 1, -cy], [0, 0, 1]], dtype=np.float64)
    rot_scale = np.array(
        [[scale * cos_t, -scale * sin_t, 0], [scale * sin_t, scale * cos_t, 0], [0, 0, 1]],
        dtype=np.float64,
    )
    from_origin = np.array([[1, 0, cx], [0, 1, cy], [0, 0, 1]], dtype=np.float64)
    translate = np.array([[1, 0, tx], [0, 1, ty], [0, 0, 1]], dtype=np.float64)
    perspective = np.array([[1, 0, 0], [0, 1, 0], [p1, p2, 1]], dtype=np.float64)

    H = perspective @ translate @ from_origin @ rot_scale @ to_origin
    return H / H[2, 2]


def apply_illumination_ramp(arr: np.ndarray, angle_deg: float = 45.0, strength: float = 0.5) -> np.ndarray:
    """Multiply by a linear brightness ramp at a chosen angle, to fake a sun-direction change."""
    h, w = arr.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    theta = np.deg2rad(angle_deg)
    direction = xx * np.cos(theta) + yy * np.sin(theta)
    direction -= direction.min()
    direction /= max(direction.max(), 1e-8)
    ramp = 1.0 - strength + strength * direction
    return np.clip(arr * ramp, 0.0, 1.0).astype(np.float32)


def make_synthetic_pair(
    img: np.ndarray,
    seed: int = 0,
    illumination: bool = False,
    illumination_angle_deg: float = 45.0,
    illumination_strength: float = 0.5,
    **homography_kwargs,
) -> "tuple[np.ndarray, np.ndarray]":
    """Warp img by a seeded homography; optionally add an illumination ramp.

    Returns (warped_image, true_homography) where true_homography maps points in
    `img` to points in the warped image.
    """
    h, w = img.shape[:2]
    H = make_homography(seed, image_shape=(h, w), **homography_kwargs)
    warped = cv2.warpPerspective(img.astype(np.float32), H, (w, h), flags=cv2.INTER_LINEAR)

    if illumination:
        warped = apply_illumination_ramp(warped, illumination_angle_deg, illumination_strength)

    return warped, H
