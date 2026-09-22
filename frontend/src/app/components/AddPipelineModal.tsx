import { useEffect, useRef, useState } from 'react';
import { ArrowDown, ArrowUp, Plus, Trash2, X } from 'lucide-react';
import type { Persona } from '../utils/personas';
import type { PipelineStepInput } from '../utils/pipelines';

interface PipelineStepDraft extends PipelineStepInput {
  key: string;
}

interface AddPipelineModalProps {
  open: boolean;
  personas: Persona[];
  onClose: () => void;
  onSubmit: (name: string, description: string, steps: PipelineStepInput[]) => Promise<void>;
  isSubmitting?: boolean;
  error?: string;
}

export function AddPipelineModal({
  open,
  personas,
  onClose,
  onSubmit,
  isSubmitting = false,
  error = '',
}: AddPipelineModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [steps, setSteps] = useState<PipelineStepDraft[]>([]);
  const [pickId, setPickId] = useState('');
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setName('');
      setDescription('');
      setSteps([]);
      setPickId(personas[0]?.id || '');
      window.setTimeout(() => nameRef.current?.focus(), 50);
    }
  }, [open, personas]);

  if (!open) {
    return null;
  }

  const addStep = () => {
    const persona = personas.find((p) => p.id === pickId);
    if (!persona) {
      return;
    }
    setSteps((prev) => [
      ...prev,
      {
        key: `${persona.id}-${Date.now()}`,
        persona_id: persona.id,
        role: persona.name,
        goal: '',
      },
    ]);
  };

  const moveStep = (index: number, direction: -1 | 1) => {
    setSteps((prev) => {
      const next = [...prev];
      const target = index + direction;
      if (target < 0 || target >= next.length) {
        return prev;
      }
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim() || steps.length === 0 || isSubmitting) {
      return;
    }
    await onSubmit(
      name.trim(),
      description.trim(),
      steps.map(({ persona_id, role, goal }) => ({
        persona_id,
        role,
        goal: goal?.trim() || undefined,
      })),
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div
        className="w-full max-w-lg max-h-[90vh] overflow-y-auto bg-[#1e1e1e] border border-[#2b2b2b] rounded-lg shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-pipeline-title"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2b2b2b] sticky top-0 bg-[#1e1e1e]">
          <h2 id="add-pipeline-title" className="text-sm font-semibold text-[#e5e9f0]">
            Новая команда
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
            <label htmlFor="pipeline-name" className="block text-xs text-[#858585] mb-1.5">
              Название
            </label>
            <input
              ref={nameRef}
              id="pipeline-name"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Например: Команда разработки"
              disabled={isSubmitting}
              className="w-full bg-[#0f1720] border border-[#212733] rounded-md px-3 py-2 text-sm text-[#e5e9f0] placeholder:text-[#6b7280] focus:outline-none focus:ring-1 focus:ring-[#7c3aed]"
            />
          </div>

          <div>
            <label htmlFor="pipeline-desc" className="block text-xs text-[#858585] mb-1.5">
              Описание
            </label>
            <input
              id="pipeline-desc"
              type="text"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Кратко: что делает команда"
              disabled={isSubmitting}
              className="w-full bg-[#0f1720] border border-[#212733] rounded-md px-3 py-2 text-sm text-[#e5e9f0] placeholder:text-[#6b7280] focus:outline-none focus:ring-1 focus:ring-[#7c3aed]"
            />
          </div>

          <div>
            <p className="text-xs text-[#858585] mb-1.5">Этапы (порядок выполнения)</p>
            {personas.length === 0 ? (
              <p className="text-xs text-amber-400/90">
                Сначала создайте хотя бы один скил в режиме «Один скил».
              </p>
            ) : (
              <div className="flex gap-2">
                <select
                  value={pickId}
                  onChange={(event) => setPickId(event.target.value)}
                  disabled={isSubmitting}
                  className="flex-1 bg-[#0f1720] text-[#e5e9f0] text-xs border border-[#212733] rounded-md px-2 py-2"
                >
                  {[...new Set(personas.map((p) => p.category_ru || 'Прочее'))]
                    .sort((a, b) => a.localeCompare(b, 'ru'))
                    .map((category) => (
                      <optgroup key={category} label={category}>
                        {personas
                          .filter((p) => (p.category_ru || 'Прочее') === category)
                          .map((persona) => (
                            <option key={persona.id} value={persona.id}>
                              {persona.name}
                            </option>
                          ))}
                      </optgroup>
                    ))}
                </select>
                <button
                  type="button"
                  onClick={addStep}
                  disabled={isSubmitting || !pickId}
                  className="flex items-center gap-1 px-2 py-2 text-xs text-[#e5e9f0] bg-[#0f1720] border border-[#212733] rounded-md hover:bg-[#1a2332] disabled:opacity-40"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Этап
                </button>
              </div>
            )}

            {steps.length > 0 ? (
              <ol className="mt-2 space-y-2">
                {steps.map((step, index) => (
                  <li
                    key={step.key}
                    className="border border-[#212733] rounded-md p-2 bg-[#0f1720]/60 space-y-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs text-[#e5e9f0] font-medium">
                        {index + 1}. {step.role || step.persona_id}
                      </span>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => moveStep(index, -1)}
                          disabled={isSubmitting || index === 0}
                          className="p-1 text-[#858585] hover:text-white disabled:opacity-30"
                          aria-label="Выше"
                        >
                          <ArrowUp className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => moveStep(index, 1)}
                          disabled={isSubmitting || index === steps.length - 1}
                          className="p-1 text-[#858585] hover:text-white disabled:opacity-30"
                          aria-label="Ниже"
                        >
                          <ArrowDown className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setSteps((prev) => prev.filter((s) => s.key !== step.key))}
                          disabled={isSubmitting}
                          className="p-1 text-red-400/80 hover:text-red-300"
                          aria-label="Удалить этап"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                    <input
                      type="text"
                      value={step.goal || ''}
                      onChange={(event) =>
                        setSteps((prev) =>
                          prev.map((s) =>
                            s.key === step.key ? { ...s, goal: event.target.value } : s,
                          ),
                        )
                      }
                      placeholder="Цель этапа (необязательно)"
                      disabled={isSubmitting}
                      className="w-full bg-[#0f1720] border border-[#212733] rounded px-2 py-1.5 text-xs text-[#e5e9f0] placeholder:text-[#6b7280]"
                    />
                  </li>
                ))}
              </ol>
            ) : null}
          </div>

          {error ? <p className="text-xs text-red-400">{error}</p> : null}

          <p className="text-[10px] text-[#6b7280]">
            Команда сохранится в проекте и появится в списке только если все этапы ссылаются
            на существующие скилы.
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
              disabled={isSubmitting || !name.trim() || steps.length === 0}
              className="px-3 py-1.5 text-xs bg-[#7c3aed] text-white rounded hover:bg-[#6d28d9] disabled:opacity-40"
            >
              {isSubmitting ? 'Сохранение...' : 'Сохранить'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
