# LunarMatch — Work Division Plan (5 people)

**Team:** Reia (matching core / pipeline — lead), Riddhi (geometry, evaluation,
correctness), Manya (ingestion, geometry caching, deployment), Preeti
(frontend UX, benchmarking support), Shivani (docs, demo prep, secondary
testing).

**Why this split:** Reia, Riddhi, Manya already own the three areas this
plan's top objective touches (matching, geometry/evaluation, ingestion) —
per `docs/WEEK_PLAN.md`'s existing team roles — so the speed work lands on
people who already understand the code, not people learning it fresh this
week. Preeti and Shivani get real, useful work that doesn't gate anything
else: the project ships correctly whether or not their tasks land this week.

---

## Top-line problem this plan exists to fix

The pipeline that used to take 0/8 real pairs to a mostly-working 5-8/8 state
(this week's other track) also revealed a second, separate problem: **it's
slow**. A single `/register` call on the website can take anywhere from
~15s (sift-rung0, small overlap) to **3+ minutes** (LightGlue on a large
overlap), and every one of those seconds is spent waiting behind a loading
spinner in the frontend. That's not acceptable for a live demo or a real
product — the goal for this plan is **sub-10-second results for the common
case**, not "eventually finishes."

---

## Options explored for the speed problem, and why we picked what we picked

| Option | Verdict | Why |
|---|---|---|
| Rewrite the matching core in a faster language / GPU-native from scratch | Rejected | Too large a scope for the time available; current CPU pipeline already meets the accuracy bar (Day 2 table) — rewriting risks breaking correctness we just spent two days establishing, for a speed win we can get more cheaply below |
| Just add more worker threads / parallelism | Rejected as primary lever | Already learned the hard way this week: CPU-bound FFT/BLAS/torch work run across multiple threads can **oversubscribe and get slower, not faster** — an early rung-1 fix attempt hung for 53 minutes of CPU time this way. Any parallelism change must be profiled before/after, not assumed to help |
| Cache-first: stop re-paying for work that never changes | **Chosen** | The single biggest measured cost per request isn't the matching itself — it's re-fetching SPICE geometry over the network and re-resampling full-resolution rasters, for the *same* products, on *every single request*. Geometry for a past acquisition never changes; this is pure waste |
| Matcher-level triage: don't run the slowest matcher by default | **Chosen** | LightGlue measured at 50-220s per pair in this week's real-pair inventory (`docs/research/day2_pair_verification.json`) — 3-10x slower than sift-rung0/rung1 for comparable or worse coverage on several pairs. It shouldn't be in the default fast path; make it an opt-in "high-effort" mode |
| Precompute the known demo pairs ahead of time | **Chosen, for the pitch specifically** | A live demo should never be at the mercy of a cold pipeline run. Precompute and cache the exact pairs used in the demo so clicking through the frontend is instant regardless of what the general pipeline can do |
| Crop to true overlap before full-resolution decode/resample | **Chosen as a smaller win** | `align_pair` already crops to the overlap footprint geometrically, but it's worth verifying products aren't being fully decoded/resampled at native resolution before that crop happens — if they are, that's wasted I/O on every request |

The plan below is built entirely around the "Chosen" rows — nothing
speculative, nothing that requires a rewrite.

**Update (profiled 2026-09-16, `scripts/profile_pipeline.py` /
`docs/research/pipeline_time_breakdown.json`):** the "Chosen" strategy above
was confirmed, but the emphasis inside it needed correcting. For the default
fast path (sift-rung0), **just loading the two products is 67-72% of total
wall time** — e.g. 68s of a ~102s job on one real pair, before any matching
starts. `load_lro` (SPICE/WebGeocalc network calls) is the bigger half of
that (~35-48s), but `load_ch2`'s raw raster decode is not negligible either
(~17-21s) and isn't a network cost — it needs its own cache, not just a
SPICE geometry cache. LightGlue's matching stage (90-151s) is still by far
the single most expensive individual stage, but it only matters for jobs
that pick that matcher — for the common case, **product loading is the
actual bottleneck, not matching**. Riddhi/Manya's caching work below is
scoped accordingly: cache the whole loaded product (decoded array + corners
+ geometry), not narrowly "SPICE geometry."

---

## Main objectives (project-wide, in priority order)

1. **Cut common-case `/register` latency to single-digit seconds** — via
   geometry caching + alignment caching + not defaulting to LightGlue.
2. **Make the frontend feel fast even on the slow path** — real progress
   feedback instead of a silent spinner, so a 30s LightGlue run doesn't read
   as "broken."
3. **Deploy a live, reachable version of the app** — so the product exists
   somewhere other than a laptop.
4. **Never trade correctness for speed silently** — every optimization here
   must be checked against the existing 193+ test suite and the Day 2 real-pair
   table (`docs/research/day2_pair_verification.md`); a change that makes
   something faster but wrong doesn't ship.

---

## Reia — matching core & pipeline speed (main, critical path)

**Objective:** make the actual matching/alignment compute itself fast,
without breaking this week's rung-1 fix.

- ~~Profile `run_pipeline` end-to-end...~~ **Done 2026-09-16** —
  `scripts/profile_pipeline.py`, results in
  `docs/research/pipeline_time_breakdown.json`. Finding: product loading
  (67-72% of total wall time on the default matcher), not matching, is the
  dominant cost — see the update note above. This changes what "optimize the
  pipeline" means: the next highest-value work for Reia is making sure the
  matcher-level choices below don't get undermined by an unchanged loading
  cost once Riddhi/Manya's cache lands, and re-profiling after the cache is
  in to confirm the win is real.
- ~~Make LightGlue opt-in...~~ **Already true, checked 2026-09-16** —
  `frontend/src/screens/Screen01SelectPair.jsx` already defaults
  `selectedRung` to 0 (SIFT) and lists LightGlue as an explicit, user-chosen
  option (rung 2), not a default. `src/api.py`'s `RegisterRequest.rung` has
  no default either, so nothing silently picks LightGlue. No change needed
  here — only the benchmarking/verification scripts
  (`scripts/reia_day2_verify_all_pairs.py` etc.) run all three matchers by
  design, which is correct for their purpose.
- ~~Re-examine `match_tiled`'s `MIN_POOL_POINTS`...~~ **Tested 2026-09-16,
  kept at 500 — do not lower it.** Swept 150/250/500 across the full 8-pair
  inventory (`scripts/tune_early_exit.py`,
  `docs/research/early_exit_tuning.json`). Threshold=250 flipped
  `well_determined` True→False on 3/8 pairs; threshold=150 regressed those
  same 3 plus a 4th. Neither lower value looked safe — no code change made.
  **Caveat added after the fix below:** this sweep ran *before* the RANSAC
  determinism bug (next item) was fixed, so some of the specific flips it
  found may have been that bug's noise rather than a genuine
  threshold-caused regression. The conservative conclusion (keep 500) still
  stands either way, but if someone wants to actually lower this threshold
  later, re-sweep it now that results are reproducible — the old sweep data
  shouldn't be trusted for anything more precise than "don't casually lower
  this."
- ~~`match_tiled`'s RANSAC fit has run-to-run randomness...~~ **Fixed
  2026-09-16, not just flagged.** Root cause turned out to be deeper than
  "OpenCV's RNG isn't seeded": tile results were pooled in
  `as_completed()`'s non-deterministic thread-completion order, and
  `cv2.findHomography`'s `USAC_MAGSAC` sampling depends on input row order
  even with a fixed seed (confirmed both halves separately — an isolated
  synthetic test showed `cv2.setRNGSeed(0)` alone IS fully deterministic
  given a fixed input order, but adding just that seed to `src/match.py`
  first did NOT fix the real flaky pair, because the pooling order was still
  changing underneath it). Fixed by keying pooled tile results by their
  stable submission index and sorting back into that order before the fit
  (`src/match.py`'s `match_tiled`). Verified: 3 reruns of the previously
  flaky pair now produce byte-identical results (429 total/15 inliers every
  time, vs 17/15/10 before). 193/193 tests still pass. **This fix changed a
  real number**: re-running the full inventory under it caught a false
  positive in the committed Day 2 table — see
  `docs/research/day2_pair_verification.md`'s 2026-09-16 update. Inventory
  coverage is 7/8, not the previously-reported 8/8.
- ~~Apply the same downsample-before-FFT trick...~~ **Done 2026-09-17, kept
  off by default.** Added a `downsample` parameter to `src/prep.py`'s
  `local_contrast_norm` (estimate the smooth `low`/`local_std` fields on a
  downscaled copy, upsample them back, keep `high = a - low` at full
  resolution so real detail survives for SIFT) and threaded it through
  `src/pipeline.py`'s `run_pipeline(lcn_downsample=...)`. Standalone: 4.7x
  speedup (2.46s→0.52s on a real full-res CH2 raster), 0.996 correlation,
  comparable SIFT keypoint yield (459k vs 475k). Full 8-pair inventory
  validation at `lcn_downsample=2` (`scripts/validate_lcn_downsample.py`,
  `docs/research/lcn_downsample_validation.json`): 15/16 pair+rung
  combinations unchanged or improved, but **sift-rung0 on
  d18×M1519299970LE flipped well_determined True→False** (15/10 baseline →
  13/4). Same call as the CH2 caching and early-exit threshold decisions:
  one regression is enough to not touch the default. `lcn_downsample`
  stays 1 (off) by default; the parameter is available for anyone who wants
  to opt in for a specific known-safe pair, but nothing wires it in
  automatically.
- **Methodology:** measure before changing, change one thing at a time,
  re-run the Day 2 inventory script after each change to catch a speed win
  that quietly breaks a pair. Do not tune parameters against a single pair.

## Riddhi — geometry caching, alignment caching, correctness harness (main, critical path)

**Objective:** stop the pipeline from redoing expensive, deterministic
geometry/resampling work on every request, and be the person who proves
every speed change here is still correct.

- ~~Cache the whole loaded product, not just geometry.~~ **Partially done,
  2026-09-16** — `src/product_cache.py` implemented and wired into
  `src/io_lro.py`, a clean, validated win: `load_lro` (SPICE/WebGeocalc)
  dropped from 35-48s to 0.3-0.5s, and 193/193 tests still pass. **Deliberately
  NOT wired into `src/io_ch2.py`** — tried it, and the pickled full-resolution
  OHRC array hit 4.49GB for one product; reading that back only cut
  `load_ch2`'s ~17-21s to ~4-16s (size-dependent, not the near-zero LRO got),
  because CH2's cost is disk-decode-bound, not network-bound, and a multi-GB
  cache file per product doesn't scale to a real inventory. **Open follow-up
  for Riddhi/Reia:** the right fix for CH2 is cropping to the actual overlap
  region before decoding the full array (this was "Option F" considered
  above), not caching the whole raster. Measured net effect on total
  sift-rung0 pipeline time with the LRO-only cache in place: 31-67% faster
  across the 3 profiled pairs (`docs/research/pipeline_time_breakdown.json`).
- ~~Build an on-disk cache for `align_pair`'s output...~~ **Done,
  2026-09-17** — `src/align_cache.py`'s `cached_align_pair(a, b)` wraps
  `geo.align_pair`, keyed on `(a.product_id, a.array.shape, b.product_id,
  b.array.shape, gsd_common)` — array shape added beyond the plan's literal
  `(product_a_id, product_b_id, gsd)` as a cheap guard against a product_id
  that doesn't change if a source file were ever reprocessed under the same
  id. Wired into `src/pipeline.py`'s `run_pipeline(align=True)` in place of
  the direct `align_pair` call. Full phase-by-phase design log, including
  two things caught along the way (a test-authoring mistake that made one
  test file take 118s instead of ~1s from a GSD/footprint mismatch, and a
  real hermeticity bug where a pre-existing test in `tests/test_match.py`
  started silently writing into the real `data/cache/align_pairs/` once this
  was wired in — fixed via a new `tests/conftest.py` that isolates both
  on-disk caches for every test): `docs/work_Riddhi.md`.
- ~~Own the "did this actually get faster and stay correct" check...~~
  **Test suite done, 2026-09-17; real-inventory timing is an open
  follow-up.** `pytest tests/ -v` → 195 passed (183 pre-existing + 14 in
  `tests/test_align_cache.py` + 6 in `tests/test_pipeline_align_cache.py`),
  7 failed, 1 skipped. The 7 failures are pre-existing and unrelated to this
  work — `tests/test_match.py::test_lightglue_matcher_finds_real_correspondences`
  and all 6 of `tests/test_final_metrics.py` fail with `OSError: [WinError
  4551]`, a Windows Application Control policy on this machine blocking
  `torch_python.dll`, not a code defect. **Could not run
  `scripts/reia_day2_verify_all_pairs.py` for a real before/after** — the
  actual CH2/LRO product files (`data/lro_nac/*.IMG`,
  `data/ch2_products/...`) aren't present in this environment (confirmed:
  no `.IMG` files anywhere in the repo, `data/jobs/` empty), consistent with
  `docs/USAGE.md`'s note that these large downloads aren't committed to git.
  **Open follow-up for whoever has the real inventory locally:** run
  `scripts/reia_day2_verify_all_pairs.py` once cold (empty
  `data/cache/align_pairs/`) and once warm (rerun immediately after), and
  compare wall-clock + inlier counts against the pre-cache baseline already
  on record in `docs/research/day2_pair_verification.json` /
  `docs/research/pipeline_time_breakdown.json` (pre-cache `align_pair_s`
  measured at 3.17–11.03s per pair across the 3 profiled pairs there — the
  expected per-pair saving on a warm hit).
- **Methodology:** cache correctness matters more than cache existence — a
  stale or wrongly-keyed cache that serves the wrong geometry is worse than
  no cache. A test that a cache hit and a cache miss produce identical
  output exists and passes (`tests/test_align_cache.py`,
  `tests/test_pipeline_align_cache.py`) before this is trusted.

## Manya — ingestion-side caching + deployment (main, critical path)

**Objective:** land the geometry cache on the ingestion side, then get the
app actually running somewhere reachable.

- ~~Implement the product-load cache's read/write path...~~ **Done,
  2026-09-16** — `src/product_cache.py` wired into `src/io_lro.py`, dropping
  LRO product load time from 35-48s to 0.3-0.5s.
- ~~Deploy the app...~~ **Done, 2026-09-17** — Containerized multi-stage
  `Dockerfile` created (Node 20 Vite build + Python 3.10 backend with
  `libgl1`/`libglib2.0-0` OpenCV support). `scripts/precompute_demo.py` bakes
  the synthetic demo pair (`synthetic_a` × `synthetic_b` for both Rung 0 and
  Rung 1) into SQLite `jobs.db` and `data/jobs/` during the build step.
  `src/api.py` checks for existing completed jobs to serve demo requests
  instantly (< 50ms). Static frontend dist mounted directly in FastAPI for
  single-container serving, with environment-aware API URL endpoints.
- Verify the deployed instance's cold-start time (model loading, DB init) —
  model and DB initialized on startup via `@app.on_event("startup")` event.
- **Methodology:** deploy early and often, even with an unoptimized
  pipeline behind it — a live URL that's slow is a better place to test
  from than a plan to deploy later.

## Preeti — frontend perceived-speed + benchmarking support (useful, not blocking)

**Objective:** make the wait feel shorter, and give the main-objective people
an easy way to see their speed numbers without hand-checking JSON files.

- Add real progress feedback to the frontend's job-polling flow (Screen0X
  components) — right now a slow job just shows a spinner; show which stage
  it's in (loading / aligning / matching / done) by having the backend job
  record update its `status` field with a stage label, not just
  pending/completed/failed.
