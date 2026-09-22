import { Send, FileCode2, StopCircle } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  extractMentionPaths,
  fetchMentionCandidates,
  getSlashQuery,
  insertMention,
} from '../utils/fileMentions';

interface ChatInputProps {
  onSend: (message: string) => void;
  isProcessing?: boolean;
  onStop?: () => void;
  projectRoot?: string;
  embedded?: boolean;
}

export function ChatInput({ onSend, isProcessing = false, onStop, projectRoot, embedded = false }: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionItems, setMentionItems] = useState<string[]>([]);
  const [mentionIndex, setMentionIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const mentionDebounceRef = useRef<number | null>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [message]);

  const loadMentions = useCallback(
    (query: string) => {
      if (!projectRoot) {
        setMentionItems([]);
        return;
      }
      void fetchMentionCandidates(query).then((files) => {
        setMentionItems(files);
        setMentionIndex(0);
      });
    },
    [projectRoot],
  );

  const updateMentionState = useCallback(
    (text: string, cursor: number) => {
      const query = getSlashQuery(text, cursor);
      if (query === null || !projectRoot) {
        setMentionOpen(false);
        setMentionQuery('');
        return;
      }
      setMentionOpen(true);
      setMentionQuery(query);
      if (mentionDebounceRef.current !== null) {
        window.clearTimeout(mentionDebounceRef.current);
      }
      mentionDebounceRef.current = window.setTimeout(() => {
        loadMentions(query);
      }, 120);
    },
    [loadMentions, projectRoot],
  );

  const applyMention = (filePath: string) => {
    const cursor = textareaRef.current?.selectionStart ?? message.length;
    const next = insertMention(message, cursor, filePath);
    setMessage(next.text);
    setMentionOpen(false);
    setMentionQuery('');
    window.requestAnimationFrame(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(next.cursor, next.cursor);
      }
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isProcessing) {
      onSend(message.trim());
      setMessage('');
      setMentionOpen(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (mentionOpen && mentionItems.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMentionIndex((i) => (i + 1) % mentionItems.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMentionIndex((i) => (i - 1 + mentionItems.length) % mentionItems.length);
        return;
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && mentionQuery.length >= 0)) {
        e.preventDefault();
        applyMention(mentionItems[mentionIndex] ?? mentionItems[0]);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setMentionOpen(false);
        return;
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const attachedPaths = extractMentionPaths(message);

  return (
    <div className={embedded ? 'bg-[var(--corex-panel)]' : 'border-t border-[var(--corex-border)] bg-[var(--corex-panel)]'}>
      <form onSubmit={handleSubmit} className="p-3 pt-2">
        {attachedPaths.length > 0 ? (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {attachedPaths.map((path) => (
              <span
                key={path}
                className="inline-flex items-center gap-1 rounded-md bg-[rgba(0,210,255,0.1)] border border-[rgba(0,210,255,0.2)] px-2 py-0.5 text-[10px] text-[var(--corex-spark)]"
              >
                <FileCode2 className="w-3 h-3" />
                /{path}
              </span>
            ))}
          </div>
        ) : null}

        <div className="relative flex items-end gap-2 corex-surface rounded-xl focus-within:ring-2 focus-within:ring-[var(--corex-spark)]/30 focus-within:border-[var(--corex-spark)]/25 transition-shadow">
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => {
              setMessage(e.target.value);
              updateMentionState(e.target.value, e.target.selectionStart ?? e.target.value.length);
            }}
            onClick={(e) =>
              updateMentionState(
                message,
                (e.target as HTMLTextAreaElement).selectionStart ?? message.length,
              )
            }
            onKeyDown={handleKeyDown}
            placeholder={
              projectRoot
                ? 'Сообщение… /файл — смотреть или править, /папка — создать файл внутри'
                : 'Напишите сообщение CoreX AI...'
            }
            aria-label="Сообщение для CoreX AI"
            className="flex-1 resize-none bg-transparent px-4 py-3 text-[var(--corex-text)] placeholder:text-[var(--corex-text-dim)] focus:outline-none max-h-[200px] text-sm"
            rows={1}
          />

          {mentionOpen && mentionItems.length > 0 ? (
            <div className="absolute left-2 right-2 bottom-full mb-1 max-h-40 overflow-auto corex-dropdown z-20 py-1">
              {mentionItems.map((file, index) => (
                <button
                  key={file}
                  type="button"
                  onMouseDown={(ev) => {
                    ev.preventDefault();
                    applyMention(file);
                  }}
                  className={`w-full text-left px-3 py-2 text-xs font-mono truncate ${
                    index === mentionIndex
                      ? 'bg-[rgba(0,210,255,0.12)] text-[var(--corex-spark)]'
                      : 'text-[var(--corex-text-muted)] hover:bg-[var(--corex-surface-hover)]'
                  }`}
                >
                  /{file}
                </button>
              ))}
            </div>
          ) : null}

          {isProcessing ? (
            <button
              type="button"
              aria-label="Остановить"
              title="Остановить"
              onClick={onStop}
              className="m-2 p-2 text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
            >
              <StopCircle className="w-5 h-5" />
            </button>
          ) : (
            <button
              type="submit"
              aria-label="Отправить сообщение"
              title="Отправить"
              disabled={!message.trim()}
              className="m-2 p-2 rounded-lg bg-[var(--corex-gradient-spark)] text-[#041018] shadow-[0_0_12px_var(--corex-glow-spark)] hover:opacity-90 transition-opacity disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="mt-1.5 text-[10px] text-[var(--corex-text-dim)] text-center">
          Enter — отправить · /файл — смотреть, изменить или куда писать
        </div>
      </form>
    </div>
  );
}
