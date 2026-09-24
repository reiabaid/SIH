import React, { useState, useEffect, useMemo } from 'react';
import { CheckCircle2, AlertCircle, Loader2, Zap } from 'lucide-react';

const API_BASE = import.meta.env.PROD ? '' : 'http://127.0.0.1:8000';

// Matches src/match.py's real rung system + the lightglue matcher branch in
// src/api.py's process_job_sync (rung == 2 -> matcher="lightglue"). No
// confidence thresholds or per-rung tuning exist in the backend, so none are
// shown here.
const RUNGS = [
  { id: 0, name: 'Rung 0 · SIFT', desc: 'Raw-intensity SIFT baseline. Expected to collapse once sun-azimuth difference grows.' },
  { id: 1, name: 'Rung 1 · Log-Gabor MIM', desc: 'Log-Gabor Maximum Index Map (RIFT-style) descriptor: matches on which orientation channel dominates each pixel, so it tolerates independent sensor contrast differences.' },
  { id: 2, name: 'LightGlue', desc: 'Learned matcher (SuperPoint + LightGlue). Slowest option: minutes on full-size real pairs.' },
];

export default function Screen01SelectPair({ onRunMatch }) {
  // Default to rung 0 (SIFT): the faster matcher on real full-size pairs
  // (~25-45s end-to-end vs ~35s+ for rung 1; LightGlue takes minutes). Purely a
  // speed default -- rung 1 finds more matches on several pairs -- and
  // still user-changeable.
  const [selectedRung, setSelectedRung] = useState(0);

  const safeFormat = (val, decimals) => {
    if (val === null || val === undefined || val === '') return 'N/A';
    const num = Number(val);
    if (Number.isNaN(num)) return 'N/A';
    return num.toFixed(decimals);
  };

  const [products, setProducts] = useState([]);
  const [isLoadingProducts, setIsLoadingProducts] = useState(true);
  const [productError, setProductError] = useState(null);

  const [selectedCh2, setSelectedCh2] = useState(null);
  const [selectedLro, setSelectedLro] = useState(null);
  const [overlapPct, setOverlapPct] = useState(null);
  const [overlapLoading, setOverlapLoading] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/products`)
      .then(res => res.json())
      .then(data => {
        setProducts(data);
        setIsLoadingProducts(false);
      })
      .catch(err => {
        console.error("Failed to fetch products:", err);
        setProductError("Failed to connect to LunarMatch backend.");
        setIsLoadingProducts(false);
      });
  }, []);

  // Fetch overlap when both products are selected
  useEffect(() => {
    if (!selectedCh2 || !selectedLro) {
      setOverlapPct(null);
      return;
    }
    setOverlapLoading(true);
    fetch(`${API_BASE}/overlap`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_a: selectedCh2.product_id, product_b: selectedLro.product_id }),
    })
      .then(res => res.json())
      .then(data => {
        setOverlapPct(data.overlap_percent);
        setOverlapLoading(false);
      })
      .catch(() => {
        setOverlapPct(null);
        setOverlapLoading(false);
      });
  }, [selectedCh2, selectedLro]);

  // Split by source agency -- CH2 (ISRO) always on the left, LRO (NASA)
  // always on the right. Confirmed this session that no two LRO products
  // overlap at all, so letting the picker offer LRO x LRO was letting users
  // build a pair that can never register -- this structurally prevents that.
  // The synthetic pair is neither instrument, so it's excluded from both
  // columns and only reachable via the dedicated fast-demo button below.
  const isSynthetic = (id) => (id || '').startsWith('synthetic_');
  const ch2Products = useMemo(() => products.filter(p => !isSynthetic(p.product_id) && (p.product_id || '').toLowerCase().includes('ch2')), [products]);
  const lroProducts = useMemo(() => products.filter(p => !isSynthetic(p.product_id) && !(p.product_id || '').toLowerCase().includes('ch2')), [products]);

  // Suggested references: rank the other instrument's images by footprint
  // overlap with the chosen Chandrayaan-2 image (GET /candidates -- metadata
  // only, no pixels decoded). Replaces a hard-coded list of pair cards.
  const [candidates, setCandidates] = useState([]);
  const [candidatesLoading, setCandidatesLoading] = useState(false);
  const [candidatesNotIngested, setCandidatesNotIngested] = useState(0);
  const [candidatesError, setCandidatesError] = useState(null);

  useEffect(() => {
    const isRealCh2 = selectedCh2 && !(selectedCh2.product_id || '').startsWith('synthetic_');
    if (!isRealCh2) {
      setCandidates([]);
      setCandidatesNotIngested(0);
      setCandidatesError(null);
      return;
    }
    let cancelled = false;
    setCandidatesLoading(true);
    setCandidatesError(null);
    fetch(`${API_BASE}/candidates?product_id=${encodeURIComponent(selectedCh2.product_id)}`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        if (cancelled) return;
        setCandidates(data.candidates || []);
        setCandidatesNotIngested(data.not_ingested || 0);
        setCandidatesLoading(false);
      })
      .catch(err => {
        if (cancelled) return;
        setCandidates([]);
        setCandidatesError(`Could not load suggestions (${err.message}).`);
        setCandidatesLoading(false);
      });
    return () => { cancelled = true; };
  }, [selectedCh2]);

  // Pre-select the best-overlapping reference unless the user's current pick
  // is still a valid (overlapping) one.
  useEffect(() => {
    if (candidates.length === 0) return;
    const stillValid = selectedLro && candidates.some(c => c.product_id === selectedLro.product_id);
    if (stillValid) return;
    const best = lroProducts.find(p => p.product_id === candidates[0].product_id);
    if (best) setSelectedLro(best);
  }, [candidates]); // eslint-disable-line react-hooks/exhaustive-deps

  const applySyntheticDemo = () => {
    const a = products.find(p => p.product_id === 'synthetic_a');
    const b = products.find(p => p.product_id === 'synthetic_b');
    if (a) setSelectedCh2(a);
    if (b) setSelectedLro(b);
  };

  const handleRunMatchClick = () => {
    if (!selectedCh2 || !selectedLro) return;
    onRunMatch(selectedCh2, selectedLro, selectedRung);
  };

  const renderProductCard = (product, isSelected, onClick, accent) => (
    <div
      key={product.product_id}
      onClick={onClick}
      className={`p-3 rounded-md cursor-pointer transition-all border ${
        isSelected
          ? accent === 'cyan'
            ? 'bg-cyan-950/40 border-cyan-500'
            : 'bg-blue-950/40 border-blue-500'
          : 'bg-[#141414] border-[#2a2a2a] hover:bg-[#1c1c1c] hover:border-slate-600'
      }`}
    >
      <div className="flex justify-between items-start mb-2">
        <div className="font-mono text-sm font-medium text-slate-200 truncate w-4/5" title={product.product_id}>
          {product.product_id.startsWith('urn:isro:')
            ? product.product_id.split(':').slice(-1)[0].replace(/^ch2_ohr_/, '')
            : product.product_id}
        </div>
        {isSelected && <CheckCircle2 className={`w-4 h-4 shrink-0 ${accent === 'cyan' ? 'text-cyan-500' : 'text-blue-500'}`} />}
      </div>
      <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
        <div className="bg-[#0a0a0a] p-1.5 rounded border border-[#2a2a2a]">
          <span className="text-slate-600 block">GSD:</span>
          <span className={accent === 'cyan' ? 'text-cyan-400' : 'text-blue-400'}>
            {safeFormat(product.gsd_m, 2) !== 'N/A' ? `${safeFormat(product.gsd_m, 2)} m/px` : 'N/A'}
          </span>
        </div>
        <div className="bg-[#0a0a0a] p-1.5 rounded border border-[#2a2a2a]">
          <span className="text-slate-600 block">SUN AZ:</span>
          <span className={accent === 'cyan' ? 'text-amber-500' : 'text-slate-300'}>
            {safeFormat(product.subsolar_azimuth_deg, 1) !== 'N/A' ? `${safeFormat(product.subsolar_azimuth_deg, 1)}°` : 'N/A'}
          </span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      <div>
        <h2 className="text-2xl font-display font-bold text-slate-100">Select an image pair</h2>
        <p className="text-sm text-slate-500 font-mono mt-0.5">
          Pick a Chandrayaan-2 image; the catalog ranks the LRO reference images that overlap it, from footprint metadata alone.
        </p>
      </div>

      {isLoadingProducts ? (
        <div className="flex justify-center items-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
          <span className="ml-3 font-mono text-slate-400">Fetching inventory from backend...</span>
        </div>
      ) : productError ? (
        <div className="bg-red-950/40 border border-red-800 rounded-md p-6 flex flex-col items-center justify-center space-y-3">
          <AlertCircle className="w-8 h-8 text-red-500" />
          <p className="font-mono text-red-300">{productError}</p>
          <p className="text-xs text-slate-500">Ensure the FastAPI backend is running on http://127.0.0.1:8000</p>
        </div>
      ) : products.length === 0 ? (
        <div className="bg-[#141414] border border-[#2a2a2a] rounded-md p-6 flex flex-col items-center justify-center space-y-3">
          <AlertCircle className="w-8 h-8 text-slate-600" />
          <p className="font-mono text-slate-400">No products available.</p>
          <p className="text-xs text-slate-500">Start the API/backend and try again.</p>
        </div>
      ) : (
        <>
          {/* Fast synthetic demo -- same real pipeline (align, tile, match,
              sub-pixel refine, deliverable, control network), small 512x512
              synthetic images instead of the real multi-minute full-resolution
              rasters. Not a shortcut result: this is the exact pair
              scripts/make_synthetic_deliverable.py already validated as
              trustworthy (473 inliers, 0.92px residual, trivial_fit=False). */}
          <button
            onClick={applySyntheticDemo}
            className="w-full flex items-center justify-between p-4 rounded-md border border-emerald-800 bg-emerald-950/20 hover:border-emerald-600 transition text-left"
          >
            <div>
              <div className="flex items-center space-x-2">
                <Zap className="w-4 h-4 text-emerald-500" />
                <span className="font-mono text-sm font-semibold text-emerald-400">Fast synthetic demo</span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Same real pipeline, small synthetic images -- completes in under a second instead of minutes.
                Previously verified: 473 inliers, 0.92px residual, trustworthy fit.
              </p>
            </div>
            <span className="text-[10px] font-mono text-emerald-500 shrink-0 ml-4">SELECT →</span>
          </button>

          {/* Suggested references for the chosen Chandrayaan-2 image, ranked by
              real footprint overlap from the backend catalog. */}
          <div className="space-y-2">
            <div className="text-xs font-mono text-slate-500 uppercase tracking-wide">
              SUGGESTED REFERENCE IMAGES{selectedCh2 && !isSynthetic(selectedCh2.product_id)
                ? ` FOR ${selectedCh2.product_id.split('_').slice(-1)[0].toUpperCase()}` : ''}
            </div>
            {!selectedCh2 || isSynthetic(selectedCh2.product_id) ? (
              <div className="text-xs font-mono text-slate-600 border border-dashed border-[#2a2a2a] rounded-md p-4">
                Select a Chandrayaan-2 image below and the catalog will list the LRO images whose footprints overlap it.
              </div>
            ) : candidatesLoading ? (
              <div className="flex items-center text-xs font-mono text-slate-500 p-4">
                <Loader2 className="w-4 h-4 animate-spin text-cyan-500 mr-2" /> Ranking overlapping references...
              </div>
            ) : candidatesError ? (
              <div className="text-xs font-mono text-red-400 border border-red-900/60 rounded-md p-4">{candidatesError}</div>
            ) : candidates.length === 0 ? (
              <div className="text-xs font-mono text-amber-400 border border-amber-900/60 rounded-md p-4">
                No catalogued LRO image overlaps this footprint.
                {candidatesNotIngested > 0 && ` ${candidatesNotIngested} image(s) have no footprint recorded yet (run scripts/ingest_catalog).`}
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {candidates.map((c, idx) => {
                    const isPicked = selectedLro?.product_id === c.product_id;
                    return (
                      <button
                        key={c.product_id}
                        onClick={() => {
                          const p = lroProducts.find(x => x.product_id === c.product_id);
                          if (p) setSelectedLro(p);
                        }}
                        className={`text-left p-3 rounded-md border transition ${
                          isPicked ? 'bg-blue-950/40 border-blue-500' : 'bg-[#141414] border-[#2a2a2a] hover:border-blue-700'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-xs font-semibold text-slate-200">{c.product_id}</span>
                          {idx === 0 && <span className="text-[9px] font-mono text-emerald-400 border border-emerald-800 rounded px-1">BEST</span>}
                        </div>
                        <div className="text-[10px] font-mono mt-1 text-emerald-500">
                          covers {c.overlap_percent}% of the CH2 image
                        </div>
                        <div className="text-[10px] font-mono text-slate-500">
                          {c.candidate_covered_percent}% of this reference lies inside it
                        </div>
                        <div className="text-[10px] font-mono text-slate-600 mt-1">
                          {c.acquired_utc ? String(c.acquired_utc).slice(0, 10) : 'date n/a'}
                          {' · '}sun incidence {safeFormat(c.incidence_deg, 1) !== 'N/A' ? `${safeFormat(c.incidence_deg, 1)}°` : 'n/a'}
                        </div>
                      </button>
                    );
                  })}
                </div>
                {candidatesNotIngested > 0 && (
                  <div className="text-[10px] font-mono text-slate-600">
                    {candidatesNotIngested} catalogued image(s) have no footprint recorded yet and are not ranked (run scripts/ingest_catalog).
                  </div>
                )}
              </>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="glass-panel p-5 relative space-y-4 flex flex-col h-[360px]">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-1 rounded bg-cyan-950/40 border border-cyan-700 text-cyan-400 text-xs font-mono font-semibold">
                  ISRO · CHANDRAYAAN-2
                </span>
                <span className="text-xs font-mono text-slate-600">OHRC</span>
              </div>
              <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
                {ch2Products.length === 0 ? (
                  <p className="text-xs font-mono text-slate-500 py-4 text-center">No CH2 products in inventory.</p>
                ) : (
                  ch2Products.map(p => renderProductCard(p, selectedCh2?.product_id === p.product_id, () => setSelectedCh2(p), 'cyan'))
                )}
              </div>
            </div>

            <div className="glass-panel p-5 relative space-y-4 flex flex-col h-[360px]">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-1 rounded bg-blue-950/40 border border-blue-700 text-blue-400 text-xs font-mono font-semibold">
                  NASA · LRO
                </span>
                <span className="text-xs font-mono text-slate-600">NAC</span>
              </div>
              <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
                {lroProducts.length === 0 ? (
                  <p className="text-xs font-mono text-slate-500 py-4 text-center">No LRO products in inventory.</p>
                ) : (
                  lroProducts.map(p => renderProductCard(p, selectedLro?.product_id === p.product_id, () => setSelectedLro(p), 'blue'))
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Matcher selector -- real rungs only, no fabricated tuning controls */}
      <div className="space-y-3">
        <div className="text-xs font-mono text-slate-500 uppercase tracking-wide">
          SELECT MATCHER
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {RUNGS.map((r) => {
            const isSelected = selectedRung === r.id;
            return (
              <div
                key={r.id}
                onClick={() => setSelectedRung(r.id)}
                className={`p-4 rounded-md cursor-pointer transition-all duration-150 border flex flex-col justify-between space-y-3 ${
                  isSelected
                    ? 'bg-cyan-950/40 border-cyan-500'
                    : 'bg-[#141414] border-[#2a2a2a] hover:bg-[#1c1c1c] hover:border-slate-600'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-mono font-semibold ${isSelected ? 'text-cyan-400' : 'text-slate-300'}`}>
                    {r.name}
                  </span>
                  {isSelected && <CheckCircle2 className="w-4 h-4 text-cyan-500" />}
                </div>
                <p className="text-xs text-slate-500">{r.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Run match -- hands the selection to Screen02, which performs the
          real registration + polling. Nothing is submitted here. */}
      <div className="glass-panel p-5 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <button
            onClick={handleRunMatchClick}
            disabled={!selectedCh2 || !selectedLro}
            className={`flex items-center space-x-3 px-8 py-3 rounded-md text-sm font-semibold transition ${
              !selectedCh2 || !selectedLro
                ? 'bg-slate-800 text-slate-600 border border-slate-700 cursor-not-allowed'
                : 'glow-btn-cyan'
            }`}
          >
            <span>Run match</span>
          </button>

          {selectedCh2 && selectedLro && (
            <div className="flex items-center gap-4 text-xs font-mono mt-2">
              <span className="text-slate-500">
                {selectedCh2.product_id.slice(-8)} × {selectedLro.product_id}
              </span>
              {overlapLoading ? (
                <span className="text-slate-600">computing overlap...</span>
              ) : overlapPct !== null ? (
                <span className={`font-semibold ${overlapPct > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {overlapPct}% overlap
                </span>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
