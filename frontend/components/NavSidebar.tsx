'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  FileText,
  Cpu,
  Users,
  ShieldCheck,
  Activity,
} from 'lucide-react';
import { useApp } from '@/app/context/AppContext';

const NAV_ITEMS = [
  { href: '/',             label: 'Overview',     icon: LayoutDashboard },
  { href: '/policy',      label: 'Policy',        icon: FileText },
  { href: '/agents',      label: 'Agents',        icon: Cpu },
  { href: '/stakeholders',label: 'Stakeholders',  icon: Users },
  { href: '/evidence',    label: 'Evidence',      icon: ShieldCheck },
];

export function NavSidebar() {
  const pathname = usePathname();
  const { isProcessing, events, report } = useApp();

  const completedAgents = events.filter((e) => e.status === 'completed').length;
  const totalAgents = 12;

  const pipelineStatus = isProcessing ? 'running' : report ? 'complete' : 'idle';

  return (
    <aside
      className="fixed left-0 top-0 h-screen flex flex-col z-40"
      style={{
        width: 'var(--nav-width)',
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border)',
      }}
    >
      {/* ── Logo ── */}
      <div
        className="px-4 py-4 flex items-center gap-2.5"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div
          className="w-7 h-7 rounded flex items-center justify-center flex-shrink-0"
          style={{ background: 'var(--accent)', opacity: 0.9 }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 4h10M2 7h7M2 10h5" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </div>
        <div>
          <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
            CivicLens
          </div>
          <div className="text-[10px]" style={{ color: 'var(--text-faint)' }}>
            Policy Analysis
          </div>
        </div>
      </div>

      {/* ── Nav ── */}
      <nav className="flex-1 px-2.5 py-3 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`nav-link ${isActive ? 'active' : ''}`}
            >
              <Icon className="w-[15px] h-[15px] flex-shrink-0" />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* ── Pipeline Status ── */}
      <div
        className="px-3.5 py-3.5"
        style={{ borderTop: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2 mb-1.5">
          <Activity
            className="w-3 h-3 flex-shrink-0"
            style={{
              color: pipelineStatus === 'running'
                ? 'var(--warning)'
                : pipelineStatus === 'complete'
                ? 'var(--success)'
                : 'var(--text-faint)',
            }}
          />
          <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
            Pipeline
          </span>
          <span
            className="ml-auto text-[11px] font-medium"
            style={{
              color: pipelineStatus === 'running'
                ? 'var(--warning)'
                : pipelineStatus === 'complete'
                ? 'var(--success)'
                : 'var(--text-faint)',
            }}
          >
            {pipelineStatus === 'running' ? 'Running' : pipelineStatus === 'complete' ? 'Complete' : 'Ready'}
          </span>
        </div>

        {(isProcessing || completedAgents > 0) && (
          <>
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{
                  width: `${(completedAgents / totalAgents) * 100}%`,
                  background: isProcessing ? 'var(--accent)' : 'var(--success)',
                }}
              />
            </div>
            <div className="mt-1 text-[10px]" style={{ color: 'var(--text-faint)' }}>
              {completedAgents}/{totalAgents} agents
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
