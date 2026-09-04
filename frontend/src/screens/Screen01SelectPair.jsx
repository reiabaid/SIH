import React, { useState, useEffect } from 'react';
import { ArrowRight, Layers, Sliders, CheckCircle2, Zap, AlertCircle, Loader2 } from 'lucide-react';
import { MOCK_DATASET } from '../data/mockLunarData';

export default function Screen01SelectPair({ onRunMatch }) {
  const [selectedRung, setSelectedRung] = useState('rung1');
  const [isProcessing, setIsProcessing] = useState(false);
  const [processStep, setProcessStep] = useState(0);
  
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
    fetch('http://127.0.0.1:8000/products')
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
    
    setIsProcessing(true);
    setProcessStep(1); // Step 1: Spatial Overlap

    setTimeout(() => {
      setProcessStep(2); // Step 2: Illumination & Edge Extraction
    }, 900);

    setTimeout(() => {
      setProcessStep(3); // Step 3: Sub-pixel RANSAC Alignment
    }, 1800);

    setTimeout(() => {
      setIsProcessing(false);
      onRunMatch(selectedA, selectedB, selectedRung);
    }, 2700);
  };

  const renderProductCard = (product, isSelected, onClick, type) => (
    <div 
      key={product.product_id}
      onClick={onClick}
      className={`p-3 rounded-lg cursor-pointer transition-all border ${
        isSelected 
          ? type === 'CH2' 
            ? 'bg-cyan-950/40 border-cyan-400 shadow-lg shadow-cyan-950/40' 
            : 'bg-blue-950/40 border-blue-400 shadow-lg shadow-blue-950/40'
          : 'bg-[#0f1520] border-[#1b273a] hover:bg-[#162030] hover:border-slate-600'
      }`}
    >
      <div className="flex justify-between items-start mb-2">
        <div className="font-mono text-sm font-bold text-slate-200 truncate w-4/5" title={product.product_id}>
          {product.product_id}
        </div>
        {isSelected && <CheckCircle2 className={`w-4 h-4 ${type === 'CH2' ? 'text-cyan-400' : 'text-blue-400'}`} />}
      </div>
      <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
        <div className="bg-[#101724] p-1.5 rounded border border-[#1b283d]">
          <span className="text-slate-500 block">GSD:</span>
          <span className={type === 'CH2' ? 'text-cyan-300' : 'text-blue-300'}>
            {safeFormat(product.gsd_m, 2) !== 'N/A' ? `${safeFormat(product.gsd_m, 2)} m/px` : 'N/A'}
          </span>
        </div>
        <div className="bg-[#101724] p-1.5 rounded border border-[#1b283d]">
          <span className="text-slate-500 block">SUN AZ:</span>
          <span className={type === 'CH2' ? 'text-amber-400' : 'text-slate-200'}>
            {safeFormat(product.subsolar_azimuth_deg, 1) !== 'N/A' ? `${safeFormat(product.subsolar_azimuth_deg, 1)}°` : 'N/A'}
          </span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Top Header */}
      <div>
        <h2 className="text-2xl font-display font-bold text-white">Select an image pair</h2>
        <p className="text-sm text-slate-400 font-mono mt-0.5">
          Select two available images to register. Both CH2 and LRO are supported.
        </p>
      </div>

      {isLoadingProducts ? (
        <div className="flex justify-center items-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
          <span className="ml-3 font-mono text-slate-300">Fetching inventory from backend...</span>
        </div>
      ) : productError ? (
        <div className="bg-red-950/40 border border-red-500/50 rounded-lg p-6 flex flex-col items-center justify-center space-y-3">
          <AlertCircle className="w-8 h-8 text-red-400" />
          <p className="font-mono text-red-200">{productError}</p>
          <p className="text-xs text-slate-400">Ensure the FastAPI backend is running on http://127.0.0.1:8000</p>
        </div>
      ) : products.length === 0 ? (
        <div className="bg-slate-900/40 border border-slate-700/50 rounded-lg p-6 flex flex-col items-center justify-center space-y-3">
          <AlertCircle className="w-8 h-8 text-slate-400" />
          <p className="font-mono text-slate-300">No products available.</p>
          <p className="text-xs text-slate-400">Start the API/backend and try again.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          
          {/* Left Card: Moving Source Image */}
          <div className="glass-panel p-5 rounded-xl border border-cyan-900/40 relative space-y-4 flex flex-col h-[500px]">
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-1 rounded bg-cyan-950/80 border border-cyan-700/60 text-cyan-300 text-xs font-mono font-semibold">
                ★ MOVING SOURCE
              </span>
              <span className="text-xs font-mono text-slate-400">(IMAGE A)</span>
            </div>

            {/* Selection List */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
              {products.map(p => renderProductCard(p, selectedA?.product_id === p.product_id, () => setSelectedA(p), 'CH2'))}
            </div>

            {/* Selected Visual Placeholder */}
            {selectedA && (
              <div className="relative h-28 bg-[#090d14] rounded-lg border border-[#1b273a] overflow-hidden flex items-center justify-center shrink-0">
                <svg viewBox="0 0 200 200" className="w-full h-full opacity-60">
                  <rect width="200" height="200" fill="#0c121c"/>
                  <circle cx="80" cy="90" r="45" fill="#151f2e" stroke="#253750" strokeWidth="2"/>
                  <circle cx="80" cy="90" r="30" fill="#0d1420" stroke="#1d2d42" strokeWidth="1.5"/>
                  <circle cx="75" cy="85" r="12" fill="#070a10"/>
                  <line x1="30" y1="30" x2="60" y2="60" stroke="#00f2fe" strokeWidth="2" strokeDasharray="3,3"/>
                  <polygon points="60,60 52,54 54,62" fill="#00f2fe"/>
                </svg>
                <div className="absolute inset-0 bg-gradient-to-t from-[#090d14] to-transparent pointer-events-none" />
                <div className="absolute bottom-2 left-2 right-2 text-center text-[10px] font-mono text-cyan-300">
                  {selectedA.product_id}
                </div>
              </div>
            )}
          </div>

          {/* Right Card: Fixed Reference Image */}
          <div className="glass-panel p-5 rounded-xl border border-blue-900/40 relative space-y-4 flex flex-col h-[500px]">
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-1 rounded bg-blue-950/80 border border-blue-700/60 text-blue-300 text-xs font-mono font-semibold">
                ⚓ FIXED REFERENCE
              </span>
              <span className="text-xs font-mono text-slate-400">(IMAGE B)</span>
            </div>

            {/* Selection List */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
              {products.map(p => renderProductCard(p, selectedB?.product_id === p.product_id, () => setSelectedB(p), 'LRO'))}
            </div>

            {/* Selected Visual Placeholder */}
            {selectedB && (
              <div className="relative h-28 bg-[#090d14] rounded-lg border border-[#1b273a] overflow-hidden flex items-center justify-center shrink-0">
                <svg viewBox="0 0 200 200" className="w-full h-full opacity-60">
                  <rect width="200" height="200" fill="#0c121c"/>
                  <circle cx="85" cy="88" r="44" fill="#172233" stroke="#283d5a" strokeWidth="2"/>
                  <circle cx="85" cy="88" r="29" fill="#0e1624" stroke="#1f3149" strokeWidth="1.5"/>
                  <circle cx="90" cy="92" r="11" fill="#080c14"/>
                  <line x1="170" y1="30" x2="135" y2="65" stroke="#ffb703" strokeWidth="2" strokeDasharray="3,3"/>
                  <polygon points="135,65 143,62 138,54" fill="#ffb703"/>
                </svg>
                <div className="absolute inset-0 bg-gradient-to-t from-[#090d14] to-transparent pointer-events-none" />
                <div className="absolute bottom-2 left-2 right-2 text-center text-[10px] font-mono text-blue-300">
                  {selectedB.product_id}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Calculated Overlap Bar - Only show if both selected */}
      {selectedA && selectedB && (
        <div className="glass-panel p-4 rounded-xl border border-[#203046] flex flex-col sm:flex-row items-center justify-between gap-4 font-mono text-xs animate-fadeIn">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-cyan-950/80 border border-cyan-700/60 flex items-center justify-center text-cyan-400 font-bold text-sm">
              {MOCK_DATASET.geometry.calculatedOverlap}%
            </div>
            <div>
              <div className="text-slate-200 font-semibold tracking-wide">CALCULATED FOOTPRINT OVERLAP</div>
              <div className="text-slate-400 text-[11px]">Computed from PDS footprint intersection (`footprint_overlap()`). Footprint segments normalized to 0-360°.</div>
            </div>
          </div>
          <div className="w-full sm:w-48 bg-[#0c131f] rounded-full h-2.5 overflow-hidden border border-[#1e2d42]">
            <div className="bg-gradient-to-r from-cyan-500 to-blue-500 h-full rounded-full w-[31.4%]" />
          </div>
        </div>
      )}

      {/* Registration Pipeline Rung Selector */}
      <div className="space-y-3">
        <div className="text-xs font-mono text-slate-400 uppercase tracking-wider">
          SELECT REGISTRATION ALGORITHM PIPELINE RUNG
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {MOCK_DATASET.pipelines.map((p) => {
            const isSelected = selectedRung === p.id;
            return (
              <div
                key={p.id}
                onClick={() => setSelectedRung(p.id)}
                className={`p-4 rounded-xl cursor-pointer transition-all duration-150 border flex flex-col justify-between space-y-3 ${
                  isSelected
                    ? 'bg-cyan-950/40 border-cyan-400 shadow-lg shadow-cyan-950/40'
                    : 'bg-[#121926] border-[#1e2c40] hover:bg-[#162030] hover:border-slate-600'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-mono font-bold ${isSelected ? 'text-cyan-300' : 'text-slate-200'}`}>
                    {p.name}
                  </span>
                  {isSelected && <CheckCircle2 className="w-4 h-4 text-cyan-400" />}
                </div>

                <p className="text-xs text-slate-400">{p.desc}</p>

                <div className="text-[11px] font-mono text-slate-500 pt-2 border-t border-[#1e2d40]">
                  Status: <span className={p.id === 'rung1' ? 'text-emerald-400 font-semibold' : 'text-slate-400'}>{p.status}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Run Match Action Trigger Bar */}
      <div className="glass-panel p-5 rounded-xl border border-cyan-800/60 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <button
            onClick={handleRunMatchClick}
            disabled={isProcessing || !selectedA || !selectedB || selectedA.product_id === selectedB.product_id}
            className={`flex items-center space-x-3 px-8 py-3.5 rounded-xl text-sm font-bold tracking-wide transition transform ${
              isProcessing || !selectedA || !selectedB || selectedA.product_id === selectedB.product_id
                ? 'bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed'
                : 'glow-btn-cyan hover:scale-[1.01] active:scale-[0.99]'
            }`}
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-cyan-500" />
                <span className="text-slate-300">Processing Rung {selectedRung.replace('rung','')}...</span>
              </>
            ) : (
              <>
                <span>➜ Run match</span>
                <Zap className={`w-4 h-4 ${(!selectedA || !selectedB || selectedA.product_id === selectedB.product_id) ? 'text-slate-500' : 'text-slate-900 fill-slate-900'}`} />
              </>
            )}
          </button>
          
          {selectedA && selectedB && selectedA.product_id === selectedB.product_id && (
            <div className="text-red-400 text-xs mt-2 font-mono">Cannot match a product with itself.</div>
          )}
        </div>

        <div className="text-xs font-mono text-slate-400 text-right space-y-0.5">
          <div>EST. {MOCK_DATASET.geometry.estimatedComputeSec} s • {MOCK_DATASET.geometry.tflopsRequired} TFLOPS</div>
          <div className="text-slate-500">{MOCK_DATASET.geometry.swathOverlapPx} px SWATH OVERLAP SEARCH WINDOW</div>
        </div>
      </div>

      {/* Animated Processing Overlay Modal */}
      {isProcessing && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-md flex items-center justify-center p-6">
          <div className="bg-[#121926] border border-cyan-500/50 rounded-xl p-8 max-w-md w-full space-y-6 text-center shadow-2xl">
            <div className="relative w-20 h-20 mx-auto flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border-4 border-cyan-500/20 border-t-cyan-400 animate-spin" />
              <Layers className="w-8 h-8 text-cyan-400" />
            </div>

            <div className="space-y-2">
              <h3 className="text-lg font-display font-bold text-white">Running Registration Engine</h3>
              <p className="text-xs font-mono text-cyan-300">
                {processStep === 1 && "1. Computing PDS footprint geometry overlap..."}
                {processStep === 2 && "2. Extracting solar-robust edge gradients..."}
                {processStep === 3 && "3. Performing sub-pixel RANSAC tie-point alignment..."}
              </p>
            </div>

            <div className="w-full bg-[#0c131f] rounded-full h-2 overflow-hidden border border-[#1e2d42]">
              <div 
                className="bg-gradient-to-r from-cyan-500 to-blue-500 h-full rounded-full transition-all duration-700" 
                style={{ width: `${(processStep / 3) * 100}%` }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
