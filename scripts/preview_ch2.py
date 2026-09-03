"""
scripts/preview_ch2.py — write a downsampled PNG preview for one or more
Chandrayaan-2 OHRC products, so the team can eyeball what's on disk
without opening raw .img files.

Usage:
    python -m scripts.preview_ch2 path/to/label1.xml path/to/label2.xml ...

Or point it at a folder and it'll find every .xml under it:
    python -m scripts.preview_ch2 --dir ch2_ohr_ncp_20200229T0938004033_d_img_d32

Output PNGs land in demo/previews/<product_id>.png (folder created if
missing). product_id characters that aren't filesystem-safe are replaced
with underscores.
"""

from __future__ import annotations

import argparse
import glob
import os
import re

import numpy as np
from PIL import Image

from src.io_ch2 import load_product


MAX_PREVIEW_DIM = 2000  # cap the longer side of the preview at this many pixels


def _safe_filename(product_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", product_id)


def _downsample(array: np.ndarray, max_dim: int = MAX_PREVIEW_DIM) -> np.ndarray:
    """
    Simple strided downsample — fast and memory-safe for a large OHRC
    array (tens of thousands of rows). We're making a preview, not a
    science product, so nearest-neighbour striding is fine here.
    """
    h, w = array.shape
    factor = max(1, int(np.ceil(max(h, w) / max_dim)))
    return array[::factor, ::factor]


def make_preview(xml_path: str, out_dir: str = "demo/previews") -> str:
    product = load_product(xml_path)
    small = _downsample(product.array)

    # array is already normalised to 0..1 float32 in load_product;
    # scale to 0..255 uint8 for a viewable PNG
    img_uint8 = (np.clip(small, 0.0, 1.0) * 255).astype(np.uint8)

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{_safe_filename(product.product_id)}.png")
    Image.fromarray(img_uint8, mode="L").save(out_path)
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml_paths", nargs="*", help="One or more .xml label paths")
    parser.add_argument(
        "--dir", help="Folder to search recursively for .xml labels"
    )
    parser.add_argument(
        "--out", default="demo/previews", help="Output folder for PNGs"
    )
    args = parser.parse_args()

    xml_paths = list(args.xml_paths)
    if args.dir:
        xml_paths.extend(
            glob.glob(os.path.join(args.dir, "**", "*.xml"), recursive=True)
        )

    if not xml_paths:
        parser.error("Provide one or more .xml paths, or --dir to search a folder.")

    for xml_path in xml_paths:
        try:
            out_path = make_preview(xml_path, out_dir=args.out)
            print(f"OK   {xml_path} -> {out_path}")
        except Exception as e:
            print(f"FAIL {xml_path}: {e}")


if __name__ == "__main__":
    main()