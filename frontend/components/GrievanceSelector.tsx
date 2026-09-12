'use client';

import React, { useState } from 'react';
import { X, AlertOctagon, CheckSquare, Square, ArrowRight, Loader2, FileWarning } from 'lucide-react';
import { ImpactItemData } from './ImpactDetailModal';

interface GrievanceSelectorProps {
  isOpen: boolean;
  onClose: () => void;
  impacts: ImpactItemData[];
  onSubmit: (selectedGrievances: string[]) => Promise<void>;
}

export const GrievanceSelector: React.FC<GrievanceSelectorProps> = ({
  isOpen,
  onClose,
  impacts,
  onSubmit,
}) => {
  // Filter to negative and mixed impacts as selectable grievances
  const grievances = impacts.filter(
    (i) => i.polarity === 'negative' || i.polarity === 'neutral_mixed'
  );

  const [selected, setSelected] = useState<Set<number>>(
    new Set(grievances.map((_, idx) => idx))
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const toggleSelection = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === grievances.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(grievances.map((_, idx) => idx)));
    }
  };

  const handleSubmit = async () => {
    const selectedTexts = grievances
      .filter((_, idx) => selected.has(idx))
      .map((g) => g.text);
    if (selectedTexts.length === 0) return;

    setIsSubmitting(true);
    try {
      await onSubmit(selectedTexts);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="glass-panel w-full max-w-2xl rounded-2xl border border-slate-700 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">

        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-rose-950/80 text-rose-400 border border-rose-800">
              <FileWarning className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Select Grievances for Objection</h3>
              <p className="text-xs text-slate-400">
                Choose the specific concerns to include in your objection petition
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-3">

          {/* Select All Toggle */}
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-400 font-medium">
              {selected.size} of {grievances.length} grievance{grievances.length !== 1 ? 's' : ''} selected
            </span>
            <button
              onClick={toggleAll}
              className="text-xs text-sky-400 hover:text-sky-300 font-medium transition-colors"
            >
              {selected.size === grievances.length ? 'Deselect All' : 'Select All'}
            </button>
          </div>

          {grievances.length === 0 ? (
            <div className="text-center py-8">
              <AlertOctagon className="w-10 h-10 text-slate-600 mx-auto mb-3" />
              <p className="text-sm text-slate-500">No negative or mixed impacts found to file as grievances.</p>
            </div>
          ) : (
            grievances.map((grievance, idx) => {
              const isSelected = selected.has(idx);
              const isNegative = grievance.polarity === 'negative';

              return (
                <button
                  key={idx}
                  onClick={() => toggleSelection(idx)}
                  className={`w-full text-left p-4 rounded-xl border-l-4 transition-all ${
                    isSelected
                      ? isNegative
                        ? 'border-l-rose-500 bg-rose-950/25 border border-r-rose-900/40 border-t-rose-900/40 border-b-rose-900/40'
                        : 'border-l-amber-500 bg-amber-950/25 border border-r-amber-900/40 border-t-amber-900/40 border-b-amber-900/40'
                      : 'border-l-slate-700 bg-slate-900/40 border border-slate-800 opacity-60 hover:opacity-80'
                  }`}
                >
                  <div className="flex items-start space-x-3">
                    <div className="mt-0.5 flex-shrink-0">
                      {isSelected ? (
                        <CheckSquare className={`w-4.5 h-4.5 ${isNegative ? 'text-rose-400' : 'text-amber-400'}`} />
                      ) : (
                        <Square className="w-4.5 h-4.5 text-slate-600" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-slate-200 leading-relaxed">{grievance.text}</p>
                      <div className="flex items-center space-x-2 mt-2">
                        <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
                          isNegative
                            ? 'bg-rose-950 text-rose-400 border border-rose-800'
                            : 'bg-amber-950 text-amber-400 border border-amber-800'
                        }`}>
                          {isNegative ? 'Negative' : 'Mixed'}
                        </span>
                        <span className="text-[10px] text-slate-500">{grievance.affected_group}</span>
                      </div>
                    </div>
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/60 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={selected.size === 0 || isSubmitting}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white text-xs font-bold shadow-lg shadow-rose-900/40 flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Generating Petition...</span>
              </>
            ) : (
              <>
                <span>Generate Objection ({selected.size})</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
