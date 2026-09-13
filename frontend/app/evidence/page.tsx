'use client';

import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import {
  ShieldCheck, FileText, AlertTriangle, CheckCircle2, XCircle,
  AlertOctagon, ExternalLink, ArrowRight, Loader2,
  ChevronDown, ChevronRight, UserCheck,
} from 'lucide-react';
import { GrievanceSelector } from '@/components/GrievanceSelector';
import { ImpactItemData } from '@/app/context/AppContext';

function VerdictBar({ verdict }: { verdict: string }) {
  const map: Record<string, { label: string; chipCls: string; desc: string }> = {
    positive: { label: 'Positive Verdict', chipCls: 'chip-success', desc: 'Analysis indicates net civic benefit.' },
    negative: { label: 'Negative Verdict', chipCls: 'chip-danger',  desc: 'Analysis indicates significant civic harm — objection warranted.' },
    mixed:    { label: 'Mixed Verdict',    chipCls: 'chip-warning', desc: 'Analysis indicates mixed outcomes — review carefully.' },
  };
  const cfg = map[verdict?.toLowerCase()] ?? map.mixed;
  return (
    <div
      className="rounded-lg px-5 py-3 flex items-center gap-3"
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
    >
      <ShieldCheck className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--text-muted)' }} />
      <span className={`chip ${cfg.chipCls}`}>{cfg.label}</span>
      <span className="text-sm" style={{ color: 'var(--text-muted)' }}>{cfg.desc}</span>
    </div>
  );
}

