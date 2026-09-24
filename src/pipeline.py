# src/pipeline.py — wires io -> geo -> prep -> match -> metrics into one callable run.

from dataclasses import asdict

import numpy as np

from src.align_cache import cached_align_pair
from src.geo import to_original_pixels, original_pixel_transform
from src.prep import to_gray_float, local_contrast_norm
from src.match import match as run_match, match_tiled, TILE_SIZE, TILE_OVERLAP
from src.metrics import fit_reliability

# Above this side length (either axis, post-alignment) tile the match instead of
# handing SIFT the whole raster -- an OHRC strip is ~55000x12000px and was never
# going to work as one call.
TILE_THRESHOLD_PX = 2048

# Order tried by run_pipeline(cascade=True): cheapest first.
CASCADE_RUNGS = (0, 1)


def _fit_key(result):
    """Rank fits: a well-determined fit beats any other, then more distinct
    inlier locations, then more inliers."""
    rel = fit_reliability(result)
    return (rel["well_determined"], rel["unique_inlier_locations"],
            int(result.inlier_mask.sum()))


def run_pipeline(
    product_a,
    product_b,
    matcher: str = "sift",
    rung: int = 0,
    use_lcn: bool = True,
    contrast_sigma: float = 15.0,
    lcn_downsample: int = 1,
    align: bool = False,
    tile_size: int = TILE_SIZE,
    tile_overlap: int = TILE_OVERLAP,
    cascade: bool = False,
) -> dict:
    """product_a, product_b: src.types.Product instances, already loaded.

    matcher: "sift" or "lightglue".
    rung: passed through to match() for the sift path — 0 = raw-intensity SIFT
      baseline, 1 = gradient-orientation-mod-pi descriptor. Ignored by lightglue.
    use_lcn: whether to apply illumination-robust local contrast normalisation before
      matching. Exposed as a toggle so the ablation can separate its contribution from
      the descriptor's — with LCN hard-wired on, a rung-1 win can't be attributed to the
      mod-pi descriptor vs the LCN prep. The four ablation cells are (use_lcn, rung) over
      {False, True} x {0, 1}.
    lcn_downsample: passed through to local_contrast_norm's own `downsample` --
      estimate its low-frequency blur/variance fields on a downscaled copy for
      speed (measured ~4.7x on a real full-resolution CH2 raster, 0.996
      correlation, comparable SIFT keypoint yield) while still returning a
      full-resolution result. Off (1) by default; validate against the full
      real-pair inventory before relying on a higher value anywhere real
      matching happens, per this docstring's own align note below about not
      trading correctness for speed silently.
    align: resample both products onto one common geo grid via geo.align_pair
      (through align_cache.cached_align_pair, an on-disk cache of that
      deterministic, expensive resampling step keyed on product identity/shape/gsd —
      see src/align_cache.py) before matching (Move 1 — closes the scale gap using
      metadata instead of asking the matcher to bridge it). Off by default so callers
      without real georeferencing
      (synthetic ablation pairs, `corners={}`) keep working unchanged; real product
      pairs should pass True. When True, match_result's pts_a/pts_b are inverted back
      out of the common-grid frame into each product's own original pixel space before
      being returned — the common grid only exists to make matching correct, nothing
      downstream (cnet.py Sample/Line, a registered-raster export against the source
      raster) should ever see a coordinate in it.
    tile_size/tile_overlap: passed to match_tiled() when either (post-alignment) image
      dimension exceeds TILE_THRESHOLD_PX. Tiling pools every tile's raw candidate
      matches and fits one global homography across the whole image rather than
      trusting each tile's own RANSAC — see match.match_tiled's docstring for why a
      per-tile fit alone is unsafe on repetitive terrain.

    cascade: try SIFT (rung 0) first; only if its fit is not well_determined
      (metrics.fit_reliability) also try rung 1, and keep whichever fit is
      better. Alignment and LCN are done once and shared. Measured on the
      8 validated real pairs, rung 0 alone is well-determined on some and
      rung 1 on others, so this covers more pairs than either fixed choice
      while paying rung 1's extra cost only when rung 0 fails. `matcher` /
      `rung` are ignored (SIFT rungs 0 then 1). config["rung"] reports the
      rung whose result was kept and config["rungs_tried"] all that ran.

    Returns a dict with the MatchResult (as a dict, in original-pixel space whenever
    align=True) plus full metrics (rmse/inlier_stats/coverage) via metrics.evaluate.
    """
    match_product_a, match_product_b = product_a, product_b
    if align:
        match_product_a, match_product_b = cached_align_pair(product_a, product_b)

    a = to_gray_float(match_product_a.array)
    b = to_gray_float(match_product_b.array)
    if use_lcn:
        a = local_contrast_norm(a, sigma=contrast_sigma, downsample=lcn_downsample)
        b = local_contrast_norm(b, sigma=contrast_sigma, downsample=lcn_downsample)

    def _match(r):
        if max(a.shape[:2]) > TILE_THRESHOLD_PX or max(b.shape[:2]) > TILE_THRESHOLD_PX:
            return match_tiled(a, b, matcher=matcher, rung=r,
                               tile_size=tile_size, overlap=tile_overlap)
        return run_match(a, b, matcher=matcher, rung=r)

    rungs_tried = []
    if cascade:
        matcher = "sift"
        result = None
        for r in CASCADE_RUNGS:
            candidate = _match(r)
            rungs_tried.append(r)
            if result is None or _fit_key(candidate) > _fit_key(result):
                result, rung = candidate, r
            if fit_reliability(result)["well_determined"]:
                break
    else:
        result = _match(rung)
        rungs_tried.append(rung)

    if align:
        m_a = original_pixel_transform(match_product_a, product_a)  # aligned_a_px -> a_px
        m_b = original_pixel_transform(match_product_b, product_b)  # aligned_b_px -> b_px
        result.pts_a = to_original_pixels(match_product_a, product_a, result.pts_a)
        result.pts_b = to_original_pixels(match_product_b, product_b, result.pts_b)
        # result.transform maps aligned_a_px -> aligned_b_px (that's the grid it was
        # fit on); pts_a/pts_b no longer live there, so the transform must be
        # re-composed into a_px -> b_px or every downstream reprojection check
        # (metrics.rmse, RANSAC-consistency of the "inliers" it already picked)
        # silently measures against the wrong frame and blows up.
        result.transform = m_b @ result.transform @ np.linalg.inv(m_a)
        result.transform = result.transform / result.transform[2, 2]
        # pts_a/pts_b now live in each product's own original pixel frame, not the
        # aligned working grid match() ran on -- shape_a/shape_b must follow them,
        # or a consumer keyed on shape (e.g. metrics.coverage's grid-cell sizing)
        # silently measures the wrong frame.
        result.shape_a = tuple(product_a.array.shape[:2])
        result.shape_b = tuple(product_b.array.shape[:2])

    return {
        "match_result": asdict(result),
        "product_a_id": product_a.product_id,
        "product_b_id": product_b.product_id,
        "config": {"matcher": matcher, "rung": rung, "use_lcn": use_lcn, "align": align,
                   "rungs_tried": rungs_tried},
    }
