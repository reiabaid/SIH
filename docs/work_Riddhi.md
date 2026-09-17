# Riddhi's Work — Phase Plan

Tracks the two open items from Riddhi's section of `WORK_DIVISION_PLAN.md`
("geometry caching, alignment caching, correctness harness"), broken into
phases to work through one at a time. The product-load cache item in that
plan is already done (`src/product_cache.py`, wired into `src/io_lro.py`) —
this file covers what's left: the `align_pair` output cache, and owning the
speed-vs-correctness verification role.

Status legend: `[ ]` not started, `[~]` in progress, `[x]` done.

---

## Phase 1 — Scaffold the align-pair cache

`[x]` **Done, 2026-09-17**

Added `src/align_cache.py`, mirroring `src/product_cache.py`'s on-disk
pickle pattern: `cached_align_pair(a, b)` wraps `geo.align_pair(a, b)`.

**What it does:** on a cache miss, calls `align_pair(a, b)` and pickles the
returned `(aligned_a, aligned_b)` tuple to
`data/cache/align_pairs/<key>.pkl` (dir overridable via
`LUNARMATCH_ALIGN_CACHE_DIR`, same convention as `product_cache.py`'s
`LUNARMATCH_PRODUCT_CACHE_DIR`), via a temp-file-then-`os.replace` so a
crash mid-write can't leave a corrupt/partial cache file behind (atomic on
both POSIX and Windows). On a hit, unpickles and returns it directly —
`align_pair` (full-raster `cv2.warpPerspective` per line-geometry segment)
never runs at all.

**Cache key:** sha256 of `(a.product_id, b.array.shape, b.product_id,
b.array.shape, gsd_common)` where `gsd_common = max(a.gsd_m, b.gsd_m)` —
matching what `align_pair` itself computes internally, so the key changes
exactly when the output would.

**Why include shape, not just product_id:** the plan's own wording
(`WORK_DIVISION_PLAN.md`) says key on `(product_a_id, product_b_id, gsd)`.
`product_id` is deterministic (CH2: `logical_identifier` from the label;
LRO: `PRODUCT_ID` from the label, or the filename stem as fallback) but
nothing enforces that it changes if a source file were ever reprocessed
under the same ID — `product_cache.py` sidesteps this same risk for raw
file loads by keying on the file's own mtime/size, but `align_pair`'s
inputs are already-loaded `Product` objects with no file handle to stat.
Folding each product's `array.shape` into the key is a free, cheap proxy
for "this is actually the same data" that turns that scenario into a cache
miss instead of a silently stale resample — cheap insurance, not a
complete guarantee (a same-shape reprocessed file would still collide), but
consistent with the plan's own methodology note that a wrongly-keyed cache
is worse than no cache.

**Why argument order matters and is preserved:** `align_pair(a, b)` is not
symmetric — `align_pair(b, a)` returns the same common GSD but a different
tuple order and different `_aligned` product-id suffixes (see
`tests/test_geo_align.py::test_align_pair_common_gsd_is_independent_of_argument_order`).
The key is built from `a` then `b` in call order, so `cached_align_pair(a,
b)` and `cached_align_pair(b, a)` land in different cache entries, matching
`align_pair`'s own actual behavior instead of incorrectly treating the pair
as unordered.

**Why errors aren't cached:** `align_pair` raises `ValueError` for
non-overlapping products or non-positive GSD. `cached_align_pair` lets that
propagate straight out of the `align_pair(a, b)` call before anything is
written to disk, so a failing pair fails the same way on every call instead
of caching a failure.

**Verified (ad hoc scripts, not yet a committed test file — that's Phase
2):**
1. Cold vs. warm: first call computes and writes, second call reads back,
   arrays/corners byte-identical.
2. Argument order: `cached_align_pair(a,b)` vs `(b,a)` hash to different
   keys, and each matches what uncached `align_pair` actually returns for
   that order — the cache doesn't collapse `align_pair`'s real
   non-symmetry (see `test_align_pair_common_gsd_is_independent_of_argument_order`).
3. Different GSD, same products → different key.
4. Different shape, same `product_id` → different key (the staleness-guard
   case from the design rationale above, actually exercised).
