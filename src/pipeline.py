# src/pipeline.py — wires io -> geo -> prep -> match -> metrics into one callable run.
# Skeleton only: geo.align_pair and metrics.evaluate land from Riddhi; io readers from
# Mehak/Manya. Wire them in as they arrive without changing this function's signature.

from dataclasses import asdict

from src.prep import to_gray_float, local_contrast_norm
from src.match import match as run_match


def run_pipeline(
    product_a,
    product_b,
    matcher: str = "sift",
    rung: int = 0,
    use_lcn: bool = True,
    contrast_sigma: float = 15.0,
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

    Returns a dict with the MatchResult (as a dict). Geometric alignment (align_pair)
    and full metrics (rmse/inlier_stats/coverage) plug in here once geo.py and
    metrics.py land — this skeleton runs match.py end to end on whatever arrays it's
    given so downstream lanes aren't blocked.
    """
    a = to_gray_float(product_a.array)
    b = to_gray_float(product_b.array)
    if use_lcn:
        a = local_contrast_norm(a, sigma=contrast_sigma)
        b = local_contrast_norm(b, sigma=contrast_sigma)

    result = run_match(a, b, matcher=matcher, rung=rung)

    return {
        "match_result": asdict(result),
        "product_a_id": product_a.product_id,
        "product_b_id": product_b.product_id,
        "config": {"matcher": matcher, "rung": rung, "use_lcn": use_lcn},
    }
