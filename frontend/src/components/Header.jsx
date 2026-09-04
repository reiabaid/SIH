import React from 'react';
import { Play, Download, Moon, ShieldCheck, Sparkles } from 'lucide-react';

export default function Header({ currentScreen, onRunDemo }) {
  return (
    <header className="h-14 bg-[#141414] border-b border-[#2a2a2a] px-5 flex items-center justify-between text-sm select-none z-20">
      {/* Left Logo & Mission Context */}
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2 text-cyan-400 font-display font-semibold text-base">
          <Moon className="w-4 h-4 text-cyan-400" />
          <span>LunarMatch</span>
        </div>
        <div className="h-4 w-px bg-[#2a2a2a]" />
        <div className="flex items-center space-x-2 text-xs font-mono text-slate-500">
          <span className="px-1.5 py-0.5 rounded-sm bg-[#1c1c1c] border border-[#2a2a2a] text-slate-400">CH2/OHRA</span>
          <span>•</span>
          <span className="px-1.5 py-0.5 rounded-sm bg-[#1c1c1c] border border-[#2a2a2a] text-slate-400">LROC/LRO</span>
          <span>•</span>
          <span className="text-slate-500">CHANDRAYAAN-2 / LRO (LRO/TMC/OHRC)</span>
        </div>
      </div>

      {/* Center Target Coordinates -- status element, not a decorative pill */}
      <div className="hidden lg:flex items-center space-x-2 text-xs font-mono border-l border-[#2a2a2a] pl-3">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
        <span className="text-slate-500">TARGET:</span>
        <span className="text-slate-300 font-medium">69.37°S, 32.35°E</span>
        <span className="text-slate-600">(CH3 LANDING POINT)</span>
      </div>

      {/* Right Controls */}
      <div className="flex items-center space-x-2">
        <button
          onClick={onRunDemo}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-transparent hover:bg-[#1c1c1c] text-slate-400 border border-[#2a2a2a] text-xs font-mono transition"
          title="Play automated mission registration demo"
        >
          <Play className="w-3.5 h-3.5 text-slate-500" />
          <span>Demo Run</span>
        </button>

        <button
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-[#1c1c1c] hover:bg-[#242424] text-cyan-400 border border-[#2a2a2a] text-xs font-mono transition"
          title="Download photogrammetry control network package"
        >
          <Download className="w-3.5 h-3.5 text-cyan-400" />
          <span>Export .net</span>
        </button>
      </div>
    </header>
  );
}
