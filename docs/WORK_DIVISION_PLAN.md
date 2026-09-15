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

- Profile `run_pipeline` end-to-end on 2-3 real pairs from the Day 2 table
  and produce a time breakdown (load / SPICE / align+LCN / tiled matching /
  RANSAC / deliverable write) — right now we have *totals* per matcher but
  not a breakdown of where the time inside each run actually goes. This is
  the prerequisite for optimizing the right thing instead of guessing.
- Make LightGlue opt-in, not part of the default matcher set run by
  `scripts/run_ch2_lro_pipeline.py`-style flows and the API's default rung —
  it's 3-10x slower for comparable coverage (Day 2 data). Expose it as a
  "thorough mode" instead of a default.
- Re-examine `match_tiled`'s `MIN_POOL_POINTS` early-exit (currently 500) —
  test whether a lower threshold (e.g. 150-200) still gives RANSAC enough
  correct correspondences without processing every tile. Validate against
  the Day 2 table, not just "it finished faster."
- Apply the same downsample-before-FFT trick that fixed rung 1's speed
  (`src/prep.py`'s `log_gabor_max_index_map(downsample=2)`) anywhere else in
  the pipeline doing full-resolution per-pixel work that doesn't need
  full resolution to be correct.
- **Methodology:** measure before changing, change one thing at a time,
  re-run the Day 2 inventory script after each change to catch a speed win
  that quietly breaks a pair. Do not tune parameters against a single pair.

## Riddhi — geometry caching, alignment caching, correctness harness (main, critical path)

**Objective:** stop the pipeline from redoing expensive, deterministic
geometry/resampling work on every request, and be the person who proves
every speed change here is still correct.

- Build an on-disk cache for `align_pair`'s output (the resampled,
  common-grid product pair) keyed by `(product_a_id, product_b_id, gsd)` —
  this is deterministic, expensive (full-raster resampling), and currently
  recomputed from scratch on every single `/register` call for the same pair.
- Build the SPICE/WebGeocalc geometry cache that was scoped but not
  implemented in `docs/WEEK_PLAN.md`'s Day 3.5 spike (keyed by `product_id` +
  `acquired_utc`, on-disk, invalidated never) — coordinate with Manya since
  this touches `src/io_lro.py` where the WebGeocalc calls actually happen.
  This alone removes ~10-20s of pure network wait *per product*, so ~20-40s
  off every cold request.
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

- Implement the SPICE geometry cache's read/write path inside
  `src/io_lro.py`'s `load_product` (paired with Riddhi's cache design above)
  — check cache before calling WebGeocalc, write through after a real call.
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
