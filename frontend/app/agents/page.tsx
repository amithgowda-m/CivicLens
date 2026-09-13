'use client';

import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import {
  Cpu, CheckCircle2, Loader2, AlertCircle, Clock,
  BarChart2, Zap, X, Brain, Shield, FileText, Search,
  Scale, Eye, RefreshCw, PlayCircle,
} from 'lucide-react';

// ─── Agent definition ──────────────────────────────────────────────────────

interface AgentDef {
  name: string;
  description: string;
  tier: 'core' | 'on_demand';
  icon: React.ComponentType<any>;
}

const AGENTS: AgentDef[] = [
  { name: 'Planner Agent',                icon: Brain,    tier: 'core',      description: 'Emits a sequential execution plan for the pipeline.' },
  { name: 'Ingestion Agent',              icon: FileText, tier: 'core',      description: 'Extracts and parses text from the uploaded PDF with offset provenance.' },
  { name: 'Extraction Agent',             icon: Search,   tier: 'core',      description: 'Extracts verbatim clauses with character-level offsets.' },
  { name: 'Typology Classifier',          icon: Cpu,      tier: 'core',      description: 'Classifies clauses by policy category (land use, tax, zoning…).' },
  { name: 'Memory & Contradiction Agent', icon: RefreshCw,tier: 'core',      description: 'Cross-checks current policy against historical ward notices.' },
  { name: 'Verification Ensemble Gate',   icon: Shield,   tier: 'core',      description: 'NLI Cross-Encoder + LLM Judge dual verification gate.' },
  { name: 'Legal Grounding Agent',        icon: Scale,    tier: 'core',      description: 'Grounds claims against KTCP 1961, GBGA 2024, and BDA Master Plan.' },
  { name: 'Impact Analysis Agent',        icon: BarChart2,tier: 'core',      description: 'Evaluates stakeholder polarities: positive, negative, mixed.' },
  { name: 'Critic Agent (Adversarial)',   icon: Eye,      tier: 'core',      description: 'Audits counter-perspectives and overlooked population subgroups.' },
  { name: 'Report Generation Agent',      icon: FileText, tier: 'core',      description: 'Synthesizes 9 structured report sections from verified data.' },
  { name: 'Action Agent (On-Demand)',     icon: Zap,      tier: 'on_demand', description: 'On-demand generation of citizen objection letters or bulletins.' },
  { name: 'Evaluation Harness',           icon: BarChart2,tier: 'on_demand', description: 'Computes system precision/recall metrics via /api/eval.' },
];

// ─── Status helpers ────────────────────────────────────────────────────────

type AgentStatus = 'pending' | 'running' | 'completed' | 'failed' | 'on_demand';

function getAgentStatus(agent: AgentDef, events: any[], currentStage: string): AgentStatus {
  if (agent.tier === 'on_demand') {
    const ev = events.find((e) => e.stage.toLowerCase().includes(agent.name.toLowerCase()));
    if (ev) return ev.status;
    return 'on_demand';
  }
  const ev = events.find((e) => e.stage.toLowerCase().includes(agent.name.toLowerCase()));
  if (ev) return ev.status;
  if (currentStage.toLowerCase().includes(agent.name.toLowerCase())) return 'running';
  return 'pending';
}

function getAgentDetails(agent: AgentDef, events: any[]): string | undefined {
  return events.find((e) => e.stage.toLowerCase().includes(agent.name.toLowerCase()))?.details;
}

// ─── Status config ─────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<AgentStatus, { dotCls: string; label: string; nodeCls: string }> = {
  completed: { dotCls: 'completed', label: 'Complete',  nodeCls: 'completed' },
  running:   { dotCls: 'running',   label: 'Running',   nodeCls: 'running' },
  failed:    { dotCls: 'failed',    label: 'Failed',    nodeCls: 'failed' },
  on_demand: { dotCls: 'on-demand', label: 'On-Demand', nodeCls: '' },
  pending:   { dotCls: 'pending',   label: 'Waiting',   nodeCls: '' },
};

// ─── Agent node ────────────────────────────────────────────────────────────

