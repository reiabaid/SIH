# LunarMatch — Project Status

_SIH26166 · Last updated 2026-09-05. Written from the actual codebase and test
suite state, not from planning docs — see the caveat at the bottom about
`ARCHITECTURE_AND_SOLUTION.md`'s benchmark numbers, which do not match what
this session measured._

## 1. What the project does

Standard feature matchers (SIFT, ORB) fail on lunar imagery when two photos of
the same terrain are taken under different sun angles: the Moon has no
atmosphere, so contrast comes almost entirely from shadows, and moving the sun
reverses which side of a crater rim is bright. The project:

1. Closes the **scale gap** between sensors (Chandrayaan-2 OHRC at ~0.23 m/px,
   LRO NAC at ~1.0 m/px) using georeferencing metadata (`geo.align_pair`),
   not the matcher.
2. Benchmarks whether **illumination-robust matching** (a custom mod-π
   descriptor, and a learned matcher, LightGlue) actually holds up where
   plain SIFT collapses.
3. Meets the two explicit, easy-to-skip statement requirements: **sub-pixel
   accuracy** (quadratic peak fit) and **uniform match distribution**
   (grid-bucketed keypoint selection + a coverage metric that measures it).
4. Exports results in a format ISRO's existing photogrammetry pipeline can
   consume (an ISIS control network, PVL format), not a bespoke one.

Stated framing (kept from the original team handbook, still accurate):
**the contribution is the benchmark and pipeline integration, not a new
matching algorithm.** Orientation-invariant descriptors (RIFT, HAPCG family)
are known; LightGlue is a published third-party model.

## 2. System architecture

```
Product (Chandrayaan-2 OHRC | LRO NAC)
   │  io_ch2.load_product / io_lro.load_product
   │  (real SPICE geometry via NAIF WebGeocalc; PDS4/PDS3 label parsing)
   ▼
geo.align_pair(a, b)          — resample both onto one common grid at the
   │                             coarser GSD, over the real footprint overlap
   ▼
prep.to_gray_float, local_contrast_norm, gradient_orientation_mod_pi
   │
   ▼
match.match / match.match_tiled   — SIFT rung 0 (baseline) | rung 1 (mod-π) |
   │                                 LightGlue; grid-balanced keypoints,
   │                                 MAGSAC homography, sub-pixel refine.
   │                                 match_tiled pools every tile's raw
   │                                 candidates and fits ONE global
   │                                 homography — required above ~2048px,
   │                                 since an OHRC strip is ~55000x12000.
   ▼
geo.to_original_pixels / original_pixel_transform
   │                             — invert points AND the transform itself
   │                               back out of the aligned working grid into
   │                               each product's own original pixel frame
   ▼
metrics.rmse / inlier_stats / coverage / fit_reliability
   │                             — fit_reliability flags a homography fit as
   │                               untrustworthy when inliers reduce to ≤4
   │                               unique locations (a homography's 8 DOF can
   │                               satisfy 4 points exactly regardless of
   │                               whether they're real correspondences)
   ▼
deliverable.build_deliverable  — registered GeoTIFF (GDAL, falls back to
   │                             rasterio if GDAL absent), match points
   │                             (CSV/GeoJSON), RGB overlay, metrics.json
   ▼
cnet.write_control_network     — ISIS PVL control network (Free points,
                                  RegisteredSubPixel measures)
```

`src/pipeline.py::run_pipeline` wires all of this into one call
(`align`, `tile_size`, `matcher`, `rung`, `use_lcn` as parameters).

Every module in `src/` is unit-tested against hand-checkable synthetic data
(homographies with known ground truth, coverage grids with known occupancy).
**188/188 tests pass** as of this update.

## 3. Status by lane (per the original 6-way team split)

### Reia — pipeline integration (critical path) — ✅ done
- Tiling bug fixed: `match_tiled` pools every tile's raw candidates and fits
  one global MAGSAC homography, instead of trusting each tile's own RANSAC
  (which was shown to lock onto wrong-but-locally-consistent homographies on
  repetitive terrain).
- `geo.align_pair` wired into `pipeline.py` (previously implemented and
  tested, but never called by the real pipeline).
- Coordinate inversion: match points **and the fitted transform itself** are
  mapped back out of the aligned working grid into each product's own
  original pixel frame (`geo.to_original_pixels`,
  `geo.original_pixel_transform`). This caught a real bug during testing — an
  earlier version inverted the points but left the transform stale, producing
  a nonsensical 3612px "reprojection residual" on real data.
- `fit_reliability` guard added to `metrics.py`: flags any fit whose inliers
  reduce to ≤4 unique locations as `trivial_fit=True`, so a spurious
  minimal-sample fit can never masquerade as a validated registration again.
  Wired into `deliverable.py`'s metrics output.
