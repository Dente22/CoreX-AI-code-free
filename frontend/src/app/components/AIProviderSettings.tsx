import { useCallback, useEffect, useState } from 'react';
import {
  fetchAiRuntime,
  setAiProvider,
  tierLabel,
  type AiProviderPreset,
} from '../utils/aiProvider';
import { OfflineModelGuide } from './OfflineModelGuide';
import { WorkloadLimitsPanel } from './WorkloadLimitsPanel';
import { fetchApi } from '../utils/api';

interface AIProviderSettingsProps {
  onNotification?: (message: string) => void;
}

export function AIProviderSettings({ onNotification }: AIProviderSettingsProps) {
  const [providers, setProviders] = useState<AiProviderPreset[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [installHint, setInstallHint] = useState('');
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [availableRamGb, setAvailableRamGb] = useState<number | undefined>(undefined);

  const loadProviders = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchAiRuntime();
      setProviders(data.local.providers ?? []);
      setSelectedId(data.local.selected_id ?? '');
      setInstallHint(data.local.install_hint ?? '');
      try {
        const profileRes = await fetchApi('/api/system/profile');
        const profile = await profileRes.json();
        if (typeof profile?.ram_gb === 'number') {
          setAvailableRamGb(profile.ram_gb);
        } else if (typeof profile?.ram_available_gb === 'number') {
          setAvailableRamGb(profile.ram_available_gb);
        }
      } catch {
        // optional hardware hint
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Ошибка загрузки провайдеров');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProviders();
  }, [loadProviders]);

  const handleSelect = async (providerId: string) => {
    if (providerId === selectedId || savingId) return;
    setSavingId(providerId);
    setError('');
    try {
      const result = await setAiProvider(providerId);
      if (!result.success) {
        setError(result.error ?? 'Не удалось сохранить выбор');
        return;
      }
      setSelectedId(result.selected_id ?? providerId);
      setProviders((current) =>
        current.map((provider) => ({
          ...provider,
          selected: provider.id === (result.selected_id ?? providerId),
        })),
      );
      const preset = result.preset;
      onNotification?.(
        preset
          ? `Выбран AI: ${preset.name}. Модель: ${preset.model_name}`
          : 'AI-провайдер обновлён',
      );
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Ошибка сохранения');
    } finally {
      setSavingId(null);
    }
  };

  if (loading) {
    return <p className="text-[#cccccc] text-sm">Загрузка AI-провайдеров…</p>;
  }

  return (
    <section className="max-w-3xl">
      <div className="flex items-center gap-2 mb-2">
        <h3 className="text-lg font-medium text-white">Локальный AI</h3>
      </div>
      <p className="text-sm text-[#9d9d9d] mb-4">
        Локальные модели Ollama. Онлайн API настраиваются в панели чата.
      </p>

      {error ? <p className="text-sm text-[#f48771] mb-4">{error}</p> : null}

      <div className="mb-4">
        <WorkloadLimitsPanel onNotification={onNotification} />
      </div>

      <div className="mb-4">
        <OfflineModelGuide
          providers={providers}
          selectedId={selectedId}
          availableRamGb={availableRamGb}
          onSelectModel={(id) => void handleSelect(id)}
        />
      </div>

      <div className="space-y-3">
        {providers.map((provider) => {
          const isSelected = provider.id === selectedId;
          const isSaving = savingId === provider.id;
          return (
            <button
              key={provider.id}
              type="button"
              onClick={() => void handleSelect(provider.id)}
              disabled={Boolean(savingId)}
              className={[
                'w-full text-left rounded-lg border p-4 transition-colors',
                isSelected
                  ? 'border-[#007acc] bg-[#252526] ring-1 ring-[#007acc]'
                  : 'border-[#3c3c3c] bg-[#252526] hover:border-[#5a5a5a]',
                savingId && !isSaving ? 'opacity-60' : '',
              ].join(' ')}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium">{provider.name}</span>
                    {provider.is_default ? (
                      <span className="text-[10px] uppercase tracking-wide text-[#4fc1ff]">
                        по умолчанию
                      </span>
                    ) : null}
                    {isSelected ? (
                      <span className="text-[10px] uppercase tracking-wide text-[#89d185]">
                        выбрано
                      </span>
                    ) : null}
                  </div>
                  <p className="text-sm text-[#9d9d9d] mt-1">{provider.description}</p>
                  {provider.pull_command ? (
                    <p className="text-xs text-[#6a6a6a] mt-2">
                      Установка: <code className="text-[#ce9178]">{provider.pull_command}</code>
                    </p>
                  ) : null}
                </div>
                <div className="text-xs text-[#cccccc] whitespace-nowrap">
                  {tierLabel(provider.tier)} · от {provider.min_ram_gb} ГБ RAM
                </div>
              </div>
              <div className="mt-3 text-xs text-[#9d9d9d]">
                Модель: <code className="text-[#ce9178]">{provider.model_name}</code>
              </div>
              {isSaving ? <p className="text-xs text-[#4fc1ff] mt-2">Сохранение…</p> : null}
            </button>
          );
        })}
      </div>

      {installHint ? <p className="text-xs text-[#6a6a6a] mt-4">{installHint}</p> : null}
    </section>
  );
}
