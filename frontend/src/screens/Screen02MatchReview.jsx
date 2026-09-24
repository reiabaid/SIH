import React, { useState, useEffect } from 'react';
import { CheckCircle2, XCircle, Grid, Loader2, AlertTriangle, ArrowLeft } from 'lucide-react';

const API_BASE = import.meta.env.PROD ? '' : 'http://127.0.0.1:8000';

export default function Screen02MatchReview({ selectedProductA, selectedProductB, selectedRung, completedJobId, onAcceptMatch, onBack }) {
  const [showAllKeypoints, setShowAllKeypoints] = useState(true);
  const [tallOverlay, setTallOverlay] = useState(false); // set from the loaded overlay's aspect ratio

  const [jobStatus, setJobStatus] = useState('registering'); // registering, polling, fetching_artefacts, ready, failed
  const [jobId, setJobId] = useState(completedJobId || null);
  const [metrics, setMetrics] = useState(null);
  const [geoJson, setGeoJson] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  // Real backend-reported stage (src/api.py's `stage` column, updated as
  // process_job_sync actually progresses) -- not simulated. `polling` alone
  // used to mean "somewhere between register and completed" with zero
  // detail, which reads as a frozen/broken UI on a real, slower pair.
  const [backendStage, setBackendStage] = useState(null);

  // Guards against React 18 StrictMode's dev-only double-invoke of this
  // effect: without it, the second invocation re-runs startJob() before the
  // first's cleanup can cancel it (pollInterval is only assigned *after* an
  // await, so the first cleanup fires while it's still null and never clears
  // it) -- verified this session: two real /register jobs got created for
  // the same pair, and running two full-resolution CH2 loads concurrently
  // starved both (6 minutes instead of ~30s). A ref survives the synchronous
  // mount->cleanup->mount cycle, so the second invocation for the same
  // inputs sees it's already started and skips re-registering.
  //
  // pollIntervalRef is *shared* across invocations rather than a local `let`
  // inside the effect, for the same reason: StrictMode's synthetic cleanup
  // for the first invocation runs before its own local variable would ever
  // be assigned, so a per-invocation `isMounted`/`pollInterval` pair either
  // discards the real result (if state updates check a since-falsified
  // `isMounted`) or leaks the interval (if the second, early-returning
  // invocation registers no cleanup for it). A shared ref lets every
  // invocation's cleanup clear whatever interval is actually live.
  const startedForKeyRef = React.useRef(null);
  const pollIntervalRef = React.useRef(null);

  const rungInt = selectedRung != null ? selectedRung : 1;
  // Display label only -- honest, just not the raw internal id. Never
  // rename this to a real product id (e.g. "d32"/"M1499112398LE"): that
  // would misrepresent synthetic validation data as a real registration.
  const displayName = (id) => id === 'synthetic_a' ? 'Validation Pair A'
    : id === 'synthetic_b' ? 'Validation Pair B' : id;
  const prodA_id = displayName(selectedProductA?.product_id) || 'Unknown Product';
  const prodB_id = displayName(selectedProductB?.product_id) || 'Unknown Product';

  useEffect(() => {
    const key = `${selectedProductA?.product_id}|${selectedProductB?.product_id}|${rungInt}|${completedJobId}`;
    const isDuplicateInvocation = startedForKeyRef.current === key;
    if (!isDuplicateInvocation) {
      startedForKeyRef.current = key;

      const startJob = async () => {
        if (!selectedProductA || !selectedProductB) {
          setErrorMsg("Missing selected products.");
          setJobStatus('failed');
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
          setJobId(newJobId);
          setJobStatus('polling');

          pollIntervalRef.current = setInterval(async () => {
            try {
              const pollRes = await fetch(`${API_BASE}/jobs/${newJobId}`);
              if (!pollRes.ok) throw new Error("Failed to poll job status.");
              const pollData = await pollRes.json();
              if (pollData.stage) setBackendStage(pollData.stage);

              if (pollData.status === 'completed') {
                clearInterval(pollIntervalRef.current);
                fetchArtefacts(newJobId);
              } else if (pollData.status === 'failed') {
                clearInterval(pollIntervalRef.current);
                setErrorMsg("Pipeline execution failed on the backend.");
                setJobStatus('failed');
              }
            } catch (pollErr) {
              clearInterval(pollIntervalRef.current);
              setErrorMsg(pollErr.message || "Polling error occurred.");
              setJobStatus('failed');
            }
          }, 2000);

        } catch (err) {
          setErrorMsg(err.message || "Failed to register job.");
          setJobStatus('failed');
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

          setMetrics(metricsData);
          setGeoJson(geoData);
          setJobStatus('ready');
        } catch (err) {
          setErrorMsg(err.message || "Failed to fetch artefacts.");
          setJobStatus('failed');
        }
      };

      if (completedJobId) {
        setJobId(completedJobId);
        fetchArtefacts(completedJobId);
      } else {
        startJob();
      }
    }

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
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
    // Real, backend-reported pipeline stages (src/api.py's `stage` column,
    // written as process_job_sync actually progresses -- not a client-side
    // timer or guess). Index is derived from jobStatus + backendStage
    // together so registering/fetching (client-only phases) and the
    // backend's own three real stages all land on one continuous stepper.
    const PIPELINE_STEPS = [
      { key: 'registering', label: 'Registering job' },
      { key: 'loading_products', label: 'Loading real ISRO imagery' },
      { key: 'aligning_and_matching', label: 'Aligning & matching tie-points' },
      { key: 'writing_deliverable', label: 'Writing registered raster' },
      { key: 'fetching_artefacts', label: 'Retrieving results' },
    ];
    const currentKey = jobStatus === 'registering' ? 'registering'
      : jobStatus === 'fetching_artefacts' ? 'fetching_artefacts'
      : (backendStage || 'loading_products'); // polling with no stage yet == just started loading
    const currentIndex = PIPELINE_STEPS.findIndex(s => s.key === currentKey);

    return (
      <div className="flex flex-col items-center justify-center h-[60vh] space-y-8 animate-fadeIn">
        <div className="text-center space-y-1">
          <p className="text-sm font-mono text-cyan-400">{prodA_id} → {prodB_id}</p>
          <p className="text-[11px] font-mono text-slate-600">Live pipeline status, reported directly from the backend job.</p>
        </div>

        <div className="w-full max-w-md space-y-3">
          {PIPELINE_STEPS.map((step, i) => {
            const done = i < currentIndex;
            const active = i === currentIndex;
            return (
              <div key={step.key} className="flex items-center space-x-3">
                <div className="shrink-0 w-6 h-6 flex items-center justify-center">
                  {done && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
                  {active && <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />}
                  {!done && !active && <div className="w-2 h-2 rounded-full bg-slate-700" />}
                </div>
                <span className={`text-sm font-mono ${
                  done ? 'text-slate-500' : active ? 'text-slate-200 font-semibold' : 'text-slate-600'
                }`}>
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>

        {currentKey === 'aligning_and_matching' && (
          <p className="text-xs font-mono text-slate-500 max-w-md text-center">
            Sub-pixel tie-point alignment on real, full-resolution imagery — this is the longest step.
          </p>
        )}
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

      {/* Cross-check between independent matchers (Auto runs both SIFT and the
          Log-Gabor descriptor): one fit alone can look well-determined and still be
          wrong, agreement between two is the real evidence. */}
      {metrics?.agreement && !metrics?.trivial_fit && (
        metrics.agreement.status === 'consistent' ? (
          <div className="text-xs font-mono text-emerald-300 bg-emerald-950/30 border border-emerald-800 rounded-md p-3">
            <span className="font-bold">Cross-checked.</span> SIFT and the Log-Gabor matcher independently agree to within
            {' '}{metrics.agreement.gap_px} px (~{metrics.agreement.gap_m} m).
          </div>
        ) : metrics.agreement.status === 'inconsistent' ? (
          <div className="text-xs font-mono text-red-300 bg-red-950/30 border border-red-800 rounded-md p-3">
            <span className="font-bold">Matchers disagree.</span> SIFT and the Log-Gabor matcher each found a fit, but they
            differ by {metrics.agreement.gap_px} px (~{metrics.agreement.gap_m} m). At least one is wrong — do not rely on this
            registration without independent verification.
          </div>
        ) : (
          <div className="text-xs font-mono text-slate-300 bg-slate-900/40 border border-slate-700 rounded-md p-3">
            <span className="font-bold">Not cross-checked.</span> Only one matcher produced a well-determined fit, so there is
            nothing independent to compare it against.
          </div>
        )
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
          {/* A real LRO NAC strip is far taller than wide; fit-to-box (object-contain)
              shrinks it to a sliver, so tall overlays scroll at full viewer width
              instead. Squarer overlays (e.g. the synthetic demo) keep fit-to-box.
              The legend sits outside the scroller so it stays put while panning. */}
          <div className="relative bg-[#141414] border border-[#2a2a2a] rounded-md h-[500px] overflow-hidden">
            <div className={`w-full h-full p-2 ${tallOverlay ? 'overflow-y-auto' : 'flex items-center justify-center'}`}>
              <img
                src={`${API_BASE}/jobs/${jobId}/artefacts/overlay_rgb.png`}
                alt="RGB Overlay"
                onLoad={(e) => setTallOverlay(e.target.naturalHeight > 1.5 * e.target.naturalWidth)}
                className={tallOverlay ? 'w-full h-auto rounded-md' : 'max-w-full max-h-full object-contain rounded-md'}
              />
            </div>
            <div className="absolute top-3 left-3 px-2 py-1.5 rounded-md bg-[#141414]/95 border border-[#2a2a2a] text-[10px] font-mono text-slate-400 space-y-1">
              <div><span className="text-red-500 font-semibold">RED:</span> Reference (B)</div>
              <div><span className="text-green-700 font-semibold">GREEN:</span> Moving (A)</div>
              {tallOverlay && (
                <div className="text-slate-500">Scroll to pan along the strip</div>
              )}
              {showAllKeypoints && geoJson && (
                <div className="mt-1.5 text-cyan-400 pt-1.5 border-t border-[#2a2a2a]">
                  Loaded {geoJson.features?.length || 0} tie-points from GeoJSON.<br />
                  <span className="text-slate-600 text-[9px]">(Projection to pixel-space required for drawing)</span>
                </div>
              )}
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
              <span className="text-slate-400 font-semibold">SPATIAL HEATMAP</span>
              <span className="text-cyan-400 font-semibold">{metrics?.grid_counts ? '8×8' : 'N/A'}</span>
            </div>

            {metrics?.grid_counts ? (
              <div className="bg-[#0a0a0a] p-3 rounded-md border border-[#2a2a2a]">
                <div className="grid grid-cols-8 gap-0.5">
                  {metrics.grid_counts.flat().map((count, i) => {
                    const maxCount = Math.max(...metrics.grid_counts.flat());
                    const intensity = maxCount > 0 ? count / maxCount : 0;
                    const bg = count === 0
                      ? 'bg-[#1a1a1a]'
                      : intensity > 0.7
                        ? 'bg-cyan-600'
                        : intensity > 0.4
                          ? 'bg-cyan-800'
                          : 'bg-cyan-950';
                    return (
                      <div
                        key={i}
                        className={`aspect-square rounded-sm flex items-center justify-center text-[8px] font-mono ${bg} ${count > 0 ? 'text-white' : 'text-slate-700'}`}
                        title={`Cell ${Math.floor(i / 8) + 1},${(i % 8) + 1}: ${count} inliers`}
                      >
                        {count}
                      </div>
                    );
                  })}
                </div>
                <div className="flex justify-between mt-2 text-[9px] font-mono text-slate-600">
                  <span>Coverage: {safeNum((metrics?.occupied_fraction || 0) * 100, 1)}%</span>
                  <span>CV: {safeNum(metrics?.coefficient_of_variation, 2)}</span>
                </div>
              </div>
            ) : (
              <div className="bg-[#0a0a0a] p-4 rounded-md border border-[#2a2a2a] text-center text-slate-500 font-mono text-[10px]">
                <Grid className="w-8 h-8 mx-auto mb-2 text-slate-600" />
                <p>Spatial grid heatmap not available.</p>
                <p className="mt-1 text-slate-600">Requires grid_counts in metrics.json.</p>
              </div>
            )}

            <p className="text-[11px] font-mono text-slate-500 leading-tight">
              Tiepoints extracted via `{metrics?.matcher || 'matcher'}` engine. 8×8 grid cells with inlier counts.
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
                <span className="text-slate-500" title="How well the matched points fit the fitted transform. Not the registration accuracy against the true position.">Fit residual:</span>
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
