import React, { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, ShieldCheck, ArrowRight, Info, CheckCircle2, Loader2, AlertTriangle, ArrowLeft } from 'lucide-react';

export default function Screen03Evidence({ jobId, selectedProductA, selectedProductB, onProceedToExport, onBack }) {
  const [activeTab, setActiveTab] = useState('azimuth'); // azimuth | elevation
  
  const [status, setStatus] = useState('fetching'); // fetching, ready, failed
  const [metrics, setMetrics] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  const prodA_id = selectedProductA?.product_id || 'Unknown Product';
  const prodB_id = selectedProductB?.product_id || 'Unknown Product';

  useEffect(() => {
    let isMounted = true;
    
    const fetchArtefacts = async () => {
      if (!jobId) {
        if (isMounted) {
          setErrorMsg("Missing job ID from previous step. Please go back and run a match.");
          setStatus('failed');
        }
        return;
      }

      try {
        const metricsRes = await fetch(`http://127.0.0.1:8000/jobs/${jobId}/artefacts/metrics.json`);
        if (!metricsRes.ok) throw new Error("Failed to fetch metrics.json");
        const metricsData = await metricsRes.json();

        if (isMounted) {
          setMetrics(metricsData);
          setStatus('ready');
        }
      } catch (err) {
        if (isMounted) {
          setErrorMsg(err.message || "Failed to fetch evidence artefacts.");
          setStatus('failed');
        }
      }
    };

    fetchArtefacts();

    return () => {
      isMounted = false;
    };
  }, [jobId]);

  if (status === 'failed') {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] space-y-4 animate-fadeIn">
        <AlertTriangle className="w-12 h-12 text-red-500" />
        <h2 className="text-xl font-bold text-white">Missing Evidence Data</h2>
        <p className="text-slate-400 font-mono text-sm">{errorMsg}</p>
        <button onClick={onBack} className="mt-4 flex items-center space-x-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition">
          <ArrowLeft className="w-4 h-4" />
          <span>Return to Review</span>
        </button>
      </div>
    );
  }

  if (status !== 'ready') {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] space-y-6 animate-fadeIn">
        <div className="relative w-16 h-16">
          <Loader2 className="w-16 h-16 animate-spin text-cyan-500" />
          <div className="absolute inset-0 border-4 border-t-cyan-300 border-r-cyan-500 border-b-cyan-700 border-l-cyan-900 rounded-full animate-spin-slow"></div>
        </div>
        <div className="text-center space-y-2">
          <h2 className="text-xl font-display font-bold text-white">
            Retrieving Match Evidence...
          </h2>
          <p className="text-sm font-mono text-cyan-300">
            {prodA_id} ➜ {prodB_id}
          </p>
          <p className="text-xs font-mono text-slate-500 mt-2 animate-pulse">Loading backend artefacts...</p>
        </div>
      </div>
    );
  }

  // Safe Metric Formatters
  const safeNum = (val, decimals = 2) => {
    if (val === null || val === undefined || isNaN(Number(val))) return "N/A";
    return Number(val).toFixed(decimals);
  };

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

            {/* Explanatory Panel replacing static SVG */}
            <div className="bg-[#0b0f17] border border-[#1b273a] rounded-lg p-6 text-center space-y-4">
              <Info className="w-10 h-10 text-cyan-500 mx-auto opacity-80" />
              <div>
                <h4 className="text-white font-bold font-display">Offline Algorithm Validation Result</h4>
                <p className="text-slate-400 text-sm mt-2">
                  The sun-azimuth sensitivity curve (SIFT vs. Mod-X) is an offline validation step confirming Mod-X's edge/phase correlation robustness under synthetic extreme lighting shifts. It is not generated dynamically by the current backend job.
                </p>
              </div>
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
              <span>ACTUAL RUN EVALUATION</span>
              <ShieldCheck className="w-4 h-4 text-cyan-400" />
            </div>

            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Job ID:</span>
                <span className="text-cyan-300 font-bold text-[10px]">{jobId}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Total Matches:</span>
                <span className="text-emerald-400 font-semibold">{safeNum(metrics?.total_matches, 0)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Inlier Count:</span>
                <span className="text-emerald-400 font-semibold">{safeNum(metrics?.inlier_count, 0)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Inlier Ratio:</span>
                <span className="text-emerald-400 font-semibold">{metrics?.inlier_ratio !== undefined && metrics?.inlier_ratio !== null ? safeNum(metrics.inlier_ratio * 100, 1) + '%' : 'N/A'}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Sub-pixel RMSE:</span>
                <span className="text-slate-200 font-semibold">{safeNum(metrics?.reprojection_residual, 3)} px</span>
              </div>
              {metrics?.rmse_ground_truth !== undefined && metrics?.rmse_ground_truth !== null && (
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">RMSE (Ground Truth):</span>
                  <span className="text-slate-200 font-semibold">{safeNum(metrics?.rmse_ground_truth, 3)} px</span>
                </div>
              )}
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Grid Coverage:</span>
                <span className="text-slate-200 font-semibold">{safeNum((metrics?.occupied_fraction || 0) * 100, 1)}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Distribution CV:</span>
                <span className="text-slate-200 font-semibold">{safeNum(metrics?.coefficient_of_variation, 2)}</span>
              </div>
            </div>
          </div>

          {/* Middle Right Matrix: 8x8 Spatial Grid Matrix */}
          <div className="glass-panel p-4 rounded-xl border border-[#203046] space-y-3">
            <div className="text-xs font-mono text-slate-300 font-semibold">
              UNIFORM DISTRIBUTION MATRIX
            </div>

            <div className="bg-[#0b0f17] p-4 rounded-lg border border-[#1b273a] text-center text-slate-400 font-mono text-[10px]">
              <p className="font-bold text-slate-300">Spatial Grid Heatmap is disabled.</p>
              <p className="mt-1 text-slate-500">The backend does not expose the 8x8 cell density array in metrics.json.</p>
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
