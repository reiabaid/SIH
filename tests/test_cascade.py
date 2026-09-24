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
