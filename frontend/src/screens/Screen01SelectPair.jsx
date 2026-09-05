import React, { useState, useEffect, useMemo } from 'react';
import { CheckCircle2, AlertCircle, Loader2, Zap } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

// Matches src/match.py's real rung system + the lightglue matcher branch in
// src/api.py's process_job_sync (rung == 2 -> matcher="lightglue"). No
// confidence thresholds or per-rung tuning exist in the backend, so none are
// shown here.
const RUNGS = [
  { id: 0, name: 'Rung 0 · SIFT', desc: 'Raw-intensity SIFT baseline. Expected to collapse once sun-azimuth difference grows.' },
  { id: 1, name: 'Rung 1 · Mod-π', desc: 'Gradient-orientation-mod-π descriptor. Illumination-robust near a full (~180°) sun reversal.' },
  { id: 2, name: 'LightGlue', desc: 'Learned matcher (SuperPoint + LightGlue). Strongest measured result across sun-angle differences.' },
];

// The only 4 pairs worth trying right now, recomputed directly against the
// real inventory this session (geo.footprint_overlap, real SPICE geometry --
// see PROJECT_STATUS.md). No LRO x LRO pair overlaps at all, which is why
// the picker below only ever offers CH2 on one side and LRO on the other.
const KNOWN_PAIRS = [
  {
    ch2Match: 'd_img_d32', lroId: 'M1499112398LE',
    label: 'd32 × M1499112398LE', overlapPct: '26.5%',
    note: 'Real overlap, but flagged trivial_fit=True (align_pair drift on a long strip) -- see Slide 8.',
  },
  {
    ch2Match: 'd_img_d18', lroId: 'M1519299970LE',
    label: 'd18 × M1519299970LE', overlapPct: '17.5%',
    note: 'Real overlap, not yet tried through the fixed pipeline.',
  },
  {
    ch2Match: 'd_img_d32', lroId: 'M1519292928LE',
    label: 'd32 × M1519292928LE', overlapPct: '0.2%',
    note: 'Real but very small overlap -- likely too little correspondence to register.',
  },
  {
    ch2Match: 'd_img_d32', lroId: 'M1164584053LE',
    label: 'd32 × M1164584053LE', overlapPct: '0%',
    note: 'Confirmed no overlap -- registration will correctly fail. Demonstrates the failure path.',
  },
];

export default function Screen01SelectPair({ onRunMatch }) {
  // Default to rung 0 (SIFT): measured this session as the fastest matcher on
  // real full-resolution imagery (~13-50s tiled) -- mod-pi's per-keypoint
  // Python descriptor loop runs ~130-180s, LightGlue ~190s on the same pair.
  // Not a quality claim, purely a demo-speed default; still user-changeable.
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

  // Split by source agency -- CH2 (ISRO) always on the left, LRO (NASA)
  // always on the right. Confirmed this session that no two LRO products
  // overlap at all, so letting the picker offer LRO x LRO was letting users
  // build a pair that can never register -- this structurally prevents that.
  // The synthetic pair is neither instrument, so it's excluded from both
  // columns and only reachable via the dedicated fast-demo button below.
  const isSynthetic = (id) => (id || '').startsWith('synthetic_');
  const ch2Products = useMemo(() => products.filter(p => !isSynthetic(p.product_id) && (p.product_id || '').toLowerCase().includes('ch2')), [products]);
  const lroProducts = useMemo(() => products.filter(p => !isSynthetic(p.product_id) && !(p.product_id || '').toLowerCase().includes('ch2')), [products]);

  const applyKnownPair = (pair) => {
    const ch2 = ch2Products.find(p => p.product_id.includes(pair.ch2Match));
    const lro = lroProducts.find(p => p.product_id === pair.lroId);
    if (ch2) setSelectedCh2(ch2);
    if (lro) setSelectedLro(lro);
  };

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
          {product.product_id}
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
          One ISRO Chandrayaan-2 product, one NASA LRO product -- no LRO x LRO pair in the inventory overlaps at all.
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

          {/* Known overlapping pairs -- recomputed against the real inventory
              this session, see KNOWN_PAIRS comment above. */}
          <div className="space-y-2">
            <div className="text-xs font-mono text-slate-500 uppercase tracking-wide">
              KNOWN REAL PAIRS (RECOMPUTED FROM REAL FOOTPRINT OVERLAP -- SLOW, FULL RESOLUTION)
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              {KNOWN_PAIRS.map((pair) => {
                const isFailing = pair.overlapPct === '0%';
                return (
                  <button
                    key={pair.label}
                    onClick={() => applyKnownPair(pair)}
                    className={`text-left p-3 rounded-md border transition ${
                      isFailing
                        ? 'bg-[#141414] border-red-900/60 hover:border-red-700'
                        : 'bg-[#141414] border-[#2a2a2a] hover:border-cyan-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-semibold text-slate-200">{pair.label}</span>
                      <Zap className={`w-3.5 h-3.5 shrink-0 ${isFailing ? 'text-red-500' : 'text-cyan-500'}`} />
                    </div>
                    <div className={`text-[10px] font-mono mt-1 ${isFailing ? 'text-red-400' : 'text-emerald-500'}`}>
                      overlap: {pair.overlapPct}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1 leading-snug">{pair.note}</div>
                  </button>
                );
              })}
            </div>
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
            <div className="text-slate-500 text-xs mt-2 font-mono">
              {selectedCh2.product_id.slice(-8)} × {selectedLro.product_id}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
