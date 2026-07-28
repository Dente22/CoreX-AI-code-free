import { Cloud, HardDrive, RefreshCw, HelpCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { SelectionBar } from './SelectionBar';
import { SelectionPickerModal } from './SelectionPickerModal';
import type { PickerItem } from './SelectionPickerModal';
import { AddOnlineProviderModal } from './AddOnlineProviderModal';
import { TokenUsageBar } from './TokenUsageBar';
import { OfflineModelHelpModal } from './OfflineModelHelpModal';
import { AIControlSection } from './AIControlSection';
import { useAiRuntime } from '../hooks/useAiRuntime';
import { getModelShortLabel, tierLabel, type AiMode } from '../utils/aiProvider';
import { shouldApplyModeChange } from '../utils/aiRuntimeUi';
import { fetchApi } from '../utils/api';
import { getFreeBaseOnlineProviderTemplate } from '../utils/onlineProviderTemplates';

interface AIModelSelectorProps {
  disabled?: boolean;
  onNotification?: (message: string) => void;
}

export function AIModelSelector({ disabled = false, onNotification }: AIModelSelectorProps) {
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

  const [pickerOpen, setPickerOpen] = useState(false);
  const [showAddOnline, setShowAddOnline] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [addOnlineError, setAddOnlineError] = useState('');
  const [addOnlineTemplateId, setAddOnlineTemplateId] = useState<string | undefined>(undefined);
  const [availableRamGb, setAvailableRamGb] = useState<number | undefined>(undefined);

  const freeBaseTemplate = useMemo(() => getFreeBaseOnlineProviderTemplate(), []);

  const openAddOnline = (templateId?: string) => {
    setAddOnlineError('');
    setAddOnlineTemplateId(templateId || freeBaseTemplate?.id);
    setShowAddOnline(true);
  };

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetchApi('/api/system/profile');
        const profile = await res.json();
        if (cancelled) return;
        if (typeof profile?.ram_gb === 'number') {
          setAvailableRamGb(profile.ram_gb);
        } else if (typeof profile?.ram_available_gb === 'number') {
          setAvailableRamGb(profile.ram_available_gb);
        }
      } catch {
        // optional
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const mode = runtime.mode;
  const isLocal = mode === 'local';

  const localItems: PickerItem[] = useMemo(
    () =>
      runtime.local.providers.map((provider) => ({
        id: provider.id,
        name: getModelShortLabel(provider),
        description: `${provider.description} · ${tierLabel(provider.tier)} · от ${provider.min_ram_gb} ГБ`,
        meta: provider.model_name,
        source: 'library',
        category_ru: provider.is_default ? 'рекомендуем' : undefined,
      })),
    [runtime.local.providers],
  );

  const onlineItems: PickerItem[] = useMemo(
    () =>
      runtime.online.providers.map((provider) => ({
        id: provider.id,
        name: provider.name,
        description: provider.base_url,
        meta: provider.model_name,
        source: 'project',
      })),
    [runtime.online.providers],
  );

  const selectedLocal = runtime.local.providers.find((item) => item.id === runtime.local.selected_id);
  const selectedOnline = runtime.online.providers.find((item) => item.id === runtime.online.selected_id);

  const selectedName = isLocal
    ? selectedLocal
      ? getModelShortLabel(selectedLocal)
      : undefined
    : selectedOnline?.name;

  const selectedDescription = isLocal
    ? selectedLocal?.model_name
    : selectedOnline
      ? `${selectedOnline.model_name} · ${selectedOnline.api_type.toUpperCase()}`
      : undefined;

  const placeholder = isLocal ? 'Выберите локальную модель' : 'Выберите онлайн API';

  const handleModeChange = async (nextMode: AiMode) => {
    if (!shouldApplyModeChange(mode, nextMode, disabled, busy)) {
      return;
    }
    const ok = await changeMode(nextMode);
    if (ok) {
      onNotification?.(nextMode === 'local' ? 'Локально' : 'Онлайн');
    }
  };

  const handlePickerSelect = async (id: string) => {
    if (isLocal) {
      const ok = await selectLocal(id);
      if (ok) {
        const provider = runtime.local.providers.find((item) => item.id === id);
        onNotification?.(provider ? `Локально: ${provider.name}` : 'Модель выбрана');
      }
      return;
    }
    const ok = await selectOnline(id);
    if (ok) {
      const provider = runtime.online.providers.find((item) => item.id === id);
      onNotification?.(provider ? `Онлайн: ${provider.name}` : 'API выбран');
    }
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

  return (
    <AIControlSection title="Модель" hint={isLocal ? 'Ollama' : 'API'}>
      <div className="corex-segmented">
        {([
          { id: 'local' as const, label: 'Локально', icon: HardDrive, activeClass: 'corex-segmented-btn--active bg-[rgba(0,210,255,0.15)] text-[var(--corex-spark)] border-[var(--corex-spark)]/30' },
          { id: 'online' as const, label: 'Онлайн', icon: Cloud, activeClass: 'corex-segmented-btn--active bg-[rgba(154,94,255,0.15)] text-[var(--corex-brand)] border-[var(--corex-brand)]/30' },
        ]).map(({ id, label, icon: Icon, activeClass }) => (
          <button
            key={id}
            type="button"
            disabled={disabled || busy}
            onClick={() => void handleModeChange(id)}
            className={`corex-segmented-btn ${mode === id ? activeClass : ''}`}
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

      <SelectionBar
        label="Активная модель"
        selectedName={selectedName}
        selectedDescription={selectedDescription}
        placeholder={placeholder}
        onOpenPicker={() => setPickerOpen(true)}
        onAdd={!isLocal ? () => openAddOnline(freeBaseTemplate?.id) : undefined}
        onDelete={
          !isLocal && selectedOnline
            ? async () => {
                if (!window.confirm(`Удалить API «${selectedOnline.name}»?`)) return;
                const ok = await removeOnlineProvider(selectedOnline.id);
                if (ok) onNotification?.('Онлайн API удалён');
              }
            : undefined
        }
        canDelete={!isLocal && Boolean(selectedOnline)}
        addLabel="API"
        disabled={disabled || busy}
      />

      {isLocal && runtime.local.providers.length > 0 ? (
        <button
          type="button"
          onClick={() => setShowHelp(true)}
          className="flex items-center gap-2 w-full px-2 py-1.5 text-left rounded-lg text-[10px] text-[var(--corex-text-muted)] hover:text-[var(--corex-spark)] hover:bg-[var(--corex-surface-hover)] transition-colors"
        >
          <HelpCircle className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="truncate">Какую модель выбрать и как установить</span>
        </button>
      ) : null}

      {!isLocal ? (
        <button
          type="button"
          onClick={() => openAddOnline(freeBaseTemplate?.id)}
          className="flex items-center gap-2 w-full px-2 py-1.5 text-left rounded-lg text-[10px] text-[var(--corex-text-muted)] hover:text-[var(--corex-brand)] hover:bg-[var(--corex-surface-hover)] transition-colors"
        >
          <HelpCircle className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="truncate">
            {runtime.online.providers.length === 0
              ? 'Бесплатные токены OpenRouter — куда зайти и как поставить'
              : 'Инструкция OpenRouter Free / добавить ещё API'}
          </span>
        </button>
      ) : null}

      {!isLocal && runtime.online.providers.length === 0 ? (
        <p className="text-[10px] text-[var(--corex-text-dim)] px-0.5">
          База для старта — OpenRouter Free: аккаунт → Keys → ключ → модель{' '}
          <code className="text-[var(--corex-text-muted)]">openrouter/free</code>. Ключ останется
          только на этом компьютере.
        </p>
      ) : null}

      <SelectionPickerModal
        open={pickerOpen}
        title={isLocal ? 'Локальные модели' : 'Онлайн API'}
        items={isLocal ? localItems : onlineItems}
        selectedId={isLocal ? runtime.local.selected_id : runtime.online.selected_id}
        filters={[{ id: 'all', label: 'Все' }]}
        onClose={() => setPickerOpen(false)}
        onSelect={(id) => void handlePickerSelect(id)}
      />

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

      {isLocal ? (
        <OfflineModelHelpModal
          open={showHelp}
          onClose={() => setShowHelp(false)}
          providers={runtime.local.providers}
          selectedId={runtime.local.selected_id}
          availableRamGb={availableRamGb}
          onSelectModel={(id) => void selectLocal(id)}
          onNotification={onNotification}
        />
      ) : null}
    </AIControlSection>
  );
}
