import { useEffect, useMemo, useState } from 'react';
import { Check, ChevronDown, ChevronRight, Copy, Download, Loader2, Trash2, X } from 'lucide-react';
import type { AiProviderPreset } from '../utils/aiProvider';
import { useOllamaModels } from '../hooks/useOllamaModels';
import { OllamaPullProgressBar } from './OllamaPullProgressBar';
import {
  buildModelInstallGuide,
  buildModelProfile,
  buildOllamaInstallGuide,
  compareOfflineModels,
  recommendOfflineModel,
  resolveInitialFocusedModelId,
} from '../utils/offlineModelGuide';

interface OfflineModelHelpModalProps {
  open: boolean;
  onClose: () => void;
  providers: AiProviderPreset[];
  selectedId?: string;
  availableRamGb?: number;
  onSelectModel?: (id: string) => void;
  onNotification?: (message: string) => void;
}

export function OfflineModelHelpModal({
  open,
  onClose,
  providers,
  selectedId,
  availableRamGb,
  onSelectModel,
  onNotification,
}: OfflineModelHelpModalProps) {
  const [copiedCommand, setCopiedCommand] = useState('');
  const [focusedModelId, setFocusedModelId] = useState('');
  const [expandedDetailsId, setExpandedDetailsId] = useState<string | null>(null);
  const {
    catalog,
    installedById,
    needsImportById,
    modelsDir,
    loading: modelsLoading,
    busyId,
    pullProgress,
    error: modelsError,
    pull,
    remove,
  } = useOllamaModels(open);

  const providersWithCommands = useMemo(() => {
    const byId = Object.fromEntries(catalog.map((item) => [item.id, item]));
    return providers.map((provider) => ({
      ...provider,
      pull_command: byId[provider.id]?.pull_command || provider.pull_command,
    }));
  }, [providers, catalog]);

  const recommendation = useMemo(
    () => recommendOfflineModel(providersWithCommands, { availableRamGb }),
    [providersWithCommands, availableRamGb],
  );

  const rows = useMemo(
    () => compareOfflineModels(providersWithCommands, recommendation.id),
    [providersWithCommands, recommendation.id],
  );

  useEffect(() => {
    if (!open) {
      setExpandedDetailsId(null);
      return;
    }
    setFocusedModelId(
      resolveInitialFocusedModelId(providersWithCommands, selectedId, recommendation.id),
    );
  }, [open, providersWithCommands, selectedId, recommendation.id]);

  const focusedModel =
    providersWithCommands.find((p) => p.id === focusedModelId) ||
    providersWithCommands.find((p) => p.id === recommendation.id) ||
    providersWithCommands[0];

  const focusedProfile = useMemo(
    () => (focusedModel ? buildModelProfile(focusedModel) : null),
    [focusedModel],
  );

  const ollamaGuide = useMemo(() => buildOllamaInstallGuide(), []);
  const modelGuide = useMemo(
    () => (focusedModel ? buildModelInstallGuide(focusedModel) : null),
    [focusedModel],
  );

  if (!open || !providers.length || !modelGuide || !focusedProfile) return null;

  const focusedInstalled = Boolean(focusedModel && installedById[focusedModel.id]);
  const focusedNeedsImport = Boolean(focusedModel && needsImportById[focusedModel.id]);
  const focusedBusy = Boolean(focusedModel && busyId === focusedModel.id);
  const showFocusedProgress = focusedBusy && pullProgress;

  const copyCommand = async (command: string) => {
    try {
      await navigator.clipboard.writeText(command);
      setCopiedCommand(command);
      window.setTimeout(() => setCopiedCommand(''), 1500);
    } catch {
      // ignore
    }
  };

  const openOllamaDownload = () => {
    window.open(ollamaGuide.downloadUrl, '_blank', 'noopener,noreferrer');
  };

  const toggleDetails = (id: string) => {
    setFocusedModelId(id);
    setExpandedDetailsId((prev) => (prev === id ? null : id));
  };

  const handlePullFocused = async () => {
    if (!focusedModel || focusedBusy) return;
    onNotification?.(
      focusedNeedsImport
        ? `Импорт ${focusedProfile.shortName} из системной Ollama…`
        : `Скачивание ${focusedProfile.shortName}…`,
    );
    const result = await pull(focusedModel.id);
    if (result.success) {
      onNotification?.(
        focusedNeedsImport
          ? `Модель ${focusedProfile.shortName} импортирована в CoreX`
          : `Модель ${focusedProfile.shortName} установлена`,
      );
    } else {
      onNotification?.(result.error || 'Не удалось скачать модель');
    }
  };

  const handleDeleteFocused = async () => {
    if (!focusedModel || focusedBusy) return;
    if (!window.confirm(`Удалить модель «${focusedProfile.shortName}» с диска?`)) return;
    const result = await remove(focusedModel.id);
    if (result.success) {
      onNotification?.(`Модель ${focusedProfile.shortName} удалена`);
    } else {
      onNotification?.(result.error || 'Не удалось удалить модель');
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/70 p-4">
      <div
        className="w-full max-w-lg max-h-[85vh] flex flex-col bg-[#1a1d24] border border-[#2b2b2b] rounded-xl shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="offline-help-title"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2b2b2b] flex-shrink-0">
          <h2 id="offline-help-title" className="text-sm font-semibold text-[#e5e9f0]">
            Локальные модели: выбор и установка
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1 text-[#858585] hover:text-white rounded"
            aria-label="Закрыть"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto min-h-0 px-4 py-3 pb-6 space-y-3">
          <p className="text-[11px] text-[#9ca3af] leading-snug">{recommendation.reason}</p>

          {modelsDir ? (
            <p className="text-[10px] text-[#6b7280] leading-snug">
              CoreX хранит модели в ollama_models (порт 11435). Если вы уже скачали модель через
              ollama pull в системе — нажмите «Импортировать» (копирование без повторной загрузки).
            </p>
          ) : null}

          {modelsError ? (
            <p className="text-[10px] text-[#f87171] leading-snug">{modelsError}</p>
          ) : null}

          <section>
            <h3 className="text-[11px] font-semibold text-[#e5e9f0] mb-1.5">
              Сравнение моделей — нажмите, чтобы читать подробности
            </h3>
            <div className="space-y-1.5">
              {rows.map((row) => {
                const profile = buildModelProfile(
                  providers.find((p) => p.id === row.id) ?? providers[0],
                );
                const isFocused = row.id === focusedModelId;
                const isExpanded = expandedDetailsId === row.id;
                const isInstalled = Boolean(installedById[row.id]);
                const needsImport = Boolean(needsImportById[row.id]);
                const rowBusy = busyId === row.id;
                const showRowProgress = rowBusy && pullProgress;

                return (
                  <div
                    key={row.id}
                    className={`rounded border px-2 py-1.5 transition-colors ${
                      isFocused
                        ? 'border-[#2563eb] bg-[#132238]'
                        : row.recommended
                          ? 'border-[#1e40af] bg-[#0f1a2e]'
                          : 'border-[#212733] bg-[#0b1220]'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => setFocusedModelId(row.id)}
                      className="w-full text-left"
                    >
                      <div className="flex items-center gap-2 text-[11px]">
                        <span className="font-medium text-[#e5e9f0]">{row.shortName}</span>
                        {row.recommended ? (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#2563eb] text-white">
                            рекомендуем
                          </span>
                        ) : null}
                        {isInstalled ? (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#065f46] text-white">
                            установлена
                          </span>
                        ) : needsImport ? (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#92400e] text-white">
                            в системной Ollama
                          </span>
                        ) : modelsLoading ? null : (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#374151] text-[#d1d5db]">
                            не скачана
                          </span>
                        )}
                        {isFocused ? (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#0f766e] text-white">
                            смотрите
                          </span>
                        ) : null}
                        <span className="text-[#6b7280] ml-auto">{row.ramLabel}</span>
                      </div>
                      <p className="text-[10px] text-[#9ca3af] mt-0.5">{row.bestFor}</p>
                      <p className="text-[10px] text-[#6b7280]">{row.tradeoff}</p>
                    </button>

                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      <button
                        type="button"
                        onClick={() => toggleDetails(row.id)}
                        className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded border border-[#334155] text-[#93c5fd] hover:text-white"
                      >
                        {isExpanded ? (
                          <ChevronDown className="w-3 h-3" />
                        ) : (
                          <ChevronRight className="w-3 h-3" />
                        )}
                        Подробнее
                      </button>
                      {!isInstalled ? (
                        <button
                          type="button"
                          disabled={rowBusy}
                          onClick={() => void pull(row.id).then((result) => {
                            if (result.success) {
                              onNotification?.(
                                needsImport
                                  ? `Модель ${row.shortName} импортирована из системной Ollama`
                                  : `Модель ${row.shortName} установлена`,
                              );
                            }
                          })}
                          className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded border border-[#2563eb] text-[#93c5fd] hover:text-white disabled:opacity-50"
                        >
                          {rowBusy ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Download className="w-3 h-3" />
                          )}
                          {needsImport ? 'Импортировать' : 'Скачать'}
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={rowBusy}
                          onClick={() => {
                            if (!window.confirm(`Удалить модель «${row.shortName}»?`)) return;
                            void remove(row.id).then((result) => {
                              if (result.success) {
                                onNotification?.(`Модель ${row.shortName} удалена`);
                              }
                            });
                          }}
                          className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded border border-[#334155] text-[#fca5a5] hover:text-white disabled:opacity-50"
                        >
                          {rowBusy ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Trash2 className="w-3 h-3" />
                          )}
                          Удалить
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => void copyCommand(row.pullCommand)}
                        className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded border border-[#334155] text-[#cbd5e1] hover:text-white"
                      >
                        {copiedCommand === row.pullCommand ? (
                          <Check className="w-3 h-3 text-emerald-400" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                        {row.pullCommand}
                      </button>
                      {onSelectModel ? (
                        <button
                          type="button"
                          onClick={() => {
                            onSelectModel(row.id);
                            onClose();
                          }}
                          className="text-[10px] px-2 py-0.5 rounded border border-[#2563eb] text-[#93c5fd] hover:text-white"
                        >
                          Выбрать
                        </button>
                      ) : null}
                    </div>

                    {showRowProgress ? (
                      <OllamaPullProgressBar progress={pullProgress} compact />
                    ) : null}

                    {isExpanded ? (
                      <div className="mt-2 pt-2 border-t border-[#212733] space-y-2 text-[10px] text-[#9ca3af]">
                        <p className="leading-snug">{profile.summary}</p>
                        <div>
                          <p className="text-[#c8c8c8] font-medium mb-0.5">Плюсы</p>
                          <ul className="list-disc list-inside space-y-0.5">
                            {profile.strengths.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="text-[#c8c8c8] font-medium mb-0.5">Минусы</p>
                          <ul className="list-disc list-inside space-y-0.5">
                            {profile.weaknesses.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </div>
                        <p>
                          <span className="text-[#c8c8c8] font-medium">Когда выбрать: </span>
                          {profile.whenToUse}
                        </p>
                        <p className="text-[#6b7280]">
                          Полное имя: {profile.fullName} · {profile.modelName}
                        </p>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </section>

          <section className="rounded border border-[#212733] bg-[#0b1220] px-2 py-1.5">
            <h3 className="text-[11px] font-medium text-[#e5e9f0] mb-1">{ollamaGuide.title}</h3>
            <ol className="list-decimal list-inside space-y-1 text-[10px] text-[#9ca3af] leading-snug">
              {ollamaGuide.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <button
              type="button"
              onClick={openOllamaDownload}
              className="mt-2 text-[10px] px-2 py-1 rounded border border-[#334155] text-[#93c5fd] hover:text-white hover:border-[#475569]"
            >
              Скачать Ollama
            </button>
          </section>

          <section className="rounded border border-[#2563eb] bg-[#0b1220] px-2 py-1.5">
            <h3 className="text-[11px] font-medium text-[#e5e9f0] mb-1">
              {modelGuide.title}
              <span className="text-[#6b7280] font-normal"> — выбрана для просмотра</span>
            </h3>
            <p className="text-[10px] text-[#9ca3af] mb-1">{focusedProfile.summary}</p>
            <p className="text-[10px] text-[#6b7280] mb-1">
              Модель: {modelGuide.modelName}
              {focusedInstalled ? ' · установлена' : focusedNeedsImport ? ' · в системной Ollama' : modelsLoading ? '' : ' · не скачана'}
            </p>

            {showFocusedProgress ? (
              <OllamaPullProgressBar progress={pullProgress} />
            ) : null}

            <div className="mt-2 flex flex-wrap gap-1.5">
              {!focusedInstalled ? (
                <button
                  type="button"
                  disabled={focusedBusy}
                  onClick={() => void handlePullFocused()}
                  className="inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded border border-[#2563eb] bg-[#1e3a5f] text-white hover:bg-[#2563eb] disabled:opacity-50"
                >
                  {focusedBusy ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Download className="w-3 h-3" />
                  )}
                  {focusedNeedsImport ? 'Импортировать' : 'Скачать'} {focusedProfile.shortName}
                </button>
              ) : (
                <button
                  type="button"
                  disabled={focusedBusy}
                  onClick={() => void handleDeleteFocused()}
                  className="inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded border border-[#7f1d1d] text-[#fca5a5] hover:text-white disabled:opacity-50"
                >
                  {focusedBusy ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Trash2 className="w-3 h-3" />
                  )}
                  Удалить {focusedProfile.shortName}
                </button>
              )}
              <button
                type="button"
                onClick={() => void copyCommand(modelGuide.pullCommand)}
                className="inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded border border-[#334155] text-[#cbd5e1] hover:text-white"
              >
                {copiedCommand === modelGuide.pullCommand ? (
                  <Check className="w-3 h-3 text-emerald-400" />
                ) : (
                  <Copy className="w-3 h-3" />
                )}
                Копировать команду
              </button>
              {onSelectModel ? (
                <button
                  type="button"
                  onClick={() => {
                    onSelectModel(focusedModelId);
                    onClose();
                  }}
                  className="text-[10px] px-2 py-1 rounded border border-[#2563eb] text-[#93c5fd] hover:text-white"
                >
                  Выбрать {focusedProfile.shortName}
                </button>
              ) : null}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
