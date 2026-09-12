'use client';

import React, { useState, useEffect } from 'react';
import { X, AlertOctagon, CheckSquare, Square, ArrowRight, Loader2, FileWarning } from 'lucide-react';
import { ImpactItemData } from './ImpactDetailModal';

interface GrievanceSelectorProps {
  isOpen: boolean;
  onClose: () => void;
  impacts: ImpactItemData[];
  onSubmit: (selectedGrievances: string[]) => Promise<void>;
}

export const GrievanceSelector: React.FC<GrievanceSelectorProps> = ({
  isOpen,
  onClose,
  impacts,
  onSubmit,
}) => {
  // Body scroll lock
  useEffect(() => {
    if (isOpen) {
      document.body.classList.add('modal-open');
    } else {
      document.body.classList.remove('modal-open');
    }
    return () => { document.body.classList.remove('modal-open'); };
  }, [isOpen]);

  // Filter to negative and mixed impacts as selectable grievances
  const grievances = impacts.filter(
    (i) => i.polarity === 'negative' || i.polarity === 'neutral_mixed'
  );

  const [selected, setSelected] = useState<Set<number>>(
    new Set(grievances.map((_, idx) => idx))
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Sync selected on impacts change
  useEffect(() => {
    setSelected(new Set(grievances.map((_, idx) => idx)));
  }, [impacts]);

  if (!isOpen) return null;

  const toggleSelection = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === grievances.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(grievances.map((_, idx) => idx)));
    }
  };

  const handleSubmit = async () => {
    const selectedTexts = grievances
      .filter((_, idx) => selected.has(idx))
      .map((g) => g.text);
    if (selectedTexts.length === 0) return;

    setIsSubmitting(true);
    try {
      await onSubmit(selectedTexts);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-panel w-full max-w-2xl" style={{ maxHeight: '88vh' }}>

        {/* Header */}
        <div className="modal-header">
          <div className="flex items-center gap-3">
            <div
              className="p-1.5 rounded"
              style={{ background: 'var(--danger-dim)', border: '1px solid rgba(239,68,68,0.2)' }}
            >
              <FileWarning className="w-4 h-4" style={{ color: '#f87171' }} />
            </div>
            <div>
              <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Select Grievances for Objection Petition
              </div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Choose specific adverse impacts to cite in the formal objection
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
        <div className="modal-body space-y-3" style={{ maxHeight: 'calc(88vh - 9rem)', overflowY: 'auto' }}>

          {/* Select All Toggle */}
          <div className="flex items-center justify-between pb-1">
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {selected.size} of {grievances.length} grievance{grievances.length !== 1 ? 's' : ''} selected
            </span>
            <button
              onClick={toggleAll}
              className="text-xs font-medium transition-colors"
              style={{ color: 'var(--accent)' }}
            >
              {selected.size === grievances.length ? 'Deselect All' : 'Select All'}
            </button>
          </div>

          {grievances.length === 0 ? (
            <div className="text-center py-8">
              <AlertOctagon className="w-8 h-8 mx-auto mb-2" style={{ color: 'var(--text-faint)' }} />
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                No negative or mixed impacts identified to file as grievances.
              </p>
            </div>
          ) : (
            grievances.map((grievance, idx) => {
              const isSelected = selected.has(idx);
              const isNegative = grievance.polarity === 'negative';

              return (
                <button
                  key={idx}
                  onClick={() => toggleSelection(idx)}
                  className="w-full text-left p-3 rounded transition-colors"
                  style={{
                    background: isSelected
                      ? isNegative ? 'var(--danger-dim)' : 'var(--warning-dim)'
                      : 'var(--bg-raised)',
                    border: '1px solid',
                    borderColor: isSelected
                      ? isNegative ? 'rgba(239,68,68,0.3)' : 'rgba(245,158,11,0.3)'
                      : 'var(--border)',
                    borderLeftWidth: '3px',
                    borderLeftColor: isNegative ? 'var(--danger)' : 'var(--warning)',
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 flex-shrink-0">
                      {isSelected ? (
                        <CheckSquare
                          className="w-4 h-4"
                          style={{ color: isNegative ? '#f87171' : '#fbbf24' }}
                        />
                      ) : (
                        <Square className="w-4 h-4" style={{ color: 'var(--text-faint)' }} />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                        {grievance.text}
                      </p>
                      <div className="flex items-center gap-2 mt-2">
                        <span className={`chip ${isNegative ? 'chip-danger' : 'chip-warning'}`}>
                          {isNegative ? 'Negative' : 'Mixed'}
                        </span>
                        {grievance.affected_group && (
                          <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                            {grievance.affected_group}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button onClick={onClose} className="btn btn-ghost">
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={selected.size === 0 || isSubmitting}
            className="btn btn-primary"
            style={{
              background: 'var(--danger)',
            }}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Generating Petition…</span>
              </>
            ) : (
              <>
                <span>Generate Objection ({selected.size})</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