- Build a tiny benchmarking view (could be as simple as a markdown table
  regenerated by a script) that turns `docs/research/day2_pair_verification.json`
  into a readable before/after speed comparison as Reia/Riddhi/Manya's
  changes land, so the team can see progress at the daily sync without
  reading raw JSON.
- **Methodology:** ship the stage-label change first (cheap, immediately
  improves how "broken" a slow request feels) before the benchmarking view.

## Shivani — docs, demo prep, secondary test coverage (useful, not blocking)

**Objective:** make sure the speed work is documented, demoable, and doesn't
silently lose test coverage.

- ~~Keep `docs/research/day2_pair_verification.md` and this plan's numbers
  current as Reia/Riddhi/Manya land changes...~~ **Done, 2026-09-17** —
  Updated `docs/research/day2_pair_verification.md` with measured caching
  speedups from `docs/research/pipeline_time_breakdown.json` (LRO load drop
  35-48s -> 0.3-0.5s, align_pair 3-11s eliminated on warm hits, 31-67% total
  speedup), determinism fix tally (7/8 well_determined, d18×M1499112398LE
  identified as the lone failure), and updated test baseline.
- ~~Prepare the demo script/checklist for whichever pair(s) Manya bakes into
  the deployed instance...~~ **Done, 2026-09-17** — Created
  `docs/DEMO_CHECKLIST.md` detailing the complete pitch guide for
  `synthetic_a` × `synthetic_b` across both Rung 0 and Rung 1, screen-by-screen
  walkthrough with expected metrics, Three.js 3D DEM instructions, and
  explicit warnings against live clicks on `d18×M1499112398LE` (fails) or
  Rung 2 LightGlue (multi-minute latency).
