import React, { useState, useEffect } from 'react';
import { CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

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

export default function Screen01SelectPair({ onRunMatch }) {
  const [selectedRung, setSelectedRung] = useState(1);

  const safeFormat = (val, decimals) => {
    if (val === null || val === undefined || val === '') return 'N/A';
    const num = Number(val);
    if (Number.isNaN(num)) return 'N/A';
    return num.toFixed(decimals);
  };

  const [products, setProducts] = useState([]);
  const [isLoadingProducts, setIsLoadingProducts] = useState(true);
  const [productError, setProductError] = useState(null);

  const [selectedA, setSelectedA] = useState(null);
  const [selectedB, setSelectedB] = useState(null);

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

  const handleRunMatchClick = () => {
    if (!selectedA || !selectedB || selectedA.product_id === selectedB.product_id) return;
    onRunMatch(selectedA, selectedB, selectedRung);
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
        {isSelected && <CheckCircle2 className={`w-4 h-4 ${accent === 'cyan' ? 'text-cyan-500' : 'text-blue-500'}`} />}
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
          Select two available images to register. Both CH2 and LRO are supported.
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
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="glass-panel p-5 relative space-y-4 flex flex-col h-[420px]">
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-1 rounded bg-cyan-950/40 border border-cyan-700 text-cyan-400 text-xs font-mono font-semibold">
                MOVING SOURCE
              </span>
              <span className="text-xs font-mono text-slate-600">(IMAGE A)</span>
            </div>
            <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
              {products.map(p => renderProductCard(p, selectedA?.product_id === p.product_id, () => setSelectedA(p), 'cyan'))}
            </div>
          </div>

          <div className="glass-panel p-5 relative space-y-4 flex flex-col h-[420px]">
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-1 rounded bg-blue-950/40 border border-blue-700 text-blue-400 text-xs font-mono font-semibold">
                FIXED REFERENCE
              </span>
              <span className="text-xs font-mono text-slate-600">(IMAGE B)</span>
            </div>
            <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
              {products.map(p => renderProductCard(p, selectedB?.product_id === p.product_id, () => setSelectedB(p), 'blue'))}
            </div>
          </div>
        </div>
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
            disabled={!selectedA || !selectedB || selectedA.product_id === selectedB.product_id}
            className={`flex items-center space-x-3 px-8 py-3 rounded-md text-sm font-semibold transition ${
              !selectedA || !selectedB || selectedA.product_id === selectedB.product_id
                ? 'bg-slate-800 text-slate-600 border border-slate-700 cursor-not-allowed'
                : 'glow-btn-cyan'
            }`}
          >
            <span>Run match</span>
          </button>

          {selectedA && selectedB && selectedA.product_id === selectedB.product_id && (
            <div className="text-red-400 text-xs mt-2 font-mono">Cannot match a product with itself.</div>
          )}
        </div>
      </div>
    </div>
  );
}
