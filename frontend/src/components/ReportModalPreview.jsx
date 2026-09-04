import React from 'react';
import { X, Printer, Download, CheckCircle, Moon, FileText } from 'lucide-react';
import { MOCK_DATASET } from '../data/mockLunarData';

export default function ReportModalPreview({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      <div className="bg-[#121926] border border-[#24344d] rounded-xl max-w-4xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden text-slate-200">
        
        {/* Modal Header */}
        <div className="bg-[#162030] px-6 py-4 border-b border-[#24344d] flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-cyan-950/80 border border-cyan-700/50 text-cyan-400">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-display font-bold text-lg text-white">Scientific Evaluation Report Preview</h3>
              <p className="text-xs text-slate-400 font-mono">ISRO Photogrammetry Standard • Report ID: CH2-LRO-2026-0904</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#24344d] transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Document Body */}
        <div className="p-8 overflow-y-auto space-y-6 font-sans text-sm leading-relaxed bg-[#0b0f17]">
          
          {/* Printable Document Paper Card */}
          <div className="bg-[#131b28] border border-[#202f45] rounded-lg p-6 space-y-6 shadow-lg">
            
            {/* Document Header */}
            <div className="border-b border-[#202f45] pb-4 flex justify-between items-start">
              <div>
                <div className="flex items-center space-x-2 text-cyan-400 font-display font-bold text-xl">
                  <Moon className="w-6 h-6" />
                  <span>LunarMatch Scientific Evaluation Report</span>
                </div>
                <p className="text-xs text-slate-400 font-mono mt-1">
                  Multi-Modal Lunar Image Registration: Chandrayaan-2 OHRC vs NASA LRO NAC
                </p>
              </div>
              <div className="text-right text-xs font-mono text-slate-400">
                <div>DATE: 2026-09-04</div>
                <div className="text-emerald-400 font-semibold mt-1">STATUS: PASS (SUBPIXEL)</div>
              </div>
            </div>

            {/* Dataset Metadata Grid */}
            <div className="grid grid-cols-2 gap-4 font-mono text-xs bg-[#0e1420] p-4 rounded-md border border-[#1b273a]">
              <div>
                <span className="text-slate-500 block">MOVING IMAGE (SOURCE):</span>
                <span className="text-cyan-300 font-semibold">{MOCK_DATASET.moving.id}</span>
                <div className="text-slate-400">{MOCK_DATASET.moving.instrument} ({MOCK_DATASET.moving.resolution})</div>
                <div className="text-slate-400">Sun Angle: {MOCK_DATASET.moving.sunAngle}</div>
              </div>
              <div>
                <span className="text-slate-500 block">FIXED REFERENCE IMAGE:</span>
                <span className="text-blue-300 font-semibold">{MOCK_DATASET.reference.id}</span>
                <div className="text-slate-400">{MOCK_DATASET.reference.instrument} ({MOCK_DATASET.reference.resolution})</div>
                <div className="text-slate-400">Sun Angle: {MOCK_DATASET.reference.sunAngle}</div>
              </div>
            </div>

            {/* Key Metrics Table */}
            <div>
              <h4 className="font-display font-semibold text-cyan-300 mb-2">1. Registration Performance Metrics</h4>
              <table className="w-full text-left font-mono text-xs border-collapse">
                <thead>
                  <tr className="bg-[#182335] text-slate-300 border-b border-[#24344d]">
                    <th className="p-2.5">Evaluation Metric</th>
                    <th className="p-2.5">Measured Value</th>
                    <th className="p-2.5">Threshold Target</th>
                    <th className="p-2.5">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1e2c42] text-slate-300">
                  <tr>
                    <td className="p-2.5">Sub-Pixel RMSE</td>
                    <td className="p-2.5 text-cyan-400 font-bold">{MOCK_DATASET.metrics.rmseSubpixel}</td>
                    <td className="p-2.5 text-slate-400">&lt; 0.500 px</td>
                    <td className="p-2.5 text-emerald-400 font-semibold">PASSED</td>
                  </tr>
                  <tr>
                    <td className="p-2.5">Inlier Match Count</td>
                    <td className="p-2.5 text-slate-200">{MOCK_DATASET.metrics.inlierCount} / {MOCK_DATASET.metrics.totalMatches}</td>
                    <td className="p-2.5 text-slate-400">&gt; 100 inliers</td>
                    <td className="p-2.5 text-emerald-400 font-semibold">PASSED</td>
                  </tr>
                  <tr>
                    <td className="p-2.5">Inlier Ratio</td>
                    <td className="p-2.5 text-slate-200">{MOCK_DATASET.metrics.inlierRatio}</td>
                    <td className="p-2.5 text-slate-400">&gt; 70.0%</td>
                    <td className="p-2.5 text-emerald-400 font-semibold">PASSED</td>
                  </tr>
                  <tr>
                    <td className="p-2.5">Spatial Grid Coverage</td>
                    <td className="p-2.5 text-slate-200">{MOCK_DATASET.metrics.gridCoverage} cells</td>
                    <td className="p-2.5 text-slate-400">&gt; 50 / 64 cells</td>
                    <td className="p-2.5 text-emerald-400 font-semibold">PASSED</td>
                  </tr>
                  <tr>
                    <td className="p-2.5">Distribution Uniformity (CV)</td>
                    <td className="p-2.5 text-slate-200">{MOCK_DATASET.metrics.distributionCV}</td>
                    <td className="p-2.5 text-slate-400">&lt; 0.30</td>
                    <td className="p-2.5 text-emerald-400 font-semibold">PASSED</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Photogrammetry ISIS Control Network Verification */}
            <div className="bg-cyan-950/40 border border-cyan-800/60 rounded-md p-4 space-y-2 text-xs font-mono">
              <div className="flex items-center text-cyan-300 font-semibold">
                <CheckCircle className="w-4 h-4 mr-2 text-cyan-400" />
                ISIS Control Network Specification (`cnet.py`)
              </div>
              <p className="text-slate-300">
                The control network has been converted to ISIS-documented PDS format and round-tripped through a PDS photogrammetry pipeline. The generated tie points are ready for bundle adjustment.
              </p>
            </div>

          </div>
        </div>

        {/* Modal Footer Controls */}
        <div className="bg-[#162030] px-6 py-4 border-t border-[#24344d] flex items-center justify-between">
          <button
            onClick={() => window.print()}
            className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-[#202d42] hover:bg-[#2a3c58] text-slate-200 text-xs font-mono transition"
          >
            <Printer className="w-4 h-4 text-slate-300" />
            <span>Print Report</span>
          </button>

          <button
            onClick={onClose}
            className="flex items-center space-x-2 px-5 py-2 rounded-lg glow-btn-cyan text-xs font-mono font-semibold"
          >
            <Download className="w-4 h-4" />
            <span>Download Report PDF (2.4 MB)</span>
          </button>
        </div>

      </div>
    </div>
  );
}
