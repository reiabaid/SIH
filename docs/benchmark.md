# MoonAnything benchmark — what's actually there, and what we can use

Surveyed 2026-09-03. Owner: Riddhi. Source: the [GitHub repo](https://github.com/clementinegrethen/MoonAnything)
(no code — it's a pointer) and the [Zenodo record](https://zenodo.org/records/18415119)
it links to, plus the `readme_geo.txt` shipped inside that record. Fetched
directly rather than assumed — the real thing turns out to differ from how
it's described in the team's own build-plan doc, in ways worth knowing
before anyone spends a hackathon evening downloading it.

## The one-line correction first

The build-plan doc describes MoonAnything as "130k+ rendered lunar samples
with multi-illumination pairs and known ground-truth correspondences." The
actual GitHub README says, verbatim:

> **Important Note (Sample Release)** — Due to the very large size of the
> full dataset and the long upload time, this Zenodo release currently
> contains only a *sample* of the MoonAnything dataset. The full dataset
> will be released progressively or via alternative hosting solutions.

So: whatever numbers exist for the *full* dataset (the paper — accepted at
ACM MMsys 2026 — presumably has them), what's downloadable *today* is a
sample of unstated size, not the full benchmark. Plan accordingly — don't
promise "we benchmarked against MoonAnything's full 130k samples" in a demo
without checking what actually downloaded.

## What's actually on Zenodo

Three files, 22.4 GB total:

| File | Size |
|---|---|
| `LunarPhoto.zip` | 11.0 GB |
| `StereoGeo.zip` | 11.4 GB |
| `readme_geo.txt` | 2.6 KB |

License: CC BY 4.0 (redistribution fine with attribution — cite the paper
and the Zenodo DOI, `10.5281/zenodo.18415119`).

## Sub-dataset 1: LunarPhoto — the one we'd actually use

Real LRO NAC imagery paired with a DEM patch, both cropped to the same
extent, plus synthetic multi-illumination renders of that same geometry.
Per the Zenodo description, each sample is:

- a **128×128 px DEM patch**, 5 m/px GSD (~0.4 km² coverage), from the Tycho
  crater region
- a **real LRO NAC image** (native 0.5–2 m/px), "orthorectified onto the
  local DEM" and "cropped to exactly match the DEM spatial extent"
- **18 rendered images per sample**: 9 solar illumination conditions
  (sampled via SPICE) × 2 reflectance models (Hapke BRDF, SVBRDF)
- additional maps: SVBRDF, surface normal, depth, line-of-sight

**The load-bearing fact for us:** every one of those 18 renders plus the
real NAC image is *pixel-aligned to the same DEM patch* — same camera
geometry throughout, only the lighting changes. That means the ground-truth
correspondence between any two illumination variants of one sample is the
**identity transform**, not a homography we'd need to solve for. That's
both a gift and a limit:

- **Gift:** perfect for testing `match.py` + `metrics.py`'s illumination
  robustness in isolation, with zero extra engineering. Run `match()` on
  two illumination variants of the same sample; a good matcher should
  recover something very close to identity, and `rmse(result,
  gt_transform=np.eye(3))` should come out near 0. Any real error is
  matcher error, not ground-truth noise — same philosophy as our own
  synthetic tests in `tests/test_match.py`, but on rendered-from-real
  geometry instead of a warped crater field.
- **Limit:** no scale or viewpoint variation within a sample, so it's
  **not** a stand-in for `geo.py`'s `align_pair` (which exists specifically
  for the ~320× OHRC-vs-NAC scale gap). LunarPhoto can't validate that —
  our own synthetic 4×-downsample tests in `tests/test_geo_align.py` remain
  the only ground truth we have for scale mismatch, until real CH2/LRO
  pairs are in hand.

Precise file formats for the DEM/BRDF/normal/depth/LOS maps within
LunarPhoto weren't stated anywhere in the README or Zenodo description —
that's a real gap in the available docs, not something I'm inferring
around. Would need to actually unzip a sample to confirm (`.exr`/`.npz`/
`.tif`, unstated) before writing a loader against it.

## Sub-dataset 2: LunarGeo / StereoGeo — real geometry, more engineering

Stereo image pairs with dense depth and camera pose supervision, covering
the lunar South Pole and Tycho crater, rendered by ray-tracing (SurRender)
over real DEMs. `readme_geo.txt` (shipped inside the Zenodo record) gives
the exact structure:

- Images: `im_00000.jpg`, `im_00001.jpg`, ... — **consecutive even/odd
  indices are one stereo pair**
- Every pair also gets **3 illumination variants**, sequential in the same
  folder: `(im_00000, im_00001)` = illum #1, `(im_00002, im_00003)` = illum
  #2 of the *same* stereo geometry, `(im_00004, im_00005)` = illum #3
- Each image has a matching `.npz` (camera intrinsics `K` and `cam2world`
  extrinsics, DUSt3R/MASt3R-convention, resolution typically 512×512 or
  1024×1024) and a matching `.exr` (single-channel float32 depth in
  metres, camera-centered, `inf` for sky/invalid)
- Three camera-motion types (nadir, oblique, dynamic), kept in separate
  batch folders "for naming and traceability reasons" even though they
  could be merged

**What we can use this for:** unlike LunarPhoto, this has genuine parallax
— real 3D structure, not a fixed viewpoint — so it's a much stronger test
of `match.py`'s matcher than our planar-homography synthetic pairs. But the
ground-truth correspondence isn't handed to us as point pairs; it has to be
**derived**: unproject a pixel in image A using its depth and `K`, transform
through `cam2world` into image B's camera frame, reproject. That's a
real but small script (numpy only, same tools we already use in
`metrics.py`) — not free, but straightforward. Worth doing only if match.py
needs a stronger real-geometry check than the synthetic tests already give;
not needed to unblock anything currently in progress.

## Recommendation

Given the "sample release" caveat and that both zips are ~11 GB each
(uncomfortable on hackathon wifi and laptop disk, per the team's own
"assume no venue wifi" planning note):

1. **Don't block on downloading either zip before the hackathon.** Nothing
   in Phases 1–5 needed it, and nothing here changes that.
2. **If time allows, prioritize LunarPhoto over StereoGeo.** It directly
   exercises this project's core stated challenge — sun-angle robustness —
   with zero extra engineering (identity ground truth). StereoGeo needs a
   depth-reprojection script before its ground truth is usable at all.
3. **Don't cite "130k+ samples" or the full dataset size in a demo** without
   re-checking the actual sample's contents — the number in the team's
   build-plan doc describes the full (not-yet-released) dataset, not what's
   downloadable today.
