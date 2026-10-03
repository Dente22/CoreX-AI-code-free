import { Bot, Sparkles, SquareTerminal } from 'lucide-react';
import { codingEngineDescription, type CodingEngineId } from '../utils/codingEngine';

interface CodingEngineSelectorProps {
  codingEngine: CodingEngineId;
  onCodingEngineChange: (engine: CodingEngineId) => void;
  disabled?: boolean;
}

const modes: {
  id: CodingEngineId;
  label: string;
  icon: typeof Sparkles;
  activeClass: string;
}[] = [
  {
    id: 'claude_code',
    label: 'Claude Code',
    icon: SquareTerminal,
    activeClass:
      'corex-segmented-btn--active bg-[rgba(255,153,0,0.15)] text-[#ffb347] border-[#ffb347]/30',
  },
  {
    id: 'aider',
    label: 'Aider',
    icon: Sparkles,
    activeClass:
      'corex-segmented-btn--active bg-[rgba(0,210,255,0.15)] text-[var(--corex-spark)] border-[var(--corex-spark)]/30',
  },
  {
    id: 'corex',
    label: 'CoreX',
    icon: Bot,
    activeClass:
      'corex-segmented-btn--active bg-[rgba(154,94,255,0.15)] text-[var(--corex-brand)] border-[var(--corex-brand)]/30',
  },
];

export function CodingEngineSelector({
  codingEngine,
  onCodingEngineChange,
  disabled = false,
}: CodingEngineSelectorProps) {
  return (
    <div className="corex-segmented">
      {modes.map(({ id, label, icon: Icon, activeClass }) => (
        <button
          key={id}
          type="button"
          disabled={disabled}
          title={codingEngineDescription(id)}
          onClick={() => onCodingEngineChange(id)}
          className={`corex-segmented-btn ${codingEngine === id ? activeClass : ''}`}
        >
          <Icon className="w-3.5 h-3.5" />
          {label}
        </button>
      ))}
    </div>
  );
}
