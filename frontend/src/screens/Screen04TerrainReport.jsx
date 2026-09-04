import React, { useState, useRef, useEffect } from 'react';
import { Globe, Sun, Download, AlertCircle, ArrowLeft } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

// Real deliverable files written by src/deliverable.py + src/cnet.py --
// nothing here is fabricated (no PDF report, no bundled .tar, no "GCP
// validation package" -- those don't exist in the pipeline).
const ARTEFACTS = [
  { file: 'registered_a_to_b.tif', label: 'Registered raster', desc: 'GeoTIFF warped into the reference frame' },
  { file: 'match_points.csv', label: 'Match points (CSV)', desc: 'Tie-points with pixel + geo coordinates' },
  { file: 'match_points.geojson', label: 'Match points (GeoJSON)', desc: 'Tie-point lines as GeoJSON' },
  { file: 'overlay_rgb.png', label: 'Overlay preview', desc: 'Red/green registered alignment' },
  { file: 'control_network.net', label: 'Control network', desc: 'ISIS PVL format, ready for jigsaw' },
  { file: 'metrics.json', label: 'Metrics', desc: 'RMSE, inliers, coverage, trivial_fit' },
];

export default function Screen04TerrainReport({ jobId, selectedProductA, selectedProductB, onBack }) {
  const [sunAzimuth, setSunAzimuth] = useState(118);
  const [sunElevation, setSunElevation] = useState(27);
  const canvas2DRef = useRef(null);

  const prodA_id = selectedProductA?.product_id || 'Unknown Product';
  const prodB_id = selectedProductB?.product_id || 'Unknown Product';

  // Illumination preview: a 2D canvas shading simulation, not a real 3D
  // terrain mesh -- src/render.py's real hillshade renderer works on a real
  // DEM offline (see demo/win_plot.png), it isn't wired into the live app.
  useEffect(() => {
    if (!canvas2DRef.current) return;
    const canvas = canvas2DRef.current;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#1c1c1c';
    ctx.fillRect(0, 0, w, h);

    const azRad = (sunAzimuth * Math.PI) / 180;
    const shadowLength = Math.tan((90 - sunElevation) * (Math.PI / 180)) * 20;
    const shadowX = Math.cos(azRad) * shadowLength;
    const shadowY = Math.sin(azRad) * shadowLength;

    const cx = w * 0.45, cy = h * 0.48, radius = 80;
    ctx.beginPath();
    ctx.ellipse(cx + shadowX * 0.6, cy + shadowY * 0.6, radius * 0.95, radius * 0.7, azRad, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(90, 78, 58, 0.35)';
    ctx.fill();

    const lightX = cx - Math.cos(azRad) * radius;
    const lightY = cy - Math.sin(azRad) * radius;
    const grad = ctx.createRadialGradient(lightX, lightY, 10, cx, cy, radius);
    grad.addColorStop(0, '#ffffff');
    grad.addColorStop(0.6, '#2a2a2a');
    grad.addColorStop(1, '#333333');
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.strokeStyle = '#3a3a3a';
    ctx.lineWidth = 2;
    ctx.stroke();
  }, [sunAzimuth, sunElevation]);

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#2a2a2a] pb-4">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            {onBack && (
              <button onClick={onBack} className="p-1.5 bg-[#1c1c1c] hover:bg-[#242424] rounded-md transition-colors border border-[#2a2a2a]">
                <ArrowLeft className="w-4 h-4 text-cyan-400" />
              </button>
            )}
            <h2 className="text-lg font-display font-semibold text-slate-200 flex items-center space-x-2">
              <Globe className="w-5 h-5 text-cyan-400" />
              <span>Terrain &amp; export</span>
            </h2>
          </div>
          <p className="text-xs text-slate-500 font-mono mt-0.5 ml-11">
            Illumination preview and the registration deliverable for this job.
          </p>
        </div>

        {selectedProductA && selectedProductB && (
          <div className="flex items-center space-x-2 text-xs font-mono text-slate-500 bg-[#141414] border border-[#2a2a2a] px-3 py-1.5 rounded-md">
            <span className="text-slate-600">PAIRED:</span>
            <span className="text-cyan-400 font-medium">{prodA_id} &amp; {prodB_id}</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="relative bg-[#141414] border border-[#2a2a2a] rounded-md h-[360px] overflow-hidden flex items-center justify-center">
            <canvas ref={canvas2DRef} width={600} height={360} className="w-full h-full object-cover" />

            <div className="absolute top-4 left-4 bg-[#141414]/90 border border-[#2a2a2a] p-3 rounded-md text-xs font-mono">
              <div className="text-cyan-400 font-semibold">Illumination preview</div>
              <div className="text-slate-500 text-[11px]">Sun-angle shading simulation, not a live 3D terrain mesh</div>
            </div>

            <div className="absolute bottom-4 left-4 bg-[#141414]/95 border border-[#2a2a2a] p-4 rounded-md text-xs font-mono space-y-3 w-72">
              <div className="flex items-center justify-between text-cyan-400 font-semibold">
                <span className="flex items-center space-x-1.5">
                  <Sun className="w-4 h-4 text-amber-500" />
                  <span>Sun angle</span>
                </span>
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span>AZIMUTH:</span>
                  <span>{sunAzimuth}°</span>
                </div>
                <input type="range" min="0" max="360" value={sunAzimuth}
                  onChange={(e) => setSunAzimuth(Number(e.target.value))}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-500" />
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span>ELEVATION:</span>
                  <span>{sunElevation}°</span>
                </div>
                <input type="range" min="5" max="85" value={sunElevation}
                  onChange={(e) => setSunElevation(Number(e.target.value))}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-500" />
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="glass-panel p-5 space-y-3 font-mono text-xs">
            <div className="text-slate-400 font-semibold uppercase tracking-wide border-b border-[#2a2a2a] pb-2">
              DELIVERABLE ARTEFACTS
            </div>

            {!jobId ? (
              <div className="flex items-center space-x-2 text-slate-500 text-[11px] py-4">
                <AlertCircle className="w-4 h-4" />
                <span>No completed job yet.</span>
              </div>
            ) : (
              <div className="space-y-2">
                {ARTEFACTS.map((a) => (
                  <a
                    key={a.file}
                    href={`${API_BASE}/jobs/${jobId}/artefacts/${a.file}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-start justify-between space-x-3 p-2.5 rounded-md bg-[#141414] border border-[#2a2a2a] hover:border-cyan-500/60 transition group"
                  >
                    <div>
                      <div className="text-slate-300 font-medium group-hover:text-cyan-400">{a.label}</div>
                      <div className="text-[11px] text-slate-500">{a.desc}</div>
                    </div>
                    <Download className="w-4 h-4 text-slate-600 group-hover:text-cyan-500 shrink-0 mt-0.5" />
                  </a>
                ))}
              </div>
            )}

            <div className="p-3 rounded-md bg-cyan-950/40 border border-cyan-800 text-[11px] text-cyan-300 leading-relaxed">
              Control network is written to the documented ISIS PVL spec and round-trips through an
              independent parser. Not yet validated by running ISIS jigsaw itself.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
