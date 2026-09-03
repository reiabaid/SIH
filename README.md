# SIH26166 — Lunar image correspondence

Multi-modal, sun-angle and scale-invariant image registration for Chandrayaan-2
optical imagery (OHRC, TMC-2, IIRS) against an LRO reference.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate       # on Windows
pip install -r requirements.txt
```

`lightglue` pulls from GitHub and needs `torch` — if you only need the SIFT
baseline, comment that line out of `requirements.txt` before installing.

## Repo layout

- `src/types.py` — frozen `Product` / `MatchResult` dataclasses. Every module
  reads and returns these; do not change the shape without telling the team.
- `src/prep.py` — grayscale conversion, illumination-robust local contrast
  normalisation, tiling/untiling for large rasters.
- `src/match.py` — `match(a, b, matcher)`, `"sift"` or `"lightglue"`. Grid-balanced
  keypoint selection (8x8) and sub-pixel refinement (quadratic peak fit) are
  applied in both paths.
- `src/pipeline.py` — wires prep → match into one callable run. `geo.py`
  (alignment) and `metrics.py` (evaluation) plug in as they land.
- `src/io_ch2.py`, `src/io_lro.py` — Chandrayaan-2 / LRO readers (owned by
  Mehak / Manya).
- `src/geo.py`, `src/metrics.py` — footprint overlap, resampling, RMSE/inlier/
  coverage metrics (owned by Riddhi).
- `tests/make_synthetic.py` — warps an image by a known seeded homography
  (optionally with a simulated illumination ramp), so matching can be
  validated against ground truth without real lunar data.

## Running the tests

```bash
python -m pytest tests/ -v
```

`test_match.py` asserts recovered-vs-true RMSE stays under 1 pixel on a
synthetic pair — if this fails, the bug is in the matcher, not the data.
