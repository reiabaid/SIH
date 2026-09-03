# Riddhi's lane — progress log

Owner: Riddhi. Lane: geometry (`src/geo.py`) + evaluation (`src/metrics.py`) +
`scripts/report.py` + the MoonAnything benchmark survey. Full plan and rationale
for the whole project lives in the team's build-plan and work-division docs;
this file tracks what's actually been built, phase by phase, so anyone (including
future me) can see what's done and why without re-reading the whole plan.

Frozen contract this lane builds against: `src/types.py` — `Product` and
`MatchResult` dataclasses. Do not change their shape without telling the team.

---

## Phase 1 — `footprint_overlap(a, b) -> float` ✅ done

**File:** [`src/geo.py`](src/geo.py)
**Test:** [`tests/test_geo.py`](tests/test_geo.py) — 9/9 passing

**What it does:** given two `Product`s, returns what fraction of `a`'s footprint
is covered by `b`, as a number in `[0, 1]`.

**How:** each `Product.corners` dict (`ul`/`ur`/`ll`/`lr` → `(lat_deg, lon_deg)`)
becomes a shapely polygon, walked `ul → ur → lr → ll` so the boundary doesn't
cross itself. Intersect the two polygons, divide by `a`'s area.

**Simplifications, on purpose, for the MVP:**
- Coordinates are treated as flat `(lon, lat)` — planar, not geodesic. Fine at
  the tile/strip sizes this project works at; would break down over a whole
  hemisphere.
- Doesn't handle the antimeridian (longitude wraparound at 0°/360°). Not an
  issue for a single Chandrayaan-3 landing-site area of interest.

**Why the tests are trustworthy:** every footprint is a synthetic rectangle
built from lat/lon bounds I chose myself, so every expected answer is
hand-computed, not eyeballed:
- identical squares → overlap `1.0`
- disjoint squares → overlap `0.0`
- two unit squares offset by half a unit → overlap `0.5`, both directions
- a small square fully inside a 3×3 one → `1.0` one way, `1/9` the other way
  (this is the case that proves the function is correctly **not symmetric** —
  `footprint_overlap(a, b) != footprint_overlap(b, a)` in general)

**Edge cases added after a review pass:**
- **touching, not overlapping** — two unit squares sharing only a boundary
  edge → `0.0` (intersection is a line, zero area)
- **small overlap** — a 100-area square clipped by 1 unit² in one corner →
  `0.01`, checks the math doesn't only work for "clean" 50/50-style splits
- **non-square rectangles** — a 5×10 and a 4×8 (not a square) → confirms
  nothing was accidentally relying on square geometry
- **degenerate zero-area footprint** — a flattened "rectangle" with zero
  height (all points collinear) → returns `0.0` cleanly, not `NaN` or a
  division-by-zero
- **corner-ordering validity** — asserts `_corners_to_polygon` produces a
  valid, non-self-intersecting polygon with the expected area, making the
  `ul → ur → lr → ll` winding-order assumption explicit rather than implicit

**Dependency added:** `shapely`, added to `requirements.txt`.

**Not yet done at the time:** `align_pair(a, b)` — the actual resampling onto
a common grid — was Phase 2. `footprint_overlap` is a building block for it
(decide whether two products overlap enough to be worth aligning at all) but
doesn't do the resampling itself.

---

## Phase 2 — `align_pair(a, b) -> (Product, Product)` ✅ done

**File:** [`src/geo.py`](src/geo.py)
**Test:** [`tests/test_geo_align.py`](tests/test_geo_align.py) — 11/11 passing

**What it does:** resamples both `Product`s onto one common grid, at the
coarser of the two GSDs, over the region where their footprints overlap.
Returns two new `Product`s of identical array shape and identical corners —
this is what removes the 320× scale gap so `match.py` never needs a
scale-invariant descriptor.

