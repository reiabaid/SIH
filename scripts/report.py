# scripts/report.py — match-overlay PNG + metrics JSON for a MatchResult
# Owner: Riddhi

import argparse
import json
import math
import os

import cv2
import numpy as np

from src.metrics import coverage, inlier_stats, rmse
from src.types import MatchResult

GAP_PX = 10
INLIER_COLOR = (0, 200, 0)    # BGR green
OUTLIER_COLOR = (0, 0, 220)   # BGR red
POINT_RADIUS = 3


def _to_uint8_bgr(image: np.ndarray) -> np.ndarray:
    """float32 0..1 grayscale -> uint8 3-channel BGR, safe against values
    slightly outside [0,1] from floating-point rounding.
    """
    gray = (np.clip(image, 0.0, 1.0) * 255).astype(np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def render_overlay(image_a: np.ndarray, image_b: np.ndarray, match_result: MatchResult) -> np.ndarray:
    """Side-by-side overlay: image_a | image_b, with a line for every match
    connecting its point in A to its point in B -- inliers in one colour,
    outliers in another. Point coordinates are not assumed to lie inside
    the image; OpenCV's drawing calls clip automatically.
    """
    canvas_a = _to_uint8_bgr(image_a)
    canvas_b = _to_uint8_bgr(image_b)

    ha, wa = canvas_a.shape[:2]
    hb, wb = canvas_b.shape[:2]
    height = max(ha, hb)
    width = wa + GAP_PX + wb

    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:ha, :wa] = canvas_a
    canvas[:hb, wa + GAP_PX: wa + GAP_PX + wb] = canvas_b

    offset = np.array([wa + GAP_PX, 0])
    for i in range(len(match_result.pts_a)):
        pt_a = tuple(np.round(match_result.pts_a[i]).astype(int).tolist())
        pt_b = tuple(np.round(match_result.pts_b[i] + offset).astype(int).tolist())
        color = INLIER_COLOR if match_result.inlier_mask[i] else OUTLIER_COLOR
        cv2.line(canvas, pt_a, pt_b, color, 1, lineType=cv2.LINE_AA)
        cv2.circle(canvas, pt_a, POINT_RADIUS, color, -1, lineType=cv2.LINE_AA)
        cv2.circle(canvas, pt_b, POINT_RADIUS, color, -1, lineType=cv2.LINE_AA)

    return canvas


def _json_safe(value):
    """Recursively replace NaN with None. Python's json module writes NaN as
    a bare token by default, which is not valid JSON and most non-Python
    parsers (including plain JS JSON.parse, which member 6's viewer will
    use) reject it outright.
    """
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def compute_metrics(match_result: MatchResult, gt_transform: "np.ndarray | None" = None) -> dict:
    """All of Phase 3 + Phase 4's numbers in one dict -- the final
    deliverable those phases were building toward.
    """
    metrics = {}
    metrics.update(rmse(match_result, gt_transform=gt_transform))
    metrics.update(inlier_stats(match_result))
    metrics.update(coverage(match_result))
    return metrics


def write_report(
    image_a: np.ndarray,
    image_b: np.ndarray,
    match_result: MatchResult,
    output_dir: str,
    gt_transform: "np.ndarray | None" = None,
) -> dict:
    """Writes <output_dir>/overlay.png and <output_dir>/metrics.json.

    Returns the metrics dict as computed (real NaN floats, not yet converted
    for JSON) so in-process callers get proper `float('nan')` to work with;
    the file on disk has NaN converted to `null` instead.
    """
    os.makedirs(output_dir, exist_ok=True)

    overlay = render_overlay(image_a, image_b, match_result)
    cv2.imwrite(os.path.join(output_dir, "overlay.png"), overlay)

    metrics = compute_metrics(match_result, gt_transform=gt_transform)
    with open(os.path.join(output_dir, "metrics.json"), "w") as f:
        json.dump(_json_safe(metrics), f, indent=2)

    return metrics


def _load_match_result_json(path: str) -> MatchResult:
    with open(path) as f:
        data = json.load(f)
    return MatchResult(
        pts_a=np.array(data["pts_a"], dtype=np.float32),
        pts_b=np.array(data["pts_b"], dtype=np.float32),
        scores=np.array(data["scores"], dtype=np.float32),
        inlier_mask=np.array(data["inlier_mask"], dtype=bool),
        transform=np.array(data["transform"], dtype=np.float64),
        matcher=data["matcher"],
        shape_a=tuple(data["shape_a"]),
        shape_b=tuple(data["shape_b"]),
        runtime_s=data["runtime_s"],
    )


def main():
    parser = argparse.ArgumentParser(description="Render a match overlay PNG and metrics JSON.")
    parser.add_argument("image_a", help="path to image A (any format cv2 can read)")
    parser.add_argument("image_b", help="path to image B")
    parser.add_argument("match_result_json", help="a serialised MatchResult (see src/types.py)")
    parser.add_argument("output_dir", help="directory to write overlay.png and metrics.json into")
    args = parser.parse_args()

    image_a = cv2.imread(args.image_a, cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
    image_b = cv2.imread(args.image_b, cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
    match_result = _load_match_result_json(args.match_result_json)

    metrics = write_report(image_a, image_b, match_result, args.output_dir)
    print(json.dumps(_json_safe(metrics), indent=2))


if __name__ == "__main__":
    main()
