'use client';

import React from 'react';
import { useApp } from './context/AppContext';
import {
  Upload, Play, RefreshCw, CheckCircle2, AlertTriangle,
  Cpu, Shield, AlertOctagon, Scale, FileText, Sparkles,
} from 'lucide-react';
import { parseSummaryToPoints } from '@/components/ExecutiveSummary';

function VerdictChip({ verdict }: { verdict: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    positive: { label: 'Positive', cls: 'chip-success' },
    negative: { label: 'Negative', cls: 'chip-danger' },
    mixed:    { label: 'Mixed',    cls: 'chip-warning' },
  };
  const cfg = map[verdict?.toLowerCase()] ?? map.mixed;
  return <span className={`chip ${cfg.cls}`}>{cfg.label}</span>;
}

export default function OverviewPage() {
  const {
    samples, selectedSample, setSelectedSample,
    file, setFile,
    isProcessing, events, report,
    handleUploadAndRun,
  } = useApp();

  const completedCount = events.filter((e) => e.status === 'completed').length;
  const failedCount    = events.filter((e) => e.status === 'failed').length;
  const runningAgent   = events.find((e) => e.status === 'running')?.stage;

  const unifiedImpacts = (() => {
    if (!report) return [];
    if (report.impacts && report.impacts.length > 0) return report.impacts;
    const pos = Array.from(new Set(report.positive_impacts || []));
    const neg = Array.from(new Set(report.negative_impacts || []));
    return [
      ...pos.map((text) => ({ text, polarity: 'positive' as const, affected_group: '', impact_reasoning: '', critic_confirmed: null, critic_note: null, overlooked_subgroups: [] })),
      ...neg.map((text) => ({ text, polarity: 'negative' as const, affected_group: '', impact_reasoning: '', critic_confirmed: null, critic_note: null, overlooked_subgroups: [] })),
    ];
  })();

  const riskFlags         = Array.from(new Set(report?.risk_flags || []));
  const legalCitations    = (report?.legal_grounding || []).filter((lg: any, i: number, arr: any[]) => arr.findIndex((x: any) => x.citation === lg.citation) === i).length;
  const verifiedClaims    = (report?.claim_confidence || []).filter((c: any) => c.status === 'ADMITTED').length;
  const stakeholderCount  = Array.from(new Set(report?.stakeholders_impacted || [])).length;

  const positiveCount = unifiedImpacts.filter((i) => i.polarity === 'positive').length;
  const negativeCount = unifiedImpacts.filter((i) => i.polarity === 'negative').length;
  const mixedCount    = unifiedImpacts.filter((i) => i.polarity === 'neutral_mixed').length;
  const totalImpacts  = unifiedImpacts.length;

  return (
    <div className="animate-in min-h-screen" style={{ background: 'var(--bg-base)' }}>

      {/* ── Header ── */}
      <div className="page-header">
        <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)', letterSpacing: '-0.015em' }}>
          Analysis Overview
        </h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
          Upload a municipal document or select a sample to begin.
        </p>
      </div>

      <div className="page-body space-y-5">

        {/* ── Upload Form ── */}
        <div
          className="rounded-lg p-5"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
        >
          <div className="text-xs font-semibold mb-3" style={{ color: 'var(--text-muted)' }}>
            Document Analysis
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* Upload zone */}
            <div className="md:col-span-2">
              <label
                htmlFor="pdf-upload-input"
                className={`upload-zone block ${file ? 'has-file' : ''}`}
              >
                <input
                  type="file"
                  accept=".pdf,.txt"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="pdf-upload-input"
                />
                <Upload className="w-5 h-5 mx-auto mb-2" style={{ color: file ? 'var(--accent)' : 'var(--text-faint)' }} />
                <div className="text-sm font-medium" style={{ color: file ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                  {file ? file.name : 'Click to upload PDF or TXT'}
                </div>
                <div className="text-xs mt-0.5" style={{ color: 'var(--text-faint)' }}>
                  BBMP, BDA, Panchayat notices · OCR enabled
                </div>
              </label>
            </div>

            {/* Sample + launch */}
            <div className="flex flex-col gap-2.5">
              <div>
                <div className="text-xs mb-1.5" style={{ color: 'var(--text-muted)' }}>
                  Or use a sample
                </div>
                <select
                  value={selectedSample}
                  onChange={(e) => { setSelectedSample(e.target.value); setFile(null); }}
                  className="input w-full"
                >
                  <option value="">Select sample…</option>
                  {samples.length > 0
                    ? samples.map((s) => <option key={s} value={s}>{s}</option>)
                    : (
                      <>
                        <option value="bda_zoning_notice.pdf">BDA Zoning Notice (Ward 150)</option>
                        <option value="bbmp_council_agenda.pdf">BBMP Council Agenda & Tax Revision</option>
                        <option value="rti_response.pdf">RTI Online Response Notice</option>
                      </>
                    )
                  }
                </select>
              </div>

              <button
                type="button"
                id="analyze-btn"
                onClick={handleUploadAndRun}
                disabled={isProcessing}
                className="btn btn-primary w-full"
                style={{ paddingTop: '0.625rem', paddingBottom: '0.625rem' }}
              >
                {isProcessing ? (
                  <><RefreshCw className="w-3.5 h-3.5 animate-spin" /><span>Running…</span></>
                ) : (
                  <><Play className="w-3.5 h-3.5 fill-current" /><span>Analyze Document</span></>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* ── Processing status ── */}
        {isProcessing && (
          <div
            className="rounded-lg px-4 py-3 animate-in"
            style={{ background: 'var(--accent-dim)', border: '1px solid var(--accent-border)' }}
          >
            <div className="flex items-center gap-3">
              <Cpu className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--accent)' }} />
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                {runningAgent ? runningAgent : 'Initializing pipeline…'}
              </span>
              <span className="ml-auto text-xs" style={{ color: 'var(--text-muted)' }}>
                {completedCount}/12
              </span>
            </div>
            <div className="mt-2 progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${(completedCount / 12) * 100}%`, background: 'var(--accent)' }}
              />
            </div>
            <div className="mt-1.5 text-[11px]" style={{ color: 'var(--text-muted)' }}>
              Executing multi-agent verification pipeline — this might take a while.
            </div>
          </div>
        )}

        {/* ── Results ── */}
        {report && (
          <div className="space-y-4 animate-in">

            {/* Verdict + summary */}
            <div
              className="rounded-lg"
              style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
            >
              {/* Title row */}
              <div
                className="px-5 py-3.5 flex items-center gap-3 flex-wrap"
                style={{ borderBottom: '1px solid var(--border)' }}
              >
                <VerdictChip verdict={report.overall_verdict} />
                {report.jurisdiction && (
                  <span className="chip chip-accent">
                    {report.jurisdiction.replace(/_/g, ' ')}
                  </span>
                )}
                {completedCount > 0 && (
                  <span className="ml-auto chip chip-neutral flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" style={{ color: 'var(--success)' }} />
                    {completedCount}/12 agents
                    {failedCount > 0 && <span style={{ color: 'var(--danger)' }}> · {failedCount} failed</span>}
                  </span>
                )}
              </div>

              {/* Summary text - Point-by-point presentation */}
              <div className="px-5 py-4 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                    Executive Policy Summary
                  </span>
                  {report.policy_summary && (
                    <span className="chip chip-neutral text-[10px] flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-sky-400" />
                      <span>{parseSummaryToPoints(report.policy_summary).length} Key Points</span>
                    </span>
                  )}
                </div>

                <div className="space-y-2">
                  {parseSummaryToPoints(report.policy_summary).map((point, idx) => (
                    <div
                      key={idx}
                      className="flex items-start gap-2.5 p-2.5 rounded-md transition-colors"
                      style={{
                        background: 'rgba(255, 255, 255, 0.015)',
                        border: '1px solid rgba(255, 255, 255, 0.04)',
                      }}
                    >
                      <div
                        className="flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold mt-0.5"
                        style={{
                          background: 'var(--accent-dim)',
                          color: 'var(--accent)',
                          border: '1px solid var(--accent-border)',
                        }}
                      >
                        {idx + 1}
                      </div>
                      <p className="text-sm leading-relaxed flex-1" style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                        {point}
                      </p>
                    </div>
                  ))}
                </div>

                {/* Addressee */}
                {report.stated_objection_authority && (
                  <div className="mt-3 pt-2.5 flex items-center gap-2 flex-wrap" style={{ borderTop: '1px solid var(--border)' }}>
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Addressee:</span>
                    <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                      {report.stated_objection_authority}
                    </span>
                    {report.authority_status && (
                      <span
                        className="chip"
                        style={{
                          background: report.authority_status === 'ADMITTED' ? 'var(--success-dim)' : 'var(--danger-dim)',
                          color: report.authority_status === 'ADMITTED' ? 'var(--success)' : '#f87171',
                          border: 'none',
                        }}
                      >
                        {report.authority_status}
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Stats row */}
              <div
                className="px-5 py-3 grid grid-cols-2 md:grid-cols-4 gap-4"
                style={{ borderTop: '1px solid var(--border)' }}
              >
                {[
                  { label: 'Stakeholders', value: stakeholderCount, Icon: FileText },
                  { label: 'Risk Flags',   value: riskFlags.length, Icon: AlertTriangle,
                    color: riskFlags.length > 0 ? 'var(--warning)' : undefined },
                  { label: 'Legal Citations', value: legalCitations, Icon: Scale },
                  { label: 'Verified Claims', value: verifiedClaims, Icon: Shield,
                    color: verifiedClaims > 0 ? 'var(--success)' : undefined },
                ].map(({ label, value, Icon, color }) => (
                  <div key={label} className="flex items-center gap-2.5">
                    <Icon className="w-4 h-4 flex-shrink-0" style={{ color: color || 'var(--text-faint)' }} />
                    <div>
                      <div
                        className="text-base font-semibold leading-none"
                        style={{ color: color || 'var(--text-primary)', letterSpacing: '-0.01em' }}
                      >
                        {value}
                      </div>
                      <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                        {label}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Risk flags */}
            {riskFlags.length > 0 && (
              <div
                className="rounded-lg"
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
              >
                <div
                  className="px-5 py-3 flex items-center gap-2"
                  style={{ borderBottom: '1px solid var(--border)' }}
                >
                  <AlertTriangle className="w-3.5 h-3.5" style={{ color: 'var(--warning)' }} />
                  <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                    Risk Flags
                  </span>
                  <span className="ml-auto chip chip-neutral">{riskFlags.length}</span>
                </div>
                <ul>
                  {riskFlags.slice(0, 4).map((flag, i) => (
                    <li
                      key={i}
                      className="px-5 py-2.5 flex items-start gap-3 text-sm"
                      style={{
                        borderBottom: i < Math.min(riskFlags.length, 4) - 1 ? '1px solid var(--border)' : 'none',
                        color: 'var(--text-secondary)',
                      }}
                    >
                      <span
                        className="mt-0.5 text-[10px] font-bold flex-shrink-0 w-4 h-4 rounded flex items-center justify-center"
                        style={{ background: 'var(--warning-dim)', color: 'var(--warning)' }}
                      >
                        {i + 1}
                      </span>
                      {flag}
                    </li>
                  ))}
                  {riskFlags.length > 4 && (
                    <li className="px-5 py-2 text-xs" style={{ color: 'var(--text-muted)' }}>
                      + {riskFlags.length - 4} more on the Policy page
                    </li>
                  )}
                </ul>
              </div>
            )}

            {/* Impact summary */}
            {totalImpacts > 0 && (
              <div
                className="rounded-lg"
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
              >
                <div
                  className="px-5 py-3 flex items-center gap-3"
                  style={{ borderBottom: '1px solid var(--border)' }}
                >
                  <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                    Impact Summary
                  </span>

                  {/* Polarity balance bar */}
                  <div className="flex-1 max-w-32">
                    <div className="polarity-bar">
                      {positiveCount > 0 && (
                        <div className="polarity-positive flex-1 rounded-sm" style={{ flex: positiveCount }} />
                      )}
                      {negativeCount > 0 && (
                        <div className="polarity-negative flex-1 rounded-sm" style={{ flex: negativeCount }} />
                      )}
                      {mixedCount > 0 && (
                        <div className="polarity-mixed flex-1 rounded-sm" style={{ flex: mixedCount }} />
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-muted)' }}>
                    {positiveCount > 0 && (
                      <span><span style={{ color: 'var(--success)' }}>{positiveCount}</span> positive</span>
                    )}
                    {negativeCount > 0 && (
                      <span><span style={{ color: 'var(--danger)' }}>{negativeCount}</span> negative</span>
                    )}
                    {mixedCount > 0 && (
                      <span><span style={{ color: 'var(--warning)' }}>{mixedCount}</span> mixed</span>
                    )}
                  </div>
                </div>

                {/* Top impacts */}
                <div>
                  {unifiedImpacts.slice(0, 3).map((impact, i) => (
                    <div
                      key={i}
                      className={`impact-row ${impact.polarity === 'positive' ? 'positive' : impact.polarity === 'negative' ? 'negative' : 'mixed'}`}
                    >
                      <p className="text-sm flex-1" style={{ color: 'var(--text-secondary)' }}>
                        {impact.text}
                      </p>
                    </div>
                  ))}
                  {totalImpacts > 3 && (
                    <div className="px-5 py-2 text-xs" style={{ color: 'var(--text-muted)' }}>
                      {totalImpacts - 3} more on Stakeholders page
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Empty state ── */}
        {!report && !isProcessing && (
          <div
            className="rounded-lg p-10 text-center"
            style={{ border: '1px dashed var(--border)', background: 'var(--bg-surface)' }}
          >
            <AlertOctagon className="w-8 h-8 mx-auto mb-3" style={{ color: 'var(--text-faint)' }} />
            <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
              No analysis yet
            </p>
            <p className="text-xs mt-1 max-w-xs mx-auto" style={{ color: 'var(--text-muted)' }}>
              Upload a municipal notice or select a pre-loaded sample above, then click Analyze.
            </p>
            <p className="text-xs mt-2" style={{ color: 'var(--text-faint)' }}>
              This might take a while as agents analyze, cross-verify, and ground the document.
            </p>
          </div>
        )}

      </div>
    </div>
  );
}
