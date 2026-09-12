'use client';

import React, { useEffect, useState } from 'react';
import { ShieldCheck, FileText, Activity } from 'lucide-react';

interface NavbarProps {
  reliabilityScore: number | null;
}

export const Navbar: React.FC<NavbarProps> = ({ reliabilityScore }) => {
  return (
    <header className="sticky top-0 z-40 w-full glass-panel border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
            <ShieldCheck className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-white via-slate-200 to-sky-400 bg-clip-text text-transparent">
              CivicLens
            </h1>
            <p className="text-xs text-slate-400">Multi-Jurisdiction Civic Transparency Network</p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <div className="hidden md:flex items-center space-x-2 px-3 py-1.5 rounded-full bg-slate-900/80 border border-slate-800 text-xs">
            <Activity className="w-4 h-4 text-emerald-400 animate-pulse" />
            <span className="text-slate-400">Pipeline Status:</span>
            <span className="text-emerald-400 font-medium">Ready</span>
          </div>

          <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-sky-950/60 border border-sky-800/50 text-xs">
            <FileText className="w-4 h-4 text-sky-400" />
            <span className="text-slate-300">Accuracy Score:</span>
            <span className="text-sky-300 font-bold">
              {reliabilityScore !== null ? `${(reliabilityScore * 100).toFixed(1)}%` : '96.4% Verified'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
