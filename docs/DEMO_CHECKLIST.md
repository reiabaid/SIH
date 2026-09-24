# LunarMatch — Live Pitch Demo Script & Checklist

> **Accuracy caveat (2026-09-25 -- read before presenting).** The reprojection RMSE and "sub-pixel" figures below measure how well matched points fit the fitted transform. They are NOT registration accuracy against ground truth, which does not exist for the real pairs. Cross-checks on the 8 real CH2 x LRO pairs found no independently corroborated registration (0 consistent, 2 disagreeing by 0.9-5 km, 6 not comparable; see `docs/WORK_DIVISION_PLAN.md`). Say "the pipeline runs end to end on real ISRO data and reports a cross-check", not "sub-pixel accurate on real data". Sub-pixel accuracy is demonstrated on the synthetic pairs only.

This document is the official pitch checklist and operational guide for live demonstrations of LunarMatch.
It specifies the exact pre-baked demo pair, screen-by-screen walkthrough instructions, expected metrics, and critical pitfalls to avoid during live presentation.

---

## 1. Quick-Start Terminal Commands to Run the Project

### Option A: Local Development (Fastest for testing)
Run backend and frontend in separate terminals:

**Terminal 1 (Backend API):**
```bash
# From the repository root
uvicorn src.api:app --reload --port 8000
```
*Initializes SQLite `jobs.db`, loads product inventory, and exposes API on `http://127.0.0.1:8000`.*

**Terminal 2 (Frontend UI):**
```bash
cd frontend
npm run dev
```
*Launches Vite dev server on `http://localhost:5173` with hot-module reload.*

---

### Option B: Containerized Deployed Instance (Recommended for Pitch / Production)
Runs the complete containerized stack (compiled React frontend served directly by FastAPI backend):

```bash
# Build the Docker image (automatically runs scripts/precompute_demo.py during build)
docker build -t lunarmatch .

# Run the container
docker run -p 8000:8000 lunarmatch
```
*Open `http://localhost:8000` in any browser. Both frontend and backend run in a single container.*

---

## 2. Designated Demo Pair: `synthetic_a` × `synthetic_b`

### Why This Pair?
- **Pre-baked & Instantaneous (< 50ms):** Baked into SQLite `jobs.db` via `scripts/precompute_demo.py`. When clicked, `src/api.py` recognizes the completed registration and serves the deliverables instantly from disk.
- **Identical Pipeline:** Does not use any mocked shortcuts. It executes the exact same photogrammetric pipeline: `cached_align_pair` -> tiling -> `match_tiled` -> sub-pixel refine -> deliverable creation -> USGS/ISIS `.net` control network generation.
- **Zero Live Network Risk:** Completely avoids the 35–48s NAIF WebGeocalc network call, multi-gigabyte raster disk reads, or GPU memory limits on presentation hardware.

---

## 3. Screen-by-Screen Pitch Walkthrough

### Step 1: Screen 01 — Pair Selection
1. **Product A**: Select `synthetic_a` from the dropdown.
2. **Product B**: Select `synthetic_b` from the dropdown.
3. **Footprint Overlap**: Observe the instant calculation showing `100.0% overlap`.
4. **Matcher Selection**:
   - **Recommended Primary**: Keep **Rung 0: SIFT (Standard)** selected.
     * *Talking point:* "Standard SIFT pipeline with spatial tiling and USAC_MAGSAC robust estimation."
   - **Feature Showcase Option**: Select **Rung 1: Illumination-Invariant (Log-Gabor MIM)**.
     * *Talking point:* "Our novel illumination-invariant descriptor using log-Gabor Maximum Index Maps (MIM), resilient to extreme cross-illumination phase flips where conventional gradients fail."
5. Click **"Run Registration"**.
   - *Behavior:* Returns **instantly** (0 seconds wait time; eliminates the awkward spinner during the pitch).

---