- GDAL dependency removed from the deliverable writer: `_write_geotiff` now
  falls back to `rasterio` (same pattern `io_ch2.py` already used for
  reading), so the registered GeoTIFF can be produced without GDAL's Python
  bindings installed.
- Real end-to-end run executed against genuine CH2 (d32) × LRO NAC
  (M1499112398LE) data, ~26.5% real footprint overlap, real SPICE geometry.
  **Honest result: no trustworthy registration found on this pair** — both
  SIFT and mod-π reduce to ≤4 unique inlier locations (correctly flagged
  `trivial_fit=True`), and a visual checkerboard diagnostic confirmed why:
  `align_pair`'s single 4-corner perspective fit is accurate near one end of
  this long (~15000×1900px), narrow, curved-orbit strip and drifts elsewhere.
  This is a real, diagnosed geometric limitation, not a wiring bug — fixing
  it properly would mean a piecewise/multi-control-point geometric model in
  `align_pair`, which was not attempted (out of scope for remaining time).
- Environment note: reading real LRO products requires `pdr` (image data) and
  `webgeocalc` (real SPICE geometry — without it, LRO corners silently
  default to a `(0,0)` sentinel and `align_pair` produces meaningless output).
  Neither was in the original `requirements.txt`; both are now confirmed
  necessary and should be added for any teammate running real-data scripts.

### Riddhi — evidence — ✅ mostly done, one finding needs a pitch decision
- Win plot (`scripts/gen_win_plot.py`) threads `rung` through the sweep and
  overlays SIFT / mod-π / LightGlue — done.
- `premise_test.py` now calls `match.match` directly (confirmed in code) —
  no longer bypasses the production pipeline.
- `rmse_fitted` renamed to `reprojection_residual` (done in `metrics.py`);
  `rmse_ground_truth` is the non-circular metric.
- Both previously-missing tests exist: azimuth-drops-faster-than-elevation
  (`tests/test_sweep_extended.py`) and tiling correctness on repetitive
  terrain (`tests/test_tiling.py`).
- **Found and fixed this session:** `scripts/gen_win_plot.py`'s title was a
  hardcoded string ("SIFT collapses at 30 degrees. Mod-pi holds.") that did
  not match the data — mod-π actually collapses alongside SIFT through most
  of the sweep and only recovers near a true ~180° sun reversal (its
  invariance is mathematically exact only for a full intensity negation, not
  an arbitrary azimuth rotation). Title and shaded zones corrected to match
  the real data; verified reproducible on both real-DEM-shaped and synthetic
  terrain.
