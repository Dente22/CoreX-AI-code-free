import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Loader } from 'lucide-react';

interface ThinkingMessageProps {
  thoughts: string[];
  isThinking?: boolean;
}

export function ThinkingMessage({ thoughts, isThinking = true }: ThinkingMessageProps) {
  const [expanded, setExpanded] = useState(false);
  const safeThoughts = thoughts ?? [];

  if (!isThinking && safeThoughts.length === 0) return null;

  const latest = safeThoughts[safeThoughts.length - 1] || '';
  const canExpand = safeThoughts.length > 0;
  const countLabel =
    safeThoughts.length === 0
      ? 'ожидание ответа'
      : `${safeThoughts.length} шаг${
          safeThoughts.length === 1 ? '' : safeThoughts.length < 5 ? 'а' : 'ов'
        }`;

  return (
    <div className="corex-chat-file-group">
      <button
        type="button"
        onClick={() => {
          if (canExpand) setExpanded((prev) => !prev);
        }}
        disabled={!canExpand}
        className="corex-chat-file-group-toggle"
        aria-expanded={expanded}
      >
        {canExpand ? (
          expanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-[var(--corex-text-dim)] flex-shrink-0" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-[var(--corex-text-dim)] flex-shrink-0" />
          )
        ) : null}
        {isThinking ? (
          <Loader className="w-3.5 h-3.5 text-[var(--corex-spark)] flex-shrink-0 animate-spin" />
        ) : null}
        <span className="corex-chat-file-group-title">Думает…</span>
        <span className="corex-chat-file-group-preview">
          {countLabel}
          {!expanded && latest ? ` · ${latest}` : ''}
        </span>
      </button>

      {expanded && canExpand ? (
        <div className="corex-chat-file-group-list max-h-40 overflow-y-auto p-2 text-[var(--corex-text-muted)] text-sm space-y-1">
          {safeThoughts.map((thought, idx) => (
            <div key={idx} className="flex gap-2 px-2">
              <span className="text-[var(--corex-spark)] flex-shrink-0">→</span>
              <span className="break-words">{thought ?? ''}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
