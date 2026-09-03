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

**Not yet done:** `align_pair(a, b)` — the actual resampling onto a common
grid — is Phase 2, still to come. `footprint_overlap` is a building block for
it (decide whether two products overlap enough to be worth aligning at all)
but doesn't do the resampling itself.

---

## Phase 2 — `align_pair(a, b) -> (Product, Product)` — not started

Resample both Products onto a common grid at the coarser GSD, over their
overlapping region. Turns the 320× scale gap into a matchable pair.

## Phase 3 — `metrics.py`: `rmse` + `inlier_stats` — not started

## Phase 4 — `metrics.py`: `coverage` — not started

## Phase 5 — `scripts/report.py` — not started

## Phase 6 — `docs/benchmark.md` (MoonAnything survey) — not started
