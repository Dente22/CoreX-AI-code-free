import { useEffect, useRef, useState } from 'react';
import { FolderOpen, X } from 'lucide-react';

interface CreateAIProjectModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: {
    parentPath: string;
    name: string;
    description: string;
    stack: string;
  }) => Promise<void>;
  isSubmitting?: boolean;
  error?: string;
  initialParentPath?: string;
}

const STACKS = [
  { id: 'python', label: 'Python' },
  { id: 'node', label: 'Node.js / React' },
  { id: 'web', label: 'HTML / CSS / JS' },
] as const;

export function CreateAIProjectModal({
  open,
  onClose,
  onSubmit,
  isSubmitting = false,
  error = '',
  initialParentPath = '',
}: CreateAIProjectModalProps) {
  const [parentPath, setParentPath] = useState(initialParentPath);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [stack, setStack] = useState('python');
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setParentPath(initialParentPath);
      setName('');
      setDescription('');
      setStack('python');
      window.setTimeout(() => nameRef.current?.focus(), 50);
    }
  }, [open, initialParentPath]);

  if (!open) return null;

  const pickParentFolder = async () => {
    if (window.electronAPI?.openFolder) {
      const selected = await window.electronAPI.openFolder();
      if (selected) setParentPath(selected);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!parentPath.trim() || !name.trim() || !description.trim() || isSubmitting) {
      return;
    }
    await onSubmit({
      parentPath: parentPath.trim(),
      name: name.trim(),
      description: description.trim(),
      stack,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-2xl rounded-3xl border border-[#2c2f38] bg-[#0f1320] p-6 shadow-2xl">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-white">Новый проект с AI</h2>
            <p className="mt-1 text-xs text-[#7c8db0]">
              Рекомендуется режим «Онлайн API» — лимиты токенов отображаются над чатом.
            </p>
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

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-xs text-[#858585] mb-1.5">Папка для проектов</label>
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

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="project-name" className="block text-xs text-[#858585] mb-1.5">
                Название проекта
              </label>
              <input
                ref={nameRef}
                id="project-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Мой сервис"
                disabled={isSubmitting}
                className="w-full rounded-2xl border border-[#2c2f38] bg-[#0f1320] px-3 py-2 text-sm text-[#d8dce6]"
              />
            </div>
            <div>
              <label htmlFor="project-stack" className="block text-xs text-[#858585] mb-1.5">
                Стек
              </label>
              <select
                id="project-stack"
                value={stack}
                onChange={(event) => setStack(event.target.value)}
                disabled={isSubmitting}
                className="w-full rounded-2xl border border-[#2c2f38] bg-[#0f1320] px-3 py-2 text-sm text-[#d8dce6]"
              >
                {STACKS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="project-description" className="block text-xs text-[#858585] mb-1.5">
              Описание — что должен уметь проект
            </label>
            <textarea
              id="project-description"
              rows={6}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="REST API для заметок с SQLite, авторизацией и тестами..."
              disabled={isSubmitting}
              className="w-full rounded-2xl border border-[#2c2f38] bg-[#0f1320] p-4 text-sm text-[#d8dce6]"
            />
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
              disabled={isSubmitting || !parentPath.trim() || !name.trim() || !description.trim()}
              className="rounded-2xl bg-[#007acc] px-4 py-2 text-sm text-white disabled:opacity-40"
            >
              {isSubmitting ? 'Создаю…' : 'Создать и запустить AI'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
