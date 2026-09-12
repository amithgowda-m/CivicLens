'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
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
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  // Body scroll lock
  useEffect(() => {
    if (isOpen) {
      document.body.classList.add('modal-open');
    } else {
      document.body.classList.remove('modal-open');
    }
    return () => { document.body.classList.remove('modal-open'); };
  }, [isOpen]);

  if (!isOpen || !impact || !mounted) return null;

  const isPos = impact.polarity === 'positive';
  const isNeg = impact.polarity === 'negative';
  const polarityLabel = isPos ? 'Positive' : isNeg ? 'Negative' : 'Mixed / Neutral';
  const polarityChipCls = isPos ? 'chip-success' : isNeg ? 'chip-danger' : 'chip-warning';
  const polarityBorder = isPos ? 'var(--success)' : isNeg ? 'var(--danger)' : 'var(--warning)';

  return createPortal(
    <div className="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-panel max-w-2xl" style={{ maxHeight: '82vh' }}>

        {/* Header */}
        <div className="modal-header">
          <div className="flex items-center gap-3">
            <div
              className="p-1.5 rounded"
              style={{
                background: isPos ? 'var(--success-dim)' : isNeg ? 'var(--danger-dim)' : 'var(--warning-dim)',
                border: `1px solid ${isPos ? 'rgba(34,197,94,0.2)' : isNeg ? 'rgba(239,68,68,0.2)' : 'rgba(245,158,11,0.2)'}`,
              }}
            >
              <Brain className="w-4 h-4" style={{ color: isPos ? 'var(--success)' : isNeg ? '#f87171' : 'var(--warning)' }} />
            </div>
            <div>
              <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Agent Impact Perspectives
              </div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Dual-agent analysis of this policy impact
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded transition-colors"
            style={{ color: 'var(--text-muted)' }}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="modal-body space-y-4">

          {/* Impact Text */}
          <div
            className="p-3.5 rounded text-xs leading-relaxed"
            style={{
              background: 'var(--bg-raised)',
              border: '1px solid var(--border)',
              borderLeftWidth: '3px',
              borderLeftColor: polarityBorder,
              color: 'var(--text-primary)',
            }}
          >
            {impact.text}
          </div>

          {/* Impact Analysis Agent Section */}
          <div
            className="rounded p-4 space-y-3"
            style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}
          >
            <div className="flex items-center gap-2">
              <Brain className="w-3.5 h-3.5" style={{ color: 'var(--accent)' }} />
              <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                Impact Analysis Agent
              </span>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex items-center gap-2">
                <span style={{ color: 'var(--text-muted)' }}>Polarity Assessment:</span>
                <span className={`chip ${polarityChipCls}`}>
                  {polarityLabel}
                </span>
              </div>

              {impact.affected_group && (
                <div>
                  <span className="block mb-1" style={{ color: 'var(--text-muted)' }}>Affected Group:</span>
                  <span
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                  >
                    <Users className="w-3 h-3" style={{ color: 'var(--text-faint)' }} />
                    <span>{impact.affected_group}</span>
                  </span>
                </div>
              )}

              {impact.impact_reasoning && (
                <div>
                  <span className="block mb-1" style={{ color: 'var(--text-muted)' }}>Analysis Reasoning:</span>
                  <div
                    className="p-3 rounded leading-relaxed"
                    style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                  >
                    {impact.impact_reasoning}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Critic Agent Section */}
          <div
            className="rounded p-4 space-y-3"
            style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}
          >
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-3.5 h-3.5" style={{ color: '#a855f7' }} />
              <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                Critic Agent (Adversarial)
              </span>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex items-center gap-2">
                <span style={{ color: 'var(--text-muted)' }}>Assessment Audit:</span>
                {impact.critic_confirmed === true ? (
                  <span className="chip chip-success flex items-center gap-1">
                    <CheckCircle className="w-3 h-3" />
                    <span>Confirmed</span>
                  </span>
                ) : impact.critic_confirmed === false ? (
                  <span className="chip chip-danger flex items-center gap-1">
                    <XCircle className="w-3 h-3" />
                    <span>Challenged</span>
                  </span>
                ) : (
                  <span className="chip chip-neutral">
                    Not Reviewed
                  </span>
                )}
              </div>

              {impact.critic_note && (
                <div>
                  <span className="block mb-1" style={{ color: 'var(--text-muted)' }}>Counter-Perspective / Validation:</span>
                  <div
                    className="p-3 rounded leading-relaxed"
                    style={{
                      background: 'rgba(168,85,247,0.06)',
                      border: '1px solid rgba(168,85,247,0.18)',
                      color: 'var(--text-secondary)',
                    }}
                  >
                    {impact.critic_note}
                  </div>
                </div>
              )}

              {impact.overlooked_subgroups && impact.overlooked_subgroups.length > 0 && (
                <div>
                  <span className="block mb-1.5" style={{ color: 'var(--text-muted)' }}>Overlooked Subgroups Identified:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {impact.overlooked_subgroups.map((sub, idx) => (
                      <span key={idx} className="chip chip-warning flex items-center gap-1">
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
        <div className="modal-footer">
          <button onClick={onClose} className="btn btn-ghost">
            Close
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};
