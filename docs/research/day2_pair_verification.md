# Day 2 — Reia: verify every real pair the inventory can produce

**Update (2026-09-15):** the original run below (sift-rung1 scoring 0/8) triggered
a full investigation into whether rung 1 was fixable — it was. See
"Rung 1 fix" section at the bottom. This file now reflects the corrected
numbers; the original 0/8 finding is kept in git history, not deleted, per
the project's own norm of writing down surprising results rather than
quietly overwriting them.

Ran `run_pipeline` (sift-rung0, sift-rung1, lightglue; `align=True`, tiled, real
scale) against every CH2×LRO pair with nonzero footprint overlap, per
`scripts/check_ch2_lro_overlap.py`. Raw data: `docs/research/day2_pair_verification.json`.
Script: `scripts/reia_day2_verify_all_pairs.py`.

8 overlapping pairs found (out of 2 CH2 × 10 LRO = 20 possible):

| pair | ch2_covered_by_lro | lro_covered_by_ch2 |
|---|---|---|
| d18 × M1164584053LE | 0.0486 | 0.0250 |
| d32 × M1177420489LE | 0.0452 | 0.1444 |
| d18 × M1499112398LE | 0.2069 | 0.0817 |
| d18 × M1519299970LE | 0.2081 | 0.1424 |
| d32 × M1519299970LE | 0.2009 | 0.1345 |
| d18 × M1529523925LE | 0.2444 | 0.1124 |
| d32 × M1529537951LE | 0.2315 | 0.1000 |
| d32 × M1531872919LE | 0.1704 | 0.0658 |

## Results table (post rung-1 fix)

`well_determined` = enough unique inlier locations that the homography fit
isn't trivially satisfiable — this is the bar for "actually registered," not
just "produced a transform."

| pair | matcher | total | inliers | unique locs | trivial_fit | well_determined | time (s) |
|---|---|--:|--:|--:|:--:|:--:|--:|
| d18×M1164584053LE | sift-rung0 | 176 | 13 | 4 | **True** | False | 7.6 |
| d18×M1164584053LE | **sift-rung1** | 82 | **23** | **14** | False | **True** | 14.1 |
| d18×M1164584053LE | lightglue | 0 | 0 | 0 | True | False | 52.8 |
| d32×M1177420489LE | sift-rung0 | 247 | 21 | 16 | False | **True** | 10.2 |
| d32×M1177420489LE | **sift-rung1** | 21 | 12 | 10 | False | **True** | 18.1 |
| d32×M1177420489LE | lightglue | 21 | 6 | 6 | False | **True** | 67.2 |
| d18×M1499112398LE | sift-rung0 | 334 | 28 | 23 | False | **True** | 44.9 |
| d18×M1499112398LE | **sift-rung1** | 0 | 0 | 0 | True | False | 39.5 |
| d18×M1499112398LE | lightglue | 4 | 4 | 4 | **True** | False | 151.9 |
| d18×M1519299970LE | sift-rung0 | 429 | 14 | 11 | False | **True** | 23.9 |
| d18×M1519299970LE | **sift-rung1** | 511 | **66** | **42** | False | **True** | 24.8 |
| d18×M1519299970LE | lightglue | 78 | 6 | 5 | False | **True** | 140.6 |
| d32×M1519299970LE (original verified pair) | sift-rung0 | 480 | 21 | 16 | False | **True** | 43.1 |
| d32×M1519299970LE | **sift-rung1** | 500 | 29 | 17 | False | **True** | 23.3 |
| d32×M1519299970LE | lightglue | 113 | 6 | 6 | False | **True** | 140.6 |
| d18×M1529523925LE | sift-rung0 | 263 | 10 | 4 | **True** | False | 47.6 |
| d18×M1529523925LE | **sift-rung1** | 0 | 0 | 0 | True | False | 52.4 |
| d18×M1529523925LE | lightglue | 62 | 5 | 5 | False | **True** | 218.3 |
| d32×M1529537951LE | sift-rung0 | 447 | 21 | 21 | False | **True** | 53.4 |
| d32×M1529537951LE | **sift-rung1** | 0 | 0 | 0 | True | False | 51.8 |
| d32×M1529537951LE | lightglue | 56 | 4 | 4 | **True** | False | 199.5 |
| d32×M1531872919LE | sift-rung0 | 221 | 11 | 10 | False | **True** | 20.9 |
| d32×M1531872919LE | **sift-rung1** | 289 | **72** | **45** | False | **True** | 27.1 |
| d32×M1531872919LE | lightglue | 37 | 5 | 5 | False | **True** | 92.1 |

