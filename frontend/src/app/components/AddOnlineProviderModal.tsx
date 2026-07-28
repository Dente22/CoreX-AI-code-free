import { useEffect, useMemo, useRef, useState } from 'react';
import { ExternalLink, X } from 'lucide-react';
import {
  getDefaultOnlineProviderTemplate,
  getProviderTemplateById,
  ONLINE_PROVIDER_TEMPLATES,
  type OnlineApiType,
  type OnlineProviderTemplate,
} from '../utils/onlineProviderTemplates';

interface AddOnlineProviderModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: {
    name: string;
    base_url: string;
    api_key: string;
    model_name: string;
    api_type: OnlineApiType;
  }) => Promise<void>;
  isSubmitting?: boolean;
  error?: string;
  /** Prefill a specific template (e.g. openrouter-free). */
  initialTemplateId?: string;
}

function applyTemplateDefaults(
  template: OnlineProviderTemplate,
  setName: (value: string) => void,
  setApiType: (value: OnlineApiType) => void,
  setBaseUrl: (value: string) => void,
  setModelName: (value: string) => void,
) {
  setApiType(template.apiType);
  setBaseUrl(template.defaultBaseUrl);
  setModelName(template.defaultModel);
  setName(template.label);
}

export function AddOnlineProviderModal({
  open,
  onClose,
  onSubmit,
  isSubmitting = false,
  error = '',
  initialTemplateId,
}: AddOnlineProviderModalProps) {
  const defaultTemplate = getDefaultOnlineProviderTemplate();
  const [name, setName] = useState(defaultTemplate.label);
  const [providerTemplateId, setProviderTemplateId] = useState(defaultTemplate.id);
  const [apiType, setApiType] = useState<OnlineApiType>(defaultTemplate.apiType);
  const [baseUrl, setBaseUrl] = useState(defaultTemplate.defaultBaseUrl);
  const [apiKey, setApiKey] = useState('');
  const [modelName, setModelName] = useState(defaultTemplate.defaultModel);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const template =
      getProviderTemplateById(initialTemplateId || '') || getDefaultOnlineProviderTemplate();
    setProviderTemplateId(template.id);
    setApiKey('');
    applyTemplateDefaults(template, setName, setApiType, setBaseUrl, setModelName);
    window.setTimeout(() => nameRef.current?.focus(), 50);
  }, [open, initialTemplateId]);

  const activeTemplate = useMemo(
    () => getProviderTemplateById(providerTemplateId) || getDefaultOnlineProviderTemplate(),
    [providerTemplateId],
  );

  if (!open) {
    return null;
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !baseUrl.trim() || !apiKey.trim() || !modelName.trim() || isSubmitting) {
      return;
    }
    await onSubmit({
      name: name.trim(),
      base_url: baseUrl.trim(),
      api_key: apiKey.trim(),
      model_name: modelName.trim(),
      api_type: apiType,
    });
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/70 p-4">
      <div
        className="w-full max-w-lg max-h-[90vh] overflow-y-auto bg-[#1a1d24] border border-[#2b2b2b] rounded-xl shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-online-provider-title"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2b2b2b] sticky top-0 bg-[#1a1d24] z-10">
          <h2 id="add-online-provider-title" className="text-sm font-semibold text-[#e5e9f0]">
            Добавить онлайн API
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1 text-[#9ca3af] hover:text-white rounded"
            aria-label="Закрыть"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={(event) => void handleSubmit(event)} className="p-4 space-y-3">
          <p className="text-xs text-[#9ca3af]">
            Рекомендуем начать с OpenRouter Free — бесплатные токены без карты. Ключ
            сохраняется только на этом ПК и не уедет с проектом.
          </p>

          <label className="block space-y-1">
            <span className="text-xs text-[#9ca3af]">AI сервис</span>
            <select
              value={providerTemplateId}
              onChange={(e) => {
                const selectedId = e.target.value || defaultTemplate.id;
                setProviderTemplateId(selectedId);
                const template = getProviderTemplateById(selectedId);
                if (!template) {
                  return;
                }
                applyTemplateDefaults(template, setName, setApiType, setBaseUrl, setModelName);
              }}
              className="w-full rounded-lg border border-[#212733] bg-[#0f1720] px-3 py-2 text-sm text-[#e5e9f0] outline-none focus:border-[#7c3aed]"
            >
              {ONLINE_PROVIDER_TEMPLATES.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.badge ? `${template.label} · ${template.badge}` : template.label}
                </option>
              ))}
            </select>
          </label>

          {activeTemplate.guide ? (
            <div className="rounded-lg border border-[#2b2b2b] bg-[#12161e] p-3 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <p className="text-xs text-[#c7d0df] leading-relaxed">{activeTemplate.guide.summary}</p>
                {activeTemplate.badge ? (
                  <span className="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wide bg-[rgba(34,197,94,0.15)] text-[#4ade80] border border-[rgba(34,197,94,0.35)]">
                    {activeTemplate.badge}
                  </span>
                ) : null}
              </div>
              {activeTemplate.guide.limits ? (
                <p className="text-[11px] text-[#9ca3af] leading-relaxed">{activeTemplate.guide.limits}</p>
              ) : null}
              <ol className="space-y-2">
                {activeTemplate.guide.steps.map((step) => (
                  <li key={step.title} className="text-[11px] text-[#b7c0cf] leading-relaxed">
                    <div className="font-medium text-[#e5e9f0]">{step.title}</div>
                    <div className="mt-0.5">{step.detail}</div>
                    {step.url ? (
                      <a
                        href={step.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 mt-1 text-[11px] text-[#a78bfa] hover:text-[#c4b5fd]"
                      >
                        <ExternalLink className="w-3 h-3" />
                        {step.urlLabel || step.url}
                      </a>
                    ) : null}
                  </li>
                ))}
              </ol>
              {activeTemplate.guide.modelExamples?.length ? (
                <div className="pt-1">
                  <div className="text-[10px] uppercase tracking-wide text-[#6b7280] mb-1">
                    Примеры free-моделей
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {activeTemplate.guide.modelExamples.map((example) => (
                      <button
                        key={example}
                        type="button"
                        onClick={() => setModelName(example)}
                        className="rounded border border-[#2b2b2b] bg-[#0f1720] px-2 py-1 text-[10px] text-[#9ca3af] hover:text-white hover:border-[#7c3aed]/40"
                        title="Подставить модель"
                      >
                        {example}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          <label className="block space-y-1">
            <span className="text-xs text-[#9ca3af]">Название</span>
            <input
              ref={nameRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="OpenRouter Free / Groq / My API"
              className="w-full rounded-lg border border-[#212733] bg-[#0f1720] px-3 py-2 text-sm text-[#e5e9f0] outline-none focus:border-[#7c3aed]"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-xs text-[#9ca3af]">Base URL</span>
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://openrouter.ai/api/v1"
              className="w-full rounded-lg border border-[#212733] bg-[#0f1720] px-3 py-2 text-sm text-[#e5e9f0] outline-none focus:border-[#7c3aed]"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-xs text-[#9ca3af]">API ключ</span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={activeTemplate.keyPlaceholder || 'sk-...'}
              className="w-full rounded-lg border border-[#212733] bg-[#0f1720] px-3 py-2 text-sm text-[#e5e9f0] outline-none focus:border-[#7c3aed]"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-xs text-[#9ca3af]">Модель</span>
            <input
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder={activeTemplate.defaultModel}
              className="w-full rounded-lg border border-[#212733] bg-[#0f1720] px-3 py-2 text-sm text-[#e5e9f0] outline-none focus:border-[#7c3aed]"
            />
            {activeTemplate.modelHint ? (
              <span className="text-[10px] text-[#6b7280]">{activeTemplate.modelHint}</span>
            ) : null}
          </label>

          {error ? <p className="text-xs text-[#f48771]">{error}</p> : null}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-sm text-[#9ca3af] hover:text-white"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 text-sm rounded-lg bg-[#7c3aed] text-white hover:bg-[#6d28d9] disabled:opacity-50"
            >
              {isSubmitting ? 'Сохранение…' : 'Добавить'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
