import React, { useState, useRef, useEffect } from 'react';
import { Eye, Layers, Sliders, CheckCircle2, XCircle, Grid, Filter } from 'lucide-react';
import { MOCK_DATASET } from '../data/mockLunarData';

export default function Screen02MatchReview({ onAcceptMatch }) {
  const [viewMode, setViewMode] = useState('sideBySide'); // sideBySide | swipe | checkerboard
  const [showEdgeDetection, setShowEdgeDetection] = useState(false);
  const [showPdsOverlap, setShowPdsOverlap] = useState(true);
  const [showAllKeypoints, setShowAllKeypoints] = useState(true);
  const [swipePosition, setSwipePosition] = useState(50); // % for swipe slider
  const [hoveredPoint, setHoveredPoint] = useState(null);

  const canvasRef = useRef(null);

  // Draw tie-lines on Canvas when in side-by-side mode
  useEffect(() => {
    if (viewMode !== 'sideBySide' || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    const halfW = width / 2;

    // Draw tie-lines connecting tiepoints
    MOCK_DATASET.tiepoints.forEach((pt, idx) => {
      const isHovered = hoveredPoint === idx;

      const x1 = (pt.x1 / 100) * halfW;
      const y1 = (pt.y1 / 100) * height;
      const x2 = halfW + (pt.x2 / 100) * halfW;
      const y2 = (pt.y2 / 100) * height;

      // Line style
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = isHovered ? '#00f2fe' : (showEdgeDetection ? '#00a8ff' : '#00f2fe88');
      ctx.lineWidth = isHovered ? 2.5 : 1.5;
      ctx.stroke();

      // Point Left
      ctx.beginPath();
      ctx.arc(x1, y1, isHovered ? 5 : 3.5, 0, Math.PI * 2);
      ctx.fillStyle = '#00f2fe';
      ctx.fill();

      // Point Right
      ctx.beginPath();
      ctx.arc(x2, y2, isHovered ? 5 : 3.5, 0, Math.PI * 2);
      ctx.fillStyle = '#ffb703';
      ctx.fill();
    });
  }, [viewMode, showEdgeDetection, hoveredPoint]);

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Top Header & Breadcrumb */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1e2d42] pb-4">
        <div>
          <h2 className="text-xl font-display font-bold text-white flex items-center space-x-2">
            <span>Match review:</span>
            <span className="font-mono text-cyan-300 text-base">{MOCK_DATASET.moving.id} ➜ {MOCK_DATASET.reference.id}</span>
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Sub-pixel tie-point verification and spatial coverage heatmap inspection.
          </p>
        </div>

        {/* View Mode Toggle Pill Bar */}
        <div className="flex items-center space-x-1 bg-[#101724] border border-[#203046] p-1 rounded-lg font-mono text-xs">
          <button
            onClick={() => setViewMode('sideBySide')}
            className={`px-3 py-1.5 rounded-md transition ${viewMode === 'sideBySide' ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/60 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}
          >
            Side by side
          </button>
          <button
            onClick={() => setViewMode('swipe')}
            className={`px-3 py-1.5 rounded-md transition ${viewMode === 'swipe' ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/60 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}
          >
            Swipe
          </button>
          <button
            onClick={() => setViewMode('checkerboard')}
            className={`px-3 py-1.5 rounded-md transition ${viewMode === 'checkerboard' ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/60 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}
          >
            Checkerboard
          </button>
        </div>
      </div>

      {/* Main Viewport & Right Metrics Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left 2 Columns: Visual Match Canvas */}
        <div className="lg:col-span-2 space-y-4">
          
          {/* Secondary Feature Filter Toggles */}
          <div className="flex items-center justify-between bg-[#121926] border border-[#1e2d42] px-4 py-2 rounded-lg text-xs font-mono">
            <div className="flex items-center space-x-4">
              <label className="flex items-center space-x-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={showPdsOverlap}
                  onChange={(e) => setShowPdsOverlap(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-0"
                />
                <span className="text-slate-300">PDS OVERLAP</span>
              </label>

              <label className="flex items-center space-x-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={showEdgeDetection}
                  onChange={(e) => setShowEdgeDetection(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-0"
                />
                <span className={showEdgeDetection ? "text-cyan-300 font-semibold" : "text-slate-300"}>
                  EDGE DETECTION FILTER
                </span>
              </label>

              <label className="flex items-center space-x-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={showAllKeypoints}
                  onChange={(e) => setShowAllKeypoints(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-0"
                />
                <span className="text-slate-300">ALL KEYPOINTS</span>
              </label>
            </div>
            <div className="text-slate-500 text-[11px]">FOV: 100% (1:1)</div>
          </div>

          {/* Interactive Match Visual Viewer Canvas */}
          <div className="relative bg-[#090d14] border border-[#1e2d42] rounded-xl h-[420px] overflow-hidden">
            
            {/* View Mode 1: SIDE BY SIDE TIE-LINES */}
            {viewMode === 'sideBySide' && (
              <div className="relative w-full h-full flex">
                {/* Left Crater Image */}
                <div className="w-1/2 h-full border-r border-[#1e2d42] relative bg-[#0d1420] flex items-center justify-center">
                  <svg viewBox="0 0 200 200" className="w-full h-full opacity-75">
                    <rect width="200" height="200" fill={showEdgeDetection ? "#05080e" : "#0c121c"}/>
                    {/* Crater Features with Edge filter highlight */}
                    <circle cx="80" cy="90" r="45" fill={showEdgeDetection ? "none" : "#151f2e"} stroke={showEdgeDetection ? "#00f2fe" : "#253750"} strokeWidth={showEdgeDetection ? "2.5" : "2"} />
                    <circle cx="80" cy="90" r="30" fill={showEdgeDetection ? "none" : "#0d1420"} stroke={showEdgeDetection ? "#00a8ff" : "#1d2d42"} strokeWidth="1.5"/>
                    <circle cx="150" cy="140" r="25" fill={showEdgeDetection ? "none" : "#131b28"} stroke={showEdgeDetection ? "#00f2fe" : "#22334b"} strokeWidth="1.5"/>
                  </svg>
                  <div className="absolute top-3 left-3 px-2 py-1 rounded bg-cyan-950/80 border border-cyan-800 text-[10px] font-mono text-cyan-300">
                    CH2 OHRC (MOVING SOURCE)
                  </div>
                </div>

                {/* Right Crater Reference Image */}
                <div className="w-1/2 h-full relative bg-[#0c131f] flex items-center justify-center">
                  <svg viewBox="0 0 200 200" className="w-full h-full opacity-75">
                    <rect width="200" height="200" fill={showEdgeDetection ? "#05080e" : "#0c121c"}/>
                    <circle cx="85" cy="88" r="44" fill={showEdgeDetection ? "none" : "#172233"} stroke={showEdgeDetection ? "#ffb703" : "#283d5a"} strokeWidth={showEdgeDetection ? "2.5" : "2"} />
                    <circle cx="85" cy="88" r="29" fill={showEdgeDetection ? "none" : "#0e1624"} stroke={showEdgeDetection ? "#ffb703" : "#1f3149"} strokeWidth="1.5"/>
                    <circle cx="152" cy="138" r="24" fill={showEdgeDetection ? "none" : "#141e2e"} stroke={showEdgeDetection ? "#ffb703" : "#243750"} strokeWidth="1.5"/>
                  </svg>
                  <div className="absolute top-3 right-3 px-2 py-1 rounded bg-blue-950/80 border border-blue-800 text-[10px] font-mono text-blue-300">
                    LRO NAC (FIXED REFERENCE)
                  </div>
                </div>

                {/* Canvas Overlay for connecting tie-lines */}
                <canvas
                  ref={canvasRef}
                  width={600}
                  height={420}
                  className="absolute inset-0 w-full h-full pointer-events-none"
                />
              </div>
            )}

            {/* View Mode 2: SWIPE SPLIT SLIDER */}
            {viewMode === 'swipe' && (
              <div className="relative w-full h-full overflow-hidden select-none">
                {/* Background Reference Image */}
                <div className="absolute inset-0 bg-[#0c131f] flex items-center justify-center">
                  <svg viewBox="0 0 200 200" className="w-full h-full opacity-90">
                    <rect width="200" height="200" fill="#0c121c"/>
                    <circle cx="85" cy="88" r="44" fill="#172233" stroke="#ffb703" strokeWidth="2" />
                    <circle cx="152" cy="138" r="24" fill="#141e2e" stroke="#ffb703" strokeWidth="1.5"/>
                  </svg>
                  <div className="absolute top-3 right-3 px-2 py-1 rounded bg-blue-950/80 text-[10px] font-mono text-blue-300">
                    LRO NAC REFERENCE
                  </div>
                </div>

                {/* Foreground Moving Source Image clipped by slider position */}
                <div 
                  className="absolute top-0 bottom-0 left-0 overflow-hidden bg-[#0d1420] border-r-2 border-cyan-400"
                  style={{ width: `${swipePosition}%` }}
                >
                  <div className="w-full h-full flex items-center justify-center" style={{ width: '600px' }}>
                    <svg viewBox="0 0 200 200" className="w-full h-full opacity-90">
                      <rect width="200" height="200" fill="#0c121c"/>
                      <circle cx="80" cy="90" r="45" fill="#151f2e" stroke="#00f2fe" strokeWidth="2" />
                      <circle cx="150" cy="140" r="25" fill="#131b28" stroke="#00f2fe" strokeWidth="1.5"/>
                    </svg>
                  </div>
                  <div className="absolute top-3 left-3 px-2 py-1 rounded bg-cyan-950/80 text-[10px] font-mono text-cyan-300">
                    CH2 OHRC MOVING REGISTERED
                  </div>
                </div>

                {/* Interactive Slider Handle */}
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={swipePosition}
                  onChange={(e) => setSwipePosition(e.target.value)}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-ew-resize z-10"
                />
              </div>
            )}

            {/* View Mode 3: CHECKERBOARD GRID ALIGNMENT */}
            {viewMode === 'checkerboard' && (
              <div className="relative w-full h-full grid grid-cols-4 grid-rows-4">
                {Array.from({ length: 16 }).map((_, idx) => {
                  const isEven = (Math.floor(idx / 4) + (idx % 4)) % 2 === 0;
                  return (
                    <div
                      key={idx}
                      className={`border border-[#1b283d] flex items-center justify-center relative overflow-hidden ${
                        isEven ? 'bg-[#0d1420]' : 'bg-[#0c131f]'
                      }`}
                    >
                      <span className="text-[10px] font-mono opacity-40 text-slate-400">
                        {isEven ? 'CH2' : 'LRO'}
                      </span>
                    </div>
                  );
                })}
                <div className="absolute bottom-3 left-3 px-3 py-1 rounded bg-black/80 border border-cyan-700/60 text-[10px] font-mono text-cyan-300">
                  CHECKERBOARD SNAPPING ALIGNMENT: 0.372 px SEAM CONTINUITY
                </div>
              </div>
            )}

          </div>

          {/* Action Button Controls Footer */}
          <div className="flex items-center justify-between pt-2">
            <button className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-red-950/40 hover:bg-red-950/70 border border-red-800/60 text-red-300 text-xs font-mono transition">
              <XCircle className="w-4 h-4" />
              <span>Reject cluster</span>
            </button>

            <button
              onClick={onAcceptMatch}
              className="flex items-center space-x-2 px-6 py-2.5 rounded-lg glow-btn-cyan text-xs font-mono font-bold tracking-wide transition"
            >
              <span>Accept &amp; Proceed to Evidence ➜</span>
              <CheckCircle2 className="w-4 h-4" />
            </button>
          </div>

        </div>

        {/* Right Column: Spatial Heatmap & Error Metrics Panel */}
        <div className="space-y-4">
          
          {/* 8x8 Spatial Distribution Grid Heatmap Matrix */}
          <div className="glass-panel p-4 rounded-xl border border-[#203046] space-y-3">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-slate-300 font-semibold">MATCH MATRIX DISTRIBUTION</span>
              <span className="text-cyan-400 font-bold">{MOCK_DATASET.metrics.gridCoverage}</span>
            </div>

            {/* 8x8 Matrix Render */}
            <div className="grid grid-cols-8 gap-1 aspect-square bg-[#0b0f17] p-2 rounded-lg border border-[#1b273a]">
              {MOCK_DATASET.gridHeatmap.map((row, rIdx) =>
                row.map((val, cIdx) => {
                  // Color intensity based on count
                  const alpha = Math.min(val / 9, 1);
                  return (
                    <div
                      key={`${rIdx}-${cIdx}`}
                      className="rounded-sm flex items-center justify-center text-[9px] font-mono transition hover:scale-110 cursor-pointer"
                      style={{
                        backgroundColor: `rgba(0, 242, 254, ${0.15 + alpha * 0.75})`,
                        color: alpha > 0.4 ? '#0b0f17' : '#00f2fe'
                      }}
                      title={`Grid Cell [${rIdx},${cIdx}]: ${val} tiepoints`}
                    >
                      {val}
                    </div>
                  );
                })
              )}
            </div>

            <p className="text-[11px] font-mono text-slate-400 leading-tight">
              Tiepoints fall into spatial match matrix, maintaining uniform distribution across the entire frame.
            </p>
          </div>

          {/* Sub-Pixel Metrics Breakdown Card */}
          <div className="glass-panel p-4 rounded-xl border border-[#203046] space-y-3 font-mono text-xs">
            <div className="text-slate-300 font-semibold border-b border-[#1e2d42] pb-2">
              MATCH QUALITY METRICS
            </div>

            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-400">Total Matches:</span>
                <span className="text-slate-200 font-semibold">{MOCK_DATASET.metrics.totalMatches}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Inliers Count:</span>
                <span className="text-emerald-400 font-semibold">{MOCK_DATASET.metrics.inlierCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Inlier Ratio:</span>
                <span className="text-emerald-400 font-semibold">{MOCK_DATASET.metrics.inlierRatio}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Sub-Pixel RMSE:</span>
                <span className="text-cyan-300 font-bold text-sm">{MOCK_DATASET.metrics.rmseSubpixel}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Sun Azimuth Delta:</span>
                <span className="text-amber-400 font-semibold">{MOCK_DATASET.metrics.sunAzimuthDiff}</span>
              </div>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
