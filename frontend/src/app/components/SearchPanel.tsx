import { Search } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchApi } from '../utils/api';
import {
  groupSearchHits,
  splitSearchSnippet,
  type FileSearchHit,
} from '../utils/fileSearch';

interface SearchPanelProps {
  projectRoot: string;
  onOpenFile: (path: string, name: string, line?: number) => void;
}

const DEBOUNCE_MS = 280;

export function SearchPanel({ projectRoot, onOpenFile }: SearchPanelProps) {
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<FileSearchHit[]>([]);
  const [truncated, setTruncated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const trimmed = query.trim();
    if (!projectRoot) {
      setHits([]);
      setTruncated(false);
      setError('');
      setLoading(false);
      return;
    }
    if (trimmed.length < 2) {
      setHits([]);
      setTruncated(false);
      setError('');
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError('');
      void (async () => {
        try {
          const response = await fetchApi(
            `/api/files/search?q=${encodeURIComponent(trimmed)}&limit=80`,
            { signal: controller.signal },
          );
          const data = await response.json();
          if (requestId !== requestIdRef.current) {
            return;
          }
          if (data?.error) {
            setHits([]);
            setError(String(data.error));
            return;
          }
          setHits(Array.isArray(data?.matches) ? data.matches : []);
          setTruncated(Boolean(data?.truncated));
        } catch (err) {
          if (controller.signal.aborted || requestId !== requestIdRef.current) {
            return;
          }
          setHits([]);
          setError(err instanceof Error ? err.message : String(err));
        } finally {
          if (requestId === requestIdRef.current) {
            setLoading(false);
          }
        }
      })();
    }, DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, projectRoot]);

  const groups = useMemo(() => groupSearchHits(hits), [hits]);
  const trimmed = query.trim();

  return (
    <div className="h-full min-h-0 flex flex-col corex-sidebar-panel">
      <div className="px-3 py-3 border-b border-[var(--corex-border)]">
        <div className="flex items-center gap-2 text-[var(--corex-spark)] text-xs font-semibold uppercase tracking-wider mb-3">
          <Search className="w-3.5 h-3.5" />
          Поиск
        </div>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Поиск в файлах..."
          className="corex-input-field w-full text-sm"
          disabled={!projectRoot}
        />
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-2 py-2">
        {!projectRoot ? (
          <p className="text-sm text-[var(--corex-text-muted)] px-2">
            Откройте папку проекта, чтобы искать по файлам.
          </p>
        ) : trimmed.length < 2 ? (
          <p className="text-sm text-[var(--corex-text-muted)] px-2">
            Введите минимум 2 символа.
          </p>
        ) : loading ? (
          <p className="text-sm text-[var(--corex-text-dim)] px-2">Ищу…</p>
        ) : error ? (
          <p className="text-sm text-red-400 px-2">{error}</p>
        ) : groups.length === 0 ? (
          <p className="text-sm text-[var(--corex-text-muted)] px-2">Ничего не найдено.</p>
        ) : (
          <div className="space-y-2">
            {groups.map((group) => (
              <div key={group.path}>
                <button
                  type="button"
                  className="w-full text-left px-2 py-1 text-[11px] font-mono text-[var(--corex-spark)] truncate hover:bg-[var(--corex-surface-hover)] rounded"
                  title={group.path}
                  onClick={() => onOpenFile(group.path, group.name, group.hits[0]?.line)}
                >
                  {group.path}
                  <span className="text-[var(--corex-text-dim)]"> · {group.hits.length}</span>
                </button>
                {group.hits.map((hit) => {
                  const parts = splitSearchSnippet(hit.text, trimmed);
                  return (
                    <button
                      key={`${hit.path}:${hit.line}:${hit.text}`}
                      type="button"
                      className="w-full text-left px-2 py-1 rounded hover:bg-[var(--corex-surface-hover)]"
                      onClick={() => onOpenFile(hit.path, hit.name, hit.line)}
                    >
                      <div className="text-[10px] text-[var(--corex-text-dim)] font-mono">{hit.line}</div>
                      <div className="text-[12px] text-[var(--corex-text)] font-mono truncate">
                        {parts.before}
                        <mark className="corex-search-mark">{parts.match}</mark>
                        {parts.after}
                      </div>
                    </button>
                  );
                })}
              </div>
            ))}
            {truncated ? (
              <p className="text-[10px] text-[var(--corex-text-dim)] px-2 pt-1">
                Показаны первые совпадения. Уточните запрос.
              </p>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
