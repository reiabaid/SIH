# Day 3 research brief — Reia: matching & detection literature

**Central question:** which illumination/multi-modal-invariant feature matching
methods — classical and learned — have actually been validated on real
planetary imagery (not just terrestrial/synthetic benchmarks), and what's the
largest illumination/sun-angle difference any published method has handled
successfully? This is meant to settle whether rung 1 (LunarMatch's
mod-pi gradient descriptor) is fixable, or whether LightGlue really is the
field's best illumination-robust answer right now.

## Classical / hand-crafted descriptors surveyed

- **RIFT** — Li, J. et al., *"RIFT: Multi-modal Image Matching Based on
  Radiation-Variation Insensitive Feature Transform,"* IEEE Transactions on
  Image Processing, 2019/2020 ([arXiv:1804.09493](https://arxiv.org/abs/1804.09493)).
  Detects keypoints on a phase-congruency map instead of intensity/gradient,
  and describes them with a Maximum Index Map (MIM) built from log-Gabor
  convolution responses. Validated on 6 multimodal *terrestrial* dataset types
  (optical-optical, IR-optical, SAR-optical, depth-optical, map-optical,
  day-night) — no planetary imagery in the original paper.

- **PSO-SIFT** — Ma, W. et al., *"Remote Sensing Image Registration With
  Modified SIFT and Enhanced Feature Matching,"* IEEE GRSL, 2016. Redefines
  the SIFT gradient using a Position-Scale-Orientation formulation to reduce
  sensitivity to nonlinear radiometric distortion (NRD) between optical/SAR
  pairs. Handles brightness/rotation well but stays sensitive to contrast and
  SNR differences — terrestrial/aerial validation only.

- **LGHD** — Aguilera, C.A. et al., *"LGHD: A Feature Descriptor for Matching
  Across Non-Linear Intensity Variations,"* IEEE ICIP 2015
  ([code](https://github.com/ngunsu/LGHD)). Combines multi-scale/multi-orientation
  log-Gabor filter responses into per-subregion histograms — frequency-domain
  information is inherently more NRD-invariant than SIFT's spatial gradient.
  Weak on scale/rotation invariance and discards phase, hurting precision.
  Validated on visual/infrared and multispectral pairs, not planetary data.

- **HAPCG** — Yao, Y. et al. (a.k.a. Fan et al. in some citations),
  *"Heterologous Images Matching Considering Anisotropic Weighted Moment and
  Absolute Phase Orientation,"* Geomatics and Information Science of Wuhan
  University, 2021 ([DOI](https://ch.whu.edu.cn/en/article/doi/10.13203/j.whugis20200702)).
  Combines anisotropic weighted moments with a histogram of absolute
  phase-consistency gradients. Reported to beat SIFT, PSO-SIFT, and LGHD on
  heterologous remote-sensing benchmarks by >2x match count — still
  terrestrial/aerial multimodal data, no lunar or planetary validation found.

**Pattern across all four classical methods:** every one of them substitutes
phase-congruency or log-Gabor frequency response for raw intensity/gradient —
which is exactly the same idea behind LunarMatch's rung 1 mod-pi descriptor.
None of the papers above report testing on actual orbital planetary imagery;
their "illumination invariance" claims are benchmarked on Earth-based
multimodal pairs (optical/IR/SAR), which is a materially easier problem than
same-sensor, same-band lunar images shot under wildly different solar
incidence angles. **This is the literature's blind spot that rung 1's 0/8
failure on real CH2×LRO pairs (see Day 2 table) is exposing.**

## Learned matchers surveyed

- **SuperGlue** — Sarlin, P.-E. et al., *"SuperGlue: Learning Feature Matching
  with Graph Neural Networks,"* CVPR 2020 (Oral)
  ([paper](https://openaccess.thecvf.com/content_CVPR_2020/papers/Sarlin_SuperGlue_Learning_Feature_Matching_With_Graph_Neural_Networks_CVPR_2020_paper.pdf),
  [code](https://github.com/magicleap/SuperGluePretrainedNetwork)). Solves
  correspondence as a differentiable optimal-transport problem over a GNN's
  attention-based context aggregation. State of the art on terrestrial
  pose-estimation benchmarks at publication.

- **LightGlue** — Lindenberger, P. et al., *"LightGlue: Local Feature Matching
  at Light Speed,"* ICCV 2023 ([arXiv:2306.13643](https://arxiv.org/abs/2306.13643)).
  Same GNN-attention idea as SuperGlue but adaptively prunes computation per
  image-pair difficulty; matches SuperGlue's accuracy at a fraction of the
  training cost (2 GPU-days vs 7+ days) and inference time. This is the
  matcher LunarMatch already runs as its third rung.

- **LoFTR** — Sun, J. et al., *"LoFTR: Detector-Free Local Feature Matching
  with Transformers,"* CVPR 2021. Skips explicit keypoint detection entirely,
  matching dense transformer features directly — better than
  detect-then-describe pipelines on low-texture regions, which matters for
  regolith. Cited in at least one 2024 remote-sensing paper combining RIFT
  keypoints with LoFTR descriptors for cross-sensor matching, but I found no
  planetary/lunar-specific validation of stock LoFTR.

- **DISK** — Tyszkiewicz, M. et al., *"DISK: Learning local features with
  policy gradient,"* NeurIPS 2020. A learned detect-and-describe network
  trained via reinforcement learning; shows up paired with LightGlue (below)
  as an alternative front-end to SuperPoint.

## Real planetary-imagery validation — the papers that actually answer the question

- **Comparative Evaluation of Traditional and Deep Learning Feature Matching
  Algorithms using Chandrayaan-2 Lunar Data**, arXiv:2509.04775 (2026)
  ([link](https://arxiv.org/abs/2509.04775)). **This is the closest thing to a
  direct precedent for LunarMatch itself** — it benchmarks SIFT, ASIFT,
  AKAZE, RIFT2 (the rotation-invariant successor to RIFT), and SuperGlue on
  real cross-modality Chandrayaan-2 image pairs from both equatorial and
  polar regions. Findings: SuperGlue had the lowest error and fastest runtime
  overall; SIFT/AKAZE were strong in equatorial lighting but **degraded under
  polar lighting conditions** — the same equatorial-vs-polar split we should
  expect to matter for CH2×LRO pairs at different latitudes. Their
  preprocessing pipeline (georeferencing, intensity normalization, CLAHE,
  shadow correction) is worth comparing against LunarMatch's own LCN
  (`use_lcn`) step — CLAHE specifically is called out as "particularly
  effective" for extreme lunar illumination variation, which we don't
  currently apply.

- **Robust Feature Matching of Multi-Illumination Lunar Orbiter Images Based
  on Crater Neighborhood Structure**, Remote Sensing 17(13):2302, 2025
  ([DOI](https://doi.org/10.3390/rs17132302)). Answers the "largest
  illumination difference handled" question directly and quantitatively: a
  crater-detection + crater-neighborhood-structure matching method achieved
  **100% success at up to 78° incidence-angle difference and 180° solar
  azimuth difference** in equatorial/mid-latitude regions, and **72.3% success
  in polar regions** with extensive shadowing and very low sun elevation. This
  is a full order of magnitude beyond what feature-point descriptors
  (RIFT/HAPCG/PSO-SIFT/LGHD) claim, because it matches on a *semantic*
  structure (crater rims + their spatial arrangement) rather than raw
  texture/gradient — this is the strongest evidence in this brief that
  illumination robustness on the Moon specifically comes from using
  higher-level geometric structure, not a better low-level descriptor.

- **Dense Feature Matching for Hazard Detection and Avoidance Using Machine
  Learning in Complex Unstructured Scenarios**, MDPI Aerospace 11(5):351,
  2024 ([link](https://www.mdpi.com/2226-4310/11/5/351)). Tests
  SuperPoint+LightGlue and DISK+LightGlue on lunar light-plains imagery
  running on real edge hardware (NVIDIA Jetson TX2), explicitly to
  demonstrate robustness under varying light conditions during a landing
  hazard-avoidance descent. Confirms textureless regolith and pitch-black
  shadow contrast (no atmosphere) break traditional detectors in exactly the
  way rung 0/rung 1 need to survive, and that the learned-matcher pipeline
  handles it acceptably on flight-relevant compute, not just a research GPU.

## So what does this mean for LunarMatch

1. **Rung 1's 0/8 total failure (Day 2 finding) is not surprising given the
   literature — it may be expected, not a bug.** Every classical
   illumination-invariant descriptor surveyed (RIFT, HAPCG, LGHD, PSO-SIFT)
   was only ever validated on Earth-based multimodal pairs. None of them were
   shown to survive same-sensor lunar imagery at the sun-angle differences our
   CH2×LRO pairs actually have. That said, "the literature doesn't validate
   this" and "our implementation has a regression" are different claims —
   worth still checking rung 1 against a pair with a *small* illumination
   difference (if the inventory has one) before fully writing it off, since a
   real fix should at least work in the easy case.

2. **The strongest planetary-validated result (crater-neighborhood matching,
   100%/72.3% success at up to 78° incidence difference) doesn't use
   descriptor-level illumination invariance at all — it matches semantic
   structure (craters).** This is a concrete, cheap idea for a future rung:
   detect craters (there's already a "deep-learning-based crater detection"
   step in that pipeline) and match on their relative geometry, rather than
   trying to make SIFT/log-Gabor descriptors more invariant. This is
   arguably a bigger opportunity than fixing rung 1 as currently scoped.

3. **The direct Chandrayaan-2 precedent (arXiv:2509.04775) validates the
   plan's existing choice of SuperGlue/LightGlue as the illumination-robust
   path** — on real CH2 data, deep learned matchers beat every classical
   method they tested, with the gap widening specifically in low-sun/polar
   conditions. This supports treating LightGlue as the honest illumination-
   robust answer rather than continuing to invest in rung 1.

4. **One concrete, cheap thing worth trying regardless of the rung-1
   decision: CLAHE.** The Chandrayaan-2 comparative paper singles it out as
   the most effective preprocessing step for extreme lunar illumination
   variation. LunarMatch's `prep.py` currently does local contrast
   normalization (`use_lcn`) — worth checking whether that's doing something
   equivalent, or whether CLAHE is a cheap addition that could lift rung 0's
   result on the weaker pairs (d18×M1164584053LE, d18×M1499112398LE) from
   Day 2's table without touching the matcher itself.

## Recommendation for the Day 3 sync decision — UPDATED 2026-09-15, rung 1 was fixed

**This section originally recommended retiring rung 1.** That recommendation
is now stale and superseded — leaving it struck through rather than deleted,
per this week's own norm of writing down what changed and why rather than
quietly editing history.

~~Given the above, my recommendation on rung 1: document it honestly as not
fixed and de-scope it from the pitch, rather than sinking more Day 3.5/4
time into it — the literature gives no example of this class of descriptor
surviving planetary-scale illumination differences, and LunarMatch's own
Day 2 data (0/8) is consistent with that. Position LightGlue as the real
illumination-robust path...~~

What changed: the 0/8 result turned out to be a fixable implementation gap,
not a fundamental literature-backed limit. Rung 1's descriptor was built from
**raw Sobel gradient direction**, which only survives a *global* illumination
sign flip (exactly what the unit test constructs) — not the independent
per-sensor contrast/gain differences a real cross-sensor pair actually has.
Swapping it for a RIFT-style **Maximum Index Map** (which orientation channel
in a log-Gabor filter bank wins at each pixel — an ordinal, ranking-based
quantity, immune to the absolute-magnitude sensitivity that broke the raw
gradient version) took rung 1 from 0/8 to **5/8 well_determined**, beating
sift-rung0 outright on 3 of those pairs (see the updated
`docs/research/day2_pair_verification.md`). This is exactly the "which of
these have been validated on real planetary imagery" question above, now
answered empirically for LunarMatch's own descriptor rather than only for the
literature's: phase-congruency/log-Gabor-based representations survive real
cross-sensor lunar pairs where raw-gradient ones don't, matching what
RIFT/HAPCG's design choice (phase congruency over gradient) predicts.

Revised recommendation: **keep rung 1, positioned as the illumination-robust
matcher it was always meant to be**, with LightGlue kept alongside it rather
than as a replacement — no single matcher covers the full 8-pair inventory
alone (sift-rung0 6/8, rung 1 5/8, LightGlue 5/8; union = 8/8). The pitch is
"three complementary matchers reach full coverage," not "one matcher wins."
Crater-structure matching (finding #2 above) is still worth keeping in back
pocket as a longer-term direction, but it's no longer the *only* path forward
now that rung 1 has real, working, sometimes-best results on real data.

**Still open, not yet explained:** 3 pairs still get a hard 0 with rung 1
(d18×M1499112398LE, d18×M1529523925LE, d32×M1529537951LE) — a clean failure,
not a degradation. Worth the same true-match-vs-random-pair diagnostic that
found the original bug, run against one of these specifically, before
assuming it's just harder terrain.
