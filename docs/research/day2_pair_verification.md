# Day 2 — Reia: verify every real pair the inventory can produce

**Update (2026-09-15):** the original run below (sift-rung1 scoring 0/8) triggered
a full investigation into whether rung 1 was fixable — it was. See
"Rung 1 fix" section at the bottom. This file now reflects the corrected
numbers; the original 0/8 finding is kept in git history, not deleted, per
the project's own norm of writing down surprising results rather than
quietly overwriting them.

**Update (2026-09-16) — numbers below are now reproducible, and that
changed one of them for real.** `match_tiled`'s global RANSAC fit was found
to be non-deterministic run-to-run (same pair, same code, same input —
different inlier counts each time), traced to tile results being pooled in
non-deterministic thread-completion order, which changes the row order fed
to `cv2.findHomography` and therefore which random sample MAGSAC draws even
with a fixed seed. Fixed in `src/match.py`'s `match_tiled` by sorting pooled
results back into a stable tile-submission order before the fit; verified
by 3 identical reruns of a previously-flaky pair (429 total/15 inliers every
time, vs 17/15/10 before the fix). **Rerunning the full inventory under this
fix exposed that one of the table's previous "successes" was luck, not a
real capability:** d18×M1499112398LE's sift-rung0 result was previously
`well_determined=True` (28 inliers/23 unique) — the deterministic result is
`11 inliers/4 unique, well_determined=False`. This is not a regression from
today's work, it's the *removal* of a false positive that was there all
along. See the corrected tallies at the bottom — inventory coverage is
**7/8, not 8/8** as previously reported.

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

## Results table (post rung-1 fix AND post RANSAC-determinism fix, 2026-09-16 — reproducible)

`well_determined` = enough unique inlier locations that the homography fit
isn't trivially satisfiable — this is the bar for "actually registered," not
just "produced a transform."

| pair | matcher | total | inliers | unique locs | trivial_fit | well_determined | time (s) |
|---|---|--:|--:|--:|:--:|:--:|--:|
| d18×M1164584053LE | sift-rung0 | 176 | 12 | 4 | **True** | False | 12.3 |
| d18×M1164584053LE | **sift-rung1** | 82 | **23** | **14** | False | **True** | 18.8 |
| d18×M1164584053LE | lightglue | 0 | 0 | 0 | True | False | 60.0 |
| d32×M1177420489LE | sift-rung0 | 247 | 22 | 16 | False | **True** | 13.1 |
| d32×M1177420489LE | **sift-rung1** | 21 | 12 | 10 | False | **True** | 22.7 |
| d32×M1177420489LE | lightglue | 21 | 6 | 6 | False | **True** | 66.8 |
| d18×M1499112398LE | sift-rung0 | 334 | 11 | 4 | **True** | **False (was True — see note above)** | 48.0 |
| d18×M1499112398LE | **sift-rung1** | 0 | 0 | 0 | True | False | 53.8 |
| d18×M1499112398LE | lightglue | 4 | 4 | 4 | **True** | False | n/a (session-paused wall-clock artifact, not a real measurement) |
| d18×M1519299970LE | sift-rung0 | 429 | 15 | 10 | False | **True** | 40.7 |
| d18×M1519299970LE | **sift-rung1** | 511 | **63** | **41** | False | **True** | 38.1 |
| d18×M1519299970LE | lightglue | 78 | 6 | 5 | False | **True** | 150.5 |
| d32×M1519299970LE (original verified pair) | sift-rung0 | 480 | 22 | 16 | False | **True** | 45.7 |
| d32×M1519299970LE | **sift-rung1** | 500 | 25 | 15 | False | **True** | 41.8 |
| d32×M1519299970LE | lightglue | 113 | 6 | 6 | False | **True** | 223.5 |
| d18×M1529523925LE | sift-rung0 | 263 | 10 | 4 | **True** | False | 70.4 |
| d18×M1529523925LE | **sift-rung1** | 0 | 0 | 0 | True | False | 67.2 |
| d18×M1529523925LE | lightglue | 62 | 5 | 5 | False | **True** | 242.2 |
| d32×M1529537951LE | sift-rung0 | 447 | 22 | 20 | False | **True** | 56.2 |
| d32×M1529537951LE | **sift-rung1** | 0 | 0 | 0 | True | False | 63.0 |
| d32×M1529537951LE | lightglue | 56 | 4 | 4 | **True** | False | 229.8 |
| d32×M1531872919LE | sift-rung0 | 221 | 8 | 7 | False | **True** | 31.5 |
| d32×M1531872919LE | **sift-rung1** | 289 | **72** | **45** | False | **True** | 35.8 |
| d32×M1531872919LE | lightglue | 37 | 5 | 5 | False | **True** | 110.5 |

