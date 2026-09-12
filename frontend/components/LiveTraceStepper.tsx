'use client';

import React from 'react';
import { CheckCircle2, Loader2, AlertCircle, Cpu, Zap, BarChart2 } from 'lucide-react';

export interface TraceEvent {
  stage: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'interrupt';
  details?: string;
  timestamp?: string;
}

const AGENT_STAGES = [
  'Planner Agent',
  'Ingestion Agent',
  'Extraction Agent',
  'Typology Classifier',
  'Memory & Contradiction Agent',
  'Verification Ensemble Gate',
  'Legal Grounding Agent',
  'Impact Analysis Agent',
  'Critic Agent (Adversarial)',
  'Report Generation Agent',
  'Action Agent (On-Demand)',
  'Evaluation Harness',
];

const ON_DEMAND_STAGES = new Set(['Action Agent (On-Demand)', 'Evaluation Harness']);

const ON_DEMAND_LABELS: Record<string, string> = {
  'Action Agent (On-Demand)': 'Click "Generate Action" after report loads',
  'Evaluation Harness': 'Runs via /api/eval — score visible in header',
};

interface LiveTraceStepperProps {
  events: TraceEvent[];
  currentStage: string;
  plannerJson: any;
}

export const LiveTraceStepper: React.FC<LiveTraceStepperProps> = ({
  events,
  currentStage,
  plannerJson,
}) => {
  const getStageEvent = (stageName: string): TraceEvent | undefined =>
    events.find((e) => e.stage.toLowerCase().includes(stageName.toLowerCase()));

  const getStageStatus = (stageName: string): TraceEvent['status'] => {
    const match = getStageEvent(stageName);
    if (match) return match.status;
    if (currentStage.toLowerCase().includes(stageName.toLowerCase())) return 'running';
    return 'pending';
  };

  const getStageDetails = (stageName: string): string | undefined =>
    getStageEvent(stageName)?.details;

  return (
    <div className="glass-panel rounded-2xl p-6 shadow-2xl border border-slate-800">
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-800">
        <div className="flex items-center space-x-3">
          <Cpu className="w-5 h-5 text-sky-400 animate-pulse" />
          <h2 className="text-lg font-semibold text-white">Live Agent Trace</h2>
        </div>
        <span className="text-xs px-2.5 py-1 rounded-full bg-sky-950 text-sky-400 border border-sky-800/60 font-mono">
          12 Agents Compiled
        </span>
      </div>

      {plannerJson && (
        <div className="mb-6 p-4 rounded-xl bg-slate-900/90 border border-slate-800 font-mono text-xs">
          <div className="text-slate-400 mb-1 font-sans font-semibold">Planner Execution Plan:</div>
          <pre className="text-sky-300 overflow-x-auto">{JSON.stringify(plannerJson, null, 2)}</pre>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {AGENT_STAGES.map((stage, idx) => {
          const status = getStageStatus(stage);
          const isOnDemand = ON_DEMAND_STAGES.has(stage) && status === 'pending';
          const isFailed = status === 'failed';

          let statusClass = 'bg-slate-900/40 border-slate-800/80 text-slate-500';
          if (status === 'completed') {
            statusClass = 'bg-emerald-950/30 border-emerald-800/50 text-emerald-300';
          } else if (status === 'running') {
            statusClass = 'bg-sky-950/40 border-sky-500/70 text-sky-300 shadow-lg shadow-sky-500/15 ring-1 ring-sky-500/30';
          } else if (isFailed) {
            statusClass = 'bg-red-950/30 border-red-800/50 text-red-400';
          } else if (isOnDemand) {
            statusClass = 'bg-amber-950/20 border-amber-800/40 text-amber-400/80';
          }

          return (
            <div
              key={stage}
              className={`p-3.5 rounded-xl border transition-all duration-500 flex items-start space-x-3 ${statusClass}`}
            >
              <div className="mt-0.5 shrink-0">
                {status === 'completed' && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
                {status === 'running' && <Loader2 className="w-5 h-5 text-sky-400 animate-spin" />}
                {isFailed && <AlertCircle className="w-5 h-5 text-red-400" />}
                {status === 'pending' && !isFailed && (
                  isOnDemand ? (
                    stage === 'Evaluation Harness' ? (
                      <BarChart2 className="w-5 h-5 text-amber-500/60" />
                    ) : (
                      <Zap className="w-5 h-5 text-amber-500/60" />
                    )
                  ) : (
                    <span className="w-5 h-5 rounded-full border border-slate-700 flex items-center justify-center text-[10px] text-slate-500 font-mono">
                      {idx + 1}
                    </span>
                  )
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-semibold truncate">{stage}</div>
                <div className="text-[11px] opacity-75 mt-0.5">
                  {status === 'completed'
                    ? (getStageDetails(stage) || 'Executed & Verified')
                    : status === 'running'
                    ? 'Active Processing...'
                    : isFailed
                    ? (getStageDetails(stage) || 'Failed — check backend logs')
                    : isOnDemand
                    ? ON_DEMAND_LABELS[stage]
                    : 'Waiting...'}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
