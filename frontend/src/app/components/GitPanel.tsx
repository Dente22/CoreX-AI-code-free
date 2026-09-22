import { GitBranch, Minus, Plus, RotateCcw, Upload } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchApi } from '../utils/api';
import {
  gitChangeLetter,
  splitGitFiles,
  type GitFileStatus,
  type GitStatusPayload,
} from '../utils/gitScm';

interface GitPanelProps {
  projectRoot: string;
  onOpenFile: (path: string, name: string) => void;
  onNotification?: (text: string) => void;
}

export function GitPanel({ projectRoot, onOpenFile, onNotification }: GitPanelProps) {
  const [status, setStatus] = useState<GitStatusPayload | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const loadStatus = useCallback(async () => {
    if (!projectRoot) {
      setStatus(null);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await fetchApi('/api/git/status');
      const data = (await response.json()) as GitStatusPayload;
      if (data?.error) {
        setError(data.error);
        setStatus(null);
        return;
      }
      setStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [projectRoot]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const postJson = async (path: string, body?: Record<string, unknown>) => {
    const response = await fetchApi(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : '{}',
    });
    const data = (await response.json()) as GitStatusPayload;
    if (data?.error) {
      throw new Error(data.error);
    }
    setStatus(data);
    return data;
  };

  const run = async (label: string, work: () => Promise<void>) => {
    setBusy(label);
    setError('');
    try {
      await work();
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setError(text);
      onNotification?.(text);
    } finally {
      setBusy('');
    }
  };

  const { staged, changes } = useMemo(() => splitGitFiles(status?.files), [status?.files]);
  const disabled = Boolean(busy) || loading;

  const renderFile = (file: GitFileStatus, kind: 'staged' | 'changes') => (
    <div key={`${kind}-${file.path}`} className="flex items-center gap-1 px-1 py-0.5 rounded hover:bg-[var(--corex-surface-hover)]">
      <span className="w-4 text-[10px] font-mono text-[var(--corex-spark)] flex-shrink-0">
        {gitChangeLetter(file)}
      </span>
      <button
        type="button"
        className="min-w-0 flex-1 text-left text-[12px] font-mono text-[var(--corex-text)] truncate"
        title={file.path}
        onClick={() => onOpenFile(file.path, file.name)}
      >
        {file.path}
      </button>
      {kind === 'staged' ? (
        <button
          type="button"
          className="corex-icon-btn"
          title="Убрать из индекса"
          disabled={disabled}
          onClick={() => void run('unstage', () => postJson('/api/git/unstage', { paths: [file.path] }).then(() => undefined))}
        >
          <Minus className="w-3.5 h-3.5" />
        </button>
      ) : (
        <>
          <button
            type="button"
            className="corex-icon-btn"
            title="Добавить в индекс"
            disabled={disabled}
            onClick={() => void run('stage', () => postJson('/api/git/stage', { paths: [file.path] }).then(() => undefined))}
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            className="corex-icon-btn"
            title="Отменить правки"
            disabled={disabled}
            onClick={() => {
              const ok = window.confirm(
                file.untracked
                  ? `Удалить новый файл ${file.path}?`
                  : `Отменить правки в ${file.path}?`,
              );
              if (!ok) {
                return;
              }
              void run('discard', () => postJson('/api/git/discard', { paths: [file.path] }).then(() => undefined));
            }}
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </>
      )}
    </div>
  );

  return (
    <div className="h-full min-h-0 flex flex-col corex-sidebar-panel">
      <div className="px-3 py-3 border-b border-[var(--corex-border)]">
        <div className="flex items-center gap-2 text-[var(--corex-spark)] text-xs font-semibold uppercase tracking-wider">
          <GitBranch className="w-3.5 h-3.5" />
          Git
        </div>
        {status?.is_repo ? (
          <div className="mt-2 text-[11px] text-[var(--corex-text-muted)] font-mono truncate" title={status.branch}>
            {status.branch}
          </div>
        ) : null}
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-2 py-2 space-y-3">
        {!projectRoot ? (
          <p className="text-sm text-[var(--corex-text-muted)] px-1">Откройте папку проекта.</p>
        ) : loading && !status ? (
          <p className="text-sm text-[var(--corex-text-dim)] px-1">Проверяю git…</p>
        ) : error && !status ? (
          <p className="text-sm text-red-400 px-1">{error}</p>
        ) : status && !status.is_repo ? (
          <div className="px-1 space-y-2">
            <p className="text-sm text-[var(--corex-text-muted)]">В этой папке ещё нет git-репозитория.</p>
            <button
              type="button"
              className="corex-btn-primary px-3 py-1.5 text-xs"
              disabled={disabled}
              onClick={() => void run('init', async () => {
                await postJson('/api/git/init');
                onNotification?.('Репозиторий создан.');
              })}
            >
              git init
            </button>
          </div>
        ) : (
          <>
            <section>
              <div className="flex items-center justify-between px-1 mb-1">
                <span className="text-[10px] uppercase tracking-wider text-[var(--corex-text-dim)]">Индекс</span>
                {staged.length > 0 ? (
                  <button
                    type="button"
                    className="text-[10px] text-[var(--corex-text-dim)] hover:text-[var(--corex-text)]"
                    disabled={disabled}
                    onClick={() => void run('unstage-all', () => postJson('/api/git/unstage', { paths: staged.map((file) => file.path) }).then(() => undefined))}
                  >
                    Убрать все
                  </button>
                ) : null}
              </div>
              {staged.length === 0 ? (
                <p className="text-[12px] text-[var(--corex-text-dim)] px-1">Пусто</p>
              ) : (
                staged.map((file) => renderFile(file, 'staged'))
              )}
            </section>

            <section>
              <div className="flex items-center justify-between px-1 mb-1">
                <span className="text-[10px] uppercase tracking-wider text-[var(--corex-text-dim)]">Изменения</span>
                {changes.length > 0 ? (
                  <button
                    type="button"
                    className="text-[10px] text-[var(--corex-text-dim)] hover:text-[var(--corex-text)]"
                    disabled={disabled}
                    onClick={() => void run('stage-all', () => postJson('/api/git/stage', { paths: changes.map((file) => file.path) }).then(() => undefined))}
                  >
                    Добавить все
                  </button>
                ) : null}
              </div>
              {changes.length === 0 ? (
                <p className="text-[12px] text-[var(--corex-text-dim)] px-1">Нет изменений</p>
              ) : (
                changes.map((file) => renderFile(file, 'changes'))
              )}
            </section>
          </>
        )}
        {error && status ? <p className="text-xs text-red-400 px-1">{error}</p> : null}
      </div>

      {status?.is_repo ? (
        <div className="flex-shrink-0 border-t border-[var(--corex-border)] px-3 py-2 space-y-2">
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Сообщение коммита"
            rows={3}
            className="corex-input-field w-full text-sm resize-none min-h-[4.5rem]"
            disabled={disabled}
          />
          <button
            type="button"
            className="corex-btn-primary w-full py-1.5 text-xs"
            disabled={disabled || !message.trim() || staged.length === 0}
            onClick={() => void run('commit', async () => {
              await postJson('/api/git/commit', { message: message.trim() });
              setMessage('');
              onNotification?.('Коммит создан.');
            })}
          >
            Commit
          </button>
          <button
            type="button"
            className="corex-btn-ghost w-full py-1.5 text-xs flex items-center justify-center gap-1"
            disabled={disabled}
            onClick={() => void run('push', async () => {
              await postJson('/api/git/push');
              onNotification?.('Push выполнен.');
            })}
          >
            <Upload className="w-3.5 h-3.5" />
            Push
          </button>
        </div>
      ) : null}
    </div>
  );
}
