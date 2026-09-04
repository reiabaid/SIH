import React, { useState } from 'react';
import { BarChart3, TrendingUp, ShieldCheck, ArrowRight, Info, CheckCircle2 } from 'lucide-react';
import { MOCK_DATASET } from '../data/mockLunarData';

export default function Screen03Evidence({ onProceedToExport }) {
  const [activeTab, setActiveTab] = useState('azimuth'); // azimuth | elevation

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1e2d42] pb-4">
        <div>
          <h2 className="text-xl font-display font-bold text-white flex items-center space-x-2">
            <BarChart3 className="w-5 h-5 text-cyan-400" />
            <span>03 - Evidence: Algorithm Robustness Proof</span>
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Validation of Mod-X solar-robust edge/phase correlation against standard SIFT across sun azimuth shifts ($0^\circ - 180^\circ$).
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center space-x-2 bg-[#101724] border border-[#203046] p-1 rounded-lg font-mono text-xs">
          <button
            onClick={() => setActiveTab('azimuth')}
            className={`px-3 py-1.5 rounded-md transition ${activeTab === 'azimuth' ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/60 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}
          >
            Matcher comparison (Azimuth)
          </button>
          <button
            onClick={() => setActiveTab('elevation')}
            className={`px-3 py-1.5 rounded-md transition ${activeTab === 'elevation' ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/60 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}
          >
            Azimuth vs elevation
          </button>
        </div>
      </div>

      {/* Main Grid: Chart Viewport & Stat Metrics Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left 2 Columns: Main Robustness Chart */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Main Chart Box */}
          <div className="glass-panel p-6 rounded-xl border border-[#203046] space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                  Inlier count against sun-azimuth difference
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Evaluated across NASA LRO &amp; Chandrayaan-2 synthetic shadow test pairs.
                </p>
              </div>

              {/* Chart Legend */}
              <div className="flex items-center space-x-4 text-xs font-mono">
                <div className="flex items-center space-x-1.5">
                  <span className="w-3 h-0.5 bg-amber-500 inline-block" />
                  <span className="text-amber-400 font-semibold">SIFT (Baseline)</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="w-3 h-0.5 bg-cyan-400 inline-block" />
                  <span className="text-cyan-300 font-semibold">Rung 1 MOD-X</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="w-3 h-0.5 bg-blue-400 inline-block" />
                  <span className="text-blue-300 font-semibold">LIGHTGLUE</span>
                </div>
              </div>
            </div>

            {/* SVG Chart Plot Render */}
            <div className="relative h-64 bg-[#090d14] border border-[#1b273a] rounded-lg p-4 overflow-hidden">
              <svg viewBox="0 0 500 200" className="w-full h-full">
                {/* Grid Lines */}
                <line x1="40" y1="20" x2="480" y2="20" stroke="#182538" strokeWidth="1" strokeDasharray="3,3" />
                <line x1="40" y1="60" x2="480" y2="60" stroke="#182538" strokeWidth="1" strokeDasharray="3,3" />
                <line x1="40" y1="100" x2="480" y2="100" stroke="#182538" strokeWidth="1" strokeDasharray="3,3" />
                <line x1="40" y1="140" x2="480" y2="140" stroke="#182538" strokeWidth="1" strokeDasharray="3,3" />
                <line x1="40" y1="180" x2="480" y2="180" stroke="#253750" strokeWidth="1" />

                {/* Y-Axis Labels */}
                <text x="32" y="24" fill="#5c6c84" fontSize="9" textAnchor="end" fontFamily="monospace">1500</text>
                <text x="32" y="64" fill="#5c6c84" fontSize="9" textAnchor="end" fontFamily="monospace">1000</text>
                <text x="32" y="104" fill="#5c6c84" fontSize="9" textAnchor="end" fontFamily="monospace">500</text>
                <text x="32" y="144" fill="#5c6c84" fontSize="9" textAnchor="end" fontFamily="monospace">100</text>
                <text x="32" y="184" fill="#5c6c84" fontSize="9" textAnchor="end" fontFamily="monospace">0</text>

                {/* X-Axis Labels */}
                <text x="40" y="195" fill="#5c6c84" fontSize="9" textAnchor="middle" fontFamily="monospace">0°</text>
                <text x="113" y="195" fill="#5c6c84" fontSize="9" textAnchor="middle" fontFamily="monospace">30°</text>
                <text x="186" y="195" fill="#5c6c84" fontSize="9" textAnchor="middle" fontFamily="monospace">60°</text>
                <text x="260" y="195" fill="#5c6c84" fontSize="9" textAnchor="middle" fontFamily="monospace">90°</text>
                <text x="333" y="195" fill="#5c6c84" fontSize="9" textAnchor="middle" fontFamily="monospace">120°</text>
                <text x="406" y="195" fill="#5c6c84" fontSize="9" textAnchor="middle" fontFamily="monospace">150°</text>
                <text x="480" y="195" fill="#5c6c84" fontSize="9" textAnchor="middle" fontFamily="monospace">180°</text>

                {/* Curve 1: SIFT (Orange - Drops rapidly) */}
                <path
                  d="M 40,22 C 80,80 113,150 186,174 C 260,178 333,179 480,180"
                  fill="none"
                  stroke="#ffb703"
                  strokeWidth="2.5"
                />

                {/* Curve 2: MOD-X (Cyan - High stability) */}
                <path
                  d="M 40,28 C 113,32 186,40 260,48 C 333,52 406,56 480,62"
                  fill="none"
                  stroke="#00f2fe"
                  strokeWidth="3"
                />

                {/* Curve 3: LIGHTGLUE (Blue - High stability) */}
                <path
                  d="M 40,18 C 113,22 186,28 260,36 C 333,40 406,44 480,50"
                  fill="none"
                  stroke="#00a8ff"
                  strokeWidth="2"
                  strokeDasharray="4,4"
                />

                {/* Interactive Callout Badge at 30° difference */}
                <g transform="translate(113, 85)">
                  <rect x="-60" y="-22" width="120" height="26" rx="4" fill="#182638" stroke="#ffb703" strokeWidth="1" />
                  <text x="0" y="-5" fill="#ffb703" fontSize="9" fontWeight="bold" textAnchor="middle" fontFamily="monospace">
                    Δ 30° SIFT inliers -78%
                  </text>
                </g>
              </svg>
            </div>
          </div>

          {/* Secondary Plot: Elevation Angle Sensitivity */}
          <div className="glass-panel p-5 rounded-xl border border-[#203046] flex items-center justify-between text-xs font-mono">
            <div className="space-y-1">
              <div className="text-slate-300 font-semibold uppercase">ELEVATION ANGLE SENSITIVITY</div>
              <p className="text-slate-400 text-[11px]">
                Elevation variation affects shadow length, but Mod-X edge extraction remains invariant.
              </p>
            </div>
            <div className="px-3 py-1.5 rounded bg-cyan-950/60 border border-cyan-800 text-cyan-300 text-right">
              <span className="block text-[10px] text-slate-400">FINDING:</span>
              <span>Height only lengthens shadows</span>
            </div>
          </div>

        </div>

        {/* Right Column: Stat Summary Box & Uniformity Matrix */}
        <div className="space-y-6">
          
          {/* Top Stat Summary Box */}
          <div className="glass-panel p-5 rounded-xl border border-cyan-900/50 space-y-4 font-mono text-xs">
            <div className="flex items-center justify-between text-cyan-300 font-bold border-b border-[#1f2e45] pb-2">
              <span>GROUND TRUTH EVALUATION</span>
              <ShieldCheck className="w-4 h-4 text-cyan-400" />
            </div>

            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-slate-400">RMSE (ground truth):</span>
                <span className="text-cyan-300 font-bold text-sm">{MOCK_DATASET.metrics.rmseGroundTruth}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Inlier Count:</span>
                <span className="text-emerald-400 font-semibold">{MOCK_DATASET.metrics.inlierCount}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Inlier Ratio:</span>
                <span className="text-emerald-400 font-semibold">{MOCK_DATASET.metrics.inlierRatio}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Grid Coverage:</span>
                <span className="text-slate-200 font-semibold">{MOCK_DATASET.metrics.gridCoverage}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Distribution CV:</span>
                <span className="text-slate-200 font-semibold">{MOCK_DATASET.metrics.distributionCV}</span>
              </div>
            </div>
          </div>

          {/* Middle Right Matrix: 8x8 Spatial Grid Matrix */}
          <div className="glass-panel p-4 rounded-xl border border-[#203046] space-y-3">
            <div className="text-xs font-mono text-slate-300 font-semibold">
              UNIFORM DISTRIBUTION MATRIX
            </div>

            <div className="grid grid-cols-8 gap-1 aspect-square bg-[#0b0f17] p-2 rounded-lg border border-[#1b273a]">
              {MOCK_DATASET.gridHeatmap.map((row, rIdx) =>
                row.map((val, cIdx) => (
                  <div
                    key={`ev-${rIdx}-${cIdx}`}
                    className="rounded-sm bg-cyan-950/60 border border-cyan-800/40 flex items-center justify-center text-[9px] font-mono text-cyan-300"
                  >
                    {val}
                  </div>
                ))
              )}
            </div>

            <p className="text-[11px] font-mono text-slate-400 leading-tight">
              Tiepoints fall into match matrix, maintaining uniform distribution across all sectors.
            </p>
          </div>

          {/* Action Button */}
          <button
            onClick={onProceedToExport}
            className="w-full flex items-center justify-center space-x-2 py-3 rounded-xl glow-btn-cyan text-xs font-mono font-bold tracking-wide transition"
          >
            <span>Proceed to 3D Terrain &amp; Report ➜</span>
            <ArrowRight className="w-4 h-4" />
          </button>

        </div>

      </div>
    </div>
  );
}