5. Non-overlapping products → `align_pair`'s `ValueError` propagates,
   nothing is written to disk, and a second call raises again rather than
   ever returning a stale/wrong success.
6. Non-positive GSD → same not-cached error behavior.
7. Cache directory missing (including a nested missing path) → created on
   demand.

**Not yet covered** (left for Phase 2's real test file rather than more ad
hoc scripts): concurrent writers racing on the same key (the atomic
`os.replace` should make this safe but hasn't been stress-tested), and a
real CH2/LRO product pair rather than small synthetic arrays.

**Scope of this phase:** the module exists standalone. It is **not** wired
into `src/pipeline.py` yet — `run_pipeline` still calls the uncached
`align_pair` directly. That's Phase 3, gated on Phase 2's correctness test
existing first.

## Phase 2 — Correctness test: cache hit == cache miss

`[x]` **Done, 2026-09-17**

Added `tests/test_align_cache.py`, formalizing Phase 1's ad hoc checks into
8 committed pytest tests, all against synthetic products (no real CH2/LRO
data needed, so this runs fast and everywhere):

1. `test_cold_then_warm_call_return_identical_output`
2. `test_cached_result_matches_uncached_align_pair`
3. `test_argument_order_is_not_collapsed_by_the_cache`
4. `test_cache_key_changes_with_gsd`
5. `test_cache_key_changes_with_shape_even_when_product_id_is_unchanged`
6. `test_non_overlapping_products_are_not_cached_and_keep_raising`
7. `test_non_positive_gsd_is_not_cached`
8. `test_cache_dir_is_created_when_missing_including_nested_path`

An `autouse` fixture (`isolated_cache_dir`) monkeypatches
`align_cache.CACHE_DIR` to a per-test `tmp_path` subdirectory, so tests
never touch the real `data/cache/align_pairs/` dir or leak state into each
other.

**Requested follow-up: pushed further on edge cases.** The first 8 covered
the design's core claims but left real gaps, so 6 more were added:

9. `test_cache_key_changes_with_bs_shape_too` — the shape-guard test above
   only exercised `a` resizing; this is the symmetric case for `b`, since
   align_pair resamples both sides and either one's staleness matters
   equally.
10. `test_distinct_pairs_coexist_in_the_cache_without_collision` — two
    different pairs cached into the same directory don't clobber or shadow
    each other.
11. `test_cached_sliver_overlap_matches_uncached_align_pair` — runs the
    cache wrapper through `test_geo_align.py`'s own near-singular-grid edge
    case (overlap smaller than one output pixel), so the key computation
    (`max(gsd)` etc.) is proven not to choke on the same inputs `align_pair`
    itself already handles.
12. `test_pickled_round_trip_preserves_every_product_field` — checks every
    `Product` field (`meta` incl. `aligned_from`, `acquired_utc`,
    `incidence_deg`, `subsolar_azimuth_deg`, array dtype), not just
    array/corners/gsd/product_id — a real CH2/LRO product carries all of
    these and a silent drop through pickling would be easy to miss with the
    narrower checks alone.
13. `test_a_crashed_write_never_leaves_a_readable_partial_cache_file` — the
    actual safety argument for the temp-file-then-`os.replace` pattern
    (rather than writing `cache_path` directly) is that a crash mid-write
    can never leave a *partial* file at the final path for a later call to
    misread as a legitimate hit. Monkeypatches `pickle.dump` to write a byte
    and then raise, confirming `cache_path` still doesn't exist afterward —
    this had only been asserted in a code comment before, not tested.
14. `test_a_corrupted_existing_cache_file_fails_loudly_instead_of_silently`
    — pre-writes garbage bytes at the expected cache path and confirms
    `cached_align_pair` raises rather than returning corrupted data. Locks
    in "fail loud beats fail wrong" (the plan's own methodology stance on
    staleness) as an actual test, not just a design intention. No recovery/
    fallback logic was added for this case — treating disk corruption as
    something to silently paper over would be exactly the kind of
    speculative error-handling for a scenario that can't happen under normal
    operation (the atomic rename means a fully-written file is never
    truncated); if it ever does happen, surfacing it is the correct behavior.

**Result:** `pytest tests/test_align_cache.py -v` → 14/14 passed.

**Full-suite regression check:** `pytest tests/ -q` → 189 passed (183 + the
6 new tests above), 7 failed, 1 skipped. Confirmed via `git status` that
only `src/align_cache.py`, `tests/test_align_cache.py`, and this doc are
new/changed — no existing source file was touched — so the 7 failures are
pre-existing and unrelated:
`tests/test_match.py::test_lightglue_matcher_finds_real_correspondences`
fails with `OSError: [WinError 4551]` (this machine's Windows Application
Control policy blocking `torch_python.dll`, i.e. a local environment
restriction, not a code defect), and the six `tests/test_final_metrics.py`
failures fail the same way for the same underlying reason (LightGlue
dependency). Not caused by this phase's changes, and out of scope to fix
here — flagging for the team rather than silently absorbing into "still
193/193."

**Still not covered** (genuinely out of reach of a unit test, or requires
real infra to matter): true multi-process concurrent writers racing on the
exact same key at the exact same instant (the atomic `os.replace` argument
is sound in theory — POSIX and Windows both guarantee `os.replace` is
atomic — but this is an OS-level guarantee, not something a single-process
pytest run can actually exercise); and cache behavior against a real
CH2/LRO product pair rather than synthetic arrays, which Phase 4's
real-inventory run will exercise as a side effect.

`tests/test_align_cache.py`, following `tests/test_geo_align.py`'s synthetic-
product style:
- Call the cached wrapper once (cold — computes via `align_pair` and writes
  to disk), once more (warm — reads from disk). Assert byte-identical
  arrays, corners, gsd, and product_id between the two.
- Assert a different key (different gsd or shape) produces a distinct cache
  entry rather than a false hit.

Per the plan's own methodology note: a stale or wrongly-keyed cache is worse
than no cache, so this test must exist and pass before Phase 3 wires the
cache into anything real.

## Phase 3 — Wire the cache into the pipeline

`[x]` **Done, 2026-09-17**

`src/pipeline.py` now imports `cached_align_pair` from `src/align_cache.py`
instead of `align_pair` from `src/geo.py`, and `run_pipeline`'s `align=True`
branch calls `cached_align_pair(product_a, product_b)` in place of the
uncached call. Docstring updated to point at `align_cache.py` for the
caching behavior. `geo.align_pair` itself is untouched — `align_cache.py`
still calls straight through to it on a miss.

**Other callers of `align_pair` found and deliberately left alone:**
`scripts/tune_early_exit.py` and `scripts/check_inliers_d32.py` call
`geo.align_pair` directly rather than through `run_pipeline`. These are
one-off tuning/debug scripts, not the `/register` request path this cache
exists for (per the plan's own framing: "recomputed from scratch on every
single `/register` call") — left uncached rather than expanding scope
beyond what was asked. `scripts/reia_day2_verify_all_pairs.py`, the actual
evaluation harness for Phase 4, calls `run_pipeline(..., align=True)`, not
`align_pair` directly, so it already benefits from this wiring without any
change of its own.

**Requested follow-up: committed integration tests, not just ad hoc
scripts.** Added `tests/test_pipeline_align_cache.py` (6 tests) — Phase 2
already proves `align_cache` is correct in isolation; this phase tests the
*integration point*, i.e. that `run_pipeline` actually uses it correctly:

1. `test_second_align_true_call_is_a_genuine_cache_hit` — `geo.align_pair`
   wrapped in a call counter; runs exactly once across two identical
   `run_pipeline(align=True)` calls.
2. `test_align_false_never_touches_align_pair_or_the_cache` — call count
   stays at 0 and no cache file is ever written when `align=False`.
3. `test_pipeline_output_is_identical_across_cold_and_warm_cache` — with
   the matcher replaced by a fixed deterministic stub (see below for why),
   asserts `pts_a`/`pts_b`/`transform`/`shape_a`/`shape_b`/product ids are
   byte-identical between a cold and a warm run. This is the test that would
   catch a real integration bug — e.g. if `original_pixel_transform`/
   `to_original_pixels` behaved differently against a freshly-computed
   aligned `Product` vs. one that came back through a pickle round-trip.
4. `test_align_true_still_raises_on_non_overlapping_products` — confirms
   the cache wiring doesn't swallow or alter `align_pair`'s `ValueError`,
   and that it keeps raising (not caching a partial/wrong result) on a
   second call.
5. `test_tiling_decision_is_consistent_across_cold_and_warm_cache` —
   `run_pipeline` picks `match_tiled` vs. plain `match` based on the
   *aligned* product's shape (`TILE_THRESHOLD_PX`). Lowers that threshold
   and stubs `match_tiled` to cheaply prove the tiling branch decision (and
   the shape it's keyed on) stays identical whether the aligned product came
   from a fresh compute or a cache hit.
6. `test_two_different_pairs_do_not_cross_contaminate_through_the_pipeline`
   — two distinct pairs run through `run_pipeline(align=True)` produce two
   distinct cache misses, and re-running each afterward hits its own entry
   without touching the other's.

**Why a deterministic matcher stub, not real SIFT, for most of these:**
comparing `run_pipeline`'s final match output directly across cold/warm runs
turned out to be an unreliable signal — the ad hoc check below hit
run-to-run variation in `match()`'s own keypoint/RANSAC behavior on
featureless synthetic random-noise images, independent of alignment
entirely (confirmed by re-running plain `match()` alone on identical
inputs). Rather than chase that down here (it's `src/match.py`, Reia's
file, and hasn't been observed on real, textured CH2/LRO imagery), the
committed tests replace `pipeline.run_match`/`pipeline.match_tiled` with a
fixed-output stub via monkeypatch, so they isolate "did the cache wiring
behave correctly" from "is SIFT deterministic on this input" — a legitimate
but separate question, flagged here for Reia's attention if it ever shows
up on a real pair.

**A test-authoring mistake worth recording:** the first draft of
`_pair()`'s helper picked an arbitrary `gsd_m=5.0` against a whole
1-degree-wide synthetic footprint. A 1° span is ~30km on the Moon, so at
5m/px `align_pair` resampled onto a ~6000×6000 output grid from a 64×64
input — the full 6-test file took 118s. Fixed by deriving `gsd_m` from the
image size and a much smaller degree-span instead (same self-consistent
pattern `tests/test_geo_align.py` already uses), which dropped it to ~1s.
Lesson for later synthetic-product tests in this codebase: always derive
`gsd_m` from `(lat_range / (size-1)) * m_per_deg_lat`, never pick GSD and
a real degree-span independently.

**Full-suite regression check:** `pytest tests/ -q` → 195 passed (189 +
these 6), 7 failed (same pre-existing, unrelated torch/LightGlue DLL
failures as Phase 2), 1 skipped. `git status` confirms only
`src/pipeline.py` changed beyond the Phase 1/2 additions, plus the two new
test files.

## Phase 4 — Measure, report, update the plan doc

`[x]` **Partially done, 2026-09-17 — real-inventory timing is an open
follow-up, not skipped silently.**

**Found and fixed first, before any measurement:** running the full suite
to get a clean baseline surfaced that Phase 3's wiring had a real side
effect — `tests/test_match.py`'s pre-existing
`test_pipeline_align_true_returns_points_in_each_products_own_pixel_space`
calls `run_pipeline(..., align=True)` without isolating the cache dir.
Harmless before Phase 3 (`align_pair` was uncached then); after it, every
full-suite run silently wrote a `.pkl` into the real
`data/cache/align_pairs/`. Not a git problem (`data/` is gitignored) but a
real hermeticity bug — repeated test runs were accumulating stray state in
the working tree instead of a clean run leaving no trace. Fixed with a new
`tests/conftest.py`: an autouse fixture that isolates both
`align_cache.CACHE_DIR` and `product_cache.CACHE_DIR` to a per-test
`tmp_path` for *every* test in the suite, not just the ones that already
had their own isolation — so no future `align=True` test can reintroduce
the same leak. Verified: deleted the stray leftover file, ran the full
suite again, confirmed `data/cache/align_pairs/` stayed empty afterward.

**`pytest tests/ -v`:** 195 passed (183 pre-existing baseline + 14 from
Phase 2 + 6 from Phase 3), 7 failed, 1 skipped. The 7 failures are
pre-existing and unrelated (see Phase 2/3 sections above — a Windows
Application Control policy on this machine blocking torch's DLL, not a
code defect).

**`scripts/reia_day2_verify_all_pairs.py` — could not run.** The real CH2
and LRO product files it needs (`data/lro_nac/*.IMG`,
`data/ch2_products/.../*.xml`) aren't present in this environment.
Confirmed by searching the whole repo for `.IMG` files (none found outside
this doc's own text) and checking `data/jobs/` (empty) — consistent with
`docs/USAGE.md`'s own note that these large downloaded files aren't
committed to git and must be fetched from an external archive separately.

**Decision (asked the user directly rather than guessing or fabricating
numbers):** document this as an explicit open follow-up and close out
everything else that's actually verifiable in this environment, rather than
inventing before/after numbers or silently skipping the check.

**What the follow-up needs, for whoever has the real inventory locally:**
1. Ensure `data/cache/align_pairs/` is empty (cold).
2. Run `scripts/reia_day2_verify_all_pairs.py`, record wall-clock + inlier
   counts per pair+config.
3. Run it again immediately (warm) without clearing the cache, record the
   same.
4. Compare both against the pre-cache baseline already on record:
   `docs/research/day2_pair_verification.json` (per-pair wall-clock/inliers
   across all 8 pairs x 3 configs) and
   `docs/research/pipeline_time_breakdown.json` (per-stage breakdown for 3
   profiled pairs — `align_pair_s` measured there at 3.17s, 4.41s, and
   11.03s pre-cache, which is the expected saving on a warm hit for those
   specific pairs).

`WORK_DIVISION_PLAN.md`'s Riddhi section has been updated to reflect all of
the above — the align-cache build and correctness-test work marked done,
the real-inventory timing explicitly called out as an open follow-up rather
than silently marked complete.

**Requested follow-up: committed regression tests for the hermeticity fix
itself.** The conftest fix above was originally verified only by hand (`ls`
both real cache dirs before/after a full suite run). Added
`tests/test_cache_isolation.py` (3 tests) to make that a permanent,
automated check instead of something that has to be manually re-verified
every time:

1. `test_align_cache_dir_is_isolated_with_conftests_fixture_alone` — proves
   isolation holds from `conftest.py`'s autouse fixture alone, with no
   test-level opt-in (unlike `tests/test_align_cache.py`'s own
   `isolated_cache_dir` fixture) — isolation shouldn't depend on every test
   file remembering to ask for it.
2. `test_product_cache_dir_is_isolated_with_conftests_fixture_alone` — same
   proof for `product_cache.py`, the other cache `conftest.py` touches.
   There's no real LRO data in this environment to exercise it via its
   normal path (`io_lro.load_product`), but `cached_load(path, loader)`
   only needs `path` to exist for its mtime/size key, so a throwaway dummy
   file is enough to test the isolation directly without needing real
   product data.
3. `test_a_realistic_burst_of_cache_activity_leaves_both_real_directories_untouched`
   — snapshots both real cache directories, runs several distinct cache
   writes through both caches, and asserts neither real directory's
   contents changed. This is the actual regression test for the bug that
   was found — formalizes the manual `ls`-before/after check into something
   that fails loudly and automatically if a future test reintroduces the
   same leak.

**Verified these tests aren't vacuously true:** temporarily renamed
`tests/conftest.py` out of the way and reran this file — all 3 failed,
correctly catching real `.pkl` files landing in `data/cache/align_pairs/`
(shown in the assertion diff). Restored `conftest.py`, deleted the
deliberately-leaked files, reran clean — all 3 passed again. This is the
same "prove the safety net actually catches something" step as Phase 2's
crashed-write/corrupted-file tests, applied to the isolation fixture itself
rather than to `align_cache.py`.

**Full-suite regression check:** `pytest tests/ -q` → 198 passed (195 + these
3), 7 failed (same pre-existing, unrelated failures), 1 skipped. Both real
cache directories confirmed empty after the run.

---

## Notes / decisions log

(Append here as phases complete — anything that changed from this initial
plan, and why.)