The `d18×M1499112398LE` lightglue timing shows as an artifact because that
run happened to be executing across a session pause — the wall-clock timer
kept counting while the process was suspended. The result (4/4, trivial) is
real and unaffected; only the reported duration is garbage.

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
pairs it substantially beats sift-rung0 (23 vs 4 unique locations, 63 vs 15,
72 vs 8) — including d18×M1164584053LE, where sift-rung0 itself fails
(trivial_fit) but rung 1 succeeds. All 9 existing unit tests in
`tests/test_match.py` still pass unchanged.

**Still open:** 3 pairs (d18×M1499112398LE, d18×M1529523925LE,
d32×M1529537951LE) still get a hard 0 with rung 1 — not degraded, a clean
failure, the same pattern as before the fix. Worth the same kind of
true-match-vs-random-pair diagnostic on one of these specifically before
assuming it's just "harder terrain" — don't quietly write this off either.

## RANSAC determinism fix (2026-09-16)

Separate from rung 1: `match_tiled`'s final homography fit was found to be
non-deterministic — rerunning the exact same pair/config/code produced
different inlier counts each time (10, 15, 17 across 3 reruns of
d18×M1519299970LE, despite an identical 429-point pooled input). Root cause:
tile results were pooled in `as_completed()`'s thread-completion order,
which is not stable run-to-run; `cv2.findHomography`'s `USAC_MAGSAC`
sampling is seed-deterministic *given a fixed input order*
(confirmed via an isolated synthetic test — same seed, same order, same
result every time), but the row order itself was changing between runs,
so a fixed seed alone (`cv2.setRNGSeed(0)`, added first) didn't fix it.
Fixed by keying pooled tile results by their stable submission index and
sorting back into that order before the fit. Verified: 3 reruns of the same
pair now produce byte-identical results (429/15 every time).

This is a real reliability fix, not just a tuning nicety — see the table
above, where re-running the full inventory under this fix caught a false
positive that had been sitting in this document since 2026-09-15.

## For the Day 2 / Day 4 checkpoint

Well-determined pairs by config, updated (2026-09-16, post-determinism-fix):
- **sift-rung0**: 5/8 (fails on d18×M1164584053LE, **d18×M1499112398LE — new,
  see above**, d18×M1529523925LE)
- **sift-rung1**: 5/8 (fails on d18×M1499112398LE, d18×M1529523925LE, d32×M1529537951LE) — but wins outright on 3 pairs where it succeeds
- **lightglue**: 5/8 (fails on d18×M1164584053LE, d18×M1499112398LE, d32×M1529537951LE)

**Corrected: inventory coverage is 7/8, not 8/8.** d18×M1499112398LE now
fails under all three matchers — sift-rung0's success on this pair was the
non-deterministic false positive fixed above, not a real capability. This
is the one pair in the inventory with no working matcher right now. Worth
leading with at the sync: the previous "every pair works under at least one
config" claim wasn't true, and the fix that caught it (determinism) matters
more for trust in every other number in this table than the 1-pair coverage
loss itself.
