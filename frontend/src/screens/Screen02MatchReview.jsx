import React, { useState, useRef, useEffect } from 'react';
import { Eye, Layers, Sliders, CheckCircle2, XCircle, Grid, Filter, Loader2, AlertTriangle, ArrowLeft } from 'lucide-react';

export default function Screen02MatchReview({ selectedProductA, selectedProductB, selectedRung, completedJobId, onAcceptMatch, onBack }) {
  const [viewMode, setViewMode] = useState('overlay'); // overlay is best since we only have overlay_rgb.png
  const [showEdgeDetection, setShowEdgeDetection] = useState(false);
  const [showPdsOverlap, setShowPdsOverlap] = useState(true);
  const [showAllKeypoints, setShowAllKeypoints] = useState(true);
  
  const [jobStatus, setJobStatus] = useState('registering'); // registering, polling, fetching_artefacts, ready, failed
  const [jobId, setJobId] = useState(completedJobId || null);
  const [metrics, setMetrics] = useState(null);
  const [geoJson, setGeoJson] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  const rungInt = selectedRung ? parseInt(selectedRung.replace('rung', ''), 10) : 1;
  const prodA_id = selectedProductA?.product_id || 'Unknown Product';
  const prodB_id = selectedProductB?.product_id || 'Unknown Product';

  useEffect(() => {
    let isMounted = true;
    let pollInterval = null;

    const startJob = async () => {
      if (!selectedProductA || !selectedProductB) {
        if (isMounted) {
          setErrorMsg("Missing selected products.");
          setJobStatus('failed');
        }
        return;
      }

      try {
        setJobStatus('registering');
        const res = await fetch('http://127.0.0.1:8000/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            product_a: selectedProductA.product_id,
            product_b: selectedProductB.product_id,
            rung: rungInt
          })
        });

        if (!res.ok) {
          throw new Error(`Failed to register job. Status: ${res.status}`);
        }

        const data = await res.json();
        const newJobId = data.job_id;
        if (isMounted) {
          setJobId(newJobId);
          setJobStatus('polling');
        }

        pollInterval = setInterval(async () => {
          try {
            const pollRes = await fetch(`http://127.0.0.1:8000/jobs/${newJobId}`);
            if (!pollRes.ok) throw new Error("Failed to poll job status.");
            const pollData = await pollRes.json();
            
            if (pollData.status === 'completed') {
              clearInterval(pollInterval);
              if (isMounted) fetchArtefacts(newJobId);
            } else if (pollData.status === 'failed') {
              clearInterval(pollInterval);
              if (isMounted) {
                setErrorMsg("Pipeline execution failed on the backend.");
                setJobStatus('failed');
              }
            }
          } catch (pollErr) {
            clearInterval(pollInterval);
            if (isMounted) {
              setErrorMsg(pollErr.message || "Polling error occurred.");
              setJobStatus('failed');
            }
          }
        }, 2000);

      } catch (err) {
        if (isMounted) {
          setErrorMsg(err.message || "Failed to register job.");
          setJobStatus('failed');
        }
      }
    };

    const fetchArtefacts = async (id) => {
      try {
        setJobStatus('fetching_artefacts');
        
        const metricsRes = await fetch(`http://127.0.0.1:8000/jobs/${id}/artefacts/metrics.json`);
        if (!metricsRes.ok) throw new Error("Failed to fetch metrics.json");
        const metricsData = await metricsRes.json();

        const geoRes = await fetch(`http://127.0.0.1:8000/jobs/${id}/artefacts/match_points.geojson`);
        if (!geoRes.ok) throw new Error("Failed to fetch match_points.geojson");
        const geoData = await geoRes.json();

        if (isMounted) {
          setMetrics(metricsData);
          setGeoJson(geoData);
          setJobStatus('ready');
        }
      } catch (err) {
        if (isMounted) {
          setErrorMsg(err.message || "Failed to fetch artefacts.");
          setJobStatus('failed');
        }
      }
    };

    if (completedJobId) {
      if (isMounted) {
        setJobId(completedJobId);
        fetchArtefacts(completedJobId);
      }
    } else {
      startJob();
    }

    return () => {
      isMounted = false;
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [selectedProductA, selectedProductB, rungInt, completedJobId]);

  if (jobStatus === 'failed') {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] space-y-4 animate-fadeIn">
        <AlertTriangle className="w-12 h-12 text-red-500" />
        <h2 className="text-xl font-bold text-white">Job Failed</h2>
        <p className="text-slate-400 font-mono text-sm">{errorMsg}</p>
        <button onClick={onBack} className="mt-4 flex items-center space-x-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition">
          <ArrowLeft className="w-4 h-4" />
          <span>Return to Selection</span>
        </button>
      </div>
    );
  }

  if (jobStatus !== 'ready') {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] space-y-6 animate-fadeIn">
        <div className="relative w-16 h-16">
          <Loader2 className="w-16 h-16 animate-spin text-cyan-500" />
          <div className="absolute inset-0 border-4 border-t-cyan-300 border-r-cyan-500 border-b-cyan-700 border-l-cyan-900 rounded-full animate-spin-slow"></div>
        </div>
        <div className="text-center space-y-2">
          <h2 className="text-xl font-display font-bold text-white">
            {jobStatus === 'registering' && "Registering Match Job..."}
            {jobStatus === 'polling' && "Executing Pipeline..."}
            {jobStatus === 'fetching_artefacts' && "Retrieving Artifacts..."}
          </h2>
          <p className="text-sm font-mono text-cyan-300">
            {prodA_id} ➜ {prodB_id}
          </p>
          {jobStatus === 'polling' && (
            <p className="text-xs font-mono text-slate-500 mt-2 animate-pulse">Running sub-pixel tie-point alignment</p>
          )}
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
      {/* Top Header & Breadcrumb */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1e2d42] pb-4">
        <div>
          <h2 className="text-xl font-display font-bold text-white flex items-center space-x-2">
            <span>Match review:</span>
            <span className="font-mono text-cyan-300 text-base">{prodA_id} ➜ {prodB_id}</span>
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Sub-pixel tie-point verification and spatial coverage heatmap inspection.
          </p>
        </div>

        {/* View Mode Toggle Pill Bar */}
        <div className="flex items-center space-x-1 bg-[#101724] border border-[#203046] p-1 rounded-lg font-mono text-xs">
          <button
            onClick={() => setViewMode('overlay')}
            className={`px-3 py-1.5 rounded-md transition ${viewMode === 'overlay' ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/60 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}
          >
            RGB Overlay
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
                  checked={showAllKeypoints}
                  onChange={(e) => setShowAllKeypoints(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-0"
                />
                <span className="text-slate-300">TIE-POINTS LAYER (GeoJSON)</span>
              </label>
            </div>
            <div className="text-slate-500 text-[11px]">FOV: AUTO</div>
          </div>

          {/* Interactive Match Visual Viewer Canvas */}
          <div className="relative bg-[#090d14] border border-[#1e2d42] rounded-xl h-[500px] overflow-hidden flex items-center justify-center p-2">
            
            {/* View Mode: OVERLAY RGB */}
            {viewMode === 'overlay' && (
              <div className="relative w-full h-full flex flex-col items-center justify-center">
                <img 
                  src={`http://127.0.0.1:8000/jobs/${jobId}/artefacts/overlay_rgb.png`}
                  alt="RGB Overlay"
                  className="max-w-full max-h-full object-contain shadow-2xl rounded-lg"
                />
                <div className="absolute top-3 left-3 px-2 py-1 rounded bg-black/80 border border-[#1e2d42] text-[10px] font-mono text-slate-300 space-y-1">
                  <div><span className="text-red-400 font-bold">RED:</span> Reference (B)</div>
                  <div><span className="text-green-400 font-bold">GREEN:</span> Moving (A)</div>
                  {showAllKeypoints && geoJson && (
                    <div className="mt-2 text-cyan-300 pt-2 border-t border-slate-700">
                      Loaded {geoJson.features?.length || 0} tie-points from GeoJSON.<br/>
                      <span className="text-slate-500 text-[9px]">(Projection to pixel-space required for drawing)</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Action Button Controls Footer */}
          <div className="flex items-center justify-between pt-2">
            <button onClick={onBack} className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-red-950/40 hover:bg-red-950/70 border border-red-800/60 text-red-300 text-xs font-mono transition">
              <XCircle className="w-4 h-4" />
              <span>Reject match</span>
            </button>

            <button
              onClick={() => onAcceptMatch(jobId)}
              className="flex items-center space-x-2 px-6 py-2.5 rounded-lg glow-btn-cyan text-xs font-mono font-bold tracking-wide transition"
            >
              <span>Accept &amp; Proceed to Evidence ➜</span>
              <CheckCircle2 className="w-4 h-4" />
            </button>
          </div>

        </div>

        {/* Right Column: Spatial Heatmap & Error Metrics Panel */}
        <div className="space-y-4">
          
          {/* Spatial Distribution / GeoJSON features */}
          <div className="glass-panel p-4 rounded-xl border border-[#203046] space-y-3">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-slate-300 font-semibold">TIE-POINTS (GEOJSON)</span>
              <span className="text-cyan-400 font-bold">{geoJson?.features?.length || 0} found</span>
            </div>

            <div className="bg-[#0b0f17] p-4 rounded-lg border border-[#1b273a] text-center text-slate-400 font-mono text-[10px]">
              <Grid className="w-8 h-8 mx-auto mb-2 text-slate-600" />
              <p>Spatial Grid Heatmap is disabled.</p>
              <p className="mt-1 text-slate-500">Real coordinate mapping requires image bounds.</p>
            </div>

            <p className="text-[11px] font-mono text-slate-400 leading-tight">
              Tiepoints extracted via `{metrics?.matcher || 'matcher'}` engine. Coordinates stored natively as [lon, lat] in GeoJSON artefact.
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
                <span className="text-slate-200 font-semibold">{safeNum(metrics?.total_matches, 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Inliers Count:</span>
                <span className="text-emerald-400 font-semibold">{safeNum(metrics?.inlier_count, 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Match Ratio:</span>
                <span className="text-emerald-400 font-semibold">
                  {metrics?.inlier_ratio !== undefined && metrics?.inlier_ratio !== null ? safeNum(metrics.inlier_ratio * 100, 1) + '%' : 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Sub-Pixel RMSE:</span>
                <span className="text-cyan-300 font-bold text-sm">{safeNum(metrics?.reprojection_residual, 3)} px</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Image Coverage:</span>
                <span className="text-amber-400 font-semibold">{safeNum((metrics?.occupied_fraction || 0) * 100, 1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Runtime:</span>
                <span className="text-slate-300">{safeNum(metrics?.runtime_s, 2)} s</span>
              </div>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