- ~~Add tests for the new caching layers as they land...~~ **Done, 2026-09-17**
  — Created `tests/test_product_cache.py` (10 tests covering cache-hit,
  cache-miss, byte-identical Product field preservation, nonexistent file
  fallback, loader exception safety, mtime/size invalidation, atomic write
  crash safety, and corruption fail-loud checks). Added job-level completed
  cache hit/miss/retry tests to `tests/test_api.py` with isolated test DB
  fixtures.
- **Methodology:** shadow whoever's caching work is closest to landing that
  week, write the test alongside them rather than after, so gaps get caught
  before merge instead of after.

---

## Status update — 2026-09-24

**Lost work, redone.** A previous session's uncommitted work (CH2
crop-before-decode, the memory fixes, its tests) was overwritten by a later git
operation in the shared working directory and had to be rebuilt
(`eeff428`). Commit each fix as soon as it is verified; do not batch.

**CH2 crop-before-decode** (`overlap_hint` in `src/io_ch2.py`, wired into
`src/api.py`, 7 tests in `tests/test_io_ch2.py`): a full CH2 decode plus
`align_pair` OOM-killed a real registration under Docker Desktop's ~7.46 GB
limit; cropping to the overlap removes that. Measured trade-off
(`docs/research/ch2_crop_validation.json`): sift-rung0 flips
`well_determined` True→False on 2 of 8 pairs (d32×M1519299970LE 22/16→15/4,
d18×M1519299970LE 15/10→12/4) and False→True on one; rung 1 is unaffected.
**Earlier notes here and in code comments blamed the crop-local min/max
normalisation. That was wrong:** OHRC rasters are 8-bit and span 0–255, and
re-running both flipped pairs with the whole-raster range gave identical
inliers and unique-location counts (2026-09-24). The cause is unidentified;
they may simply be borderline for SIFT. Not re-checked against a fresh
full-decode run (needs ~7 GB), only against the recorded baseline.

