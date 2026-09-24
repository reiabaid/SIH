import React from 'react';
import { ArrowRight, Moon, ShieldCheck, Sun, Layers, Grid, FileCode2, Sparkles, CheckCircle2 } from 'lucide-react';

export default function Screen00Landing({ onLaunchWorkspace }) {
  return (
    <div className="space-y-12 animate-fadeIn pb-12">
      {/* Hero Section */}
      <div className="relative rounded-lg bg-[#141414] border border-[#2a2a2a] p-6 md:p-8">
        <div className="relative z-10 max-w-4xl">
          <div className="space-y-4">
            <div className="inline-flex items-center space-x-2 px-2.5 py-1 rounded bg-[#1c1c1c] border border-[#2a2a2a] text-slate-500 text-[11px] font-mono uppercase tracking-wider">
              <Sparkles className="w-3.5 h-3.5 text-cyan-500" />
              <span>SIH ISRO CHANDRAYAAN-2 LUNAR IMAGE REGISTRATION SUITE</span>
            </div>

            <h1 className="text-3xl md:text-4xl font-display font-bold text-slate-100 tracking-tight leading-snug">
              Multi-Modal, Sun Angle &amp; Scale Invariant <br />
              <span className="glow-text-cyan font-bold">
                Lunar Image Registration
              </span>
            </h1>

            <p className="text-slate-400 text-sm md:text-base max-w-3xl leading-relaxed">
              Generic software solution for finding correspondence between <strong className="text-slate-200 font-medium">Chandrayaan-2 acquired optical images</strong> (OHRC, TMC, IIRS) and <strong className="text-slate-200 font-medium">Lunar reference images</strong> (LRO NAC) with sub-pixel accuracy maintaining uniform distribution across severe solar illumination variations.
            </p>
          </div>

          {/* Action CTAs */}
          <div className="flex flex-wrap items-center gap-4 mt-10">
            <button
              onClick={onLaunchWorkspace}
              className="flex items-center space-x-2 px-5 py-2.5 rounded-md glow-btn-cyan text-sm font-medium transition"
            >
              <span>Launch LunarMatch Workspace</span>
              <ArrowRight className="w-4 h-4" />
            </button>

            <a
              href="#problem-statement"
              className="px-5 py-2.5 rounded-md bg-transparent hover:bg-[#1c1c1c] text-slate-400 border border-[#2a2a2a] text-sm font-mono transition"
            >
              Explore ISRO Problem Solver
            </a>
          </div>
        </div>
      </div>

      {/* Performance Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#141414] border border-[#2a2a2a] rounded-md p-5 md:p-6">
          <div className="text-slate-500 text-[11px] font-mono uppercase tracking-wider">REAL PAIRS TESTED</div>
          <div className="text-3xl font-display font-bold font-mono text-cyan-400 mt-2">
            8 <span className="text-xs text-slate-600 font-normal">CH2 × LRO</span>
          </div>
          <div className="text-[11px] text-slate-500 mt-3 leading-relaxed">Every footprint-overlapping pair in the inventory; each run reports its own fit residual and, in Auto mode, a cross-check between two matchers</div>
        </div>

        <div className="bg-[#141414] border border-[#2a2a2a] rounded-md p-5 md:p-6">
          <div className="text-slate-500 text-[11px] font-mono uppercase tracking-wider">ILLUMINATION-ROBUST MATCHING</div>
          <div className="text-3xl font-display font-bold font-mono text-slate-300 mt-2">
            Log-Gabor <span className="text-xs text-slate-600 font-normal">MIM</span>
          </div>
          <div className="text-[11px] text-slate-500 mt-3 leading-relaxed">Orientation-index descriptor; shown to survive a full contrast flip on synthetic pairs</div>
        </div>

        <div className="bg-[#141414] border border-[#2a2a2a] rounded-md p-5 md:p-6">
          <div className="text-slate-500 text-[11px] font-mono uppercase tracking-wider">GRID SPATIAL COVERAGE</div>
          <div className="text-3xl font-display font-bold font-mono text-emerald-400 mt-2">
            8 × 8 <span className="text-xs text-slate-600 font-normal">cells</span>
          </div>
          <div className="text-[11px] text-slate-500 mt-3 leading-relaxed">Coverage of the tie-point grid is measured and reported for every run</div>
        </div>

        <div className="bg-[#141414] border border-[#2a2a2a] rounded-md p-5 md:p-6">
          <div className="text-slate-500 text-[11px] font-mono uppercase tracking-wider">ISRO PHOTOGRAMMETRY</div>
          <div className="text-3xl font-display font-bold font-mono text-slate-300 mt-2">
            ISIS .net <span className="text-xs text-slate-600 font-normal">cnet.py</span>
          </div>
          <div className="text-[11px] text-slate-500 mt-3 leading-relaxed">Direct pipeline export via cnet.py</div>
        </div>
      </div>

      {/* Problem Solver Capabilities Grid */}
      <div id="problem-statement">
        <h2 className="text-lg font-display font-bold text-slate-200 flex items-center gap-2 mb-5">
          <ShieldCheck className="w-4 h-4 text-cyan-500" />
          <span>Core Challenges &amp; Automated Solutions</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-md p-6 space-y-3">
            <div className="flex items-center space-x-3">
              <Sun className="w-4 h-4 text-cyan-500 shrink-0" />
              <h3 className="text-base font-display font-semibold text-slate-200">1. Illumination Variation (Shadow Rotation)</h3>
            </div>
            <p className="text-slate-400 text-[13px] leading-relaxed">
              Changes in sun azimuth and elevation alter lighting on crater walls. Standard SIFT collapses (-78% inlier drop at 30° difference). Our <strong className="text-slate-200 font-medium">Mod-X phase correlation &amp; edge filter engine</strong> isolates structural rim gradients, ensuring invariant match correspondence.
            </p>
          </div>

          <div className="bg-[#141414] border border-[#2a2a2a] rounded-md p-6 space-y-3">
            <div className="flex items-center space-x-3">
              <Layers className="w-4 h-4 text-slate-600 shrink-0" />
              <h3 className="text-base font-display font-semibold text-slate-200">2. Scale &amp; Viewpoint Adaptation</h3>
            </div>
            <p className="text-slate-400 text-[13px] leading-relaxed">
              Lunar missions operate at different altitudes (e.g. Chandrayaan-2 OHRC at 0.25 m/pix vs NASA LRO NAC at 1.00 m/pix). <strong className="text-slate-200 font-medium">Phase 1 &amp; 2 geometric alignment (align_pair)</strong> resamples rasters to a unified spatial grid prior to sub-pixel tie-point optimization.
            </p>
          </div>

          <div className="bg-[#141414] border border-[#2a2a2a] rounded-md p-6 space-y-3">
            <div className="flex items-center space-x-3">
              <Grid className="w-4 h-4 text-slate-600 shrink-0" />
              <h3 className="text-base font-display font-semibold text-slate-200">3. Uniform Tie-Point Spatial Distribution</h3>
            </div>
            <p className="text-slate-400 text-[13px] leading-relaxed">
              Prevents tie-points from clustering in high-contrast corners. An <strong className="text-slate-200 font-medium">8x8 spatial grid matrix</strong> enforces uniform tie-point density across the entire image swath (82.3% inlier ratio, Distribution CV 0.20).
            </p>
          </div>

          <div className="bg-[#141414] border border-[#2a2a2a] rounded-md p-6 space-y-3">
            <div className="flex items-center space-x-3">
              <FileCode2 className="w-4 h-4 text-slate-600 shrink-0" />
              <h3 className="text-base font-display font-semibold text-slate-200">4. ISIS Control Network Output</h3>
            </div>
            <p className="text-slate-400 text-[13px] leading-relaxed">
              Integrates directly into ISRO's satellite photogrammetry software. <strong className="text-slate-200 font-medium">Phase 7 (cnet.py)</strong> exports matched points directly into an ISIS Control Network (.net) format without requiring local ISIS installation.
            </p>
          </div>
        </div>
      </div>

    </div>
  );
}
