import React, { useState } from 'react';
import { Globe, FileText, ArrowLeft, AlertTriangle, Mountain, DownloadCloud } from 'lucide-react';

export default function Screen04TerrainReport({ jobId, selectedProductA, selectedProductB, onBack }) {
  const [selectedExports, setSelectedExports] = useState({
    raster: true,
    points: true,
    metrics: true
  });

  const prodA_id = selectedProductA?.product_id || 'Unknown Product';
  const prodB_id = selectedProductB?.product_id || 'Unknown Product';
  
  const resA = selectedProductA?.resolution_m ? Number(selectedProductA.resolution_m).toFixed(2) : 'N/A';
  const resB = selectedProductB?.resolution_m ? Number(selectedProductB.resolution_m).toFixed(2) : 'N/A';

  const handleDownloadAvailable = () => {
    if (!jobId) return;
    const baseUrl = `http://127.0.0.1:8000/jobs/${jobId}/artefacts`;
    
    if (selectedExports.raster) {
      window.open(`${baseUrl}/registered_a_to_b.tif`, '_blank');
      window.open(`${baseUrl}/overlay_rgb.png`, '_blank');
    }
    if (selectedExports.points) {
      window.open(`${baseUrl}/match_points.csv`, '_blank');
      window.open(`${baseUrl}/match_points.geojson`, '_blank');
    }
    if (selectedExports.metrics) {
      window.open(`${baseUrl}/metrics.json`, '_blank');
    }
  };

  const toggleExport = (key) => {
    setSelectedExports((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1e2d42] pb-4">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <button onClick={onBack} className="p-1.5 bg-[#1a2536] hover:bg-[#203046] rounded-lg transition-colors border border-[#2a3a56]">
              <ArrowLeft className="w-4 h-4 text-cyan-300" />
            </button>
            <h2 className="text-xl font-display font-bold text-white flex items-center space-x-2">
              <Globe className="w-5 h-5 text-cyan-400" />
              <span>04 - Registration Deliverables</span>
            </h2>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5 ml-11">
            Download and export successfully aligned artifacts and match data.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono text-slate-400 bg-[#101724] border border-[#203046] px-3 py-1.5 rounded-lg">
          <span className="text-slate-500">PAIRED:</span>
          <span className="text-cyan-300 font-semibold">{prodA_id} &amp; {prodB_id}</span>
        </div>
      </div>

      {/* Main Grid: Info Viewport & Export Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left 2 Columns: Offline Limitation Info Panel */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-[#090d14] border border-[#1e2d42] rounded-xl h-[400px] flex flex-col items-center justify-center p-8 text-center space-y-4">
            <Mountain className="w-16 h-16 text-slate-700 mx-auto" />
            <div>
              <h3 className="text-white font-bold font-display text-lg">3D Terrain Generation is Offline</h3>
              <p className="text-slate-400 text-sm mt-2 max-w-md mx-auto">
                The creation of 3D Digital Elevation Models (DEMs) and synthetic Hillshade renders requires the offline ISIS photogrammetry pipeline. The current registration job is constrained to 2D image-to-image matching.
              </p>
            </div>
            <div className="p-3 mt-4 rounded-lg bg-amber-950/20 border border-amber-900/50 flex items-start space-x-3 text-left max-w-md">
              <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-400/80 leading-relaxed">
                DEM synthesis, slope/elevation extraction, and 3D hillshade generation are not currently generated per-job by the backend API. Please download the 2D registration artifacts instead.
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Export Panel */}
        <div className="space-y-4">
          <div className="glass-panel p-5 rounded-xl border border-[#203046] space-y-4 font-mono text-xs">
            <div className="text-cyan-300 font-semibold uppercase tracking-wider border-b border-[#1e2d42] pb-2 flex justify-between items-center">
              <span>EXPORT ARTIFACTS</span>
            </div>

            {/* Checkbox List */}
            <div className="space-y-3">
              
              {/* Disabled Offline Option */}
              <label className="flex items-start space-x-3 p-2.5 rounded-lg bg-[#0e1522] border border-[#1b283d] opacity-50 cursor-not-allowed select-none">
                <input
                  type="checkbox"
                  disabled
                  checked={false}
                  className="mt-0.5 rounded border-slate-700 bg-slate-900"
                />
                <div className="w-full">
                  <div className="flex justify-between items-center w-full">
                    <span className="text-slate-400 font-semibold">Control network</span>
                    <span className="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded font-bold">OFFLINE ONLY</span>
                  </div>
                  <div className="text-[11px] text-slate-500">ISIS / PDS format (.net) via `cnet.py`</div>
                </div>
              </label>

              {/* Raster Option */}
              <label 
                onClick={() => toggleExport('raster')}
                className={`flex items-start space-x-3 p-2.5 rounded-lg border cursor-pointer transition select-none ${selectedExports.raster ? 'bg-[#0e1522] border-cyan-800/60' : 'bg-[#0b0f17] border-[#1b283d]'}`}
              >
                <input
                  type="checkbox"
                  checked={selectedExports.raster}
                  onChange={() => {}}
                  className="mt-0.5 rounded border-slate-700 bg-slate-900 text-cyan-500"
                />
                <div>
                  <div className="text-slate-200 font-semibold">Registered raster</div>
                  <div className="text-[11px] text-slate-400">GeoTIFF (`.tif`) &amp; Overlay (`.png`) output</div>
                </div>
              </label>

              {/* Points Option */}
              <label 
                onClick={() => toggleExport('points')}
                className={`flex items-start space-x-3 p-2.5 rounded-lg border cursor-pointer transition select-none ${selectedExports.points ? 'bg-[#0e1522] border-cyan-800/60' : 'bg-[#0b0f17] border-[#1b283d]'}`}
              >
                <input
                  type="checkbox"
                  checked={selectedExports.points}
                  onChange={() => {}}
                  className="mt-0.5 rounded border-slate-700 bg-slate-900 text-cyan-500"
                />
                <div>
                  <div className="text-slate-200 font-semibold">Match points</div>
                  <div className="text-[11px] text-slate-400">CSV &amp; GeoJSON format tiepoints</div>
                </div>
              </label>

              {/* Metrics Option */}
              <label 
                onClick={() => toggleExport('metrics')}
                className={`flex items-start space-x-3 p-2.5 rounded-lg border cursor-pointer transition select-none ${selectedExports.metrics ? 'bg-[#0e1522] border-cyan-800/60' : 'bg-[#0b0f17] border-[#1b283d]'}`}
              >
                <input
                  type="checkbox"
                  checked={selectedExports.metrics}
                  onChange={() => {}}
                  className="mt-0.5 rounded border-slate-700 bg-slate-900 text-cyan-500"
                />
                <div className="w-full">
                  <div className="flex justify-between items-center w-full">
                    <span className="text-slate-200 font-semibold">Metrics report</span>
                  </div>
                  <div className="text-[11px] text-slate-400">JSON metrics report</div>
                </div>
              </label>

            </div>

            {/* Validation Notice Box */}
            <div className="p-3 rounded-lg bg-cyan-950/40 border border-cyan-800/50 text-[11px] text-cyan-300 leading-relaxed break-all">
              Artifacts are generated directly by the backend for Job ID: {jobId ? jobId.substring(0, 8) + '...' : 'Unknown'}
            </div>

            {/* Primary Download All Button */}
            <button
              onClick={handleDownloadAvailable}
              disabled={!jobId}
              className={`w-full flex items-center justify-center space-x-2 py-3 rounded-xl text-xs font-mono font-bold tracking-wide transition ${jobId ? 'glow-btn-cyan' : 'bg-slate-800 text-slate-500 cursor-not-allowed'}`}
            >
              <DownloadCloud className="w-4 h-4" />
              <span>Download Selected Artifacts</span>
            </button>

            {/* Summary Footer */}
            <div className="text-[10px] text-slate-500 text-center space-y-0.5 pt-1 border-t border-[#1e2d42]">
              <div>Moving: A {resA} m • Reference: B {resB} m</div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
