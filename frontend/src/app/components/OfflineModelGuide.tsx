import { useState } from 'react';
import { ChevronRight, HelpCircle } from 'lucide-react';
import type { AiProviderPreset } from '../utils/aiProvider';
import { OfflineModelHelpModal } from './OfflineModelHelpModal';

interface OfflineModelGuideProps {
  providers: AiProviderPreset[];
  selectedId?: string;
  availableRamGb?: number;
  onSelectModel?: (id: string) => void;
  onNotification?: (message: string) => void;
}

export function OfflineModelGuide({
  providers,
  selectedId,
  availableRamGb,
  onSelectModel,
  onNotification,
}: OfflineModelGuideProps) {
  const [modalOpen, setModalOpen] = useState(false);

  if (!providers.length) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setModalOpen(true)}
        className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left rounded-md border border-[#212733] bg-[#0f1720] hover:bg-[#131a28] transition-colors"
        aria-expanded={modalOpen}
      >
        <HelpCircle className="w-3.5 h-3.5 text-[#60a5fa] flex-shrink-0" />
        <span className="text-[11px] text-[#c8c8c8] flex-1 min-w-0 truncate">
          Помощь: какую модель выбрать и как установить
        </span>
        <ChevronRight className="w-3.5 h-3.5 text-[#6b7280] flex-shrink-0" />
      </button>

      <OfflineModelHelpModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        providers={providers}
        selectedId={selectedId}
        availableRamGb={availableRamGb}
        onSelectModel={onSelectModel}
        onNotification={onNotification}
      />
    </>
  );
}
