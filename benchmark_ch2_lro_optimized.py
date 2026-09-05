#!/usr/bin/env python
"""Benchmark CH2×LRO matching with optimized vectorization & parallelization."""

import time
import sys
sys.path.insert(0, '.')
from src.io_ch2 import load_product as load_ch2
from src.io_lro import load_product as load_lro
from src.match import match_tiled
import numpy as np

# Load the confirmed overlapping pair: CH2 OHRC vs LRO d32
print('Loading CH2 OHRC product...')
start = time.time()
ch2 = load_ch2('data/ch2_products/ch2_ohr_ncp_20200229T0938004033_d_img_d32/miscellaneous/calibrated/20200229/ch2_ohr_ncp_20200229T0938004033_d_img_d32.xml')
print(f'  CH2 loaded in {time.time()-start:.2f}s')

print('Loading LRO M1499112398LE product...')
start = time.time()
lro = load_lro('data/lro_nac/M1499112398LE.IMG')
print(f'  LRO loaded in {time.time()-start:.2f}s')

print(f'CH2 shape: {ch2.array.shape}, LRO shape: {lro.array.shape}')

# Convert to uint8 for matching (array is already 0..1)
ch2_u8 = (ch2.array * 255).astype(np.uint8)
lro_u8 = (lro.array * 255).astype(np.uint8)

# Benchmark the two key matchers (sift with rung=0 vs rung=1)
results = {}
for rung in [0, 1]:
    label = f'SIFT (rung {rung})'
    print(f'\nBenchmarking {label}...')
    try:
        start = time.time()
        result = match_tiled(ch2_u8, lro_u8, matcher='sift', rung=rung)
        elapsed = time.time() - start
        inlier_count = np.sum(result.inlier_mask) if result.inlier_mask is not None else 0
        print(f'  Time: {elapsed:.2f}s')
        print(f'  Raw matches: {len(result.pts_a)}')
        print(f'  Inliers (after RANSAC): {inlier_count}')
        results[label] = {'time': elapsed, 'inliers': inlier_count, 'total': len(result.pts_a), 'runtime_s': result.runtime_s}
    except Exception as e:
        print(f'  Error: {e}')
        import traceback
        traceback.print_exc()

print('\n' + '='*60)
print('SUMMARY')
print('='*60)
for label, data in results.items():
    print(f"{label:20s} : {data['time']:7.2f}s (wall-clock) | {data['inliers']:3d} / {data['total']:4d} matches | internal time: {data['runtime_s']:.2f}s")
