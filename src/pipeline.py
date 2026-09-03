# src/pipeline.py — wires io -> geo -> prep -> match -> metrics into one callable run.
# Skeleton only: geo.align_pair and metrics.evaluate land from Riddhi; io readers from
# Mehak/Manya. Wire them in as they arrive without changing this function's signature.

from dataclasses import asdict

from src.prep import to_gray_float, local_contrast_norm
from src.match import match as run_match


def run_pipeline(product_a, product_b, matcher: str = "sift", contrast_sigma: float = 15.0) -> dict:
    """product_a, product_b: src.types.Product instances, already loaded.

    Returns a dict with the MatchResult (as a dict) and basic metrics. Geometric
    alignment (align_pair) and full metrics (rmse/inlier_stats/coverage) plug in
    here once geo.py and metrics.py land — this skeleton runs match.py end to end
    on whatever arrays it's given so downstream lanes aren't blocked.
    """
    a = local_contrast_norm(to_gray_float(product_a.array), sigma=contrast_sigma)
    b = local_contrast_norm(to_gray_float(product_b.array), sigma=contrast_sigma)

    result = run_match(a, b, matcher=matcher)

    return {
        "match_result": asdict(result),
        "product_a_id": product_a.product_id,
        "product_b_id": product_b.product_id,
    }
