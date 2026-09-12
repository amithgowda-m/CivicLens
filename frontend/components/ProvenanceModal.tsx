'use client';

import React, { useEffect } from 'react';
import { X, Search } from 'lucide-react';

interface ProvenanceModalProps {
  isOpen: boolean;
  onClose: () => void;
  claim: any | null;
}

export const ProvenanceModal: React.FC<ProvenanceModalProps> = ({ isOpen, onClose, claim }) => {
  // Body scroll lock
  useEffect(() => {
    if (isOpen) {
      document.body.classList.add('modal-open');
    } else {
      document.body.classList.remove('modal-open');
    }
    return () => { document.body.classList.remove('modal-open'); };
  }, [isOpen]);

  if (!isOpen || !claim) return null;

  return (
    <div className="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-panel w-full max-w-xl">
        {/* Header */}
        <div className="modal-header">
          <div className="flex items-center gap-3">
            <div className="p-1.5 rounded" style={{ background: 'var(--accent-dim)', border: '1px solid var(--accent-border)' }}>
              <Search className="w-4 h-4" style={{ color: 'var(--accent)' }} />
            </div>
            <div>
              <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Source Text Provenance
              </div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Verbatim verification anchor from original document
              </div>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded transition-colors" style={{ color: 'var(--text-muted)' }}>
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="modal-body space-y-3 text-xs">
          {/* Offset grid */}
          <div className="grid grid-cols-3 gap-2 font-mono">
            <div className="rounded px-3 py-2" style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}>
              <div className="section-label mb-0.5">Page</div>
              <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                {claim.page || 1}
              </span>
            </div>
            <div className="rounded px-3 py-2" style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}>
              <div className="section-label mb-0.5">Start Char</div>
              <span className="text-sm font-semibold" style={{ color: 'var(--success)' }}>
                {claim.char_start ?? 0}
              </span>
            </div>
            <div className="rounded px-3 py-2" style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}>
              <div className="section-label mb-0.5">End Char</div>
              <span className="text-sm font-semibold" style={{ color: '#f87171' }}>
                {claim.char_end ?? 0}
              </span>
            </div>
          </div>

          {/* Claim text */}
          <div>
            <div className="section-label mb-1">Extracted Claim</div>
            <div
              className="rounded px-3 py-2.5 leading-relaxed"
              style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            >
              {claim.text}
            </div>
          </div>

          {/* Metadata */}
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded px-3 py-2" style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}>
              <div className="section-label mb-0.5">Jurisdiction Hint</div>
              <span style={{ color: '#93c5fd' }}>{claim.jurisdiction_hint || 'General / Unspecified'}</span>
            </div>
            <div className="rounded px-3 py-2" style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}>
              <div className="section-label mb-0.5">Extraction Source</div>
              <span className="font-mono" style={{ color: 'var(--success)' }}>
                {Array.isArray(claim.extraction_source)
                  ? claim.extraction_source.join(' + ')
                  : claim.extraction_source || 'regex'}
              </span>
            </div>
          </div>

          {/* Authority */}
          {claim.stated_objection_authority && (
            <div
              className="rounded px-3 py-2.5 flex items-center justify-between"
              style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}
            >
              <div>
                <div className="section-label mb-0.5">Stated Objection Authority</div>
                <span style={{ color: 'var(--text-secondary)' }}>{claim.stated_objection_authority}</span>
              </div>
              {claim.authority_status && (
                <span
                  className="chip"
                  style={{
                    background: claim.authority_status === 'ADMITTED' ? 'var(--success-dim)' : claim.authority_status === 'REJECTED_PRUNED' ? 'var(--danger-dim)' : 'var(--warning-dim)',
                    color: claim.authority_status === 'ADMITTED' ? 'var(--success)' : claim.authority_status === 'REJECTED_PRUNED' ? '#f87171' : 'var(--warning)',
                    border: 'none',
                  }}
                >
                  {claim.authority_status}
                </span>
              )}
            </div>
          )}

          {/* Verification gate */}
          <div
            className="rounded px-3 py-2.5"
            style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}
          >
            <div className="section-label mb-1.5">Verification Gate</div>
            <div className="flex flex-wrap gap-4">
              {claim.nli_score != null && (
                <span style={{ color: 'var(--text-muted)' }}>
                  NLI Score:{' '}
                  <strong style={{ color: 'var(--success)' }}>
                    {(claim.nli_score * 100).toFixed(1)}%
                  </strong>
                </span>
              )}
              <span style={{ color: 'var(--text-muted)' }}>
                Status: <strong style={{ color: 'var(--text-secondary)' }}>{claim.status}</strong>
              </span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button onClick={onClose} className="btn btn-ghost">
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
