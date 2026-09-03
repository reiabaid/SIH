# src/types.py — frozen contract, do not change without telling the team

from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class Product:
    """One lunar image with everything needed to place it on the Moon."""
    array: np.ndarray          # 2D grayscale, float32, 0..1
    gsd_m: float                # metres per pixel
    corners: dict                # {ul,ur,ll,lr: (lat_deg, lon_deg)}
    source: str                  # "OHRC" | "TMC2" | "IIRS" | "NAC" | "WAC" | "SYNTH"
    product_id: str
    acquired_utc: Optional[str] = None
    incidence_deg: Optional[float] = None      # None for CH-2, present for NAC
    subsolar_azimuth_deg: Optional[float] = None
    meta: dict = field(default_factory=dict)   # anything else from the label


@dataclass
class MatchResult:
    """Correspondences between two Products, in pixel coordinates."""
    pts_a: np.ndarray          # (N,2) float32, sub-pixel, in image A
    pts_b: np.ndarray          # (N,2) float32, sub-pixel, in image B
    scores: np.ndarray         # (N,) float32 confidence
    inlier_mask: np.ndarray    # (N,) bool, survived RANSAC
    transform: np.ndarray      # (3,3) float64 homography A -> B
    matcher: str                # "sift" | "lightglue" | "loftr"
    shape_a: tuple               # (H, W)
    shape_b: tuple
    runtime_s: float


# Function signatures every module implements against these dataclasses:
#   load_product(path: str) -> Product                              # io_ch2.py, io_lro.py
#   align_pair(a: Product, b: Product) -> tuple[Product, Product]    # geo.py
#   match(a: np.ndarray, b: np.ndarray, matcher: str) -> MatchResult # match.py
#   evaluate(m: MatchResult, gt_transform=None) -> dict              # metrics.py