**How:** each product's four corners are fit to a 3×3 homography (pixel →
lon/lat) with `cv2.getPerspectiveTransform` — the same planar approximation
`footprint_overlap` uses. The overlap region (via shapely, reusing Phase 1's
`_corners_to_polygon`) defines the destination grid's bounds; the coarser
GSD converted to degrees (using the Moon's mean radius, 1,737,400 m) defines
its resolution. Composing `dst_geo→pixel ∘ src_pixel→geo` gives one matrix
per product that `cv2.warpPerspective` uses to resample straight onto the
shared grid in a single call — no explicit per-pixel geo math needed.

**Deliberate choice:** used `cv2` (already a project dependency, via
`match.py`) instead of `rasterio`/GDAL for the warp. Avoids a heavy native
dependency that's often fiddly to install on Windows, at the cost of the same
planar (not geodesic) approximation already in use for Phase 1 — acceptable
at the tile/strip sizes this project works at.

**A real bug the tests caught (not just a test artifact):** the destination
grid's pixel count was originally computed with `range / deg_per_px`
(pixel-is-area math — N pixels span N steps), while the source corner-fit
implicitly treats N pixels as spanning N-1 steps (pixel-is-center math,
since corner 0 and corner N-1 are the two extreme pixel indices given to
`cv2.getPerspectiveTransform`). The two halves of the same function disagreed
with each other — invisible on large images (the mismatch is ~1/N, negligible
at real OHRC/NAC resolutions) but caught immediately by an idempotency test
using a small 64×64 synthetic image, where it showed up as a wrong output
shape (63 vs 64) and low correlation (0.94 instead of >0.99) against an
identity case. Fixed by using `N-1` consistently on both sides.

**Tests, each hand-checkable:**
- **happy path** — a 256×256 synthetic image and its own 4× `cv2.resize`
  downsample, both given self-consistent corners/GSD; `align_pair` on the two
  should recover matching shapes (~64×64) with correlation > 0.9
- **no overlap** — two products with disjoint footprints raise a `ValueError`
  naming both product IDs (per the project's "fails clearly" definition of
  done), not a stack trace from inside a warp call
- **partial overlap windowing** — two 128×128 products offset so only a
  quarter of each overlaps; checks the aligned output's corners equal the
  exact intersection bounds and both outputs share one shape
- **idempotency** — aligning a product against an identical copy of itself
  (same corners, same GSD) should reproduce the original array almost
  exactly (correlation > 0.99) — this is the test that caught the bug above

**Second round of edge cases, after a further review pass:**
- **mismatched input array dimensions** — a 128×128 and a 256×256 at the same
  GSD but different physical extents; confirms the function never assumes
  `a.array.shape == b.array.shape`
- **one footprint fully contains the other** — checks the overlap window is
  exactly the smaller footprint, not a partial-rectangle case, and that both
  outputs share its corners
- **very small (sub-pixel) overlap** — two footprints overlapping by less
  than one output pixel. **This one caught a second real bug**: when the
  overlap collapses to a single output row/column, the fallback step size
  was `0.0`, making the destination grid's matrix singular — `np.linalg.inv`
  would have raised on real, valid (if extreme) input. Fixed by falling back
  to the target step size instead of `0.0` (harmless, since only index 0 is
  ever sampled on that axis — the step value is irrelevant to the result,
  only to keeping the matrix invertible)
- **argument order** — `align_pair(fine, coarse)` and `align_pair(coarse,
  fine)` must agree on the common GSD and produce identically-shaped output
- **non-square images** (80×160) — rules out bugs that only work when
  height equals width
- **known gradient direction** — a horizontal ramp must stay non-decreasing
  left-to-right after warping; a stronger check than correlation alone,
  since it would catch a flipped or transposed warp that correlation might
  not
- **non-positive GSD** (`0.0` or negative) — now raises `ValueError` naming
  the bad value, instead of silently dividing by zero inside the grid-sizing
  math

**Not yet done:** Phase 3, `metrics.py`'s `rmse` + `inlier_stats`.

## Phase 3 — `metrics.py`: `rmse` + `inlier_stats` — not started

## Phase 4 — `metrics.py`: `coverage` — not started

## Phase 5 — `scripts/report.py` — not started

## Phase 6 — `docs/benchmark.md` (MoonAnything survey) — not started
