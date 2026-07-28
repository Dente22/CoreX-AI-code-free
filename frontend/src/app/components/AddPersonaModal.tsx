import { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { fetchSkillCategories, type SkillCategory } from '../utils/skillsMeta';

interface AddPersonaModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (name: string, prompt: string, category: string) => Promise<void>;
  isSubmitting?: boolean;
  error?: string;
}

export function AddPersonaModal({
  open,
  onClose,
  onSubmit,
  isSubmitting = false,
  error = '',
}: AddPersonaModalProps) {
  const [name, setName] = useState('');
  const [prompt, setPrompt] = useState('');
  const [category, setCategory] = useState('');
  const [categories, setCategories] = useState<SkillCategory[]>([]);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setName('');
      setPrompt('');
      setCategory('');
      void fetchSkillCategories().then(setCategories);
      window.setTimeout(() => nameRef.current?.focus(), 50);
    }
  }, [open]);

  if (!open) {
    return null;
  }

  const selectedCategory = categories.find((item) => item.id === category);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !prompt.trim() || isSubmitting) {
      return;
    }
    await onSubmit(name.trim(), prompt.trim(), category);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div
        className="w-full max-w-lg bg-[#1e1e1e] border border-[#2b2b2b] rounded-lg shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-persona-title"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2b2b2b]">
          <h2 id="add-persona-title" className="text-sm font-semibold text-[#e5e9f0]">
            Новый скил
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
            <label htmlFor="persona-name" className="block text-xs text-[#858585] mb-1.5">
              Название
            </label>
            <input
              ref={nameRef}
              id="persona-name"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Например: Разработчик"
              disabled={isSubmitting}
              className="w-full bg-[#0f1720] border border-[#212733] rounded-md px-3 py-2 text-sm text-[#e5e9f0] placeholder:text-[#6b7280] focus:outline-none focus:ring-1 focus:ring-[#2563eb]"
            />
          </div>

          <div>
            <label htmlFor="persona-category" className="block text-xs text-[#858585] mb-1.5">
              Категория
            </label>
            <select
              id="persona-category"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              disabled={isSubmitting}
              className="w-full bg-[#0f1720] text-[#e5e9f0] text-sm border border-[#212733] rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#2563eb]"
            >
              <option value="">— Без категории —</option>
              {categories.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            {selectedCategory?.hint ? (
              <p className="mt-1 text-[10px] text-[#6b7280]">{selectedCategory.hint}</p>
            ) : null}
          </div>

          <div>
            <label htmlFor="persona-prompt" className="block text-xs text-[#858585] mb-1.5">
              Промпт
            </label>
            <textarea
              id="persona-prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Опишите роль и стиль работы AI..."
              rows={8}
              disabled={isSubmitting}
              className="w-full resize-y bg-[#0f1720] border border-[#212733] rounded-md px-3 py-2 text-sm text-[#e5e9f0] placeholder:text-[#6b7280] focus:outline-none focus:ring-1 focus:ring-[#2563eb] min-h-[160px]"
            />
          </div>

          {error ? <p className="text-xs text-red-400">{error}</p> : null}

          <p className="text-[10px] text-[#6b7280]">
            Скил сохранится в chat/personas/ открытого проекта и сразу появится в списке.
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
