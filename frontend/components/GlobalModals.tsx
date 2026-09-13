'use client';

import { useApp } from '@/app/context/AppContext';
import { ActionModal } from './ActionModal';
import { ProvenanceModal } from './ProvenanceModal';

export function GlobalModals() {
  const {
    isActionOpen, setIsActionOpen, actionArtifact,
    isProvenanceOpen, setIsProvenanceOpen, activeClaim,
  } = useApp();

  return (
    <>
      <ActionModal
        isOpen={isActionOpen}
        onClose={() => setIsActionOpen(false)}
        actionArtifact={actionArtifact}
      />
      <ProvenanceModal
        isOpen={isProvenanceOpen}
        onClose={() => setIsProvenanceOpen(false)}
        claim={activeClaim}
      />
    </>
  );
}
