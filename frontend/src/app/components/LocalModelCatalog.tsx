import { useEffect, useMemo, useState } from 'react';
import { Check, Download, Loader2, Trash2 } from 'lucide-react';
import {
  CODING_PROVIDER_BY_TIER,
  getModelShortLabel,
  recommendHardwareTier,
  tierLabel,
  type AiProviderPreset,
  type HardwareTier,
  type OllamaPullProgress,
} from '../utils/aiProvider';
import { OllamaPullProgressBar } from './OllamaPullProgressBar';

const TABS: { id: HardwareTier; hint: string }[] = [
  { id: 'low', hint: '4 ГБ VRAM' },
  { id: 'medium', hint: '8 ГБ VRAM' },
  { id: 'high', hint: '14B / запас RAM' },
];

interface LocalModelCatalogProps {
  providers: AiProviderPreset[];
  selectedId: string;
  recommendedId?: string;
  vramGb?: number;
  ramGb?: number;
  installedById: Record<string, boolean>;
  needsImportById: Record<string, boolean>;
  busyId: string;
  pullProgress: OllamaPullProgress | null;
  savingId: string | null;
  onSelect: (id: string) => void;
  onPull: (id: string) => void;
  onRemove: (id: string) => void;
}

export function LocalModelCatalog({
  providers,
  selectedId,
  recommendedId,
  vramGb,
  ramGb,
  installedById,
  needsImportById,
  busyId,
  pullProgress,
  savingId,
  onSelect,
  onPull,
  onRemove,
}: LocalModelCatalogProps) {
  const autoTier = recommendHardwareTier(vramGb, ramGb);
  const [tab, setTab] = useState<HardwareTier>(autoTier);
  const [tabTouched, setTabTouched] = useState(false);

  useEffect(() => {
    if (!tabTouched) setTab(autoTier);
  }, [autoTier, tabTouched]);

  const visible = useMemo(
    () => providers.filter((provider) => provider.tier === tab),
    [providers, tab],
  );

  const selected = providers.find((provider) => provider.id === selectedId);
  const codingId = CODING_PROVIDER_BY_TIER[tab];
  const highlightId = recommendedId && visible.some((row) => row.id === recommendedId)
    ? recommendedId
    : codingId;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-[var(--corex-text-muted)]">
        {typeof vramGb === 'number' ? (
          <span>VRAM {vramGb.toFixed(1)} ГБ</span>
        ) : (
          <span>VRAM не определена</span>
        )}
        {typeof ramGb === 'number' ? <span>· RAM {Math.round(ramGb)} ГБ</span> : null}
        <span>· вкладка «{tierLabel(autoTier)}» подходит этому ПК</span>
      </div>

      {selected ? (
        <p className="text-[11px] text-[var(--corex-text-dim)]">
          Сейчас выбрана {getModelShortLabel(selected)} · {selected.model_name}
        </p>
      ) : null}
      {installedById['ollama-lite'] && installedById['ollama-qwen'] ? (
        <p className="text-[11px] text-[var(--corex-spark)]">
          Автосмена на слабом ПК: простой чат — Phi-3 Mini, код — Qwen 3B
        </p>
      ) : null}

      <div className="corex-segmented">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => {
              setTabTouched(true);
              setTab(item.id);
            }}
            className={`corex-segmented-btn ${
              tab === item.id
                ? 'corex-segmented-btn--active bg-[rgba(0,210,255,0.15)] text-[var(--corex-spark)] border-[var(--corex-spark)]/30'
                : ''
            }`}
          >
            {tierLabel(item.id)}
            {item.id === autoTier ? (
              <span className="text-[9px] uppercase tracking-wide opacity-80">вам</span>
            ) : null}
          </button>
        ))}
      </div>
      <p className="text-[10px] text-[var(--corex-text-dim)]">{TABS.find((item) => item.id === tab)?.hint}</p>

      <div className="space-y-1.5">
        {visible.map((provider) => {
          const installed = Boolean(installedById[provider.id]);
          const needsImport = Boolean(needsImportById[provider.id]);
          const isSelected = provider.id === selectedId;
          const isBusy = busyId === provider.id || savingId === provider.id;
          const isRecommend = provider.id === highlightId;
          const sizeLabel =
            typeof provider.size_gb === 'number' ? `${provider.size_gb.toFixed(1)} ГБ` : '';

          return (
            <div
              key={provider.id}
              className={[
                'rounded-md border px-2.5 py-2',
                isSelected
                  ? 'border-[var(--corex-spark)] bg-[rgba(0,210,255,0.06)]'
                  : 'border-[#212733] bg-[#0f1720]',
              ].join(' ')}
            >
              <div className="flex items-center gap-2 min-w-0">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="text-[13px] font-medium text-white truncate">
                      {getModelShortLabel(provider)}
                    </span>
                    {isRecommend ? (
                      <span className="text-[9px] uppercase tracking-wide text-[#4fc1ff] shrink-0">
                        рекомендуем
                      </span>
                    ) : null}
                    {isSelected ? (
                      <span className="text-[9px] uppercase tracking-wide text-[#89d185] shrink-0">
                        выбрано
                      </span>
                    ) : null}
                    {installed ? (
                      <Check className="w-3 h-3 text-[#89d185] shrink-0" />
                    ) : null}
                  </div>
                  <p className="text-[10px] text-[var(--corex-text-dim)] truncate">
                    {provider.model_name}
                    {sizeLabel ? ` · ${sizeLabel}` : ''}
                    {provider.min_vram_gb ? ` · от ${provider.min_vram_gb} ГБ VRAM` : ''}
                  </p>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  {installed && !isSelected ? (
                    <button
                      type="button"
                      disabled={Boolean(savingId)}
                      onClick={() => onSelect(provider.id)}
                      className="px-2 py-1 rounded text-[11px] text-[var(--corex-spark)] border border-[var(--corex-spark)]/30 hover:bg-[rgba(0,210,255,0.08)] disabled:opacity-40"
                    >
                      Выбрать
                    </button>
                  ) : null}
                  {!installed || needsImport ? (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => onPull(provider.id)}
                      className="px-2 py-1 rounded text-[11px] text-white bg-[#1d4ed8] hover:bg-[#2563eb] disabled:opacity-40 inline-flex items-center gap-1"
                    >
                      {isBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                      {needsImport ? 'Импорт' : 'Скачать'}
                    </button>
                  ) : null}
                  {installed && isSelected ? (
                    <span className="px-2 py-1 rounded text-[11px] text-[#89d185] border border-[#89d185]/30">
                      Активна
                    </span>
                  ) : null}
                  {installed ? (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => onRemove(provider.id)}
                      className="p-1 rounded text-[var(--corex-text-dim)] hover:text-[#f48771]"
                      title="Удалить с диска"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  ) : null}
                </div>
              </div>
              {isBusy && pullProgress ? <OllamaPullProgressBar progress={pullProgress} compact /> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
