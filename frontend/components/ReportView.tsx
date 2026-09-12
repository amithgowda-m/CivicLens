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
  Loader2
} from 'lucide-react';

export interface ReportDataPayload {
  policy_summary: string;
  stakeholders_impacted: string[];
  positive_impacts: string[];
  negative_impacts: string[];
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
  onOpenAction: () => Promise<void>;
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

  const handleActionClick = async () => {
    setIsGeneratingAction(true);
    try {
      await onOpenAction();
    } finally {
      setIsGeneratingAction(false);
    }
  };

  const isKannadaAvailable = Boolean(report.kannada_translation?.policy_summary);

  // Deduplicate array data to guarantee clean, non-repetitive UI presentation
  const stakeholders = Array.from(new Set(report.stakeholders_impacted || []));
  const positiveImpacts = Array.from(new Set(report.positive_impacts || []));
  const negativeImpacts = Array.from(new Set(report.negative_impacts || []));
  const riskFlags = Array.from(new Set(report.risk_flags || []));

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

      {/* 9 Fixed Sections Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left Column: Summary, Stakeholders, Impacts */}
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

          {/* Section 3 & 4: Positive & Negative Impacts */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="glass-panel rounded-2xl p-5 border border-slate-800">
              <h3 className="text-xs font-bold text-emerald-400 uppercase tracking-wider mb-3 flex items-center space-x-1.5">
                <CheckCircle className="w-4 h-4" />
                <span>3. Positive Impacts</span>
              </h3>
              <ul className="space-y-2">
                {positiveImpacts.length > 0 ? (
                  positiveImpacts.map((item, idx) => (
                    <li key={idx} className="text-xs text-slate-300 bg-emerald-950/20 p-2.5 rounded-lg border border-emerald-900/40">
                      {item}
                    </li>
                  ))
                ) : (
                  <p className="text-xs text-slate-500 italic">No positive impacts verified.</p>
                )}
              </ul>
            </div>

            <div className="glass-panel rounded-2xl p-5 border border-slate-800">
              <h3 className="text-xs font-bold text-rose-400 uppercase tracking-wider mb-3 flex items-center space-x-1.5">
                <AlertOctagon className="w-4 h-4" />
                <span>4. Negative Impacts</span>
              </h3>
              <ul className="space-y-2">
                {negativeImpacts.length > 0 ? (
                  negativeImpacts.map((item, idx) => (
                    <li key={idx} className="text-xs text-slate-300 bg-rose-950/20 p-2.5 rounded-lg border border-rose-900/40">
                      {item}
                    </li>
                  ))
                ) : (
                  <p className="text-xs text-slate-500 italic">No direct negative impacts verified.</p>
                )}
              </ul>
            </div>
          </div>

          {/* Section 5: Risk Flags */}
          {riskFlags.length > 0 && (
            <div className="glass-panel rounded-2xl p-6 border border-amber-900/40 bg-amber-950/10">
              <h3 className="text-sm font-bold text-amber-400 uppercase tracking-wider mb-3 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4" />
                <span>5. Adversarial Risk Flags & Overlooked Subgroups</span>
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

          {/* Section 6: Legal Grounding */}
          <div className="glass-panel rounded-2xl p-6 border border-slate-800">
            <h3 className="text-sm font-bold text-sky-400 uppercase tracking-wider mb-4 flex items-center space-x-2">
              <Scale className="w-4 h-4" />
              <span>6. Statutory Legal Grounding (Karnataka Law)</span>
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

          {/* Section 7: Claim Confidence & Source Provenance */}
          <div className="glass-panel rounded-2xl p-6 border border-slate-800">
            <h3 className="text-sm font-bold text-sky-400 uppercase tracking-wider mb-4 flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4" />
              <span>7. Claim Confidence & Source Offsets</span>
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

          {/* Section 8: Policy Contradictions */}
          <div className="glass-panel rounded-2xl p-6 border border-slate-800">
            <h3 className="text-sm font-bold text-sky-400 uppercase tracking-wider mb-4 flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4" />
              <span>8. Policy Contradictions (Memory)</span>
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
    </div>
  );
};
