import { useCallback, useEffect, useMemo, useState } from 'react';
import { Cloud, HardDrive, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { OfflineModelGuide } from './OfflineModelGuide';
import { WorkloadLimitsPanel } from './WorkloadLimitsPanel';
import { LocalModelCatalog } from './LocalModelCatalog';
import { AddOnlineProviderModal } from './AddOnlineProviderModal';
import { TokenUsageBar } from './TokenUsageBar';
import { fetchApi } from '../utils/api';
import { shouldApplyModeChange } from '../utils/aiRuntimeUi';
import { useAiRuntime } from '../hooks/useAiRuntime';
import { useOllamaModels } from '../hooks/useOllamaModels';
import { recommendOfflineModel } from '../utils/offlineModelGuide';
import { getFreeBaseOnlineProviderTemplate } from '../utils/onlineProviderTemplates';
import { gpuButtonLabel, saveGpuPreference, type GpuOption } from '../utils/gpuPreference';
import {
  saveWebAccessMode,
  WEB_ACCESS_MODES,
  webAccessHint,
  type WebAccessMode,
} from '../utils/webAccess';
import type { AiMode } from '../utils/aiProvider';

interface AIProviderSettingsProps {
  onNotification?: (message: string) => void;
}

export function AIProviderSettings({ onNotification }: AIProviderSettingsProps) {
  const {
    runtime,
    loading,
    synced,
    busy,
    error,
    loadRuntime,
    changeMode,
    selectLocal,
    selectOnline,
    addOnlineProvider,
    removeOnlineProvider,
  } = useAiRuntime();
  const {
    installedById,
    needsImportById,
    busyId,
    pullProgress,
    error: modelsError,
    pull,
    remove,
    load: loadModels,
  } = useOllamaModels(true);

  const [savingId, setSavingId] = useState<string | null>(null);
  const [showAddOnline, setShowAddOnline] = useState(false);
  const [addOnlineError, setAddOnlineError] = useState('');
  const [addOnlineTemplateId, setAddOnlineTemplateId] = useState<string | undefined>(undefined);
  const [ramGb, setRamGb] = useState<number | undefined>(undefined);
  const [vramGb, setVramGb] = useState<number | undefined>(undefined);
  const [gpus, setGpus] = useState<GpuOption[]>([]);
  const [gpuChoiceNeeded, setGpuChoiceNeeded] = useState(false);
  const [ollamaUsingDesktop, setOllamaUsingDesktop] = useState(false);
  const [savingGpu, setSavingGpu] = useState(false);
  const [webAccessMode, setWebAccessMode] = useState<WebAccessMode>('ask');
  const [savingWebAccess, setSavingWebAccess] = useState(false);

  const freeBaseTemplate = useMemo(() => getFreeBaseOnlineProviderTemplate(), []);
  const providers = runtime.local.providers;
  const selectedId = runtime.local.selected_id;
  const mode = runtime.mode;
  const isLocal = mode === 'local';

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const profileRes = await fetchApi('/api/system/profile');
        const profile = await profileRes.json();
        if (cancelled) return;
        if (typeof profile?.vram_gb === 'number') setVramGb(profile.vram_gb);
        if (typeof profile?.ram_gb === 'number') setRamGb(profile.ram_gb);
        else if (typeof profile?.ram_available_gb === 'number') setRamGb(profile.ram_available_gb);
        if (Array.isArray(profile?.gpus)) setGpus(profile.gpus as GpuOption[]);
        setGpuChoiceNeeded(Boolean(profile?.gpu_choice_needed));
        setOllamaUsingDesktop(Boolean(profile?.ollama_using_desktop));
        const webMode = profile?.web_access?.mode;
        if (webMode === 'never' || webMode === 'ask' || webMode === 'always') {
          setWebAccessMode(webMode);
        }
      } catch {
        // optional hardware hint
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const recommendation = useMemo(
    () => recommendOfflineModel(providers, { availableRamGb: ramGb, availableVramGb: vramGb }),
    [providers, ramGb, vramGb],
  );

  const handleSelectGpu = useCallback(
    async (gpuId: string) => {
      const current = gpus.find((item) => item.selected)?.id;
      if (!gpuId || gpuId === current || savingGpu) return;
      setSavingGpu(true);
      try {
        const snapshot = await saveGpuPreference(gpuId);
        if (Array.isArray(snapshot.gpus)) setGpus(snapshot.gpus);
        setOllamaUsingDesktop(Boolean(snapshot.ollama_using_desktop));
        const chosen = snapshot.gpus?.find((item) => item.id === snapshot.gpu_id);
        onNotification?.(
          snapshot.ollama_restarted === false
            ? `Выбран ${(chosen?.label || chosen?.name || snapshot.gpu_name)}. Перезапустите CoreX, если карта не сменилась.`
            : `Ollama перезапущена на ${(chosen?.label || chosen?.name || snapshot.gpu_name)}`,
        );
      } catch (saveError) {
        onNotification?.(saveError instanceof Error ? saveError.message : 'Не удалось сменить GPU');
      } finally {
        setSavingGpu(false);
      }
    },
    [gpus, onNotification, savingGpu],
  );

  const handleSelectWebAccess = useCallback(
    async (mode: WebAccessMode) => {
      if (!mode || mode === webAccessMode || savingWebAccess) return;
      setSavingWebAccess(true);
      try {
        const snapshot = await saveWebAccessMode(mode);
        if (snapshot.mode === 'never' || snapshot.mode === 'ask' || snapshot.mode === 'always') {
          setWebAccessMode(snapshot.mode);
        }
        onNotification?.(
          snapshot.mode === 'never'
            ? 'Поиск в интернете выключен'
            : snapshot.mode === 'always'
              ? 'Агент может искать сниппеты в интернете для задач на код'
              : 'Поиск в интернете — только когда вы об этом попросите',
        );
      } catch (saveError) {
        onNotification?.(
          saveError instanceof Error ? saveError.message : 'Не удалось сохранить доступ в интернет',
        );
      } finally {
        setSavingWebAccess(false);
      }
    },
    [onNotification, savingWebAccess, webAccessMode],
  );

  const handleSelectLocal = useCallback(
    async (providerId: string) => {
      if (providerId === selectedId || savingId) return;
      setSavingId(providerId);
      try {
        const ok = await selectLocal(providerId);
        if (!ok) {
          onNotification?.('Не удалось сохранить выбор модели');
          return;
        }
        const preset = providers.find((item) => item.id === providerId);
        onNotification?.(
          preset ? `Выбран AI: ${preset.name}. Модель: ${preset.model_name}` : 'AI-провайдер обновлён',
        );
      } finally {
        setSavingId(null);
      }
    },
    [onNotification, providers, savingId, selectLocal, selectedId],
  );

  const handlePull = async (providerId: string) => {
    const provider = providers.find((item) => item.id === providerId);
    const needsImport = Boolean(needsImportById[providerId]);
    onNotification?.(
      needsImport
        ? `Импорт ${provider?.name ?? providerId} из системной Ollama…`
        : `Скачивание ${provider?.name ?? providerId}…`,
    );
    const result = await pull(providerId);
    if (result.success) {
      onNotification?.(needsImport ? 'Модель импортирована в CoreX' : 'Модель установлена');
      await handleSelectLocal(providerId);
      await loadModels();
    } else {
      onNotification?.(result.error || 'Не удалось скачать модель');
    }
  };

  const handleRemove = async (providerId: string) => {
    const provider = providers.find((item) => item.id === providerId);
    if (!window.confirm(`Удалить модель «${provider?.name ?? providerId}» с диска?`)) return;
    const result = await remove(providerId);
    if (result.success) {
      onNotification?.('Модель удалена');
    } else {
      onNotification?.(result.error || 'Не удалось удалить модель');
    }
  };

  const handleModeChange = async (nextMode: AiMode) => {
    if (!shouldApplyModeChange(mode, nextMode, false, busy)) return;
    const ok = await changeMode(nextMode);
    if (ok) onNotification?.(nextMode === 'local' ? 'Локально' : 'Онлайн');
  };

  const openAddOnline = (templateId?: string) => {
    setAddOnlineError('');
    setAddOnlineTemplateId(templateId || freeBaseTemplate?.id);
    setShowAddOnline(true);
  };

  const handleAddOnline = async (payload: {
    name: string;
    base_url: string;
    api_key: string;
    model_name: string;
    api_type: 'openai' | 'gemini';
  }) => {
    setAddOnlineError('');
    const ok = await addOnlineProvider(payload);
    if (!ok) {
      setAddOnlineError(error || 'Не удалось сохранить API');
      return;
    }
    setShowAddOnline(false);
    onNotification?.(`Добавлен API: ${payload.name}`);
  };

  if (loading) {
    return <p className="text-[#cccccc] text-sm">Загрузка AI-провайдеров…</p>;
  }

  return (
    <section className="max-w-3xl space-y-5">
      <div>
        <h3 className="text-lg font-medium text-white">Модели</h3>
        <p className="text-sm text-[#9d9d9d] mt-1">
          Локальные Ollama и облачные API живут здесь. В чате остаются скиллы, агенты и команды.
        </p>
      </div>

      {error ? <p className="text-sm text-[#f48771]">{error}</p> : null}
      {modelsError ? <p className="text-sm text-[#f48771]">{modelsError}</p> : null}

      <div className="corex-segmented">
        {(
          [
            { id: 'local' as const, label: 'Локально', icon: HardDrive },
            { id: 'online' as const, label: 'Онлайн', icon: Cloud },
          ]
        ).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            disabled={busy}
            onClick={() => void handleModeChange(id)}
            className={`corex-segmented-btn ${
              mode === id
                ? id === 'local'
                  ? 'corex-segmented-btn--active bg-[rgba(0,210,255,0.15)] text-[var(--corex-spark)] border-[var(--corex-spark)]/30'
                  : 'corex-segmented-btn--active bg-[rgba(154,94,255,0.15)] text-[var(--corex-brand)] border-[var(--corex-brand)]/30'
                : ''
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
        {!synced ? (
          <button
            type="button"
            onClick={() => void loadRuntime()}
            className="corex-picker-action w-8"
            title="Синхронизировать"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        ) : null}
      </div>

      <TokenUsageBar mode={mode} />

      <div className="space-y-2">
        <div>
          <p className="text-[13px] text-white">Интернет</p>
          <p className="text-[11px] text-[var(--corex-text-muted)] mt-0.5">
            {webAccessHint(webAccessMode)}
          </p>
        </div>
        <div className="corex-segmented flex-wrap">
          {WEB_ACCESS_MODES.map((item) => (
            <button
              key={item.id}
              type="button"
              disabled={savingWebAccess}
              onClick={() => void handleSelectWebAccess(item.id)}
              className={`corex-segmented-btn ${
                webAccessMode === item.id
                  ? 'corex-segmented-btn--active bg-[rgba(0,210,255,0.15)] text-[var(--corex-spark)] border-[var(--corex-spark)]/30'
                  : ''
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {isLocal ? (
        <>
          {gpuChoiceNeeded && gpus.length > 1 ? (
            <div className="space-y-2">
              <div>
                <p className="text-[13px] text-white">Графический процессор</p>
                <p className="text-[11px] text-[var(--corex-text-muted)] mt-0.5">
                  На этом ПК несколько видеокарт. Выберите дискретную NVIDIA — иначе Ollama часто садится на встроенную Intel.
                </p>
                {ollamaUsingDesktop ? (
                  <p className="text-[11px] text-[#f48771] mt-1">
                    Сейчас отвечает приложение Ollama в трее — оно грузит Intel. Нажмите T600: CoreX закроет трей и запустит CUDA на NVIDIA.
                  </p>
                ) : null}
              </div>
              <div className="corex-segmented flex-wrap">
                {gpus.map((gpu) => (
                  <button
                    key={gpu.id}
                    type="button"
                    disabled={savingGpu}
                    title={gpu.name}
                    onClick={() => void handleSelectGpu(gpu.id)}
                    className={`corex-segmented-btn ${
                      gpu.selected
                        ? gpu.kind === 'nvidia'
                          ? 'corex-segmented-btn--active bg-[rgba(0,210,255,0.15)] text-[var(--corex-spark)] border-[var(--corex-spark)]/30'
                          : 'corex-segmented-btn--active bg-[rgba(154,94,255,0.15)] text-[var(--corex-brand)] border-[var(--corex-brand)]/30'
                        : ''
                    }`}
                  >
                    {gpuButtonLabel(gpu)}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          <LocalModelCatalog
            providers={providers}
            selectedId={selectedId}
            recommendedId={recommendation.id}
            vramGb={vramGb}
            ramGb={ramGb}
            installedById={installedById}
            needsImportById={needsImportById}
            busyId={busyId}
            pullProgress={pullProgress}
            savingId={savingId}
            onSelect={(id) => void handleSelectLocal(id)}
            onPull={(id) => void handlePull(id)}
            onRemove={(id) => void handleRemove(id)}
          />
          <OfflineModelGuide
            providers={providers}
            selectedId={selectedId}
            availableRamGb={ramGb}
            availableVramGb={vramGb}
            onSelectModel={(id) => void handleSelectLocal(id)}
            onNotification={onNotification}
          />
        </>
      ) : (
        <div className="space-y-2">
          {runtime.online.providers.length === 0 ? (
            <p className="text-[12px] text-[var(--corex-text-muted)]">
              Нет облачных API. Добавьте OpenRouter Free или другой ключ — он останется только на этом компьютере.
            </p>
          ) : null}
          {runtime.online.providers.map((provider) => {
            const isSelected = provider.id === runtime.online.selected_id;
            return (
              <div
                key={provider.id}
                className={[
                  'flex items-center gap-2 rounded-md border px-2.5 py-2',
                  isSelected
                    ? 'border-[var(--corex-brand)] bg-[rgba(154,94,255,0.08)]'
                    : 'border-[#212733] bg-[#0f1720]',
                ].join(' ')}
              >
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] text-white truncate">{provider.name}</p>
                  <p className="text-[10px] text-[var(--corex-text-dim)] truncate">
                    {provider.model_name} · {provider.api_type.toUpperCase()}
                  </p>
                </div>
                {!isSelected ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void selectOnline(provider.id)}
                    className="px-2 py-1 rounded text-[11px] text-[var(--corex-brand)] border border-[var(--corex-brand)]/30"
                  >
                    Выбрать
                  </button>
                ) : (
                  <span className="text-[9px] uppercase tracking-wide text-[#89d185]">активен</span>
                )}
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    if (!window.confirm(`Удалить API «${provider.name}»?`)) return;
                    void removeOnlineProvider(provider.id).then((ok) => {
                      if (ok) onNotification?.('Онлайн API удалён');
                    });
                  }}
                  className="p-1 rounded text-[var(--corex-text-dim)] hover:text-[#f48771]"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })}
          <button
            type="button"
            onClick={() => openAddOnline(freeBaseTemplate?.id)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[12px] text-[var(--corex-brand)] border border-[var(--corex-brand)]/30"
          >
            <Plus className="w-3.5 h-3.5" />
            Добавить API
          </button>
        </div>
      )}

      <WorkloadLimitsPanel onNotification={onNotification} />

      <AddOnlineProviderModal
        open={showAddOnline}
        initialTemplateId={addOnlineTemplateId}
        onClose={() => {
          if (!busy) {
            setShowAddOnline(false);
            setAddOnlineError('');
            setAddOnlineTemplateId(undefined);
          }
        }}
        onSubmit={handleAddOnline}
        isSubmitting={busy}
        error={addOnlineError}
      />
    </section>
  );
}
