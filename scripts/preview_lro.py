"""
scripts/preview_lro.py

Writes a downsampled PNG preview for every product in data/lro_nac/, into
demo/previews/. Filename includes the incidence angle so the lighting
difference is visible at a glance in a file browser.

Run from repo root:
    python scripts/preview_lro.py
"""

import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from src.io_lro import LROReadError, load_product  # noqa: E402

DATA_DIR = "data/lro_nac"
OUT_DIR = "demo/previews"
MAX_DIM = 1024  # downsample so previews open instantly


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    paths = sorted(glob.glob(os.path.join(DATA_DIR, "*.IMG"))) + \
        sorted(glob.glob(os.path.join(DATA_DIR, "*.img")))
    paths = sorted(set(paths))

    if not paths:
        print(f"No .IMG files found in {DATA_DIR}/")
        return

    for path in paths:
        print(f"Previewing {path} ...")
        try:
            p = load_product(path)
        except LROReadError as e:
            print(f"  FAILED: {e}")
            continue

        arr8 = (np.clip(p.array, 0, 1) * 255).astype(np.uint8)
        img = Image.fromarray(arr8)

        h, w = arr8.shape[:2]
        scale = MAX_DIM / max(h, w)
        if scale < 1.0:
            # Handle both older Pillow versions and Pillow 10+
            resample_filter = getattr(Image, "Resampling", Image).LANCZOS
            img = img.resize((int(w * scale), int(h * scale)), resample_filter)

        inc_str = f"{p.incidence_deg:.0f}" if p.incidence_deg is not None else "NA"
        out_name = f"{p.product_id}_inc{inc_str}deg.png"
        out_path = os.path.join(OUT_DIR, out_name)
        img.save(out_path)
        print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()