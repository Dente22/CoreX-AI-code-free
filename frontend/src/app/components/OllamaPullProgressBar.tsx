import type { OllamaPullProgress } from '../utils/aiProvider';

interface OllamaPullProgressBarProps {
  progress: OllamaPullProgress | null;
  compact?: boolean;
}

export function OllamaPullProgressBar({ progress, compact = false }: OllamaPullProgressBarProps) {
  if (!progress) return null;

  const hasTotal = progress.total_bytes > 0;
  const indeterminate = Boolean(progress.indeterminate) || !hasTotal;
  const percent = hasTotal ? Math.min(100, Math.max(0, progress.percent)) : 0;

  return (
    <div className={compact ? 'mt-1' : 'mt-2 rounded border border-[#1e3a5f] bg-[#0b1220] px-2 py-1.5'}>
      <div className="flex items-center gap-2 mb-1">
        <div className="flex-1 h-2 bg-[#1f2937] rounded overflow-hidden relative">
          {indeterminate ? (
            <div className="corex-pull-indeterminate absolute inset-y-0 left-0 w-2/5 bg-[#2563eb] rounded" />
          ) : (
            <div
              className="h-full bg-[#2563eb] transition-all duration-500 ease-out"
              style={{ width: `${percent}%` }}
            />
          )}
        </div>
        {!indeterminate && hasTotal ? (
          <span className="text-[11px] font-semibold text-[#e5e9f0] tabular-nums min-w-[2.5rem] text-right">
            {progress.percent_label || `${percent}%`}
          </span>
        ) : null}
      </div>

      <p className="text-[10px] text-[#9ca3af] leading-snug space-y-0.5">
        {hasTotal ? (
          <span className="block text-[#e5e9f0]">
            <span className="tabular-nums">{progress.completed_label}</span>
            {' / '}
            <span className="tabular-nums">{progress.total_label}</span>
            {progress.percent_label ? ` (${progress.percent_label})` : null}
          </span>
        ) : null}

        {progress.speed_label || progress.eta_label ? (
          <span className="block">
            {progress.speed_label ? <span>{progress.speed_label}</span> : null}
            {progress.speed_label && progress.eta_label ? ' · ' : null}
            {progress.eta_label ? (
              <span>осталось {progress.eta_label.replace(/^~/, '')}</span>
            ) : null}
          </span>
        ) : null}

        <span className="block">
          {progress.resumed ? (
            <span className="text-[#fbbf24]">Продолжение с прошлой загрузки · </span>
          ) : null}
          {progress.message}
          {indeterminate && progress.elapsed_sec ? (
            <span className="text-[#6b7280]">
              {progress.status === 'importing'
                ? ' · копирование 4+ ГБ может занять 10–30 мин'
                : progress.download_method !== 'direct'
                  ? ' · ждём ответ сервера'
                  : null}
            </span>
          ) : null}
        </span>
      </p>
    </div>
  );
}
