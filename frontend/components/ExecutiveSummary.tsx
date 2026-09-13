'use client';

import React from 'react';
import { FileText, UserCheck, Sparkles } from 'lucide-react';

export function parseSummaryToPoints(summary: string): string[] {
  if (!summary) return [];

  // Check if string contains newline-delimited bullet points or items
  const lines = summary
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  const bulletLines = lines
    .map((l) => l.replace(/^[-*•\d+.)\]]\s*/, '').trim())
    .filter((l) => l.length > 0);

  if (bulletLines.length > 1) {
    return bulletLines;
  }

  // If it's a single block / paragraph wall of text, split by sentence boundaries or semicolons
  // Split after punctuation followed by space and capital letter or digit, or after semicolons
  const rawPoints = summary
    .split(/(?<=[.?!])\s+(?=[A-Z0-9])|;\s+/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0)
    // Clean leading bullets or punctuation
    .map((p) => p.replace(/^[-*•\d+.)\]]\s*/, '').trim())
    .filter((p) => p.length > 0);

  if (rawPoints.length > 1) {
    return rawPoints;
  }

  return [summary.replace(/^[-*•\d+.)\]]\s*/, '').trim()];
}

interface ExecutiveSummaryProps {
  summary: string;
  jurisdiction?: string;
  statedAuthority?: string;
  authorityStatus?: string;
  title?: string;
  subtitle?: string;
}

export function ExecutiveSummary({
  summary,
  jurisdiction,
  statedAuthority,
  authorityStatus,
  title = 'Executive Policy Summary',
  subtitle,
}: ExecutiveSummaryProps) {
  const points = parseSummaryToPoints(summary);

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div
        className="px-5 py-3 flex items-center justify-between gap-2 flex-wrap"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2">
          <FileText className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--accent)' }} />
          <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
            {title}
          </span>
        </div>
        <div className="flex items-center gap-2 ml-auto">
          {points.length > 0 && (
            <span className="chip chip-neutral text-[11px] flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-sky-400" />
              <span>{points.length} Key Provision{points.length !== 1 ? 's' : ''}</span>
            </span>
          )}
        </div>
      </div>

      {/* Point-by-point body */}
      <div className="p-5 space-y-3">
        {subtitle && (
          <p className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>
            {subtitle}
          </p>
        )}

        <div className="space-y-2.5">
          {points.map((point, idx) => (
            <div
              key={idx}
              className="flex items-start gap-3 p-3 rounded-lg transition-colors"
              style={{
                background: 'rgba(255, 255, 255, 0.015)',
                border: '1px solid rgba(255, 255, 255, 0.04)',
              }}
            >
              <div
                className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold mt-0.5"
                style={{
                  background: 'var(--accent-dim)',
                  color: 'var(--accent)',
                  border: '1px solid var(--accent-border)',
                }}
              >
                {idx + 1}
              </div>
              <p
                className="text-sm leading-relaxed flex-1"
                style={{ color: 'var(--text-secondary)', lineHeight: '1.6' }}
              >
                {point}
              </p>
            </div>
          ))}
        </div>

        {/* Metadata Badges (Jurisdiction & Addressee) */}
        {(jurisdiction || statedAuthority) && (
          <div className="mt-4 pt-3 flex flex-wrap items-center gap-2" style={{ borderTop: '1px solid var(--border)' }}>
            {jurisdiction && (
              <span className="chip chip-accent text-xs">
                Jurisdiction: {jurisdiction.replace(/_/g, ' ')}
              </span>
            )}
            {statedAuthority && (
              <span className="chip chip-neutral text-xs flex items-center gap-1.5">
                <UserCheck className="w-3.5 h-3.5" style={{ color: 'var(--text-muted)' }} />
                <span>Addressee: <strong>{statedAuthority}</strong></span>
                {authorityStatus && (
                  <span
                    className="font-semibold ml-1 text-[10px]"
                    style={{
                      color: authorityStatus === 'ADMITTED' ? 'var(--success)' : '#f87171',
                    }}
                  >
                    [{authorityStatus}]
                  </span>
                )}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
