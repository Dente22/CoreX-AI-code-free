import { useState } from 'react';
import { Wrench, FilePlus, ExternalLink, Loader2 } from 'lucide-react';
import { splitErrorSegments } from '../utils/parseErrorSegments';
import { buildAiFixPrompt, remediateError } from '../utils/errorRemediation';

interface ErrorActionTextProps {
  text: string;
  defaultFilePath?: string;
  onFixWithAI: (prompt: string) => void;
  onOpenFile?: (path: string, name: string) => void;
  onRemediated?: (path: string, message: string) => void;
  className?: string;
}

export function ErrorActionText({
  text,
  defaultFilePath = 'main.py',
  onFixWithAI,
  onOpenFile,
  onRemediated,
  className = '',
}: ErrorActionTextProps) {
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const segments = splitErrorSegments(text);

  const runRemediate = async (segment: string, filePath: string, mode: 'auto' | 'stub') => {
    const key = `${mode}-${filePath}`;
    setBusyAction(key);
    try {
      const result = await remediateError(filePath, segment, mode);
      if (result.ok) {
        onRemediated?.(filePath, result.message || 'Готово');
        if (onOpenFile) {
          onOpenFile(filePath, filePath.split('/').pop() || filePath);
        }
      } else {
        onRemediated?.(filePath, result.error || result.message || 'Не удалось создать заготовку');
      }
    } catch (error) {
      onRemediated?.(filePath, error instanceof Error ? error.message : String(error));
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <span className={className}>
      {segments.map((segment, index) => {
        if (segment.type === 'text') {
          return <span key={`t-${index}`}>{segment.value}</span>;
        }

        const filePath = segment.filePath || defaultFilePath;
        const fixKey = `fix-${filePath}`;
        const stubKey = `stub-${filePath}`;

        return (
          <span
            key={`e-${index}`}
            className="group/error relative inline rounded px-0.5 underline decoration-red-400/80 decoration-dotted underline-offset-2 cursor-help text-[#fca5a5]"
          >
            {segment.value}
            <span
              role="tooltip"
              className="pointer-events-none absolute left-0 top-full z-50 mt-1 hidden min-w-[220px] flex-col gap-1 rounded-md border border-[#3f3f46] bg-[#18181b] p-2 text-left shadow-xl group-hover/error:pointer-events-auto group-hover/error:flex"
            >
              <span className="text-[10px] uppercase tracking-wide text-[#71717a]">Действия</span>
              <button
                type="button"
                disabled={busyAction !== null}
                onClick={() => onFixWithAI(buildAiFixPrompt(filePath, segment.value))}
                className="flex items-center gap-1.5 rounded px-2 py-1.5 text-left text-xs text-[#e4e4e7] hover:bg-[#27272a] disabled:opacity-50"
              >
                <Wrench className="h-3.5 w-3.5 text-[#60a5fa]" />
                Исправить через AI
              </button>
              <button
                type="button"
                disabled={busyAction !== null}
                onClick={() => void runRemediate(segment.value, filePath, 'auto')}
                className="flex items-center gap-1.5 rounded px-2 py-1.5 text-left text-xs text-[#e4e4e7] hover:bg-[#27272a] disabled:opacity-50"
              >
                {busyAction === fixKey ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Wrench className="h-3.5 w-3.5 text-[#4ade80]" />
                )}
                Авто-исправить / заготовка
              </button>
              <button
                type="button"
                disabled={busyAction !== null}
                onClick={() => void runRemediate(segment.value, filePath, 'stub')}
                className="flex items-center gap-1.5 rounded px-2 py-1.5 text-left text-xs text-[#e4e4e7] hover:bg-[#27272a] disabled:opacity-50"
              >
                {busyAction === stubKey ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <FilePlus className="h-3.5 w-3.5 text-[#fbbf24]" />
                )}
                Создать файл-заготовку
              </button>
              {onOpenFile ? (
                <button
                  type="button"
                  onClick={() => onOpenFile(filePath, filePath.split('/').pop() || filePath)}
                  className="flex items-center gap-1.5 rounded px-2 py-1.5 text-left text-xs text-[#e4e4e7] hover:bg-[#27272a]"
                >
                  <ExternalLink className="h-3.5 w-3.5 text-[#a78bfa]" />
                  Открыть {filePath}
                </button>
              ) : null}
            </span>
          </span>
        );
      })}
    </span>
  );
}
