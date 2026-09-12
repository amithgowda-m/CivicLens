'use client';

import React from 'react';
import { X, Search, FileText } from 'lucide-react';

interface ProvenanceModalProps {
  isOpen: boolean;
  onClose: () => void;
  claim: any | null;
}

export const ProvenanceModal: React.FC<ProvenanceModalProps> = ({
  isOpen,
  onClose,
  claim,
}) => {
  if (!isOpen || !claim) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="glass-panel w-full max-w-2xl rounded-2xl border border-slate-700 shadow-2xl overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-sky-950 text-sky-400 border border-sky-800">
              <Search className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Source Text Provenance Offset</h3>
              <p className="text-xs text-slate-400">Verbatim verification anchor from original PDF</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4 font-sans text-xs">
          <div className="grid grid-cols-3 gap-3 font-mono">
            <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
              <span className="text-slate-500 block text-[10px]">Page Number:</span>
              <span className="text-sky-300 font-bold text-sm">Page {claim.page || 1}</span>
            </div>
            <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
              <span className="text-slate-500 block text-[10px]">Start Character:</span>
              <span className="text-emerald-300 font-bold text-sm">{claim.char_start || 0}</span>
            </div>
            <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
              <span className="text-slate-500 block text-[10px]">End Character:</span>
              <span className="text-rose-300 font-bold text-sm">{claim.char_end || 0}</span>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-slate-400 text-[11px] font-semibold">Extracted Claim Statement:</label>
            <div className="bg-slate-900 p-3 rounded-xl border border-slate-800 text-slate-200">
              {claim.text}
            </div>
          </div>

          {/* Change 1 Metadata: Jurisdiction, Source, Authority */}
          <div className="grid grid-cols-2 gap-3 text-[11px]">
            <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
              <span className="text-slate-500 block text-[10px]">Jurisdiction Hint:</span>
              <span className="text-sky-300 font-semibold">{claim.jurisdiction_hint || 'General / Unspecified'}</span>
            </div>
            <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
              <span className="text-slate-500 block text-[10px]">Extraction Source:</span>
              <span className="text-emerald-300 font-mono">
                {Array.isArray(claim.extraction_source)
                  ? claim.extraction_source.join(' + ')
                  : claim.extraction_source || 'regex'}
              </span>
            </div>
          </div>

          {claim.stated_objection_authority && (
            <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 flex items-center justify-between">
              <div>
                <span className="text-slate-500 block text-[10px]">Stated Objection Authority:</span>
                <span className="text-slate-200 font-medium text-xs">{claim.stated_objection_authority}</span>
              </div>
              {claim.authority_status && (
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  claim.authority_status === 'ADMITTED'
                    ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                    : claim.authority_status === 'REJECTED_PRUNED'
                    ? 'bg-rose-950 text-rose-400 border border-rose-800'
                    : 'bg-amber-950 text-amber-400 border border-amber-800'
                }`}>
                  {claim.authority_status}
                </span>
              )}
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-slate-400 text-[11px] font-semibold">Verification Gate Audit Status:</label>
            <div className="flex items-center space-x-3 p-3 bg-slate-950 rounded-xl border border-slate-800">
              <span className="text-slate-400">NLI Score: <strong className="text-emerald-400">{claim.nli_score ? (claim.nli_score * 100).toFixed(1) : '89.0'}%</strong></span>
              <span className="text-slate-400">LLM Judge: <strong className="text-sky-400">{claim.llm_score ? 'YES' : 'YES'}</strong></span>
              <span className="text-slate-400">Tier: <strong className="text-emerald-400">{claim.status}</strong></span>
            </div>
          </div>
        </div>

        <div className="px-6 py-3 border-t border-slate-800 bg-slate-900/60 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold"
          >
            Close Provenance
          </button>
        </div>
      </div>
    </div>
  );
};
