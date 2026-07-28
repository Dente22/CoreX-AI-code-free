import { Bot, Users, Sparkles } from 'lucide-react';
import type { WorkMode } from '../utils/pipelines';

interface WorkModeSelectorProps {
  workMode: WorkMode;
  onWorkModeChange: (mode: WorkMode) => void;
  disabled?: boolean;
}

const modes: { id: WorkMode; label: string; icon: typeof Sparkles; activeClass: string }[] = [
  {
    id: 'single',
    label: 'Скил',
    icon: Sparkles,
    activeClass: 'corex-segmented-btn--active bg-[rgba(0,210,255,0.15)] text-[var(--corex-spark)] border-[var(--corex-spark)]/30',
  },
  {
    id: 'agent',
    label: 'Агент',
    icon: Bot,
    activeClass: 'corex-segmented-btn--active bg-[rgba(154,94,255,0.15)] text-[var(--corex-brand)] border-[var(--corex-brand)]/30',
  },
  {
    id: 'pipeline',
    label: 'Команда',
    icon: Users,
    activeClass: 'corex-segmented-btn--active bg-[rgba(154,94,255,0.1)] text-white border-[var(--corex-brand)]/40',
  },
];

export function WorkModeSelector({
  workMode,
  onWorkModeChange,
  disabled = false,
}: WorkModeSelectorProps) {
  return (
    <div className="corex-segmented">
      {modes.map(({ id, label, icon: Icon, activeClass }) => (
        <button
          key={id}
          type="button"
          disabled={disabled}
          onClick={() => onWorkModeChange(id)}
          className={`corex-segmented-btn ${workMode === id ? activeClass : ''}`}
        >
          <Icon className="w-3.5 h-3.5" />
          {label}
        </button>
      ))}
    </div>
  );
}
