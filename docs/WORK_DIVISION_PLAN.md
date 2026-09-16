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
- Build an on-disk cache for `align_pair`'s output (the resampled,
  common-grid product pair) keyed by `(product_a_id, product_b_id, gsd)` —
  this is deterministic, expensive (full-raster resampling), and currently
  recomputed from scratch on every single `/register` call for the same pair.
  Smaller win than the product-load cache above (~9-17s vs ~35-68s measured)
  but still real, especially for repeated demo pairs.
- Own the "did this actually get faster and stay correct" check: after each
  of Reia's/Manya's changes, re-run `pytest tests/ -v` (193+ baseline) and
  `scripts/reia_day2_verify_all_pairs.py`, and report the before/after
  wall-clock times and inlier counts side by side. This is the same
  evaluation-lead role Riddhi already has this week, applied to speed
  instead of accuracy.
- **Methodology:** cache correctness matters more than cache existence — a
  stale or wrongly-keyed cache that serves the wrong geometry is worse than
  no cache. Write a test that a cache hit and a cache miss produce identical
  output before this is trusted.

## Manya — ingestion-side caching + deployment (main, critical path)

**Objective:** land the geometry cache on the ingestion side, then get the
app actually running somewhere reachable.

- Implement the product-load cache's read/write path inside `src/io_lro.py`'s
  `load_product` (paired with Riddhi's cache design above) — check cache
  before calling WebGeocalc *and* before re-decoding the raster, write
  through after a real load. Measured cost this is removing: ~35-48s per
  LRO product load, ~67-72% of a default job's total wall time when combined
  with the CH2-side cache.
- **Deploy the app** (assigned per this plan's requirement that deployment
  goes to Riddhi or Manya): pick a target (a simple containerized deploy —
  e.g. Docker image running the FastAPI backend + built frontend, on
  whatever free/low-cost host the team has access to) and get `/register`
  through `/jobs/{id}` reachable over a real URL, not just `localhost`.
  Precompute and bake in the known demo pair(s) so the deployed instance can
  serve those instantly even before the general caching work lands.
- Verify the deployed instance's cold-start time (model loading, DB init) —
  a slow *first* request after a deploy/restart is a different problem from
  a slow *steady-state* request, and both need to be acceptable for a live
  demo.
- **Methodology:** deploy early and often, even with an unoptimized
  pipeline behind it — a live URL that's slow is a better place to test
  from than a plan to deploy later. Treat the caching work above as
  something that gets deployed incrementally, not saved for one big deploy.

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

- Keep `docs/research/day2_pair_verification.md` and this plan's numbers
  current as Reia/Riddhi/Manya land changes — a stale performance doc is
  worse than none once people start citing old numbers in the pitch.
- Prepare the demo script/checklist for whichever pair(s) Manya bakes into
  the deployed instance — know in advance which pair to click through live
  so the pitch doesn't hit a cold, slow path by accident.
- Add tests for the new caching layers as they land (cache-hit-returns-same-
  result tests, cache-miss-falls-back-correctly tests) — extra coverage on
  new code, not owning the caching implementation itself.
- **Methodology:** shadow whoever's caching work is closest to landing that
  week, write the test alongside them rather than after, so gaps get caught
  before merge instead of after.

---

## Definition of done for this plan

- [ ] A measured time breakdown exists for `run_pipeline` on at least one
      real pair (Reia)
- [ ] Aligned-product cache and SPICE geometry cache both implemented, with
      tests proving cache-hit == cache-miss output (Riddhi + Manya)
- [ ] LightGlue is opt-in, not default, in both the API and demo scripts
      (Reia)
- [ ] The app is deployed and reachable at a real URL, with at least one
      demo pair pre-baked for instant results (Manya)
- [ ] Frontend shows real stage progress instead of a bare spinner (Preeti)
- [ ] 193+ tests still pass and the Day 2 real-pair table shows no
      regressions after all of the above (Riddhi, checked continuously)
- [ ] Docs and demo checklist reflect the final, current numbers (Shivani)
