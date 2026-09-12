'use client';

import React, { useState } from 'react';
import { useApp, ImpactItemData } from '../context/AppContext';
import {
  Users, AlertTriangle, CheckCircle2, XCircle, AlertOctagon,
  ChevronDown, ChevronRight, Eye, Loader2, ArrowRight,
} from 'lucide-react';
import { ImpactDetailModal } from '@/components/ImpactDetailModal';
import { GrievanceSelector } from '@/components/GrievanceSelector';

function ImpactRow({
  impact,
  onViewDetails,
}: {
  impact: ImpactItemData;
  onViewDetails: (i: ImpactItemData) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const isPos = impact.polarity === 'positive';
  const isNeg = impact.polarity === 'negative';
  const polarityClass = isPos ? 'positive' : isNeg ? 'negative' : 'mixed';
  const polarityColor = isPos ? 'var(--success)' : isNeg ? 'var(--danger)' : 'var(--warning)';
  const polarityLabel = isPos ? 'Positive' : isNeg ? 'Negative' : 'Mixed';
  const polarityChipCls = isPos ? 'chip-success' : isNeg ? 'chip-danger' : 'chip-warning';

  return (
    <>
      <div className={`impact-row ${polarityClass}`}>
        {/* Polarity */}
        <div className="flex-shrink-0 pt-0.5">
          <span className={`chip ${polarityChipCls}`}>{polarityLabel}</span>
        </div>

        {/* Text */}
        <p className="flex-1 text-sm" style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>
          {impact.text}
        </p>

        {/* Affected group */}
        {impact.affected_group && (
          <div className="flex-shrink-0 text-xs hidden md:block" style={{ color: 'var(--text-muted)', maxWidth: '10rem' }}>
            {impact.affected_group}
          </div>
        )}

        {/* Critic verdict */}
        <div className="flex-shrink-0 w-6">
          {impact.critic_confirmed === true && (
            <span title="Critic confirmed">
              <CheckCircle2 className="w-4 h-4" style={{ color: 'var(--success)' }} />
            </span>
          )}
          {impact.critic_confirmed === false && (
            <span title="Critic challenged">
              <XCircle className="w-4 h-4" style={{ color: 'var(--danger)' }} />
            </span>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-xs transition-colors"
            style={{ color: 'var(--text-muted)' }}
          >
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          </button>
          <button
            onClick={() => onViewDetails(impact)}
            className="flex items-center gap-1 text-xs transition-colors"
            style={{ color: 'var(--accent)' }}
            title="Agent view"
          >
            <Eye className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div
          className="px-5 py-3 space-y-2.5 text-sm animate-in"
          style={{
            borderBottom: '1px solid var(--border)',
            borderLeft: `2px solid ${polarityColor}`,
            background: 'rgba(255,255,255,0.015)',
          }}
        >
          {impact.impact_reasoning && (
            <div>
              <div className="section-label mb-1">Reasoning</div>
              <p style={{ color: 'var(--text-muted)' }}>{impact.impact_reasoning}</p>
            </div>
          )}
          {impact.critic_note && (
            <div>
              <div className="section-label mb-1">Critic Note</div>
              <p style={{ color: 'var(--text-muted)' }}>{impact.critic_note}</p>
            </div>
          )}
          {impact.overlooked_subgroups && impact.overlooked_subgroups.length > 0 && (
            <div>
              <div className="section-label mb-1">Overlooked Subgroups</div>
              <div className="flex flex-wrap gap-1.5">
                {impact.overlooked_subgroups.map((sub, i) => (
                  <span key={i} className="chip chip-warning text-[11px]">{sub}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

export default function StakeholdersPage() {
  const { report, handleGenerateAction } = useApp();
  const [filter, setFilter] = useState<'all' | 'positive' | 'negative' | 'neutral_mixed'>('all');
  const [activeImpact, setActiveImpact] = useState<ImpactItemData | null>(null);
  const [isImpactOpen, setIsImpactOpen] = useState(false);
  const [isGrievanceOpen, setIsGrievanceOpen] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  if (!report) {
    return (
      <div className="animate-in min-h-screen">
        <div className="page-header">
          <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)', letterSpacing: '-0.015em' }}>
            Stakeholders & Impact
          </h1>
        </div>
        <div className="flex items-center justify-center h-[70vh]">
          <div className="text-center">
            <Users className="w-8 h-8 mx-auto mb-3" style={{ color: 'var(--text-faint)' }} />
            <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>No stakeholder data available</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
              Run an analysis from the <strong style={{ color: 'var(--accent)' }}>Overview</strong> page first.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const stakeholders = Array.from(new Set(report.stakeholders_impacted || []));

  const unifiedImpacts: ImpactItemData[] = (() => {
    if (report.impacts && report.impacts.length > 0) return report.impacts;
    const pos = Array.from(new Set(report.positive_impacts || []));
    const neg = Array.from(new Set(report.negative_impacts || []));
    return [
      ...pos.map((text) => ({ text, polarity: 'positive' as const, affected_group: text.split(':')[0]?.trim() || '', impact_reasoning: text.split(':').slice(1).join(':').trim() || text, critic_confirmed: null, critic_note: null, overlooked_subgroups: [] })),
      ...neg.map((text) => ({ text, polarity: 'negative' as const, affected_group: text.split(':')[0]?.trim() || '', impact_reasoning: text.split(':').slice(1).join(':').trim() || text, critic_confirmed: null, critic_note: null, overlooked_subgroups: [] })),
    ];
  })();

  const positiveCount = unifiedImpacts.filter((i) => i.polarity === 'positive').length;
  const negativeCount = unifiedImpacts.filter((i) => i.polarity === 'negative').length;
  const mixedCount    = unifiedImpacts.filter((i) => i.polarity === 'neutral_mixed').length;
  const total = unifiedImpacts.length;

  const filtered = filter === 'all' ? unifiedImpacts : unifiedImpacts.filter((i) => i.polarity === filter);

  const handleActionClick = () => {
    if (unifiedImpacts.length > 0) {
      setIsGrievanceOpen(true);
    } else {
      setIsGenerating(true);
      handleGenerateAction().finally(() => setIsGenerating(false));
    }
  };

  const handleGrievanceSubmit = async (selected: string[]) => {
    setIsGrievanceOpen(false);
    setIsGenerating(true);
    try { await handleGenerateAction(selected); } finally { setIsGenerating(false); }
  };

  return (
    <div className="animate-in min-h-screen">
      {/* Header */}
      <div className="page-header flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)', letterSpacing: '-0.015em' }}>
            Stakeholders & Impact
          </h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
            {stakeholders.length > 0 ? `${stakeholders.length} stakeholder group${stakeholders.length !== 1 ? 's' : ''} identified` : 'No stakeholder groups identified'}
            {total > 0 && ` · ${total} impact${total !== 1 ? 's' : ''}`}
          </p>
        </div>
        <button
          onClick={handleActionClick}
          disabled={isGenerating}
          className="btn"
          style={{
            background: 'var(--danger)',
            color: '#fff',
            opacity: isGenerating ? 0.5 : 1,
          }}
        >
          {isGenerating
            ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />Drafting Objection…</>
            : <>Draft Objection<ArrowRight className="w-3.5 h-3.5" /></>
          }
        </button>
      </div>

      <div className="page-body space-y-5">

        {/* ── Stakeholder groups ── */}
        {stakeholders.length > 0 && (
          <div
            className="rounded-lg"
            style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
          >
            <div
              className="px-5 py-3 flex items-center gap-2"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <Users className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--text-muted)' }} />
              <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                Stakeholders Impacted
              </span>
              <span className="ml-auto chip chip-neutral">{stakeholders.length}</span>
            </div>
            <div className="px-5 py-3 flex flex-wrap gap-1.5">
              {stakeholders.map((s, i) => (
                <span key={i} className="chip chip-neutral">{s}</span>
              ))}
            </div>
          </div>
        )}

        {/* ── Impact balance ── */}
        {total > 0 && (
          <div
            className="rounded-lg px-5 py-3 flex items-center gap-4 flex-wrap"
            style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
          >
            <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
              Impact Balance
            </span>
            <div className="flex-1 min-w-24">
              <div className="polarity-bar">
                {positiveCount > 0 && (
                  <div className="polarity-positive" style={{ flex: positiveCount }} />
                )}
                {negativeCount > 0 && (
                  <div className="polarity-negative" style={{ flex: negativeCount }} />
                )}
                {mixedCount > 0 && (
                  <div className="polarity-mixed" style={{ flex: mixedCount }} />
                )}
              </div>
            </div>
            <div className="flex gap-3 text-xs" style={{ color: 'var(--text-muted)' }}>
              {positiveCount > 0 && <span><span style={{ color: 'var(--success)' }}>{positiveCount}</span> positive</span>}
              {negativeCount > 0 && <span><span style={{ color: 'var(--danger)' }}>{negativeCount}</span> negative</span>}
              {mixedCount > 0    && <span><span style={{ color: 'var(--warning)' }}>{mixedCount}</span> mixed</span>}
            </div>
          </div>
        )}

        {/* ── Impact list ── */}
        {total > 0 && (
          <div
            className="rounded-lg overflow-hidden"
            style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
          >
            {/* Toolbar */}
            <div
              className="px-5 py-3 flex items-center gap-3 flex-wrap"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                Policy Impacts
              </span>

              {/* Column headers (md+) */}
              <div className="hidden md:flex items-center gap-6 ml-auto text-[11px]" style={{ color: 'var(--text-faint)' }}>
                <span>Polarity</span>
                <span className="flex-1">Description</span>
                <span style={{ width: '10rem' }}>Affected Group</span>
                <span>Critic</span>
              </div>

              {/* Filter pills */}
              <div className="flex items-center gap-1 md:ml-4">
                {(['all', 'positive', 'negative', 'neutral_mixed'] as const).map((key) => (
                  <button
                    key={key}
                    onClick={() => setFilter(key)}
                    className="text-[11px] px-2 py-0.5 rounded transition-colors"
                    style={{
                      background: filter === key ? 'var(--accent)' : 'transparent',
                      color: filter === key ? '#fff' : 'var(--text-muted)',
                    }}
                  >
                    {key === 'all' ? 'All' : key === 'neutral_mixed' ? 'Mixed' : key.charAt(0).toUpperCase() + key.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            {/* Rows */}
            {filtered.length > 0 ? (
              filtered.map((impact, i) => (
                <ImpactRow
                  key={i}
                  impact={impact}
                  onViewDetails={(imp) => { setActiveImpact(imp); setIsImpactOpen(true); }}
                />
              ))
            ) : (
              <div className="px-5 py-8 text-center text-sm italic" style={{ color: 'var(--text-faint)' }}>
                No {filter === 'all' ? '' : filter} impacts found.
              </div>
            )}
          </div>
        )}

        {/* ── Omission warnings ── */}
        {report.omission_warnings && report.omission_warnings.length > 0 && (
          <div
            className="rounded-lg"
            style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
          >
            <div
              className="px-5 py-3 flex items-center gap-2"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <AlertOctagon className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--danger)' }} />
              <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                Policy Omission Warnings
              </span>
            </div>
            {report.omission_warnings.map((w, i) => (
              <div
                key={i}
                className="px-5 py-3 text-sm"
                style={{
                  borderBottom: i < report.omission_warnings!.length - 1 ? '1px solid var(--border)' : 'none',
                  color: 'var(--text-secondary)',
                }}
              >
                <strong style={{ color: '#f87171' }}>⚠ </strong>{w}
              </div>
            ))}
          </div>
        )}
      </div>

      <ImpactDetailModal
        isOpen={isImpactOpen}
        onClose={() => setIsImpactOpen(false)}
        impact={activeImpact}
      />

      <GrievanceSelector
        isOpen={isGrievanceOpen}
        onClose={() => setIsGrievanceOpen(false)}
        impacts={unifiedImpacts}
        onSubmit={handleGrievanceSubmit}
      />
    </div>
  );
}
