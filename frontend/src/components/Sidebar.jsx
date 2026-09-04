import React from 'react';
import { Home, SlidersHorizontal, Eye, BarChart3, Globe, ShieldCheck, CheckCircle2 } from 'lucide-react';

export default function Sidebar({ currentScreen, setCurrentScreen }) {
  const steps = [
    { id: 0, title: '00 - Home', subtitle: 'Mission Overview', icon: Home },
    { id: 1, title: '01 - Select pair', subtitle: 'Source & Reference', icon: SlidersHorizontal },
    { id: 2, title: '02 - Match review', subtitle: 'Side-by-side & Swipe', icon: Eye },
    { id: 3, title: '03 - Evidence', subtitle: 'Metrics & Robustness', icon: BarChart3 },
    { id: 4, title: '04 - Terrain & report', subtitle: '3D Sun & Export', icon: Globe },
  ];

  return (
    <aside className="w-64 bg-[#1c1c1c] border-r border-[#2a2a2a] flex flex-col justify-between p-3 select-none shrink-0 z-10">
      <div>
        <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wide px-3 mb-3">
          WORKFLOW PIPELINE
        </div>

        <nav className="space-y-0.5">
          {steps.map((step) => {
            const Icon = step.icon;
            const isActive = currentScreen === step.id;
            return (
              <button
                key={step.id}
                onClick={() => setCurrentScreen(step.id)}
                className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-md text-left transition-colors duration-150 border-l-2 ${
                  isActive
                    ? 'bg-cyan-900/40 text-cyan-300 border-cyan-500 font-medium'
                    : 'text-slate-500 hover:bg-[#242424] hover:text-slate-300 border-transparent'
                }`}
              >
                <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-cyan-400' : 'text-slate-600'}`} />
                <div className="overflow-hidden">
                  <div className="text-xs font-mono font-medium tracking-wide truncate">{step.title}</div>
                  <div className="text-[10px] text-slate-600 truncate">{step.subtitle}</div>
                </div>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Diagnostics / System Health Footer */}
      <div className="bg-[#141414] border border-[#2a2a2a] rounded-md p-3 space-y-1.5 text-xs font-mono">
        <div className="flex items-center justify-between text-[11px] text-slate-500 border-b border-[#2a2a2a] pb-1.5">
          <span>DATASET STATUS</span>
          <span className="flex items-center text-emerald-400 text-[10px]">
            <CheckCircle2 className="w-3 h-3 mr-1" /> VALIDATED
          </span>
        </div>
        <div className="flex justify-between text-[11px]">
          <span className="text-slate-500">CH2 OHRC:</span>
          <span className="text-slate-300">0.25 m/px</span>
        </div>
        <div className="flex justify-between text-[11px]">
          <span className="text-slate-500">LRO NAC:</span>
          <span className="text-slate-300">1.00 m/px</span>
        </div>
        <div className="flex justify-between text-[11px]">
          <span className="text-slate-500">SUB-PIXEL REFINE:</span>
          <span className="text-cyan-400 font-medium">ALWAYS ON</span>
        </div>
      </div>
    </aside>
  );
}