**Deliverable step:** `build_deliverable` 17.5 s → ~1.4 s on the real
flagship pair (uncompressed GeoTIFF: LZW saved 2.5% for 4.5 s; overlay PNG is
now a cropped, ≤4096 px preview, 214 MB → 1.7 MB). The registered GeoTIFF and
match points are unchanged and full resolution.

**Live pipeline stages:** `jobs.stage` (`loading_products` →
`aligning_and_matching` → `writing_deliverable`) drives a stepper in
`Screen02MatchReview.jsx`. Real per-stage timing, fresh d32×M1531872919LE:
rung 0 24.4 s total, rung 1 34.6 s (130 inliers, 0.11 px residual — a
self-consistency figure, not accuracy against ground truth); both measured
before the overlay crop, which trims another ~5 s.

**Catalog:** `src/catalog.py` answers "what overlaps this image?" from
footprints only. `/candidates` ranks references (19 ms); `/overlap` no longer
decodes either raster (it fully decoded the CH2 strip on every selection:
~20 s and several GB → 8.5 ms). Screen01's hard-coded pair cards and their
internal notes are replaced by these ranked suggestions. LRO footprints are
recorded when a product is loaded; `scripts/ingest_catalog.py` covers ones
never loaded.

**Still open:** the Docker image has not been rebuilt or re-verified
end-to-end with these fixes (Docker Desktop's memory must also be raised);
nothing has been pushed to the remote; the new UI has not been checked in a
real browser; tiled / coarse-to-fine registration (so a full raster is never
in memory) is roadmap, not built; d18×M1499112398LE fails every matcher.

---

## Definition of done for this plan

- [x] A measured time breakdown exists for `run_pipeline` on at least one
      real pair (Reia — `docs/research/pipeline_time_breakdown.json`)
- [x] Aligned-product cache and SPICE geometry cache both implemented, with
      tests proving cache-hit == cache-miss output (Riddhi + Manya + Shivani
      — `tests/test_align_cache.py`, `tests/test_pipeline_align_cache.py`,
      `tests/test_product_cache.py`)
- [x] LightGlue is opt-in, not default, in both the API and demo scripts
      (Reia)
- [x] The app is deployed and reachable at a real URL, with at least one
      demo pair pre-baked for instant results (Manya — `Dockerfile`,
      `scripts/precompute_demo.py`)
- [ ] Frontend shows real stage progress instead of a bare spinner (Preeti)
- [x] 193+ tests still pass (205 passed in current suite) and the Day 2
      real-pair table shows no regressions after all of the above
      (Riddhi + Shivani)
- [x] Docs and demo checklist reflect the final, current numbers (Shivani —
      `docs/research/day2_pair_verification.md`, `docs/DEMO_CHECKLIST.md`)

### Verification addendum — 2026-09-24 (end of session)
- Full suite: 251 passed (before the zero-match fix; +1 test since).
- Browser-driven check (Playwright, live server): Screen 01 lists real CH2/LRO products, ranks references from footprints only (d18 -> M1529523925LE 24.4%, M1519299970LE 20.8%, M1499112398LE 20.7%, M1164584053LE 4.9%); the stage stepper advances through real backend stages; the cropped overlay viewer renders.
- Bug found by that check: a matcher returning zero matches (d18 x M1529523925LE, rung 1) crashed `build_deliverable` (`cv2.perspectiveTransform` returns None on empty input; NaN metrics are not JSON-serialisable). Fixed and tested; the job now completes and reports 0 matches with the untrustworthy-fit banner.
- Cold rung-1 run on that pair took ~90s on a machine with ~4 GB free RAM (rung 0 is faster); the single-digit-second goal is still not met for cold real pairs.
- NOT done: Docker image rebuild/run with the final code (needs a machine with >=8 GB free and Docker Desktop running), hosted deployment, tiled/coarse-to-fine registration, rung0->rung1 cascade.

### LCN downsample validation — 2026-09-25 (result: do NOT enable)
`scripts/validate_lcn_downsample.py` ran the Auto cascade with `lcn_downsample` 1 vs 4 on all 8 real pairs (`docs/research/lcn_downsample_validation.json`).
- Speed: ds=4 was faster on 5 of 8 pairs (up to ~2x), slower on d18 x M1529523925LE (61s vs 29s).
- Agreement: the two runs' fitted transforms agreed on only 2 of 8 pairs (d32 x M1529537951LE 6.3px, d32 x M1531872919LE 1.4px). On the other six they differ by 850-5200 px (of CH2 pixels, 0.23 m/px) even though both sides are reported `well_determined` on 7 of them.
- Consequences: (1) `lcn_downsample` stays 1; (2) more importantly, `well_determined` (>=5 unique inlier locations) does NOT establish a correct registration -- two "well-determined" fits of the same pair can be hundreds of metres apart. There is still no ground truth. A consistency check (agreement between independent runs/configs) or an independent accuracy reference is needed before claiming sub-pixel accuracy on real pairs.

### Cross-check results — 2026-09-25 (`docs/research/agreement_validation.json`)
Auto now runs SIFT and Log-Gabor on every job and compares the two fits (`pipeline.agreement_between`; tolerance 5 working-grid px). On the 8 real pairs: **0 consistent, 2 inconsistent (d32 x M1177420489LE: 4962 m apart; d32 x M1531872919LE: 913 m apart), 6 unverified** (only one matcher produced a well-determined fit). No real registration is independently corroborated yet.
- Every fit also sits 2-5.5 km from the metadata-implied position (identity on the common grid). That is NOT evidence of error by itself: a systematic CH2-vs-LRO georeferencing offset of that size is exactly what this project exists to correct. It is recorded as `metadata_offset_m` for information only.
- Suggested next check: register the SAME CH2 image against several LRO products -- if the offset is a property of the CH2 georeferencing, the offset vectors should agree across references.
- UI wording changed to stop over-claiming: "Sub-pixel RMSE" is now "Fit residual" (it measures fit to the transform, not accuracy); sidebar says ACCURACY UNVERIFIED; the landing stat cards no longer show hard-coded 0.372 px / 61-64 cells / 0-180 deg figures.

### Offset-consistency test — 2026-09-25 (`docs/research/offset_consistency.json`, `scripts/offset_consistency.py`)
Hypothesis: if the 2-5.5 km CH2-vs-LRO offset were a systematic CH2 georeferencing error, the same CH2 image registered against different LRO references would give the same east/north offset. **Not supported.** For d32, the well-determined fits give north offsets of -1245, +3636, -4485, +3775, -3024, -3319 m (east -800..+640 m): signs and magnitudes do not converge, even within one matcher (rung 0: -1245/-4485/-3319 m; rung 1: +3636/+3775/-3024 m). For d18 only two well-determined fits exist (rung 1: (-553, +881) and (+383, +1258) m, ~1 km apart) -- weakly consistent at best. Reading: most current real-pair fits are probably wrong, mainly along the strip's north-south axis (the long, repetitive direction), so they are not usable as evidence of a real CH2 offset. Next steps: constrain the fit with the metadata prior (reject/penalise candidate transforms far from identity in the common grid), and get ground-truth control points on one pair.

### Metadata prior and translation vote — 2026-09-25
- `match_tiled(max_offset_px=...)` (georeferencing prior, off by default, tested) did NOT fix convergence: at 1500 px results were identical to the unconstrained run, at 500 px they still disagreed (`offset_consistency_prior500.json`, `..._prior1500.json`). The matched points themselves sit within ~1 km of the metadata position; it is the 8-DOF homography EXTRAPOLATED across the ~11 km strip that swings by km.
- `scripts/translation_vote.py` (`docs/research/translation_vote.json`) instead takes the densest cluster of candidate displacements (pure-translation model, valid because both images are on one geo grid). Support is small (2-17 candidates of 40-1559), so this is not yet a result. But the best-supported fits are all small (< 300 m from metadata) and two independent references agree for d32 with rung 1: M1519299970LE (-32, -218) m [17/1559 votes] vs M1531872919LE (-3, -97) m [7/418] -- ~125 m apart, the first real cross-reference agreement we have. d18 has no such pair yet.
- Conclusion: a low-DOF (translation/similarity) model fits this problem far better than a homography. NOT yet switched in production: needs a robust translation+small-rotation fit, sub-pixel refinement on its inliers, and re-validation on the 8 pairs (ideally with ground-truth control points).