- **New finding, pitch decision already resolved:** LightGlue outperforms both
  SIFT variants by roughly 10-100x through the 0-60° range (e.g. ~890-950
  inliers at 30° vs. single digits for SIFT/mod-π), and holds sub-pixel
  residual and 80-94% grid coverage in that range where classical descriptors
  are below 16% coverage. A companion plot exists (`demo/coverage_plot.png` /
  `scripts/gen_coverage_plot.py`) backing this. Manya's deck (`demo/deck.html`)
  already leads with LightGlue as the headline ("SIFT collapses at 30°.
  LightGlue holds at 90°.") — confirmed this session that the deck's own
  numbers and framing are accurate and consistent with this finding.
- **Superseded:** `data/dem/LDEM_60S_240MPP_ADJ.tiff` is not present in this
  checkout, so `win_plot.png`/`coverage_plot.png` were first regenerated here
  on synthetic terrain to verify the fix. Manya has since regenerated
  `win_plot.png` from the real DEM on her own machine and committed it — see
  her lane below for the one remaining action (re-run with the *current*
  script, since her run used a pre-fix copy).

### Mehak — Deliverable 2 (registered product + match points) — ✅ safe example now packaged
- `deliverable.build_deliverable` writes a registered GeoTIFF, match points
  (CSV + GeoJSON), an RGB overlay, and `metrics.json` — confirmed working
  end-to-end in tests, GDAL-optional now (see Reia's lane).
- `cnet.py` (control network writer) is implemented, tested, and validated by
  round-tripping through the independent `pvl` parser.
- **Done this session:** since the real CH2×LRO pair is `trivial_fit=True`,
  built a complete, honestly-labelled Deliverable 2 example on a synthetic
  pair instead (`scripts/make_synthetic_deliverable.py` →
  `demo/synthetic_deliverable/`), run through the full production pipeline
  (LightGlue, the strongest benchmarked matcher) — **473 unique inliers,
  0.92px reprojection residual, `trivial_fit=False`**. Includes the
  registered GeoTIFF, match points (CSV/GeoJSON), overlay, metrics.json, and
  a control network re-verified to parse cleanly via `pvl`. This is a real,
  demoable, self-verified example of every deliverable artifact — Mehak
  should treat this as the reference for what a valid package looks like,
  and can point Slide 6 of the deck at it instead of the empty real-pair
  placeholder.
- **Still not independently verified:** whether the CH-2 rasters made it onto
  a USB stick for travel (a logistics item, not code).

### Manya — visual assets, deck, demo script, rehearsal — ✅ 5/6 done, 1 blocked on regeneration
- All visual assets, the 8-slide deck (`demo/deck.html`), and the SPICE
  cross-check script (`scripts/spice_cross_check.py`) exist and were checked
  this session. The deck's own text/tables (slides 4, 5, 7) are accurate and
  already lead with LightGlue as the headline result — independently reached
  the same conclusion recommended earlier in this session.
- **Found and fixed this session:** `demo/win_plot.png` was regenerated by
  Manya from the real SLDEM2015 DEM, but from a copy of `scripts/gen_win_plot.py`
  that predated the title fix — so the image embedded on Slide 4 still showed
  the stale "SIFT collapses at 30 degrees. Mod-pi holds." title, directly
  contradicting that same slide's correct headline text. **Manya needs to
  re-run `python -m scripts.gen_win_plot` (and ideally the new
  `python -m scripts.gen_coverage_plot`) after pulling latest, then re-commit
  the regenerated PNGs** — the fix is on `main`, this just needs a re-run with
  her local real-DEM file.
- **Found and fixed this session:** a branch merge (`Manya` → `main`) silently
  dropped the `fit_reliability` safety-check wiring from `src/deliverable.py`
  that had been added on `main` — Manya's branch touched the same function
  (adding the rasterio GDAL fallback, independently and correctly) but
  branched before that check existed, and the merge lost it. Restored; all
  tests pass again.
- **Edited directly this session:** Slide 8 (limitations) was stale — it
  listed the tiling bug as unfixed ("understood but not yet implemented"),
  which is now done and tested. Replaced with an honest, more specific
  limitation actually discovered this session: `align_pair`'s single 4-corner
  perspective fit drifts on long/narrow strips, which is *why* the real CH-2
  × LRO pair doesn't have a trustworthy registration yet. Slide 6's
  placeholder note was also updated to stop pointing at
  `demo/real_pair_result/` (now correctly flagged `trivial_fit=True`) and
  instead recommend assembling that slide from the synthetic/DEM pair.
- **Not checked this session:** whether any rehearsal has happened (item 6
  from the original handbook, explicitly called out as the one item requiring
  the whole team, not just Manya).

### Members 5 & 6 — API/job store, viewer/3D scene — not checked (explicitly excluded from this review)

## 4. Known risks / things to double check before presenting

1. **`ARCHITECTURE_AND_SOLUTION.md`'s benchmark table is not trustworthy as
   written** — it reports mod-π holding ~910-1340 matches at 120-180° sun
   difference; this session's actual measurements show mod-π at 0 matches
   through 60-120° and only a modest recovery (5-18) near 150-180°. Do not
   present that table without correcting it or removing it.
2. **The real CH2×LRO pair does not currently have a trustworthy
   registration** — be ready to explain this honestly (see Reia's lane) if
   asked about real-data results; do not present the raw inlier counts from
   that pair as a validated win.
3. **`demo/win_plot.png`'s title is stale** (pre-fix copy of the generator
   script was used) — regenerate from the real DEM before final printing.
   See Manya's lane above; this is the one remaining visual defect on the
   deck as it stands.
4. ~~New Python dependencies~~ — **done this session:** `requirements.txt`
   now lists `pdr` and `webgeocalc` (with comments explaining why); `rasterio`
   was already present.

## 5. Suggested immediate next steps

1. ~~Decide and lock the headline framing~~ — **done:** deck already leads
   with LightGlue, confirmed accurate.
2. Manya: `git pull`, re-run `python -m scripts.gen_win_plot` and
   `python -m scripts.gen_coverage_plot` with the real DEM, re-commit.
3. ~~Assemble a Deliverable 2 package~~ — **done this session:**
   `demo/synthetic_deliverable/` (473 inliers, 0.92px residual,
   `trivial_fit=False`, valid control network). Mehak should point Slide 6
   at this instead of the empty real-pair placeholder, and can still pursue
   a genuine real-pair package separately once `align_pair`'s geometric
   model is improved.
4. Correct or remove the stale benchmark table in
   `ARCHITECTURE_AND_SOLUTION.md`.
5. Check in with Manya on rehearsal timing (item 6, whole-team task).
