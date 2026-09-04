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
    <aside className="w-64 bg-[#0d131f] border-r border-[#24344d] flex flex-col justify-between p-4 select-none shrink-0 z-10">
      <div>
        <div className="text-[10px] font-mono text-slate-500 uppercase tracking-widest px-3 mb-4">
          WORKFLOW PIPELINE
        </div>
        
        <nav className="space-y-1.5">
          {steps.map((step) => {
            const Icon = step.icon;
            const isActive = currentScreen === step.id;
            return (
              <button
                key={step.id}
                onClick={() => setCurrentScreen(step.id)}
                className={`w-full flex items-center space-x-3 px-3.5 py-3 rounded-lg text-left transition-all duration-150 ${
                  isActive
                    ? 'bg-gradient-to-r from-cyan-950/80 to-[#182638] text-cyan-300 border-l-4 border-cyan-400 font-medium shadow-md shadow-cyan-950/30'
                    : 'text-slate-400 hover:bg-[#131b28] hover:text-slate-200 border-l-4 border-transparent'
                }`}
              >
                <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`} />
                <div className="overflow-hidden">
                  <div className="text-xs font-mono font-semibold tracking-wide truncate">{step.title}</div>
                  <div className="text-[10px] text-slate-500 truncate">{step.subtitle}</div>
                </div>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Diagnostics / System Health Footer */}
      <div className="bg-[#121a27] border border-[#1f2d42] rounded-lg p-3 space-y-2 text-xs font-mono">
        <div className="flex items-center justify-between text-[11px] text-slate-400 border-b border-[#1f2d42] pb-1.5">
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
          <span className="text-slate-500">SUBPIXEL RMSE:</span>
          <span className="text-cyan-400 font-semibold">0.372 px</span>
        </div>
      </div>
    </aside>
  );
}
