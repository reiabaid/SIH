import React, { useState, useRef, useEffect } from 'react';
import { Globe, Sun, Download, FileText, CheckSquare, ShieldCheck, Compass, Sliders, CheckCircle2 } from 'lucide-react';
import { MOCK_DATASET } from '../data/mockLunarData';

export default function Screen04TerrainReport({ onOpenReportModal }) {
  const [sunAzimuth, setSunAzimuth] = useState(118); // 0 - 360 deg dial
  const [sunElevation, setSunElevation] = useState(27); // 0 - 90 deg slider
  const [selectedExports, setSelectedExports] = useState({
    cnet: true,
    raster: true,
    points: true,
    report: true
  });

  const canvas3DRef = useRef(null);

  // Render 3D Crater Hillshade Canvas driven by sun azimuth and elevation angles
  useEffect(() => {
    if (!canvas3DRef.current) return;

    const canvas = canvas3DRef.current;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Background Lunar surface
    ctx.fillStyle = '#0b1019';
    ctx.fillRect(0, 0, w, h);

    // Convert angles to radians
    const azRad = (sunAzimuth * Math.PI) / 180;
    const elRad = (sunElevation * Math.PI) / 180;

    const shadowLength = Math.tan((90 - sunElevation) * (Math.PI / 180)) * 20;
    const shadowX = Math.cos(azRad) * shadowLength;
    const shadowY = Math.sin(azRad) * shadowLength;

    // Draw Main Crater 1
    const cx = w * 0.45;
    const cy = h * 0.48;
    const radius = 80;

    // Shadow cast ellipse
    ctx.beginPath();
    ctx.ellipse(cx + shadowX * 0.6, cy + shadowY * 0.6, radius * 0.95, radius * 0.7, azRad, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(4, 7, 12, 0.85)';
    ctx.fill();

    // Crater Rim Lighting Gradient
    const lightX = cx - Math.cos(azRad) * radius;
    const lightY = cy - Math.sin(azRad) * radius;

    const grad = ctx.createRadialGradient(lightX, lightY, 10, cx, cy, radius);
    grad.addColorStop(0, '#384d6b');
    grad.addColorStop(0.6, '#182436');
    grad.addColorStop(1, '#0e1624');

    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.strokeStyle = '#283d5a';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Secondary Crater 2
    const c2x = w * 0.78;
    const c2y = h * 0.65;
    const r2 = 45;

    ctx.beginPath();
    ctx.ellipse(c2x + shadowX * 0.5, c2y + shadowY * 0.5, r2 * 0.9, r2 * 0.6, azRad, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(4, 7, 12, 0.85)';
    ctx.fill();

    ctx.beginPath();
    ctx.arc(c2x, c2y, r2, 0, Math.PI * 2);
    ctx.fillStyle = '#141e2e';
    ctx.fill();
    ctx.strokeStyle = '#22344d';
    ctx.stroke();

    // Sun Angle Indicator Line
    ctx.beginPath();
    ctx.moveTo(w - 60, 60);
    ctx.lineTo(w - 60 + Math.cos(azRad) * 30, 60 + Math.sin(azRad) * 30);
    ctx.strokeStyle = '#ffb703';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(w - 60, 60, 6, 0, Math.PI * 2);
    ctx.fillStyle = '#ffb703';
    ctx.fill();

  }, [sunAzimuth, sunElevation]);

  const toggleExport = (key) => {
    setSelectedExports((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1e2d42] pb-4">
        <div>
          <h2 className="text-xl font-display font-bold text-white flex items-center space-x-2">
            <Globe className="w-5 h-5 text-cyan-400" />
            <span>04 - Terrain &amp; report generator</span>
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Interactive 3D crater shadow simulation and ISIS Photogrammetry export suite.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono text-slate-400 bg-[#101724] border border-[#203046] px-3 py-1.5 rounded-lg">
          <span className="text-slate-500">COORDINATES:</span>
          <span className="text-cyan-300 font-semibold">69.37°S, 32.35°E</span>
          <span>(CH3 LANDING POINT)</span>
        </div>
      </div>

      {/* Main Grid: 3D Viewport & Export Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left 2 Columns: 3D Crater Viewport & Solar Controls */}
        <div className="lg:col-span-2 space-y-4">
          
          {/* 3D WebGL Canvas Viewport */}
          <div className="relative bg-[#090d14] border border-[#1e2d42] rounded-xl h-[400px] overflow-hidden flex items-center justify-center">
            
            <canvas
              ref={canvas3DRef}
              width={600}
              height={400}
              className="w-full h-full object-cover"
            />

            {/* Viewport Info Overlay Top Left */}
            <div className="absolute top-4 left-4 bg-black/70 backdrop-blur-md border border-[#1e2d42] p-3 rounded-lg text-xs font-mono space-y-1">
              <div className="text-cyan-300 font-semibold">NASA SLDEM2015 HILLSHADE MODEL</div>
              <div className="text-slate-400 text-[11px]">Chandrayaan-3 South Pole Crater Cluster</div>
              <div className="flex space-x-3 text-[10px] text-slate-500 pt-1 border-t border-[#1b283d]">
                <span>SCALE: 250 m/pix</span>
                <span>GRID: 100 x 100 km</span>
              </div>
            </div>

            {/* Interactive Sun Azimuth Dial & Elevation Slider Controls Overlay Bottom Left */}
            <div className="absolute bottom-4 left-4 bg-black/80 backdrop-blur-md border border-cyan-800/60 p-4 rounded-xl text-xs font-mono space-y-3 w-72">
              <div className="flex items-center justify-between text-cyan-300 font-semibold">
                <span className="flex items-center space-x-1.5">
                  <Sun className="w-4 h-4 text-amber-400" />
                  <span>Solar Illumination Controls</span>
                </span>
                <span className="text-amber-400">{sunAzimuth}°</span>
              </div>

              {/* Sun Azimuth Dial Slider */}
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-slate-400">
                  <span>SUN AZIMUTH:</span>
                  <span>{sunAzimuth}° (Drag to rotate shadow)</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="360"
                  value={sunAzimuth}
                  onChange={(e) => setSunAzimuth(Number(e.target.value))}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                />
              </div>

              {/* Sun Elevation Slider */}
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-slate-400">
                  <span>SUN ELEVATION:</span>
                  <span>{sunElevation}°</span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="85"
                  value={sunElevation}
                  onChange={(e) => setSunElevation(Number(e.target.value))}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
                />
              </div>
            </div>

          </div>

        </div>

        {/* Right Column: Export Panel */}
        <div className="space-y-4">
          
          <div className="glass-panel p-5 rounded-xl border border-[#203046] space-y-4 font-mono text-xs">
            <div className="text-cyan-300 font-semibold uppercase tracking-wider border-b border-[#1e2d42] pb-2 flex justify-between items-center">
              <span>EXPORT ARTIFACTS</span>
              <span className="text-[10px] text-slate-400 font-normal">ISIS / PDS READY</span>
            </div>

            {/* Checkbox List */}
            <div className="space-y-3">
              
              <label 
                onClick={() => toggleExport('cnet')}
                className="flex items-start space-x-3 p-2.5 rounded-lg bg-[#0e1522] border border-[#1b283d] hover:border-cyan-800/60 cursor-pointer transition select-none"
              >
                <input
                  type="checkbox"
                  checked={selectedExports.cnet}
                  onChange={() => {}}
                  className="mt-0.5 rounded border-slate-700 bg-slate-900 text-cyan-500"
                />
                <div>
                  <div className="text-slate-200 font-semibold">Control network</div>
                  <div className="text-[11px] text-slate-400">ISIS / PDS format (.net) via `cnet.py`</div>
                </div>
              </label>

              <label 
                onClick={() => toggleExport('raster')}
                className="flex items-start space-x-3 p-2.5 rounded-lg bg-[#0e1522] border border-[#1b283d] hover:border-cyan-800/60 cursor-pointer transition select-none"
              >
                <input
                  type="checkbox"
                  checked={selectedExports.raster}
                  onChange={() => {}}
                  className="mt-0.5 rounded border-slate-700 bg-slate-900 text-cyan-500"
                />
                <div>
                  <div className="text-slate-200 font-semibold">Registered raster</div>
                  <div className="text-[11px] text-slate-400">GeoTIFF / PNG aligned output</div>
                </div>
              </label>

              <label 
                onClick={() => toggleExport('points')}
                className="flex items-start space-x-3 p-2.5 rounded-lg bg-[#0e1522] border border-[#1b283d] hover:border-cyan-800/60 cursor-pointer transition select-none"
              >
                <input
                  type="checkbox"
                  checked={selectedExports.points}
                  onChange={() => {}}
                  className="mt-0.5 rounded border-slate-700 bg-slate-900 text-cyan-500"
                />
                <div>
                  <div className="text-slate-200 font-semibold">Match points</div>
                  <div className="text-[11px] text-slate-400">CSV / GeoJSON format tiepoints</div>
                </div>
              </label>

              <label 
                onClick={() => toggleExport('report')}
                className="flex items-start space-x-3 p-2.5 rounded-lg bg-[#0e1522] border border-[#1b283d] hover:border-cyan-800/60 cursor-pointer transition select-none"
              >
                <input
                  type="checkbox"
                  checked={selectedExports.report}
                  onChange={() => {}}
                  className="mt-0.5 rounded border-slate-700 bg-slate-900 text-cyan-500"
                />
                <div>
                  <div className="text-slate-200 font-semibold">Metrics report</div>
                  <div className="text-[11px] text-slate-400">PDF / Evaluation summary report</div>
                </div>
              </label>

            </div>

            {/* Validation Notice Box */}
            <div className="p-3 rounded-lg bg-cyan-950/40 border border-cyan-800/50 text-[11px] text-cyan-300 leading-relaxed">
              Control network is written to ISIS-documented PDS format and round-tripped through a PDS photogrammetry pipeline (`cnet.py`).
            </div>

            {/* Live Report Modal Trigger Button */}
            <button
              onClick={onOpenReportModal}
              className="w-full flex items-center justify-center space-x-2 py-2.5 rounded-lg bg-[#182638] hover:bg-[#20324a] text-cyan-300 border border-cyan-800/60 text-xs font-mono transition"
            >
              <FileText className="w-4 h-4" />
              <span>Preview Scientific Report</span>
            </button>

            {/* Primary Download All Button */}
            <button
              onClick={() => alert("Downloading all registration artifacts package (34 MB)...")}
              className="w-full flex items-center justify-center space-x-2 py-3 rounded-xl glow-btn-cyan text-xs font-mono font-bold tracking-wide transition"
            >
              <Download className="w-4 h-4" />
              <span>Download all (34 MB)</span>
            </button>

            {/* Summary Footer */}
            <div className="text-[10px] text-slate-500 text-center space-y-0.5 pt-1 border-t border-[#1e2d42]">
              <div>Moving: OHRC 0.25 m • Reference: NAC 1.00 m</div>
              <div>Matcher: Rung 1 - mod-x • Coordinates: Original line/sample</div>
            </div>

          </div>

        </div>

      </div>
    </div>
  );
}
