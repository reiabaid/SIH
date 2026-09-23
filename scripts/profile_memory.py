"""Real peak-RSS profiling of the FULL production job path (run_pipeline +
build_deliverable, exactly as src/api.py's process_job_sync calls them), run
INSIDE the actual deployment container (Linux). `resource.ru_maxrss` gives
the process's high-water-mark resident memory in KB on Linux -- monotonically
non-decreasing, so printing it after each stage shows exactly which stage
pushes memory up, not just a final total.

Run inside the container, e.g.:
    docker run --rm -v "<repo>/scripts:/app/scripts" -v "<repo>/src:/app/src" \
        lunarmatch:latest sh -c "pip install --quiet webgeocalc && python -m scripts.profile_memory"
"""
import resource
import tempfile

from src.io_ch2 import load_product as load_ch2
from src.io_lro import load_product as load_lro
from src.pipeline import run_pipeline
from src.deliverable import build_deliverable
from src.types import MatchResult

CH2_XML = ("data/ch2_products/ch2_ohr_ncp_20200229T0938004033_d_img_d32/"
           "miscellaneous/calibrated/20200229/"
           "ch2_ohr_ncp_20200229T0938004033_d_img_d32.xml")
LRO_IMG = "data/lro_nac/M1529537951LE.IMG"


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0  # KB -> MB on Linux


def report(label):
    print(f"[{label}] peak RSS so far: {rss_mb():.0f} MB", flush=True)


def main():
    report("startup (imports only)")

    # Same order src/api.py's process_job_sync now uses: load the non-CH2
    # product first, then CH2 with overlap_hint=the other product.
    lro = load_lro(LRO_IMG)
    report("after load_lro")

    ch2 = load_ch2(CH2_XML, overlap_hint=lro)
    report(f"after load_ch2 (cropped={'cropped_window' in ch2.meta})")

    out = run_pipeline(ch2, lro, matcher="sift", rung=0, align=True)
    mr = out["match_result"]
    result = MatchResult(
        pts_a=mr["pts_a"], pts_b=mr["pts_b"], scores=mr["scores"],
        inlier_mask=mr["inlier_mask"], transform=mr["transform"], matcher=mr["matcher"],
        shape_a=mr["shape_a"], shape_b=mr["shape_b"], runtime_s=mr["runtime_s"],
    )
    report(f"after run_pipeline (total={len(result.pts_a)}, inliers={int(result.inlier_mask.sum())})")

    with tempfile.TemporaryDirectory() as out_dir:
        metrics = build_deliverable(ch2, lro, result, out_dir)
    report(f"after build_deliverable (inlier_count={metrics.get('inlier_count')})")

    print(f"\nFINAL PEAK RSS: {rss_mb():.0f} MB")


if __name__ == "__main__":
    main()
