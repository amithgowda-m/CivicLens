'use client';

import React from 'react';
import { X, Brain, ShieldAlert, CheckCircle, XCircle, Users, AlertTriangle } from 'lucide-react';

export interface ImpactItemData {
  text: string;
  polarity: 'positive' | 'negative' | 'neutral_mixed';
  affected_group: string;
  impact_reasoning: string;
  critic_confirmed?: boolean | null;
  critic_note?: string | null;
  overlooked_subgroups?: string[];
}

interface ImpactDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  impact: ImpactItemData | null;
}

export const ImpactDetailModal: React.FC<ImpactDetailModalProps> = ({
  isOpen,
  onClose,
  impact,
}) => {
  if (!isOpen || !impact) return null;

  const polarityConfig = {
    positive: {
      label: 'Positive',
      color: 'emerald',
      bgClass: 'bg-emerald-950/30',
      borderClass: 'border-emerald-800/60',
      textClass: 'text-emerald-400',
      badgeBg: 'bg-emerald-950',
    },
    negative: {
      label: 'Negative',
      color: 'rose',
      bgClass: 'bg-rose-950/30',
      borderClass: 'border-rose-800/60',
      textClass: 'text-rose-400',
      badgeBg: 'bg-rose-950',
    },
    neutral_mixed: {
      label: 'Mixed / Neutral',
      color: 'amber',
      bgClass: 'bg-amber-950/30',
      borderClass: 'border-amber-800/60',
      textClass: 'text-amber-400',
      badgeBg: 'bg-amber-950',
    },
  };

  const cfg = polarityConfig[impact.polarity] || polarityConfig.neutral_mixed;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="glass-panel w-full max-w-2xl rounded-2xl border border-slate-700 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">

        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-xl ${cfg.bgClass} ${cfg.textClass} border ${cfg.borderClass}`}>
              <Brain className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Agent Impact Perspectives</h3>
              <p className="text-xs text-slate-400">
                Dual-agent analysis of this policy impact
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-5">

          {/* Impact Text */}
          <div className={`p-4 rounded-xl border-l-4 ${
            impact.polarity === 'positive' ? 'border-l-emerald-500 bg-emerald-950/15' :
            impact.polarity === 'negative' ? 'border-l-rose-500 bg-rose-950/15' :
            'border-l-amber-500 bg-amber-950/15'
          }`}>
            <p className="text-sm text-slate-200 leading-relaxed">{impact.text}</p>
          </div>

          {/* Impact Analysis Agent Section */}
          <div className="glass-panel rounded-xl p-5 border border-slate-800">
            <div className="flex items-center space-x-2 mb-3">
              <div className="p-1.5 rounded-lg bg-sky-950/80 text-sky-400 border border-sky-800/60">
                <Brain className="w-4 h-4" />
              </div>
              <h4 className="text-sm font-bold text-sky-400 uppercase tracking-wider">
                Impact Analysis Agent
              </h4>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex items-center space-x-3">
                <span className="text-slate-400 font-medium">Polarity Assessment:</span>
                <span className={`px-2.5 py-1 rounded-full ${cfg.badgeBg} ${cfg.textClass} border ${cfg.borderClass} text-[10px] font-bold uppercase tracking-wider`}>
                  {cfg.label}
                </span>
              </div>

              <div>
                <span className="text-slate-400 font-medium block mb-1">Affected Group:</span>
                <span className="text-slate-200 bg-slate-900/80 px-3 py-1.5 rounded-lg border border-slate-800 inline-flex items-center space-x-1.5">
                  <Users className="w-3.5 h-3.5 text-slate-400" />
                  <span>{impact.affected_group}</span>
                </span>
              </div>

              <div>
                <span className="text-slate-400 font-medium block mb-1">Analysis Reasoning:</span>
                <p className="text-slate-200 bg-slate-950/60 p-3 rounded-lg border border-slate-800/80 leading-relaxed">
                  {impact.impact_reasoning}
                </p>
              </div>
            </div>
          </div>

          {/* Critic Agent Section */}
          <div className="glass-panel rounded-xl p-5 border border-slate-800">
            <div className="flex items-center space-x-2 mb-3">
              <div className="p-1.5 rounded-lg bg-purple-950/80 text-purple-400 border border-purple-800/60">
                <ShieldAlert className="w-4 h-4" />
              </div>
              <h4 className="text-sm font-bold text-purple-400 uppercase tracking-wider">
                Critic Agent (Adversarial)
              </h4>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex items-center space-x-3">
                <span className="text-slate-400 font-medium">Confirms Assessment:</span>
                {impact.critic_confirmed === true ? (
                  <span className="px-2.5 py-1 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px] font-bold uppercase tracking-wider flex items-center space-x-1">
                    <CheckCircle className="w-3 h-3" />
                    <span>Confirmed</span>
                  </span>
                ) : impact.critic_confirmed === false ? (
                  <span className="px-2.5 py-1 rounded-full bg-rose-950 text-rose-400 border border-rose-800 text-[10px] font-bold uppercase tracking-wider flex items-center space-x-1">
                    <XCircle className="w-3 h-3" />
                    <span>Challenged</span>
                  </span>
                ) : (
                  <span className="px-2.5 py-1 rounded-full bg-slate-800 text-slate-400 border border-slate-700 text-[10px] font-bold uppercase tracking-wider">
                    Not Reviewed
                  </span>
                )}
              </div>

              {impact.critic_note && (
                <div>
                  <span className="text-slate-400 font-medium block mb-1">Counter-Perspective / Validation:</span>
                  <p className="text-slate-200 bg-purple-950/20 p-3 rounded-lg border border-purple-900/40 leading-relaxed">
                    {impact.critic_note}
                  </p>
                </div>
              )}

              {impact.overlooked_subgroups && impact.overlooked_subgroups.length > 0 && (
                <div>
                  <span className="text-slate-400 font-medium block mb-1.5">Overlooked Subgroups Identified:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {impact.overlooked_subgroups.map((sub, idx) => (
                      <span
                        key={idx}
                        className="px-2.5 py-1 rounded-lg bg-amber-950/40 text-amber-300 border border-amber-900/50 text-[11px] font-medium flex items-center space-x-1"
                      >
                        <AlertTriangle className="w-3 h-3" />
                        <span>{sub}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-900/60">
          <p className="text-[11px] text-slate-500 text-center">
            Both perspectives are shown for transparency. You decide whether this impact is beneficial or harmful.
          </p>
        </div>
      </div>
    </div>
  );
};