function AgentNode({
  agent, status, details, onClick, isSelected, index,
}: {
  agent: AgentDef; status: AgentStatus; details?: string;
  onClick: () => void; isSelected: boolean; index: number;
}) {
  const Icon = agent.icon;
  const cfg = STATUS_CONFIG[status];

  return (
    <button
      onClick={onClick}
      className={`agent-node ${cfg.nodeCls} ${isSelected ? 'selected' : ''}`}
      aria-pressed={isSelected}
    >
      {/* Index */}
      <span
        className="flex-shrink-0 text-[10px] font-bold w-5 h-5 rounded flex items-center justify-center"
        style={{ background: 'var(--bg-overlay)', color: 'var(--text-faint)' }}
      >
        {index + 1}
      </span>

      {/* Status dot */}
      <span className={`status-dot ${cfg.dotCls} flex-shrink-0`} />

      {/* Agent icon */}
      <Icon className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--text-muted)' }} />

      {/* Name + output */}
      <div className="flex-1 min-w-0 text-left">
        <div
          className="text-xs font-medium truncate"
          style={{ color: status === 'pending' ? 'var(--text-faint)' : 'var(--text-primary)' }}
        >
          {agent.name}
        </div>
        {status === 'completed' && details && (
          <div className="text-[10px] truncate mt-0.5" style={{ color: 'var(--text-muted)' }}>
            {details}
          </div>
        )}
        {status === 'running' && (
          <div className="text-[10px] mt-0.5" style={{ color: 'var(--accent)' }}>Active…</div>
        )}
        {status === 'failed' && (
          <div className="text-[10px] mt-0.5" style={{ color: 'var(--danger)' }}>
            {details || 'Failed — check backend logs'}
          </div>
        )}
      </div>

      {/* Status label */}
      <span
        className="chip flex-shrink-0"
        style={{
          background: status === 'completed' ? 'var(--success-dim)' : status === 'running' ? 'var(--accent-dim)' : status === 'failed' ? 'var(--danger-dim)' : status === 'on_demand' ? 'var(--warning-dim)' : 'rgba(255,255,255,0.04)',
          color: status === 'completed' ? 'var(--success)' : status === 'running' ? 'var(--accent)' : status === 'failed' ? '#f87171' : status === 'on_demand' ? 'var(--warning)' : 'var(--text-faint)',
          border: 'none',
        }}
      >
        {cfg.label}
      </span>
    </button>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────

export default function AgentsPage() {
  const { events, currentStage, isProcessing } = useApp();
  const [selectedAgent, setSelectedAgent] = useState<AgentDef | null>(null);

  const coreAgents     = AGENTS.filter((a) => a.tier === 'core');
  const onDemandAgents = AGENTS.filter((a) => a.tier === 'on_demand');

  const totalComplete = AGENTS.filter((a) => getAgentStatus(a, events, currentStage) === 'completed').length;

  const selectedStatus  = selectedAgent ? getAgentStatus(selectedAgent, events, currentStage) : null;
  const selectedDetails = selectedAgent ? getAgentDetails(selectedAgent, events) : null;

  return (
    <div className="animate-in min-h-screen flex flex-col">
      {/* Header */}
      <div className="page-header flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)', letterSpacing: '-0.015em' }}>
            Agent Pipeline
          </h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
            {totalComplete}/{AGENTS.length} agents complete
          </p>
        </div>
        {isProcessing && (
          <span className="chip chip-accent flex items-center gap-1.5">
            <Loader2 className="w-3 h-3 animate-spin" />
            Pipeline running
          </span>
        )}
      </div>

      {/* Body — split pane */}
      <div className="flex flex-1 overflow-hidden" style={{ height: 'calc(100vh - 5.5rem)' }}>

        {/* ── Left: Pipeline ── */}
        <div className="flex-1 overflow-y-auto" style={{ padding: '1rem 1.25rem', borderRight: '1px solid var(--border)' }}>

          {/* Orchestrator */}
          <div
            className="rounded-lg px-4 py-3 mb-3 flex items-center gap-3"
            style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}
          >
            <PlayCircle className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--accent)' }} />
            <div>
              <div className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                LangGraph Orchestrator
              </div>
              <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                MemorySaver thread state · HITL breakpoint enabled
              </div>
            </div>
          </div>

          {/* Core agents */}
          <div className="space-y-1">
            {coreAgents.map((agent, idx) => {
              const status  = getAgentStatus(agent, events, currentStage);
              const details = getAgentDetails(agent, events);
              const isLast  = idx === coreAgents.length - 1;

              return (
                <React.Fragment key={agent.name}>
                  <AgentNode
                    agent={agent}
                    status={status}
                    details={details}
                    index={idx}
                    isSelected={selectedAgent?.name === agent.name}
                    onClick={() => setSelectedAgent(selectedAgent?.name === agent.name ? null : agent)}
                  />
                  {!isLast && (
                    <div className="flex justify-start ml-[1.625rem]">
                      <div
                        className={`connector h-2.5 ${status === 'completed' ? 'completed' : status === 'running' ? 'running' : ''}`}
                        style={{ width: '1px' }}
                      />
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>

          {/* On-demand separator */}
          <div className="flex items-center gap-3 my-3">
            <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
            <span className="section-label">On-Demand</span>
            <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
          </div>

          <div className="space-y-1">
            {onDemandAgents.map((agent, idx) => {
              const status  = getAgentStatus(agent, events, currentStage);
              const details = getAgentDetails(agent, events);
              return (
                <AgentNode
                  key={agent.name}
                  agent={agent}
                  status={status}
                  details={details}
                  index={coreAgents.length + idx}
                  isSelected={selectedAgent?.name === agent.name}
                  onClick={() => setSelectedAgent(selectedAgent?.name === agent.name ? null : agent)}
                />
              );
            })}
          </div>
        </div>

        {/* ── Right: Detail panel ── */}
        <div
          className="w-72 flex-shrink-0 overflow-y-auto"
          style={{ background: 'var(--bg-surface)' }}
        >
          {selectedAgent ? (
            <div className="p-4 space-y-3 animate-in">
              {/* Header */}
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <div
                    className="w-8 h-8 rounded flex items-center justify-center flex-shrink-0"
                    style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)' }}
                  >
                    <selectedAgent.icon className="w-4 h-4" style={{ color: 'var(--text-secondary)' }} />
                  </div>
                  <div>
                    <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                      {selectedAgent.name}
                    </div>
                    <span className="chip chip-neutral text-[10px]">
                      {selectedAgent.tier === 'core' ? 'Core Pipeline' : 'On-Demand'}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedAgent(null)}
                  className="p-1 rounded transition-colors"
                  style={{ color: 'var(--text-muted)' }}
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Description */}
              <div
                className="rounded px-3 py-2.5"
                style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}
              >
                <p className="text-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                  {selectedAgent.description}
                </p>
              </div>

              {/* Status + output */}
              {selectedStatus && (
                <div
                  className="rounded px-3 py-3 space-y-2.5"
                  style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}
                >
                  <div className="flex items-center gap-2">
                    <span className="section-label">Status</span>
                    <span className={`status-dot ${STATUS_CONFIG[selectedStatus].dotCls}`} />
                    <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {STATUS_CONFIG[selectedStatus].label}
                    </span>
                  </div>

                  <div>
                    <div className="section-label mb-1">Output</div>
                    {selectedDetails ? (
                      <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                        {selectedDetails}
                      </p>
                    ) : (
                      <p className="text-xs italic" style={{ color: 'var(--text-faint)' }}>
                        {selectedStatus === 'pending'
                          ? 'Awaiting execution.'
                          : selectedStatus === 'on_demand'
                          ? 'Triggered via user action.'
                          : 'No output captured.'}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full p-6 text-center">
              <div>
                <Cpu className="w-6 h-6 mx-auto mb-2" style={{ color: 'var(--text-faint)' }} />
                <p className="text-xs" style={{ color: 'var(--text-faint)' }}>
                  Select an agent to view details.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
