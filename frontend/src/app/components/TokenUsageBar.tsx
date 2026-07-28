import { useEffect, useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { fetchTokenUsage, resetSessionTokenUsage, type TokenUsageSummary } from '../utils/tokenUsage';

interface TokenUsageBarProps {
  mode: 'local' | 'online';
}

export function TokenUsageBar({ mode }: TokenUsageBarProps) {
  const [usage, setUsage] = useState<TokenUsageSummary | null>(null);
  const [resetting, setResetting] = useState(false);

  const refresh = () => void fetchTokenUsage().then(setUsage);

  useEffect(() => {
    if (mode !== 'online') {
      setUsage(null);
      return;
    }
    refresh();
    const timer = window.setInterval(refresh, 15000);
    return () => window.clearInterval(timer);
  }, [mode]);

  const handleReset = async () => {
    setResetting(true);
    try {
      await resetSessionTokenUsage();
      await refresh();
    } finally {
      setResetting(false);
    }
  };

  if (mode !== 'online' || !usage?.limits?.enabled) {
    return null;
  }

  const sessionPct = Math.min(100, usage.session_percent || 0);
  const tone =
    sessionPct >= 95 ? 'bg-red-500' : sessionPct >= usage.limits.warn_at_percent ? 'bg-amber-400' : 'bg-emerald-500';

  return (
    <div className="rounded-lg px-2.5 py-2 corex-surface">
      <div className="flex items-center justify-between gap-2 text-[10px] text-[var(--corex-text-muted)]">
        <span>Токены (сессия)</span>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => void handleReset()}
            disabled={resetting}
            className="p-0.5 rounded hover:bg-[var(--corex-surface-hover)] text-[var(--corex-text-dim)] hover:text-[var(--corex-spark)] disabled:opacity-50"
            title="Сбросить счётчик сессии"
          >
            <RotateCcw className={`w-3 h-3 ${resetting ? 'animate-spin' : ''}`} />
          </button>
          <span className="font-mono tabular-nums">
            {(usage.session?.total_tokens || 0).toLocaleString('ru-RU')}
            <span className="text-[var(--corex-text-dim)]"> / {(usage.limits.session_limit ?? 0).toLocaleString('ru-RU')}</span>
          </span>
        </div>
      </div>
      <div className="mt-1.5 h-1 rounded-full bg-[var(--corex-panel)] overflow-hidden">
        <div className={`h-full ${tone} transition-all`} style={{ width: `${sessionPct}%` }} />
      </div>
      <p className="mt-1 text-[9px] text-[var(--corex-text-dim)] font-mono">
        День: {(usage.daily?.total_tokens || 0).toLocaleString('ru-RU')} / {(usage.limits.daily_limit ?? 0).toLocaleString('ru-RU')}
      </p>
    </div>
  );
}
