import { useEffect, useRef, useState } from 'react';
import { FolderOpen, Github, X } from 'lucide-react';
import { folderNameFromRemote, isAllowedGitRemote } from '../utils/gitClone';

interface CloneRepoModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: { url: string; parentPath: string }) => Promise<void>;
  isSubmitting?: boolean;
  error?: string;
  initialParentPath?: string;
}

export function CloneRepoModal({
  open,
  onClose,
  onSubmit,
  isSubmitting = false,
  error = '',
  initialParentPath = '',
}: CloneRepoModalProps) {
  const [parentPath, setParentPath] = useState(initialParentPath);
  const [url, setUrl] = useState('');
  const urlRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setParentPath(initialParentPath);
      setUrl('');
      window.setTimeout(() => urlRef.current?.focus(), 50);
    }
  }, [open, initialParentPath]);

  if (!open) {
    return null;
  }

  const pickParentFolder = async () => {
    if (window.electronAPI?.openFolder) {
      const selected = await window.electronAPI.openFolder();
      if (selected) {
        setParentPath(selected);
      }
    }
  };

  const canSubmit = isAllowedGitRemote(url) && Boolean(parentPath.trim()) && !isSubmitting;
  const previewName = isAllowedGitRemote(url) ? folderNameFromRemote(url) : '';

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    await onSubmit({ url: url.trim(), parentPath: parentPath.trim() });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-lg rounded-3xl border border-[#2c2f38] bg-[#0f1320] p-6 shadow-2xl">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Github className="w-5 h-5 text-white" />
            <div>
              <h2 className="text-xl font-semibold text-white">Git clone</h2>
              <p className="mt-1 text-xs text-[#7c8db0]">
                HTTPS или git@… Системный Git и ваши SSH-ключи, как в терминале.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="p-1 text-[#858585] hover:text-white rounded"
            aria-label="Закрыть"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={(event) => void handleSubmit(event)} className="mt-6 space-y-4">
          <div>
            <label htmlFor="clone-url" className="block text-xs text-[#858585] mb-1.5">
              Ссылка на репозиторий
            </label>
            <input
              ref={urlRef}
              id="clone-url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://github.com/user/repo.git или git@github.com:user/repo.git"
              disabled={isSubmitting}
              className="w-full rounded-2xl border border-[#2c2f38] bg-[#0f1320] px-3 py-2 text-sm text-[#d8dce6]"
            />
            {previewName ? (
              <p className="mt-1 text-[10px] text-[#7c8db0]">Папка: {previewName}</p>
            ) : null}
          </div>

          <div>
            <label className="block text-xs text-[#858585] mb-1.5">Куда клонировать</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={parentPath}
                onChange={(event) => setParentPath(event.target.value)}
                placeholder="C:\Projects"
                disabled={isSubmitting}
                className="flex-1 rounded-2xl border border-[#2c2f38] bg-[#0f1320] px-3 py-2 text-sm text-[#d8dce6]"
              />
              <button
                type="button"
                onClick={() => void pickParentFolder()}
                disabled={isSubmitting}
                className="inline-flex items-center gap-1 rounded-2xl border border-[#2c2f38] px-3 py-2 text-xs text-[#9da7c1] hover:border-[#5f95ff]"
              >
                <FolderOpen className="w-4 h-4" />
                Выбрать
              </button>
            </div>
          </div>

          {error ? <p className="text-xs text-red-400">{error}</p> : null}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="rounded-2xl border border-[#2c2f38] px-4 py-2 text-sm text-[#9da7c1]"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={!canSubmit}
              className="rounded-2xl bg-[#007acc] px-4 py-2 text-sm text-white disabled:opacity-40"
            >
              {isSubmitting ? 'Клонирую…' : 'Клонировать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
