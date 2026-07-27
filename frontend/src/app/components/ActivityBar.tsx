import { Files, Search, GitBranch, Activity, Package, MessageSquare, Settings } from 'lucide-react';
import { CoreXLogo } from './CoreXLogo';

interface ActivityBarProps {
  activeView: string;
  onViewChange: (view: string) => void;
}

export function ActivityBar({ activeView, onViewChange }: ActivityBarProps) {
  const items = [
    { id: 'explorer', icon: Files, label: 'Проводник' },
    { id: 'search', icon: Search, label: 'Поиск' },
    { id: 'git', icon: GitBranch, label: 'Git' },
    { id: 'debug', icon: Activity, label: 'Нейротрасса AI' },
    { id: 'extensions', icon: Package, label: 'Расширения' },
    { id: 'chat', icon: MessageSquare, label: 'CoreX AI', highlight: true },
  ];

  return (
    <div className="corex-activity-bar h-full flex flex-col items-center py-3">
      <div className="w-9 h-9 mb-4 rounded-xl overflow-hidden ring-2 ring-[var(--corex-brand)]/50 shadow-[0_0_16px_var(--corex-glow-brand)] flex items-center justify-center bg-[var(--corex-surface)]">
        <CoreXLogo className="w-7 h-7" />
      </div>

      <div className="flex-1 flex flex-col gap-0.5 w-full px-1.5">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={`corex-activity-item mx-auto ${isActive ? 'corex-activity-item--active' : ''} ${
                item.highlight && !isActive ? 'text-[var(--corex-brand)]' : ''
              }`}
              title={item.label}
            >
              <Icon className="w-5 h-5" />
            </button>
          );
        })}
      </div>

      <button
        onClick={() => onViewChange('settings')}
        className={`corex-activity-item mx-auto mb-1 ${activeView === 'settings' ? 'corex-activity-item--active' : ''}`}
        title="Настройки"
      >
        <Settings className="w-5 h-5" />
      </button>
    </div>
  );
}
