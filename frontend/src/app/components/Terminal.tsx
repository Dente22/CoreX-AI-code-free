import { useEffect, useRef } from 'react';
import { Terminal as TerminalIcon, ChevronUp, ChevronDown, Trash2, Square } from 'lucide-react';
import { ErrorActionText } from './ErrorActionText';

export type TerminalLineKind = 'command' | 'output' | 'error' | 'info';

export interface TerminalLine {
  id: string;
  kind: TerminalLineKind;
  text: string;
}

interface TerminalProps {
  isExpanded: boolean;
  onToggle: () => void;
  lines: TerminalLine[];
  onCommand: (command: string) => void;
  onClear: () => void;
  onStop?: () => void;
  isRunning?: boolean;
  projectRoot?: string;
  onFixWithAI?: (prompt: string) => void;
  onOpenFile?: (path: string, name: string) => void;
  onRemediated?: (path: string, message: string) => void;
}

function lineClass(kind: TerminalLineKind): string {
  switch (kind) {
    case 'command':
      return 'text-[#4ec9b0]';
    case 'error':
      return 'text-[#f87171]';
    case 'info':
      return 'text-[#94a3b8]';
    default:
      return 'text-[#cccccc]';
  }
}

export function Terminal({
  isExpanded,
  onToggle,
  lines,
  onCommand,
  onClear,
  onStop,
  isRunning = false,
  projectRoot,
  onFixWithAI,
  onOpenFile,
  onRemediated,
}: TerminalProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isExpanded) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [lines, isExpanded]);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem('terminal-input') as HTMLInputElement;
    const value = input.value.trim();
    if (!value || isRunning) {
      return;
    }
    onCommand(value);
    input.value = '';
  };

  if (!isExpanded) {
    return (
      <div className="h-9 bg-[var(--corex-panel)] border-t border-[var(--corex-border)] flex items-center justify-between px-3 flex-shrink-0">
        <button
          type="button"
          onClick={onToggle}
          aria-label="Открыть консоль"
          title="Открыть консоль"
          className="flex items-center gap-2 text-[var(--corex-text-muted)] hover:text-[var(--corex-text)] text-xs"
        >
          <TerminalIcon className="w-4 h-4 text-indigo-400" />
          <span>Консоль</span>
          {isRunning ? <span className="text-amber-400">● выполняется...</span> : null}
        </button>
        <button type="button" onClick={onToggle} className="corex-icon-btn">
          <ChevronUp className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="h-56 min-h-[140px] max-h-[50vh] bg-[var(--corex-panel)] border-t border-[var(--corex-border)] flex flex-col flex-shrink-0">
      <div className="corex-panel-header">
        <div className="flex items-center gap-3 text-xs text-[var(--corex-text-muted)]">
          <TerminalIcon className="w-4 h-4 text-indigo-400" />
          <span className="font-medium text-[var(--corex-text)]">Консоль</span>
          {projectRoot ? (
            <span className="text-[var(--corex-text-dim)] truncate max-w-[240px] font-mono" title={projectRoot}>
              {projectRoot}
            </span>
          ) : null}
          {isRunning ? <span className="text-amber-400">выполняется...</span> : null}
        </div>
        <div className="flex items-center gap-0.5">
          {isRunning && onStop ? (
            <button type="button" onClick={onStop} title="Остановить" className="corex-icon-btn text-red-400">
              <Square className="w-3.5 h-3.5" />
            </button>
          ) : null}
          <button type="button" onClick={onClear} title="Очистить" className="corex-icon-btn">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
          <button type="button" onClick={onToggle} title="Свернуть" className="corex-icon-btn">
            <ChevronDown className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div
        className="flex-1 overflow-y-auto p-3 font-mono text-xs leading-relaxed"
        onClick={() => inputRef.current?.focus()}
      >
        {lines.length === 0 ? (
          <p className="text-[var(--corex-text-dim)]">
            Запустите файл кнопкой ▶ в редакторе или введите команду ниже (npm run dev, python main.py…)
          </p>
        ) : (
          lines.map((line) => (
            <div key={line.id} className={`whitespace-pre-wrap break-words ${lineClass(line.kind)}`}>
              {line.kind === 'error' && onFixWithAI ? (
                <ErrorActionText
                  text={line.text}
                  onFixWithAI={onFixWithAI}
                  onOpenFile={onOpenFile}
                  onRemediated={onRemediated}
                />
              ) : (
                line.text
              )}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex items-center gap-2 px-3 py-2 border-t border-[var(--corex-border)] flex-shrink-0 bg-[var(--corex-surface)]">
        <span className="text-emerald-400 font-mono text-xs select-none">$</span>
        <input
          ref={inputRef}
          name="terminal-input"
          type="text"
          disabled={isRunning}
          aria-label="Команда консоли"
          placeholder={isRunning ? 'Ожидание...' : 'Команда (Enter)'}
          className="flex-1 bg-transparent outline-none text-[var(--corex-text)] font-mono text-xs disabled:opacity-50"
          autoComplete="off"
          spellCheck={false}
        />
      </form>
    </div>
  );
}