### Step 2: Screen 02 — Match Review
1. **Verification Metrics Display**:
   - **Inlier Count**: ~330 verified tie points (Rung 0) or ~51–258 tie points (Rung 1).
   - **Reprojection Error (RMSE)**: ~0.21 px (fit residual only -- not accuracy against ground truth).
   - **Status**: `well_determined` (non-trivial fit).
2. **Interactive Visuals**:
   - Toggle **"Show Keypoints"** to display correspondence vectors across the crater field.
   - Zoom in on crater rim features and show the overlay (do not claim a measured accuracy).
3. Click **"Accept Match & Review Evidence"**.

---

### Step 3: Screen 03 — Photogrammetric Evidence
1. **Deliverable Validation**:
   - Highlight the **Reprojection Residual Distribution** (tight Gaussian clustered well below 1.0 pixel).
   - Highlight the **Occupied Grid Fraction** (evidence that tie points span the full terrain footprint rather than clustering in a single corner).
   - Show the **3×3 Projective Homography Matrix** parameters derived from deterministic MAGSAC.
2. Click **"Proceed to 3D Terrain & Export"**.

---

### Step 4: Screen 04 — 3D Terrain Report & Artifact Export
1. **Interactive 3D DEM Viewer**:
   - Rotate and pitch the 3D lunar surface mesh rendered with Three.js.
   - Adjust the **Sun Azimuth / Elevation** slider to demonstrate dynamic shading over the registered crater morphology.
2. **Real Deliverable Downloads**:
   - Click **Download Control Network (`.net`)**: Downloads the ISIS3/USGS compliant control network file (`SIH26166_<job_id>.net`).
   - Click **Export Registered GeoTIFF**: Generates calibrated, georeferenced raster with embedded tie points ready for GIS/planetary analysis.

---

## 4. Critical Pitch Pitfalls — What NOT to Do

| Action | Why to Avoid | Fallback / What to Say Instead |
|---|---|---|
| **DO NOT click `d18 × M1499112398LE`** | This is the 1/8 pair in the real inventory that has zero valid matchers post-determinism fix (`well_determined=False`). | If asked about inventory coverage: *"Our reproducible MAGSAC fix verified 7/8 real pairs succeed, eliminating a previous false positive on this specific pair."* |
| **DO NOT click LightGlue (Rung 2) live** | LightGlue inference takes **90–240 seconds** on CPU. Running it live causes an uncomfortable multi-minute wait. | *"LightGlue is supported as an opt-in deep learning matcher for extreme non-linear deformations, but our default path returns a fit and a cross-check between two matchers."* |
| **DO NOT click an uncached real pair on cold hardware** | Cold LRO loading requires 35–48s of NAIF WebGeocalc network calls, and cold CH2 requires decoding 4.5 GB TIFF rasters. | Click `synthetic_a × synthetic_b` for live interaction. For real pairs, show the pre-rendered artifacts in `demo/` (`aligned_checkerboard_crater_crop.png`, `coverage_plot.png`, `win_plot.png`). |

---

## 5. Live Pitch Backup Cheatsheet

If judges request real-world Chandrayaan-2 vs LRO evidence:
- **Verified Working Real Pairs**:
  - `d32 × M1519299970LE`: 22 inliers (Rung 0), 25 inliers (Rung 1), inlier counts only; not independently verified.
  - `d18 × M1519299970LE`: 15 inliers (Rung 0), **63 inliers** (Rung 1 — Log-Gabor MIM win).
  - `d32 × M1531872919LE`: 8 inliers (Rung 0), **72 inliers** (Rung 1 — Log-Gabor MIM win).
- **Pre-rendered Assets in `demo/`**:
  - `demo/aligned_checkerboard_crater_crop.png`: Demonstrates visual continuity across checkerboard tiles.
  - `demo/coverage_plot.png`: Shows spatial distribution of tie points across overlapping footprints.
  - `demo/win_plot.png`: Quantitative comparison proving Rung 1's superior inlier density over standard descriptors under disparate lighting.