function ClaimRow({
  claim,
  onOpenProvenance,
  onResolveAudit,
}: {
  claim: any;
  onOpenProvenance: (c: any) => void;
  onResolveAudit?: (id: string, approved: boolean) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const isAdmitted = claim.status === 'ADMITTED';
  const isPending  = claim.status === 'PENDING_AUDIT';
  const nliScore   = claim.nli_score ? Math.round(claim.nli_score * 100) : null;

  const statusChipCls = isAdmitted ? 'chip-success' : isPending ? 'chip-warning' : 'chip-danger';
  const statusLabel   = isAdmitted ? 'Admitted' : isPending ? 'Pending' : 'Rejected';

  return (
    <>
      <div className="claim-row">
        <div className="flex items-start gap-3">
          {/* Page ref */}
          <code
            className="text-[10px] flex-shrink-0 mt-0.5 px-1.5 py-0.5 rounded"
            style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)', color: 'var(--text-faint)', fontFamily: 'inherit' }}
          >
            P{claim.page || 1}
          </code>

          {/* Claim text */}
          <p className="flex-1 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            {claim.text}
          </p>

          {/* NLI score */}
          {nliScore !== null && (
            <div className="flex-shrink-0 flex items-center gap-1.5 hidden md:flex">
              <span className="text-[10px]" style={{ color: 'var(--text-faint)' }}>NLI</span>
              <div className="w-12 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-overlay)' }}>
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${nliScore}%`,
                    background: nliScore >= 80 ? 'var(--success)' : nliScore >= 60 ? 'var(--warning)' : 'var(--danger)',
                  }}
                />
              </div>
              <span className="text-[10px] font-semibold" style={{ color: 'var(--text-muted)' }}>{nliScore}%</span>
            </div>
          )}

          {/* Status */}
          <span className={`chip ${statusChipCls} flex-shrink-0`}>{statusLabel}</span>

          {/* Actions */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={() => onOpenProvenance(claim)}
              className="text-xs flex items-center gap-1 transition-colors"
              style={{ color: 'var(--accent)' }}
            >
              <ExternalLink className="w-3 h-3" />
              <span className="hidden sm:inline">Source</span>
            </button>
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs flex items-center gap-1 transition-colors"
              style={{ color: 'var(--text-muted)' }}
            >
              {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            </button>
          </div>
        </div>

        {/* Pending audit controls */}
        {isPending && onResolveAudit && (
          <div className="flex gap-2 mt-2 pl-7">
            <button
              onClick={() => onResolveAudit(claim.claim_id, true)}
              className="btn"
              style={{ background: 'var(--success-dim)', color: 'var(--success)', border: '1px solid rgba(34,197,94,0.2)', fontSize: '11px', padding: '0.2rem 0.6rem' }}
            >
              <CheckCircle2 className="w-3 h-3" /> Approve
            </button>
            <button
              onClick={() => onResolveAudit(claim.claim_id, false)}
              className="btn btn-danger"
              style={{ fontSize: '11px', padding: '0.2rem 0.6rem' }}
            >
              <XCircle className="w-3 h-3" /> Reject
            </button>
          </div>
        )}
      </div>

      {/* Expanded provenance detail */}
      {expanded && (
        <div
          className="px-5 py-3 text-xs space-y-2 animate-in"
          style={{ background: 'rgba(255,255,255,0.015)', borderBottom: '1px solid var(--border)' }}
        >
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            <div className="rounded px-3 py-2" style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}>
              <div className="section-label mb-0.5">Character Range</div>
              <span style={{ color: 'var(--text-secondary)' }}>
                {claim.char_start || 0}–{claim.char_end || 0}
              </span>
            </div>
            {claim.jurisdiction_hint && (
              <div className="rounded px-3 py-2" style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}>
                <div className="section-label mb-0.5">Jurisdiction</div>
                <span style={{ color: '#93c5fd' }}>{claim.jurisdiction_hint}</span>
              </div>
            )}
            {claim.extraction_source && (
              <div className="rounded px-3 py-2" style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}>
                <div className="section-label mb-0.5">Extraction</div>
                <span className="font-mono" style={{ color: 'var(--success)' }}>
                  {Array.isArray(claim.extraction_source)
                    ? claim.extraction_source.join(' + ')
                    : claim.extraction_source}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

export default function EvidencePage() {
  const { report, setActiveClaim, setIsProvenanceOpen, handleResolveAudit, handleGenerateAction } = useApp();
  const [isGrievanceOpen, setIsGrievanceOpen] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [statusFilter, setStatusFilter] = useState<'all' | 'ADMITTED' | 'PENDING_AUDIT' | 'REJECTED_PRUNED'>('all');

  if (!report) {
    return (
      <div className="animate-in min-h-screen">
        <div className="page-header">
          <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)', letterSpacing: '-0.015em' }}>
            Evidence & Civic Report
          </h1>
        </div>
        <div className="flex items-center justify-center h-[70vh]">
          <div className="text-center">
            <ShieldCheck className="w-8 h-8 mx-auto mb-3" style={{ color: 'var(--text-faint)' }} />
            <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>No evidence data available</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
              Run an analysis from the <strong style={{ color: 'var(--accent)' }}>Overview</strong> page first.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const claims        = report.claim_confidence || [];
  const admittedCount = claims.filter((c: any) => c.status === 'ADMITTED').length;
  const pendingCount  = claims.filter((c: any) => c.status === 'PENDING_AUDIT').length;
  const rejectedCount = claims.filter((c: any) => c.status === 'REJECTED_PRUNED').length;

  const filteredClaims = statusFilter === 'all'
    ? claims
    : claims.filter((c: any) => c.status === statusFilter);

  const isEnacted = report.document_category === 'enacted_regulation_master_plan' || report.action_type_recommended === 'citizen_compliance_guide';

  const handleActionClick = () => {
    const unifiedImpacts: ImpactItemData[] = (() => {
      if (report.impacts && report.impacts.length > 0) return report.impacts;
      return [
        ...Array.from(new Set(report.positive_impacts || [])).map((text) => ({ text, polarity: 'positive' as const, affected_group: '', impact_reasoning: '', critic_confirmed: null, critic_note: null, overlooked_subgroups: [] })),
        ...Array.from(new Set(report.negative_impacts || [])).map((text) => ({ text, polarity: 'negative' as const, affected_group: '', impact_reasoning: '', critic_confirmed: null, critic_note: null, overlooked_subgroups: [] })),
      ];
    })();
    if (!isEnacted && report.overall_verdict !== 'positive' && unifiedImpacts.length > 0) {
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
            {report.document_title || 'Evidence & Civic Report'}
          </h1>
          <div className="flex items-center gap-2 mt-0.5">
            {report.document_legal_status && (
              <span className="chip chip-neutral" style={{ fontSize: '10px' }}>
                {report.document_legal_status.replace(/_/g, ' ')}
              </span>
            )}
            {claims.length > 0 && (
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                {claims.length} claim{claims.length !== 1 ? 's' : ''} analyzed
              </p>
            )}
          </div>
        </div>
        <button
          onClick={handleActionClick}
          disabled={isGenerating}
          className="btn"
          style={{
            background: isEnacted ? 'var(--accent)' : report.overall_verdict === 'positive' ? 'var(--success)' : 'var(--danger)',
            color: '#fff',
            opacity: isGenerating ? 0.5 : 1,
          }}
        >
          {isGenerating
            ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />Generating…</>
            : <>
                {isEnacted ? 'Generate Compliance Guide' : report.overall_verdict === 'positive' ? 'Generate Bulletin' : 'Draft Objection'}
                <ArrowRight className="w-3.5 h-3.5" />
              </>
          }
        </button>
      </div>


      <div className="page-body space-y-5">

        {/* Verdict bar */}
        <VerdictBar verdict={report.overall_verdict} />

        {/* Executive summary */}
        <div
          className="rounded-lg"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
        >
          <div
            className="px-5 py-3 flex items-center gap-2"
            style={{ borderBottom: '1px solid var(--border)' }}
          >
            <FileText className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--text-muted)' }} />
            <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>Executive Summary</span>
          </div>
          <div className="px-5 py-4">
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)', maxWidth: '80ch', lineHeight: '1.7' }}>
              {report.policy_summary}
            </p>
            {(report.jurisdiction || report.stated_objection_authority) && (
              <div className="mt-3 flex flex-wrap gap-2">
                {report.jurisdiction && (
                  <span className="chip chip-accent">
                    Jurisdiction: {report.jurisdiction.replace(/_/g, ' ')}
                  </span>
                )}
                {report.stated_objection_authority && (
                  <span className="chip chip-neutral flex items-center gap-1">
                    <UserCheck className="w-3 h-3" />
                    {report.stated_objection_authority}
                    {report.authority_status && (
                      <span
                        className="font-semibold ml-1"
                        style={{ color: report.authority_status === 'ADMITTED' ? 'var(--success)' : '#f87171' }}
                      >
                        [{report.authority_status}]
                      </span>
                    )}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Claims stats */}
        {claims.length > 0 && (
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Admitted',     count: admittedCount, Icon: CheckCircle2, chipCls: 'chip-success' },
              { label: 'Pending Audit', count: pendingCount, Icon: AlertTriangle, chipCls: 'chip-warning' },
              { label: 'Rejected',     count: rejectedCount, Icon: XCircle,      chipCls: 'chip-danger' },
            ].map(({ label, count, Icon, chipCls }) => (
              <div
                key={label}
                className="rounded-lg px-4 py-3 flex items-center gap-3"
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
              >
                <Icon className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--text-faint)' }} />
                <div>
                  <div
                    className="text-lg font-semibold leading-none"
                    style={{ color: 'var(--text-primary)', letterSpacing: '-0.02em' }}
                  >
                    {count}
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{label}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Dropped claims notice */}
        {report.dropped_claims_count !== undefined && report.dropped_claims_count > 0 && (
          <div
            className="rounded-lg px-4 py-2.5 flex items-center gap-2.5 text-sm"
            style={{ background: 'var(--warning-dim)', border: '1px solid rgba(245,158,11,0.2)', color: 'var(--warning)' }}
          >
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
            <span>
              <strong>{report.dropped_claims_count}</strong> unverified claim(s) failed the NLI entailment gate and were pruned.
            </span>
          </div>
        )}

        {/* Claims table */}
        {claims.length > 0 && (
          <div
            className="rounded-lg overflow-hidden"
            style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
          >
            {/* Toolbar */}
            <div
              className="px-5 py-3 flex items-center gap-3 flex-wrap"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <ShieldCheck className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--text-muted)' }} />
              <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                Claim Confidence & Source Offsets
              </span>
              <span className="ml-auto chip chip-neutral">{filteredClaims.length} claims</span>

              {/* Filter */}
              <div className="flex items-center gap-1">
                {(['all', 'ADMITTED', 'PENDING_AUDIT', 'REJECTED_PRUNED'] as const).map((key) => (
                  <button
                    key={key}
                    onClick={() => setStatusFilter(key)}
                    className="text-[11px] px-2 py-0.5 rounded transition-colors"
                    style={{
                      background: statusFilter === key ? 'var(--accent)' : 'transparent',
                      color: statusFilter === key ? '#fff' : 'var(--text-muted)',
                    }}
                  >
                    {key === 'all' ? 'All' : key === 'PENDING_AUDIT' ? 'Pending' : key === 'REJECTED_PRUNED' ? 'Rejected' : 'Admitted'}
                  </button>
                ))}
              </div>
            </div>

            {filteredClaims.length > 0 ? (
              filteredClaims.map((claim: any, i: number) => (
                <ClaimRow
                  key={i}
                  claim={claim}
                  onOpenProvenance={(c) => { setActiveClaim(c); setIsProvenanceOpen(true); }}
                  onResolveAudit={handleResolveAudit}
                />
              ))
            ) : (
              <div className="px-5 py-8 text-center text-sm italic" style={{ color: 'var(--text-faint)' }}>
                No claims match the selected filter.
              </div>
            )}
          </div>
        )}

      </div>

      <GrievanceSelector
        isOpen={isGrievanceOpen}
        onClose={() => setIsGrievanceOpen(false)}
        impacts={(() => {
          if (report.impacts && report.impacts.length > 0) return report.impacts;
          return [
            ...Array.from(new Set(report.positive_impacts || [])).map((text) => ({ text, polarity: 'positive' as const, affected_group: '', impact_reasoning: '', critic_confirmed: null, critic_note: null, overlooked_subgroups: [] })),
            ...Array.from(new Set(report.negative_impacts || [])).map((text) => ({ text, polarity: 'negative' as const, affected_group: '', impact_reasoning: '', critic_confirmed: null, critic_note: null, overlooked_subgroups: [] })),
          ];
        })()}
        onSubmit={handleGrievanceSubmit}
      />
    </div>
  );
}
