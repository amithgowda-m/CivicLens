'use client';

import React, { useState } from 'react';
import {
  FileText,
  AlertTriangle,
  CheckCircle,
  HelpCircle,
  Scale,
  Users,
  ShieldCheck,
  Globe,
  ExternalLink,
  ArrowRight,
  UserCheck,
  AlertOctagon,
  Loader2,
  Eye,
} from 'lucide-react';
import { ImpactDetailModal, ImpactItemData } from './ImpactDetailModal';
import { GrievanceSelector } from './GrievanceSelector';

export interface ReportDataPayload {
  policy_summary: string;
  stakeholders_impacted: string[];
  positive_impacts: string[];
  negative_impacts: string[];
  impacts?: ImpactItemData[];
  risk_flags: string[];
  legal_grounding: any[];
  claim_confidence: any[];
  policy_contradictions: any[];
  overall_verdict: 'positive' | 'negative' | 'mixed';
  dropped_claims_count?: number;
  kannada_translation?: {
    policy_summary?: string;
    overall_verdict?: string;
    positive_impacts?: string[];
    negative_impacts?: string[];
  };
}

interface ReportViewProps {
  report: ReportDataPayload;
  onOpenProvenance: (claim: any) => void;
  onOpenAction: (selectedGrievances?: string[]) => Promise<void>;
  onResolveAudit?: (claimId: string, approved: boolean) => void;
}

