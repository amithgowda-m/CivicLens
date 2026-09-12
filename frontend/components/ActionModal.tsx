'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
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

export const ActionModal: React.FC<ActionModalProps> = ({ isOpen, onClose, actionArtifact }) => {
  const [copied, setCopied] = useState(false);
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  // Body scroll lock
  useEffect(() => {
    if (isOpen) {
      document.body.classList.add('modal-open');
    } else {
      document.body.classList.remove('modal-open');
    }
    return () => { document.body.classList.remove('modal-open'); };
  }, [isOpen]);

  if (!isOpen || !actionArtifact || !mounted) return null;

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
    element.download = `${isObjection ? 'Objection_Petition' : 'Citizen_Bulletin'}_CivicLens.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  return createPortal(
    <div className="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-panel max-w-3xl" style={{ maxHeight: '85vh' }}>
        {/* Header */}
        <div className="modal-header">
          <div className="flex items-center gap-3">
            <div
              className="p-1.5 rounded"
              style={{
                background: isObjection ? 'var(--danger-dim)' : 'var(--success-dim)',
                border: `1px solid ${isObjection ? 'rgba(239,68,68,0.2)' : 'rgba(34,197,94,0.2)'}`,
              }}
            >
              <FileText
                className="w-4 h-4"
                style={{ color: isObjection ? '#f87171' : 'var(--success)' }}
              />
            </div>
            <div>
              <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                {isObjection ? 'Formal Citizen Objection Petition' : 'Community Civic Awareness Bulletin'}
              </div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                {isObjection
                  ? 'Ready to sign and submit to municipal authority'
                  : 'Formatted for Resident Welfare Associations'}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded transition-colors"
            style={{ color: 'var(--text-muted)' }}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="modal-body space-y-3">
          {actionArtifact.recipient_authority && (
            <div
              className="rounded px-3 py-2.5 flex flex-wrap gap-4 text-xs"
              style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}
            >
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Recipient Authority: </span>
                <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {actionArtifact.recipient_authority}
                </span>
              </div>
              {actionArtifact.target_deadline && (
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Submission Window: </span>
                  <span className="font-semibold" style={{ color: '#f87171' }}>
                    {actionArtifact.target_deadline}
                  </span>
                </div>
              )}
            </div>
          )}

          <div
            className="rounded p-4 text-xs font-mono whitespace-pre-wrap leading-relaxed"
            style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}
          >
            {actionArtifact.content}
          </div>
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <span className="text-xs mr-auto" style={{ color: 'var(--text-faint)' }}>
            Generated via CivicLens Action Agent
          </span>
          <button onClick={handleCopy} className="btn btn-ghost">
            {copied ? <Check className="w-3.5 h-3.5" style={{ color: 'var(--success)' }} /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button onClick={handleDownload} className="btn btn-primary">
            <Download className="w-3.5 h-3.5" />
            Download
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};
