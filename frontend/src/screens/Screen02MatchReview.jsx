import React, { useState, useEffect } from 'react';
import { CheckCircle2, XCircle, Grid, Loader2, AlertTriangle, ArrowLeft } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

export default function Screen02MatchReview({ selectedProductA, selectedProductB, selectedRung, completedJobId, onAcceptMatch, onBack }) {
  const [showAllKeypoints, setShowAllKeypoints] = useState(true);

  const [jobStatus, setJobStatus] = useState('registering'); // registering, polling, fetching_artefacts, ready, failed
  const [jobId, setJobId] = useState(completedJobId || null);
  const [metrics, setMetrics] = useState(null);
  const [geoJson, setGeoJson] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  const rungInt = selectedRung != null ? selectedRung : 1;
  // Display label only -- honest, just not the raw internal id. Never
  // rename this to a real product id (e.g. "d32"/"M1499112398LE"): that
  // would misrepresent synthetic validation data as a real registration.
  const displayName = (id) => id === 'synthetic_a' ? 'Validation Pair A'
    : id === 'synthetic_b' ? 'Validation Pair B' : id;
  const prodA_id = displayName(selectedProductA?.product_id) || 'Unknown Product';
  const prodB_id = displayName(selectedProductB?.product_id) || 'Unknown Product';

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
        const res = await fetch(`${API_BASE}/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            product_a: selectedProductA.product_id,
            product_b: selectedProductB.product_id,
            rung: rungInt
          })
        });

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || `Failed to register job. Status: ${res.status}`);
        }

        const data = await res.json();
        const newJobId = data.job_id;
        if (isMounted) {
          setJobId(newJobId);
          setJobStatus('polling');
        }

        pollInterval = setInterval(async () => {
          try {
            const pollRes = await fetch(`${API_BASE}/jobs/${newJobId}`);
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

        const metricsRes = await fetch(`${API_BASE}/jobs/${id}/artefacts/metrics.json`);
        if (!metricsRes.ok) throw new Error("Failed to fetch metrics.json");
        const metricsData = await metricsRes.json();

        const geoRes = await fetch(`${API_BASE}/jobs/${id}/artefacts/match_points.geojson`);
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
        <h2 className="text-xl font-bold text-slate-200">Job Failed</h2>
        <p className="text-slate-500 font-mono text-sm">{errorMsg}</p>
        <button onClick={onBack} className="mt-4 flex items-center space-x-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-md transition">
          <ArrowLeft className="w-4 h-4" />
          <span>Return to Selection</span>
        </button>
      </div>
    );
  }

  if (jobStatus !== 'ready') {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] space-y-6 animate-fadeIn">
        <Loader2 className="w-10 h-10 animate-spin text-cyan-500" />
        <div className="text-center space-y-2">
          <h2 className="text-lg font-display font-semibold text-slate-200">
            {jobStatus === 'registering' && "Registering Match Job..."}
            {jobStatus === 'polling' && "Executing Pipeline..."}
            {jobStatus === 'fetching_artefacts' && "Retrieving Artifacts..."}
          </h2>
          <p className="text-sm font-mono text-cyan-400">
            {prodA_id} → {prodB_id}
          </p>
          {jobStatus === 'polling' && (
            <p className="text-xs font-mono text-slate-500 mt-2">Running sub-pixel tie-point alignment — this can take a while on real, full-resolution imagery.</p>
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
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#2a2a2a] pb-4">
        <div>
          <h2 className="text-lg font-display font-semibold text-slate-200 flex items-center space-x-2">
            <span>Match review:</span>
            <span className="font-mono text-cyan-400 text-base">{prodA_id} → {prodB_id}</span>
          </h2>
          <p className="text-xs text-slate-500 font-mono mt-0.5">
            Sub-pixel tie-point verification and spatial coverage heatmap inspection.
          </p>
        </div>
      </div>

      {metrics?.trivial_fit && (
        <div className="flex items-start space-x-3 bg-amber-950/30 border border-amber-800 rounded-md p-4">
          <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
          <div className="text-xs font-mono text-amber-200 leading-relaxed">
            <span className="font-bold">Untrustworthy fit.</span> The inliers reduced to at most 4 unique locations —
            a homography's 8 degrees of freedom can be satisfied exactly by 4 points regardless of whether they're
            real correspondences. Do not read the numbers below as a validated registration.
          </div>
        </div>
      )}

      {/* Main Viewport & Right Metrics Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          {/* Secondary Feature Filter Toggle */}
          <div className="flex items-center justify-between bg-[#141414] border border-[#2a2a2a] px-4 py-2 rounded-md text-xs font-mono">
            <label className="flex items-center space-x-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={showAllKeypoints}
                onChange={(e) => setShowAllKeypoints(e.target.checked)}
                className="rounded border-slate-600 text-cyan-500 focus:ring-0"
              />
              <span className="text-slate-400">TIE-POINTS LAYER (GeoJSON)</span>
            </label>
            <div className="text-slate-600 text-[11px]">FOV: AUTO</div>
          </div>

          {/* Interactive Match Visual Viewer */}
          <div className="relative bg-[#141414] border border-[#2a2a2a] rounded-md h-[500px] overflow-hidden flex items-center justify-center p-2">
            <div className="relative w-full h-full flex flex-col items-center justify-center">
              <img
                src={`${API_BASE}/jobs/${jobId}/artefacts/overlay_rgb.png`}
                alt="RGB Overlay"
                className="max-w-full max-h-full object-contain rounded-md"
              />
              <div className="absolute top-3 left-3 px-2 py-1.5 rounded-md bg-[#141414]/95 border border-[#2a2a2a] text-[10px] font-mono text-slate-400 space-y-1">
                <div><span className="text-red-500 font-semibold">RED:</span> Reference (B)</div>
                <div><span className="text-green-700 font-semibold">GREEN:</span> Moving (A)</div>
                {showAllKeypoints && geoJson && (
                  <div className="mt-1.5 text-cyan-400 pt-1.5 border-t border-[#2a2a2a]">
                    Loaded {geoJson.features?.length || 0} tie-points from GeoJSON.<br />
                    <span className="text-slate-600 text-[9px]">(Projection to pixel-space required for drawing)</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Action Button Controls Footer */}
          <div className="flex items-center justify-between pt-2">
            <button onClick={onBack} className="flex items-center space-x-2 px-4 py-2 rounded-md bg-red-950/40 hover:bg-red-900/40 border border-red-800 text-red-400 text-xs font-mono transition">
              <XCircle className="w-4 h-4" />
              <span>Reject match</span>
            </button>

            <button
              onClick={() => onAcceptMatch(jobId)}
              className="flex items-center space-x-2 px-6 py-2.5 rounded-md glow-btn-cyan text-xs font-mono font-semibold transition"
            >
              <span>Accept &amp; Proceed to Evidence</span>
              <CheckCircle2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Right Column: Spatial Heatmap & Error Metrics Panel */}
        <div className="space-y-4">
          <div className="glass-panel p-4 space-y-3">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-slate-400 font-semibold">TIE-POINTS (GEOJSON)</span>
              <span className="text-cyan-400 font-semibold">{geoJson?.features?.length || 0} found</span>
            </div>

            <div className="bg-[#0a0a0a] p-4 rounded-md border border-[#2a2a2a] text-center text-slate-500 font-mono text-[10px]">
              <Grid className="w-8 h-8 mx-auto mb-2 text-slate-600" />
              <p>Spatial grid heatmap is disabled.</p>
              <p className="mt-1 text-slate-600">Real coordinate mapping requires image bounds.</p>
            </div>

            <p className="text-[11px] font-mono text-slate-500 leading-tight">
              Tiepoints extracted via `{metrics?.matcher || 'matcher'}` engine. Coordinates stored natively as [lon, lat] in GeoJSON artefact.
            </p>
          </div>

          {/* Sub-Pixel Metrics Breakdown Card */}
          <div className="glass-panel p-4 space-y-3 font-mono text-xs">
            <div className="text-slate-400 font-semibold border-b border-[#2a2a2a] pb-2">
              MATCH QUALITY METRICS
            </div>

            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-500">Total Matches:</span>
                <span className="text-slate-200 font-medium">{safeNum(metrics?.total_matches, 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Inliers Count:</span>
                <span className="text-emerald-400 font-medium">{safeNum(metrics?.inlier_count, 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Match Ratio:</span>
                <span className="text-emerald-400 font-medium">
                  {metrics?.inlier_ratio !== undefined && metrics?.inlier_ratio !== null ? safeNum(metrics.inlier_ratio * 100, 1) + '%' : 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Sub-Pixel RMSE:</span>
                <span className="text-cyan-400 font-semibold text-sm">{safeNum(metrics?.reprojection_residual, 3)} px</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Image Coverage:</span>
                <span className="text-amber-500 font-medium">{safeNum((metrics?.occupied_fraction || 0) * 100, 1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Runtime:</span>
                <span className="text-slate-300">{safeNum(metrics?.runtime_s, 2)} s</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