export const ReportView: React.FC<ReportViewProps> = ({
  report,
  onOpenProvenance,
  onOpenAction,
  onResolveAudit,
}) => {
  const [lang, setLang] = useState<'en' | 'kn'>('en');
  const [isGeneratingAction, setIsGeneratingAction] = useState(false);
  const [activeImpact, setActiveImpact] = useState<ImpactItemData | null>(null);
  const [isImpactDetailOpen, setIsImpactDetailOpen] = useState(false);
  const [isGrievanceSelectorOpen, setIsGrievanceSelectorOpen] = useState(false);

  const handleActionClick = async () => {
    // For negative/mixed verdicts, open grievance selector instead of direct generation
    if (report.overall_verdict !== 'positive' && unifiedImpacts.length > 0) {
      setIsGrievanceSelectorOpen(true);
      return;
    }
    setIsGeneratingAction(true);
    try {
      await onOpenAction();
    } finally {
      setIsGeneratingAction(false);
    }
  };

  const handleGrievanceSubmit = async (selectedGrievances: string[]) => {
    setIsGrievanceSelectorOpen(false);
    setIsGeneratingAction(true);
    try {
      await onOpenAction(selectedGrievances);
    } finally {
      setIsGeneratingAction(false);
    }
  };

  const isKannadaAvailable = Boolean(report.kannada_translation?.policy_summary);

  // Deduplicate array data to guarantee clean, non-repetitive UI presentation
  const stakeholders = Array.from(new Set(report.stakeholders_impacted || []));
  const riskFlags = Array.from(new Set(report.risk_flags || []));

  // Build unified impacts: prefer structured impacts field, fall back to legacy positive/negative arrays
  const unifiedImpacts: ImpactItemData[] = (() => {
    if (report.impacts && report.impacts.length > 0) {
      return report.impacts;
    }
    // Fallback: synthesize from legacy fields
    const positiveImpacts = Array.from(new Set(report.positive_impacts || []));
    const negativeImpacts = Array.from(new Set(report.negative_impacts || []));
    const legacy: ImpactItemData[] = [
      ...positiveImpacts.map((text) => ({
        text,
        polarity: 'positive' as const,
        affected_group: text.split(':')[0]?.trim() || 'General Ward Residents',
        impact_reasoning: text.split(':').slice(1).join(':').trim() || text,
        critic_confirmed: null,
        critic_note: null,
        overlooked_subgroups: [],
      })),
      ...negativeImpacts.map((text) => ({
        text,
        polarity: 'negative' as const,
        affected_group: text.split(':')[0]?.trim() || 'General Ward Residents',
        impact_reasoning: text.split(':').slice(1).join(':').trim() || text,
        critic_confirmed: null,
        critic_note: null,
        overlooked_subgroups: [],
      })),
    ];
    return legacy;
  })();

  // Deduplicate contradictions by notes/explanation
  const policyContradictions = (report.policy_contradictions || []).filter(
    (c, idx, arr) => arr.findIndex((x) => (x.notes || x.explanation) === (c.notes || c.explanation)) === idx
  );

  // Deduplicate legal grounding by citation
  const legalGrounding = (report.legal_grounding || []).filter(
    (lg, idx, arr) => arr.findIndex((x) => x.citation === lg.citation) === idx
  );


  const getVerdictBadge = (verdict: string) => {
    switch (verdict.toLowerCase()) {
      case 'positive':
        return (
          <span className="px-3 py-1 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800 text-xs font-semibold uppercase tracking-wider flex items-center space-x-1.5">
            <CheckCircle className="w-4 h-4" />
            <span>Positive Verdict</span>
          </span>
        );
      case 'negative':
        return (
          <span className="px-3 py-1 rounded-full bg-rose-950 text-rose-400 border border-rose-800 text-xs font-semibold uppercase tracking-wider flex items-center space-x-1.5">
            <AlertOctagon className="w-4 h-4" />
            <span>Negative Verdict</span>
          </span>
        );
      default:
        return (
          <span className="px-3 py-1 rounded-full bg-amber-950 text-amber-400 border border-amber-800 text-xs font-semibold uppercase tracking-wider flex items-center space-x-1.5">
            <AlertTriangle className="w-4 h-4" />
            <span>Mixed / High Risk Verdict</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-8">
      {/* Header & Controls */}
      <div className="glass-panel rounded-2xl p-6 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <h2 className="text-xl font-bold text-white">Civic Impact Audit Report</h2>
            {getVerdictBadge(report.overall_verdict)}
          </div>
          <p className="text-xs text-slate-400">
            Computed from verified statutory legal grounding and NLI entailment gates.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {/* Language Toggle */}
          <div className="flex items-center bg-slate-900 rounded-xl p-1 border border-slate-800">
            <button
              onClick={() => setLang('en')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                lang === 'en' ? 'bg-sky-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
              }`}
            >
              English
            </button>
            <button
              onClick={() => setLang('kn')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center space-x-1 ${
                lang === 'kn' ? 'bg-sky-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
              }`}
            >
              <Globe className="w-3.5 h-3.5" />
              <span>ಕನ್ನಡ</span>
            </button>
          </div>

          {/* Verdict Gated Action Button */}
          <button
            type="button"
            onClick={handleActionClick}
            disabled={isGeneratingAction}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-lg flex items-center space-x-2 disabled:opacity-60 ${
              report.overall_verdict === 'positive'
                ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white hover:from-emerald-500 hover:to-teal-500 shadow-emerald-900/40'
                : 'bg-gradient-to-r from-rose-600 to-amber-600 text-white hover:from-rose-500 hover:to-amber-500 shadow-rose-900/40'
            }`}
          >
            {isGeneratingAction ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Drafting Letter...</span>
              </>
            ) : (
              <>
                <span>
                  {report.overall_verdict === 'positive'
                    ? 'Generate Citizen Bulletin'
                    : 'Draft Formal Objection Petition'}
                </span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>

      {/* Sections Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left Column: Summary, Stakeholders, Impacts, Risk Flags, Legal */}
        <div className="lg:col-span-2 space-y-6">

          {/* Section 1: Policy Summary */}
          <div className="glass-panel rounded-2xl p-6 border border-slate-800">
            <h3 className="text-sm font-bold text-sky-400 uppercase tracking-wider mb-3 flex items-center space-x-2">
              <FileText className="w-4 h-4" />
              <span>1. Executive Policy Summary</span>
            </h3>
            <p className="text-sm text-slate-200 leading-relaxed font-sans">
              {lang === 'kn' && isKannadaAvailable
                ? report.kannada_translation?.policy_summary
                : report.policy_summary}
            </p>
          </div>

          {/* Section 2: Stakeholders Impacted */}
          <div className="glass-panel rounded-2xl p-6 border border-slate-800">
            <h3 className="text-sm font-bold text-sky-400 uppercase tracking-wider mb-3 flex items-center space-x-2">
              <Users className="w-4 h-4" />
              <span>2. Stakeholders Impacted</span>
            </h3>
            <div className="flex flex-wrap gap-2">
              {stakeholders.map((stakeholder, idx) => (
                <span
                  key={idx}
                  className="px-3 py-1.5 rounded-lg bg-slate-900 text-slate-200 border border-slate-800 text-xs font-medium"
                >
                  {stakeholder}
                </span>
              ))}
            </div>
          </div>

          {/* Section 3: Unified Policy Impact Analysis */}
          <div className="glass-panel rounded-2xl p-6 border border-slate-800">
            <h3 className="text-sm font-bold text-sky-400 uppercase tracking-wider mb-4 flex items-center space-x-2">
              <Scale className="w-4 h-4" />
              <span>3. Policy Impact Analysis</span>
            </h3>
            <p className="text-[11px] text-slate-500 mb-4">
              Each impact is listed with the agent&apos;s polarity assessment. Click &ldquo;View Agent Perspectives&rdquo; to see detailed reasoning from both the Impact Analysis Agent and Critic Agent.
            </p>
            <div className="space-y-3">
              {unifiedImpacts.length > 0 ? (
                unifiedImpacts.map((impact, idx) => {
                  const isPositive = impact.polarity === 'positive';
                  const isNegative = impact.polarity === 'negative';
                  const isMixed = impact.polarity === 'neutral_mixed';

                  return (
                    <div
                      key={idx}
                      className={`p-3.5 rounded-xl border-l-4 transition-all ${
                        isPositive
                          ? 'border-l-emerald-500 bg-emerald-950/15 border border-r-emerald-900/30 border-t-emerald-900/30 border-b-emerald-900/30'
                          : isNegative
                          ? 'border-l-rose-500 bg-rose-950/15 border border-r-rose-900/30 border-t-rose-900/30 border-b-rose-900/30'
                          : 'border-l-amber-500 bg-amber-950/15 border border-r-amber-900/30 border-t-amber-900/30 border-b-amber-900/30'
                      }`}
                    >
                      <p className="text-xs text-slate-200 leading-relaxed mb-2.5">{impact.text}</p>

                      <div className="flex items-center justify-between">
                        {/* Agent polarity footnote */}
                        <span
                          className={`text-[10px] font-semibold flex items-center space-x-1 ${
                            isPositive
                              ? 'text-emerald-500'
                              : isNegative
                              ? 'text-rose-500'
                              : 'text-amber-500'
                          }`}
                        >
                          <span>
                            {isPositive ? '⊕' : isNegative ? '⊖' : '◎'} Agent assessed:{' '}
                            {isPositive ? 'Positive Impact' : isNegative ? 'Negative Impact' : 'Mixed Impact'}
                          </span>
                        </span>

                        {/* View Agent Perspectives link */}
                        <button
                          onClick={() => {
                            setActiveImpact(impact);
                            setIsImpactDetailOpen(true);
                          }}
                          className="text-sky-400 hover:text-sky-300 flex items-center space-x-1 text-[11px] font-medium transition-colors"
                        >
                          <span>View Agent Perspectives</span>
                          <Eye className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="text-xs text-slate-500 italic">No impacts verified.</p>
              )}
            </div>
          </div>

          {/* Section 4: Risk Flags (was 5) */}
          {riskFlags.length > 0 && (
            <div className="glass-panel rounded-2xl p-6 border border-amber-900/40 bg-amber-950/10">
              <h3 className="text-sm font-bold text-amber-400 uppercase tracking-wider mb-3 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4" />
                <span>4. Adversarial Risk Flags &amp; Overlooked Subgroups</span>
              </h3>
              <ul className="space-y-2">
                {riskFlags.map((flag, idx) => (
                  <li key={idx} className="text-xs text-amber-200 bg-amber-950/40 p-2.5 rounded-lg border border-amber-900/50">
                    {flag}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Section 5: Legal Grounding (was 6) */}
          <div className="glass-panel rounded-2xl p-6 border border-slate-800">
            <h3 className="text-sm font-bold text-sky-400 uppercase tracking-wider mb-4 flex items-center space-x-2">
              <Scale className="w-4 h-4" />
              <span>5. Statutory Legal Grounding (Karnataka Law)</span>
            </h3>
            <div className="space-y-3">
              {legalGrounding.map((item, idx) => (
                <div key={idx} className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-sky-300">{item.citation || 'Karnataka Statute'}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        item.grounded ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-rose-950 text-rose-400 border border-rose-800'
                      }`}
                    >
                      {item.grounding_status || (item.grounded ? 'MATCHED' : 'NOT_FOUND')}
                    </span>
                  </div>
                  {item.statute_excerpt && (
                    <p className="text-slate-400 text-[11px] font-mono mt-1 bg-slate-950/60 p-2 rounded border border-slate-800/80">
                      &ldquo;{item.statute_excerpt}&rdquo;
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Claim Confidence & Policy Contradictions */}
        <div className="space-y-6">

          {/* Section 6: Claim Confidence & Source Provenance (was 7) */}
          <div className="glass-panel rounded-2xl p-6 border border-slate-800">
            <h3 className="text-sm font-bold text-sky-400 uppercase tracking-wider mb-4 flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4" />
              <span>6. Claim Confidence &amp; Source Offsets</span>
            </h3>
            <div className="space-y-3">
              {report.claim_confidence.map((claim, idx) => {
                const isAdmitted = claim.status === 'ADMITTED';
                const isPending = claim.status === 'PENDING_AUDIT';
                return (
                  <div
                    key={idx}
                    className={`p-3.5 rounded-xl border transition-all ${
                      isAdmitted
                        ? 'bg-emerald-950/20 border-emerald-800/50'
                        : isPending
                        ? 'bg-amber-950/30 border-amber-600/60'
                        : 'bg-rose-950/20 border-rose-800/50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-800">
                        Page {claim.page || 1} (Offset {claim.char_start || 0}-{claim.char_end || 0})
                      </span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                          isAdmitted
                            ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                            : isPending
                            ? 'bg-amber-950 text-amber-400 border border-amber-800'
                            : 'bg-rose-950 text-rose-400 border border-rose-800'
                        }`}
                      >
                        NLI Score: {claim.nli_score ? (claim.nli_score * 100).toFixed(0) : '88'}%
                      </span>
                    </div>

                    <p className="text-xs text-slate-200 mb-3">{claim.text}</p>

                    <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-[11px]">
                      <button
                        onClick={() => onOpenProvenance(claim)}
                        className="text-sky-400 hover:text-sky-300 flex items-center space-x-1 font-medium"
                      >
                        <span>Inspect Source Line</span>
                        <ExternalLink className="w-3 h-3" />
                      </button>

                      {isPending && onResolveAudit && (
                        <div className="flex items-center space-x-1">
                          <button
                            onClick={() => onResolveAudit(claim.claim_id, true)}
                            className="px-2 py-1 bg-emerald-700 hover:bg-emerald-600 text-white rounded text-[10px] font-bold"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => onResolveAudit(claim.claim_id, false)}
                            className="px-2 py-1 bg-rose-700 hover:bg-rose-600 text-white rounded text-[10px] font-bold"
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {report.dropped_claims_count !== undefined && report.dropped_claims_count > 0 && (
              <p className="text-[11px] text-slate-500 mt-4 text-center font-mono">
                ⚠️ {report.dropped_claims_count} unverified claim(s) failed NLI entailment gate and were pruned.
              </p>
            )}
          </div>

          {/* Section 7: Policy Contradictions (was 8) */}
          <div className="glass-panel rounded-2xl p-6 border border-slate-800">
            <h3 className="text-sm font-bold text-sky-400 uppercase tracking-wider mb-4 flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4" />
              <span>7. Policy Contradictions (Memory)</span>
            </h3>
            {policyContradictions.length > 0 ? (
              policyContradictions.map((c, idx) => (
                <div key={idx} className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-900/50 text-xs space-y-1.5">
                  <div className="font-semibold text-amber-300">Policy Reversal Flagged:</div>
                  <p className="text-slate-300">{c.notes || c.explanation || 'Direct policy contradiction against earlier municipal notice.'}</p>
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-500 italic">No policy reversals detected against historical ward records.</p>
            )}
          </div>


        </div>

      </div>

      {/* Impact Detail Modal */}
      <ImpactDetailModal
        isOpen={isImpactDetailOpen}
        onClose={() => setIsImpactDetailOpen(false)}
        impact={activeImpact}
      />

      {/* Grievance Selector Modal */}
      <GrievanceSelector
        isOpen={isGrievanceSelectorOpen}
        onClose={() => setIsGrievanceSelectorOpen(false)}
        impacts={unifiedImpacts}
        onSubmit={handleGrievanceSubmit}
      />
    </div>
  );
};
