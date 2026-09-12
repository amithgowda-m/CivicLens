'use client';

import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import {
  FileText, Scale, AlertTriangle, AlertOctagon,
  ChevronDown, ChevronRight, Search, CheckCircle2,
} from 'lucide-react';

function AccordionRow({
  title,
  badge,
  children,
  defaultOpen = false,
}: {
  title: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ borderBottom: '1px solid var(--border)' }}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3 text-left transition-colors hover:bg-white/[0.02]"
      >
        <div className="flex items-center gap-2.5 flex-1 min-w-0 pr-3">
          {open
            ? <ChevronDown className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--accent)' }} />
            : <ChevronRight className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--text-faint)' }} />
          }
          <span className="text-sm font-medium truncate" style={{ color: 'var(--text-secondary)' }}>
            {title}
          </span>
        </div>
        {badge}
      </button>
      {open && (
        <div className="px-5 pb-4" style={{ borderTop: '1px solid var(--border)' }}>
          <div className="pt-3">{children}</div>
        </div>
      )}
    </div>
  );
}

export default function PolicyPage() {
  const { report } = useApp();
  const [search, setSearch] = useState('');

  if (!report) {
    return (
      <div className="animate-in min-h-screen">
        <div className="page-header">
          <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)', letterSpacing: '-0.015em' }}>
            Policy Analysis
          </h1>
        </div>
        <div className="flex items-center justify-center h-[70vh]">
          <div className="text-center">
            <FileText className="w-8 h-8 mx-auto mb-3" style={{ color: 'var(--text-faint)' }} />
            <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>No policy data available</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
              Run an analysis from the <strong style={{ color: 'var(--accent)' }}>Overview</strong> page first.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const riskFlags = Array.from(new Set(report.risk_flags || []));
  const legalGrounding = (report.legal_grounding || []).filter(
    (lg: any, i: number, arr: any[]) => arr.findIndex((x: any) => x.citation === lg.citation) === i
  );
  const policyContradictions = (report.policy_contradictions || []).filter(
    (c: any, i: number, arr: any[]) =>
      arr.findIndex((x: any) => (x.notes || x.explanation) === (c.notes || c.explanation)) === i
  );

  const filteredLegal = search
    ? legalGrounding.filter(
        (item: any) =>
          (item.citation || '').toLowerCase().includes(search.toLowerCase()) ||
          (item.notes || '').toLowerCase().includes(search.toLowerCase())
      )
    : legalGrounding;

  const statusMap: Record<string, { chip: string; label: string }> = {
    matched:            { chip: 'chip-success', label: 'Matched' },
    contradictory:      { chip: 'chip-danger',  label: 'Contradictory' },
    corpus_unavailable: { chip: 'chip-neutral', label: 'Corpus N/A' },
    not_found:          { chip: 'chip-warning', label: 'Not Found' },
  };

  return (
    <div className="animate-in min-h-screen">
      {/* Header */}
      <div className="page-header">
        <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)', letterSpacing: '-0.015em' }}>
          Policy Analysis
        </h1>
        <div className="flex flex-wrap gap-2 mt-2">
          {report.jurisdiction && (
            <span className="chip chip-accent">
              {report.jurisdiction.replace(/_/g, ' ')}
            </span>
          )}
          {report.stated_objection_authority && (
            <span className="chip chip-neutral">
              Addressee: {report.stated_objection_authority}
              {report.authority_status && (
                <span
                  className="ml-1 font-semibold"
                  style={{ color: report.authority_status === 'ADMITTED' ? 'var(--success)' : '#f87171' }}
                >
                  [{report.authority_status}]
                </span>
              )}
            </span>
          )}
        </div>
      </div>

      <div className="page-body space-y-5">

        {/* ── Executive Summary ── */}
        <div
          className="rounded-lg"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
        >
          <div
            className="px-5 py-3 flex items-center gap-2"
            style={{ borderBottom: '1px solid var(--border)' }}
          >
            <FileText className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--text-muted)' }} />
            <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
              Executive Summary
            </span>
          </div>
          <div className="px-5 py-4">
            <p
              className="text-sm leading-relaxed"
              style={{ color: 'var(--text-secondary)', maxWidth: '80ch', lineHeight: '1.7' }}
            >
              {report.policy_summary}
            </p>
          </div>
        </div>

        {/* ── Legal Grounding ── */}
        <div
          className="rounded-lg"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
        >
          <div
            className="px-5 py-3 flex items-center gap-3 flex-wrap"
            style={{ borderBottom: '1px solid var(--border)' }}
          >
            <Scale className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--text-muted)' }} />
            <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
              Statutory Legal Grounding
              {report.jurisdiction && ` — ${report.jurisdiction.replace(/_/g, ' ')}`}
            </span>
            <span className="ml-auto chip chip-neutral">{filteredLegal.length} citations</span>

            {/* Search */}
            <div className="relative w-full mt-2">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: 'var(--text-faint)' }} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search citations or notes…"
                className="input w-full pl-8 text-xs"
              />
            </div>
          </div>

          {filteredLegal.length > 0 ? filteredLegal.map((item: any, i: number) => {
            const rawStatus = (item.grounding_status || (item.grounded ? 'matched' : 'not_found')).toLowerCase();
            const sCfg = statusMap[rawStatus] || statusMap.not_found;
            return (
              <AccordionRow
                key={i}
                title={item.citation || 'Statute Citation'}
                badge={<span className={`chip ${sCfg.chip} flex-shrink-0`}>{sCfg.label}</span>}
                defaultOpen={i === 0}
              >
                {item.notes && (
                  <p className="text-xs leading-relaxed mb-3" style={{ color: 'var(--text-muted)' }}>
                    {item.notes}
                  </p>
                )}
                {item.statute_excerpt && (
                  <div
                    className="rounded px-3 py-2.5 text-xs font-mono leading-relaxed"
                    style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', color: '#93c5fd' }}
                  >
                    "{item.statute_excerpt}"
                  </div>
                )}
                {!item.notes && !item.statute_excerpt && (
                  <p className="text-xs italic" style={{ color: 'var(--text-faint)' }}>No additional details.</p>
                )}
              </AccordionRow>
            );
          }) : (
            <div className="px-5 py-6 text-xs text-center italic" style={{ color: 'var(--text-faint)' }}>
              {search ? 'No citations match your search.' : 'No legal grounding data available.'}
            </div>
          )}
        </div>

        {/* ── Risk Flags ── */}
        {(riskFlags.length > 0 || (report.omission_warnings && report.omission_warnings.length > 0)) && (
          <div
            className="rounded-lg"
            style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
          >
            <div
              className="px-5 py-3 flex items-center gap-2"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--warning)' }} />
              <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                Risk Flags & Omissions
              </span>
              <span className="ml-auto chip chip-warning">{riskFlags.length + (report.omission_warnings?.length || 0)}</span>
            </div>

            {/* Omission warnings */}
            {report.omission_warnings && report.omission_warnings.map((w: string, i: number) => (
              <div
                key={`o-${i}`}
                className="px-5 py-3 flex items-start gap-3 text-sm"
                style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}
              >
                <AlertOctagon className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" style={{ color: 'var(--danger)' }} />
                <span><strong style={{ color: '#f87171' }}>Omission:</strong> {w}</span>
              </div>
            ))}

            {/* Risk flags */}
            {riskFlags.map((flag, i) => (
              <div
                key={i}
                className="px-5 py-3 flex items-start gap-3 text-sm"
                style={{
                  borderBottom: i < riskFlags.length - 1 ? '1px solid var(--border)' : 'none',
                  color: 'var(--text-secondary)',
                }}
              >
                <span
                  className="flex-shrink-0 text-[10px] font-bold w-4 h-4 rounded flex items-center justify-center mt-0.5"
                  style={{ background: 'var(--warning-dim)', color: 'var(--warning)' }}
                >
                  {i + 1}
                </span>
                {flag}
              </div>
            ))}
          </div>
        )}

        {/* ── Policy Contradictions ── */}
        <div
          className="rounded-lg"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
        >
          <div
            className="px-5 py-3 flex items-center gap-2"
            style={{ borderBottom: '1px solid var(--border)' }}
          >
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--text-muted)' }} />
            <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
              Policy Contradictions — Historical Memory
            </span>
          </div>

          {policyContradictions.length > 0 ? (
            policyContradictions.map((c: any, i: number) => (
              <div
                key={i}
                className="px-5 py-4 flex items-start gap-3"
                style={{ borderBottom: i < policyContradictions.length - 1 ? '1px solid var(--border)' : 'none' }}
              >
                <div
                  className="flex-shrink-0 text-[10px] font-bold w-5 h-5 rounded flex items-center justify-center mt-0.5"
                  style={{ background: 'rgba(249,115,22,0.15)', color: '#f97316' }}
                >
                  {i + 1}
                </div>
                <div>
                  <div className="text-xs font-semibold mb-1" style={{ color: '#fb923c' }}>
                    Policy Reversal Detected
                  </div>
                  <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                    {c.notes || c.explanation || 'Direct policy contradiction against earlier municipal notice.'}
                  </p>
                </div>
              </div>
            ))
          ) : (
            <div className="px-5 py-4 flex items-center gap-2.5">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--success)' }} />
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                No policy reversals detected against historical ward records.
              </p>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
