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
    <div className="flex gap-3 opacity-80">
      <div className="w-7 h-7 rounded flex items-center justify-center flex-shrink-0 bg-purple-600">
        <Loader className={`w-4 h-4 text-white ${isThinking ? 'animate-spin' : ''}`} />
      </div>
      <div className="flex-1 min-w-0">
        <button
          type="button"
          onClick={() => {
            if (canExpand) setExpanded((prev) => !prev);
          }}
          disabled={!canExpand}
          className="w-full text-left rounded-md border border-[#333] bg-[#1e1e1e] px-3 py-2 hover:bg-[#252525] transition-colors disabled:hover:bg-[#1e1e1e] disabled:cursor-default"
          aria-expanded={expanded}
        >
          <div className="flex items-center gap-2 text-sm text-[#c8c8c8] min-w-0">
            {canExpand ? (
              expanded ? (
                <ChevronDown className="w-3.5 h-3.5 text-[#858585] flex-shrink-0" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 text-[#858585] flex-shrink-0" />
              )
            ) : (
              <span className="w-3.5 h-3.5 flex-shrink-0" />
            )}
            <span className="font-medium flex-shrink-0">Думает…</span>
            <span className="text-[#858585] truncate min-w-0">
              {countLabel}
              {!expanded && latest ? ` · ${latest}` : ''}
            </span>
          </div>
        </button>

        {expanded && canExpand ? (
          <div className="mt-1 max-h-40 overflow-y-auto rounded-md border border-[#333] bg-[#2a2a2a] p-2 text-[#a0a0a0] text-sm space-y-1">
            {safeThoughts.map((thought, idx) => (
              <div key={idx} className="flex gap-2">
                <span className="text-purple-400 flex-shrink-0">→</span>
                <span className="break-words">{thought ?? ''}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
