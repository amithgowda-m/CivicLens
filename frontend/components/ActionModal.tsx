'use client';

import React, { useState } from 'react';
import { X, Copy, Download, Check, FileText } from 'lucide-react';

interface ActionModalProps {
  isOpen: boolean;
  onClose: () => void;
  actionArtifact: {
    action_type: string;
    content: string;
    target_deadline?: string;
    recipient_authority?: string;
    cited_clauses?: string[];
  } | null;
}

export const ActionModal: React.FC<ActionModalProps> = ({
  isOpen,
  onClose,
  actionArtifact,
}) => {
  const [copied, setCopied] = useState(false);

  if (!isOpen || !actionArtifact) return null;

  const isObjection = actionArtifact.action_type === 'objection_letter';

  const handleCopy = () => {
    navigator.clipboard.writeText(actionArtifact.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const element = document.createElement('a');
    const file = new Blob([actionArtifact.content], { type: 'text/plain' });
    element.href = URL.createObjectURL(file);
    element.download = `${isObjection ? 'Objection_Petition' : 'Citizen_Bulletin'}_Ward150.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="glass-panel w-full max-w-3xl rounded-2xl border border-slate-700 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-xl ${isObjection ? 'bg-rose-950/80 text-rose-400 border border-rose-800' : 'bg-emerald-950/80 text-emerald-400 border border-emerald-800'}`}>
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">
                {isObjection ? 'Formal Citizen Objection Petition' : 'Community Civic Awareness Bulletin'}
              </h3>
              <p className="text-xs text-slate-400">
                {isObjection ? 'Ready to sign and submit to municipal authority' : 'Formatted for Resident Welfare Associations'}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-4 font-sans">
          {actionArtifact.recipient_authority && (
            <div className="flex flex-wrap gap-4 text-xs bg-slate-900/80 p-3 rounded-xl border border-slate-800">
              <div>
                <span className="text-slate-400">Recipient Authority: </span>
                <span className="text-sky-300 font-semibold">{actionArtifact.recipient_authority}</span>
              </div>
              {actionArtifact.target_deadline && (
                <div>
                  <span className="text-slate-400">Submission Window: </span>
                  <span className="text-rose-300 font-semibold">{actionArtifact.target_deadline}</span>
                </div>
              )}
            </div>
          )}

          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-xs text-slate-200 whitespace-pre-wrap leading-relaxed">
            {actionArtifact.content}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/60 flex items-center justify-between">
          <span className="text-xs text-slate-400">
            Generated on-demand via CivicLens Action Agent.
          </span>
          <div className="flex items-center space-x-3">
            <button
              onClick={handleCopy}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center space-x-2 border border-slate-700"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
              <span>{copied ? 'Copied!' : 'Copy Text'}</span>
            </button>
            <button
              onClick={handleDownload}
              className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold flex items-center space-x-2 shadow-lg shadow-sky-600/30"
            >
              <Download className="w-4 h-4" />
              <span>Download File</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
