"""
tests/test_io_lro.py

Run from repo root:
    pytest tests/test_io_lro.py -v
"""

import glob
import os

import pytest

from src.io_lro import load_product, LROReadError

DATA_DIR = "data/lro_nac"


def _all_products():
    paths = sorted(glob.glob(os.path.join(DATA_DIR, "*.IMG"))) + \
            sorted(glob.glob(os.path.join(DATA_DIR, "*.img")))
    return sorted(set(paths))


PRODUCT_PATHS = _all_products()


@pytest.mark.skipif(not PRODUCT_PATHS, reason="no LRO .IMG files found in data/lro_nac/")
@pytest.mark.parametrize("path", PRODUCT_PATHS)
def test_product_loads(path):
    p = load_product(path)

    assert p.array.ndim == 2
    assert p.array.dtype.kind == "f"
    assert p.array.min() >= 0.0