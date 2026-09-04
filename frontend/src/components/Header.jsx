import React from 'react';
import { Play, Download, Moon, ShieldCheck, Sparkles } from 'lucide-react';

export default function Header({ currentScreen, onRunDemo }) {
  return (
    <header className="h-16 bg-[#0f1622] border-b border-[#24344d] px-6 flex items-center justify-between text-sm select-none z-20">
      {/* Left Logo & Mission Context */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2 text-cyan-400 font-display font-bold text-lg tracking-wider glow-text-cyan">
          <Moon className="w-5 h-5 text-cyan-400 animate-pulse" />
          <span>LunarMatch</span>
        </div>
        <div className="h-4 w-[1px] bg-[#24344d]" />
        <div className="flex items-center space-x-2 text-xs font-mono text-slate-400">
          <span className="px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-800/50 text-cyan-300">CH2/OHRA</span>
          <span>•</span>
          <span className="px-2 py-0.5 rounded bg-blue-950/60 border border-blue-800/50 text-blue-300">LROC/LRO</span>
          <span>•</span>
          <span className="text-slate-300">CHANDRAYAAN-2 / LRO (LRO/TMC/OHRC)</span>
        </div>
      </div>

      {/* Center Target Coordinates */}
      <div className="hidden lg:flex items-center space-x-2 bg-[#182232] border border-[#24344d] px-3 py-1 rounded-full text-xs font-mono">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
        <span className="text-slate-400">TARGET:</span>
        <span className="text-cyan-300 font-semibold">69.37°S, 32.35°E</span>
        <span className="text-slate-500">(CH3 LANDING POINT)</span>
      </div>

      {/* Right Controls */}
      <div className="flex items-center space-x-3">
        <button 
          onClick={onRunDemo}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-[#1c293d] hover:bg-[#24344d] text-slate-200 border border-[#2c3f5c] text-xs font-mono transition"
          title="Play automated mission registration demo"
        >
          <Play className="w-3.5 h-3.5 text-cyan-400 fill-cyan-400" />
          <span>Demo Run</span>
        </button>

        <button 
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-cyan-950/70 hover:bg-cyan-900/80 text-cyan-300 border border-cyan-700/60 text-xs font-mono transition"
          title="Download photogrammetry control network package"
        >
          <Download className="w-3.5 h-3.5 text-cyan-400" />
          <span>Export .net</span>
        </button>
      </div>
    </header>
  );
}