## Rung 1 fix (2026-09-15)

The original run of this table found **sift-rung1 scored a hard 0 total
matches on all 8/8 real pairs** — not a gradual degradation, a total
failure. That got written down and flagged rather than quietly patched, per
this week's own ground rule (the same way the corner-orientation bug was
found). A full investigation followed (see conversation history / commit for
the diagnostic scripts), which found:

1. **Not a literature-level dead end.** A synthetic ablation with independent
   per-image noise and a blur mismatch degraded gracefully (40 → 15 → 8
   inliers), not to zero — ruling out "any real-world nuisance kills this
   descriptor."
2. **Not a rotation/scale problem.** `align_pair` already resamples both
   products onto a common north-up grid at a common GSD before matching, so
   there's no large residual rotation/scale left for the descriptor to survive.
3. **Root cause, confirmed via a true-match-vs-random-pair descriptor-distance
   test on real RANSAC-confirmed inliers:** rung 1's descriptor
   (`_describe_modpi`, via `src/prep.py`'s `gradient_orientation_mod_pi`) was
   built from **raw Sobel gradient direction folded mod π**. That representation
   only survives a *global, pixel-for-pixel* illumination sign flip — exactly
   what the existing unit test (`test_rung1_beats_rung0_under_illumination_flip`)
   constructs via `1.0 - warped`, same texture, same noise, only inverted. On
   real cross-sensor pairs (independent optics/noise/dynamic range, a genuinely
   non-uniform illumination difference, not a clean inversion), the descriptor
   carried **zero discriminative signal at true correspondences**: mean
   distance at RANSAC-confirmed true matches (1.18) was not even below the
   mean distance between random point pairs (1.13, std 0.086). A raw gradient's
   direction and magnitude are sensitive to local contrast, and two
   independent sensors don't preserve local contrast at the same edge the way
   a global inversion does.
4. **The fix:** replaced raw gradient orientation with a RIFT-style
   **Maximum Index Map** — for each pixel, which of N log-Gabor
   orientation-channel filters carries the most energy (`log_gabor_max_index_map`
   in `src/prep.py`). This is a ranking/ordinal quantity ("which orientation
   wins"), not a raw derivative, and is far less sensitive to independent
   per-sensor contrast/gain differences — the same intuition behind the
   published RIFT/HAPCG methods surveyed in `docs/research/reia.md`, which use
   phase congruency rather than gradient direction for exactly this reason.
5. **Performance:** the FFT-based filter bank was initially ~5.6s/tile
   (nscale=4, full resolution) — impractically slow at ~52 tiles/image.
   Added a `downsample` parameter (compute the filter bank on a 2× downscaled
   copy, upsample the integer/energy maps back with nearest-neighbour) and
   dropped `nscale` 4→3, for a combined ~4x speedup to ~1.4s/tile, competitive
   with sift-rung0.

**Result: rung 1 went from 0/8 to 5/8 well_determined**, and on 3 of those 5
pairs it substantially beats sift-rung0 (23 vs 4 unique locations, 66 vs 11,
72 vs 10) — including d18×M1164584053LE, where sift-rung0 itself fails
(trivial_fit) but rung 1 succeeds. All 9 existing unit tests in
`tests/test_match.py` still pass unchanged.

**Still open:** 3 pairs (d18×M1499112398LE, d18×M1529523925LE,
d32×M1529537951LE) still get a hard 0 with rung 1 — not degraded, a clean
failure, the same pattern as before the fix. Worth the same kind of
true-match-vs-random-pair diagnostic on one of these specifically before
assuming it's just "harder terrain" — don't quietly write this off either.

## For the Day 2 / Day 4 checkpoint

Well-determined pairs by config, updated:
- **sift-rung0**: 6/8 (fails on d18×M1164584053LE, d18×M1529523925LE)
- **sift-rung1**: 5/8 (fails on d18×M1499112398LE, d18×M1529523925LE, d32×M1529537951LE) — but wins outright on 3 pairs where it succeeds
- **lightglue**: 5/8 (fails on d18×M1164584053LE, d18×M1499112398LE, d32×M1529537951LE)

No single matcher covers the full inventory; sift-rung0 ∪ sift-rung1 ∪
lightglue together cover **8/8** — every pair is well_determined under at
least one config, none are fully dead. This is worth surfacing at the sync:
the pitch isn't "one matcher wins," it's "the pipeline needs all three
configs to reach full inventory coverage."
