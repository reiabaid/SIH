"""run_pipeline(cascade=True): SIFT first, rung 1 only if the fit is unreliable."""
import numpy as np

import src.pipeline as pipeline
from src.types import MatchResult, Product


def _product(pid):
    return Product(array=np.random.default_rng(0).random((64, 64)).astype(np.float32), gsd_m=1.0,
                   corners={}, source="SYNTH", product_id=pid)


def _result(n_unique):
    """A MatchResult whose inliers sit at n_unique distinct locations."""
    pts = np.array([[10.0 * i, 5.0 * i] for i in range(n_unique)], dtype=np.float32).reshape(-1, 2)
    return MatchResult(pts_a=pts, pts_b=pts.copy(), scores=np.ones(len(pts), np.float32),
                       inlier_mask=np.ones(len(pts), bool), transform=np.eye(3),
                       matcher="sift", shape_a=(64, 64), shape_b=(64, 64), runtime_s=0.0)


def _run(monkeypatch, per_rung):
    calls = []

    def fake(a, b, matcher="sift", rung=0):
        calls.append(rung)
        return _result(per_rung[rung])

    monkeypatch.setattr(pipeline, "run_match", fake)
    out = pipeline.run_pipeline(_product("a"), _product("b"), cascade=True, use_lcn=False)
    return out, calls


def test_cascade_stops_at_rung0_when_the_fit_is_well_determined(monkeypatch):
    out, calls = _run(monkeypatch, {0: 12, 1: 30})
    assert calls == [0]
    assert out["config"]["rung"] == 0 and out["config"]["rungs_tried"] == [0]


def test_cascade_falls_back_to_rung1_and_keeps_the_better_fit(monkeypatch):
    out, calls = _run(monkeypatch, {0: 3, 1: 9})
    assert calls == [0, 1]
    assert out["config"]["rung"] == 1
    assert len(out["match_result"]["pts_a"]) == 9


def test_cascade_keeps_rung0_when_rung1_is_no_better(monkeypatch):
    out, calls = _run(monkeypatch, {0: 4, 1: 2})
    assert calls == [0, 1]
    assert out["config"]["rung"] == 0 and out["config"]["rungs_tried"] == [0, 1]


def test_agreement_consistent_inconsistent_and_unverified():
    from src.pipeline import agreement_between
    good0, good1 = _result(12), _result(12)
    assert agreement_between({0: good0, 1: good1}, 0.25)["status"] == "consistent"

    shifted = _result(12)
    shifted.transform = np.array([[1, 0, 300.0], [0, 1, 0], [0, 0, 1]])
    out = agreement_between({0: good0, 1: shifted}, 0.25)
    assert out["status"] == "inconsistent" and out["gap_px"] == 300.0 and out["gap_m"] == 75.0

    # a degenerate (<5 unique locations) fit is never compared
    assert agreement_between({0: good0, 1: _result(3)}, 0.25)["status"] == "unverified"


def test_verify_runs_both_rungs_even_when_rung0_is_good(monkeypatch):
    out, calls = _run_verify(monkeypatch, {0: 12, 1: 12})
    assert calls == [0, 1]
    assert out["config"]["agreement"]["status"] == "consistent"


def _run_verify(monkeypatch, per_rung):
    calls = []

    def fake(a, b, matcher="sift", rung=0):
        calls.append(rung)
        return _result(per_rung[rung])

    monkeypatch.setattr(pipeline, "run_match", fake)
    return pipeline.run_pipeline(_product("a"), _product("b"), cascade=True, verify=True,
                                 use_lcn=False), calls


def test_offset_prior_drops_candidates_far_from_the_metadata_position():
    from src.match import match_tiled
    from tests.test_match import _synthetic_crater_field
    from tests.make_synthetic import make_synthetic_pair
    img = _synthetic_crater_field(size=512, seed=3)
    warped, _ = make_synthetic_pair(img, seed=5, rotation_deg=0.0, scale_range=(1.0, 1.0),
                                    translation_frac=0.10)  # true shift ~50 px
    free = match_tiled(img, warped, matcher="sift", tile_size=256, overlap=32)
    tight = match_tiled(img, warped, matcher="sift", tile_size=256, overlap=32, max_offset_px=5)
    assert len(free.pts_a) > 0
    assert len(tight.pts_a) < len(free.pts_a)
    if len(tight.pts_a):
        assert np.linalg.norm(tight.pts_b - tight.pts_a, axis=1).max() <= 5


def test_similarity_model_recovers_a_known_shift():
    import cv2
    from src.match import match_tiled
    from tests.test_match import _synthetic_crater_field
    img = _synthetic_crater_field(size=512, seed=3)
    dx, dy = 20.0, -15.0
    warped = cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (512, 512))

    sim = match_tiled(img, warped, matcher="sift", tile_size=256, overlap=32, model="similarity")

    assert sim.inlier_mask.sum() >= 4
    assert sim.transform[2].tolist() == [0.0, 0.0, 1.0]
    pts = np.array([[100.0, 100.0, 1.0], [400.0, 300.0, 1.0]]).T
    got = sim.transform @ pts
    assert np.abs(got[:2] - (pts[:2] + np.array([[dx], [dy]]))).max() < 1.0
