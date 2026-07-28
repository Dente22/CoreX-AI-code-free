import { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';

const AGENT_CATEGORIES = [
  'Разработка',
  'Тестирование',
  'Ревью',
  'Безопасность',
  'DevOps',
  'Архитектура',
  'Мои агенты',
] as const;

interface AddAgentModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (name: string, prompt: string, categoryRu: string) => Promise<void>;
  isSubmitting?: boolean;
  error?: string;
}

export function AddAgentModal({
  open,
  onClose,
  onSubmit,
  isSubmitting = false,
  error = '',
}: AddAgentModalProps) {
  const [name, setName] = useState('');
  const [prompt, setPrompt] = useState('');
  const [categoryRu, setCategoryRu] = useState('Мои агенты');
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setName('');
      setPrompt('');
      setCategoryRu('Мои агенты');
      window.setTimeout(() => nameRef.current?.focus(), 50);
    }
  }, [open]);

  if (!open) {
    return null;
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !prompt.trim() || isSubmitting) {
      return;
    }
    await onSubmit(name.trim(), prompt.trim(), categoryRu);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div
        className="w-full max-w-lg bg-[#1e1e1e] border border-[#2b2b2b] rounded-lg shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-agent-title"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2b2b2b]">
          <h2 id="add-agent-title" className="text-sm font-semibold text-[#e5e9f0]">
            Новый агент
          </h2>
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

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label htmlFor="agent-name" className="block text-xs text-[#858585] mb-1.5">
              Название
            </label>
            <input
              ref={nameRef}
              id="agent-name"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Например: Ревьюер API"
              disabled={isSubmitting}
              className="w-full bg-[#0f1720] border border-[#212733] rounded-md px-3 py-2 text-sm text-[#e5e9f0] placeholder:text-[#6b7280] focus:outline-none focus:ring-1 focus:ring-[#2563eb]"
            />
          </div>

          <div>
            <label htmlFor="agent-category" className="block text-xs text-[#858585] mb-1.5">
              Категория
            </label>
            <select
              id="agent-category"
              value={categoryRu}
              onChange={(event) => setCategoryRu(event.target.value)}
              disabled={isSubmitting}
              className="w-full bg-[#0f1720] text-[#e5e9f0] text-sm border border-[#212733] rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#2563eb]"
            >
              {AGENT_CATEGORIES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="agent-prompt" className="block text-xs text-[#858585] mb-1.5">
              Промпт
            </label>
            <textarea
              id="agent-prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Опишите роль, инструменты и правила работы агента..."
              rows={8}
              disabled={isSubmitting}
              className="w-full resize-y bg-[#0f1720] border border-[#212733] rounded-md px-3 py-2 text-sm text-[#e5e9f0] placeholder:text-[#6b7280] focus:outline-none focus:ring-1 focus:ring-[#2563eb] min-h-[160px]"
            />
          </div>

          {error ? <p className="text-xs text-red-400">{error}</p> : null}

          <p className="text-[10px] text-[#6b7280]">
            Агент сохранится в chat/agents/ открытого проекта. Можно ссылаться на скилы:
            `core_x_skills/.../SKILL.md`
          </p>

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-3 py-1.5 text-xs text-[#cccccc] hover:bg-[#2a2d2e] rounded"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !name.trim() || !prompt.trim()}
              className="px-3 py-1.5 text-xs bg-[#2563eb] text-white rounded hover:bg-[#1d4ed8] disabled:opacity-40"
            >
              {isSubmitting ? 'Сохранение...' : 'Сохранить'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
