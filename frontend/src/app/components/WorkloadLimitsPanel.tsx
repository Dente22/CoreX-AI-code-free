import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  fetchWorkloadLimits,
  saveWorkloadLimits,
  type TeamStepTurnLimit,
  type WorkloadLimitsSettings,
  type WorkloadLimitValues,
} from '../utils/workloadLimits';

interface WorkloadLimitsSettingsProps {
  onNotification?: (message: string) => void;
}

function interpolatePreview(settings: WorkloadLimitsSettings, slider: number): WorkloadLimitValues {
  const pct = Math.max(0, Math.min(100, slider)) / 100;
  const keys = Object.keys(settings.min_limits) as Array<keyof WorkloadLimitValues>;
  const preview = {} as WorkloadLimitValues;
  for (const key of keys) {
    const min = settings.min_limits[key];
    const max = settings.max_limits[key];
    preview[key] = Math.round(min + (max - min) * pct);
  }
  return preview;
}

export function WorkloadLimitsPanel({ onNotification }: WorkloadLimitsSettingsProps) {
  const [settings, setSettings] = useState<WorkloadLimitsSettings | null>(null);
  const [slider, setSlider] = useState(58);
  const [turnsEnabled, setTurnsEnabled] = useState(false);
  const [turnsMode, setTurnsMode] = useState<'team' | 'per_agent'>('team');
  const [teamTotalTurns, setTeamTotalTurns] = useState(40);
  const [teamStepTurns, setTeamStepTurns] = useState(16);
  const [perAgentTurns, setPerAgentTurns] = useState<Record<string, number>>({});
  const [teamSteps, setTeamSteps] = useState<TeamStepTurnLimit[]>([]);
  const [unlimitedLimits, setUnlimitedLimits] = useState(false);
  const [stepByStep, setStepByStep] = useState(true);
  const [designFolderPath, setDesignFolderPath] = useState('design-system');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const applySettings = useCallback((data: WorkloadLimitsSettings) => {
    setSettings(data);
    setSlider(data.slider);
    setTurnsEnabled(Boolean(data.turns_limit_enabled));
    setTurnsMode(data.turns_limit_mode === 'per_agent' ? 'per_agent' : 'team');
    setTeamTotalTurns(data.team_max_total_turns ?? data.limits.max_total_turns);
    setTeamStepTurns(data.team_max_turns_per_step ?? data.limits.max_turns_per_step);
    setPerAgentTurns(data.per_agent_turns ?? {});
    setTeamSteps(data.team_steps ?? []);
    setUnlimitedLimits(Boolean(data.unlimited_limits));
    setStepByStep(data.step_by_step_enabled !== false);
    setDesignFolderPath(data.design_folder_path ?? 'design-system');
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchWorkloadLimits();
      if (!data) {
        setError('Не удалось загрузить лимиты нагрузки');
        return;
      }
      applySettings(data);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Ошибка загрузки лимитов');
    } finally {
      setLoading(false);
    }
  }, [applySettings]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      const data = await saveWorkloadLimits({
        slider,
        turns_limit_enabled: turnsEnabled,
        turns_limit_mode: turnsMode,
        team_max_total_turns: teamTotalTurns,
        team_max_turns_per_step: teamStepTurns,
        per_agent_turns: perAgentTurns,
        unlimited_limits: unlimitedLimits,
        step_by_step_enabled: stepByStep,
        design_folder_path: designFolderPath.trim(),
      });
      if (!data) {
        setError('Не удалось сохранить лимиты');
        return;
      }
      applySettings(data);
      const turnsSummary = data.unlimited_limits
        ? 'без лимитов (эксперимент)'
        : turnsEnabled
          ? turnsMode === 'per_agent'
            ? `ручные ходы по агентам`
            : `ходы команды ${teamTotalTurns}, на этап ${teamStepTurns}`
          : `ходы ${data.limits.max_total_turns}, на этап ${data.limits.max_turns_per_step}`;
      onNotification?.(`Лимиты обновлены: ${turnsSummary}`);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const preview = useMemo(
    () => (settings ? interpolatePreview(settings, slider) : null),
    [settings, slider],
  );

  const effectivePreview = useMemo(() => {
    if (!preview) return null;
    if (unlimitedLimits) {
      return {
        ...preview,
        max_total_turns: 9999,
        max_turns_per_step: 9999,
        max_file_writes: 9999,
      };
    }
    if (!turnsEnabled) return preview;
    return {
      ...preview,
      max_total_turns: teamTotalTurns,
      max_turns_per_step: turnsMode === 'team' ? teamStepTurns : preview.max_turns_per_step,
    };
  }, [preview, turnsEnabled, turnsMode, teamTotalTurns, teamStepTurns, unlimitedLimits]);

  if (loading) {
    return <p className="text-sm text-[#9d9d9d]">Загрузка лимитов нагрузки…</p>;
  }

  if (!settings || !effectivePreview) {
    return error ? <p className="text-sm text-[#f48771]">{error}</p> : null;
  }

  return (
    <section className="rounded-lg border border-[#2a2a2a] bg-[#1a1a1a] p-4">
      <div className="flex items-center justify-between gap-3 mb-2">
        <h4 className="text-sm font-medium text-white">Лимиты нагрузки (локальный AI)</h4>
        <span className="text-[11px] text-[#9d9d9d] uppercase tracking-wide">{settings.tier}</span>
      </div>
      <p className="text-xs text-[#9d9d9d] mb-4 leading-relaxed">
        Ползунок задаёт базовые лимиты. «Без лимитов» полностью снимает потолок ходов/записей.
        «Лимит ходов» — ручная настройка команды «Дизайн и разработка (локально)».
      </p>

      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={slider}
        onChange={(event) => setSlider(Number(event.target.value))}
        className="w-full accent-[#2563eb]"
        disabled={turnsEnabled || unlimitedLimits}
      />

      <div className="flex items-center justify-between text-[11px] text-[#9d9d9d] mt-1 mb-3">
        <span>Минимум (слабый ПК)</span>
        <span className="text-[#e5e9f0] font-semibold tabular-nums">{slider}%</span>
        <span>Максимум (топовое железо)</span>
      </div>

      <div className="grid grid-cols-3 gap-2 text-[11px] mb-4">
        <div className="rounded border border-[#2a2a2a] bg-[#111] px-2 py-1.5">
          <p className="text-[#9d9d9d]">Ходы</p>
          <p className="text-[#e5e9f0] font-semibold tabular-nums">
            {unlimitedLimits ? '∞' : effectivePreview.max_total_turns}
          </p>
        </div>
        <div className="rounded border border-[#2a2a2a] bg-[#111] px-2 py-1.5">
          <p className="text-[#9d9d9d]">На этап</p>
          <p className="text-[#e5e9f0] font-semibold tabular-nums">
            {unlimitedLimits ? '∞' : effectivePreview.max_turns_per_step}
          </p>
        </div>
        <div className="rounded border border-[#2a2a2a] bg-[#111] px-2 py-1.5">
          <p className="text-[#9d9d9d]">Записи</p>
          <p className="text-[#e5e9f0] font-semibold tabular-nums">
            {unlimitedLimits ? '∞' : effectivePreview.max_file_writes}
          </p>
        </div>
      </div>

      {unlimitedLimits ? (
        <p className="text-[11px] text-[#86efac] mb-3">
          Режим без лимитов активен — ходы и записи не ограничиваются.
        </p>
      ) : null}

      <div className="rounded border border-[#2a2a2a] bg-[#111] p-3 mb-4 space-y-3">
        <label className="flex items-center gap-2 text-xs text-[#e5e9f0] cursor-pointer">
          <input
            type="checkbox"
            checked={unlimitedLimits}
            onChange={(event) => setUnlimitedLimits(event.target.checked)}
            className="accent-[#2563eb]"
          />
          Без лимитов (эксперимент — ходы и записи не ограничиваются)
        </label>

        <label className="flex items-center gap-2 text-xs text-[#e5e9f0] cursor-pointer">
          <input
            type="checkbox"
            checked={stepByStep}
            onChange={(event) => setStepByStep(event.target.checked)}
            className="accent-[#2563eb]"
          />
          Поэтапный режим (план → шаг за шагом, offline и online)
        </label>

        <label className="block text-[11px]">
          <span className="text-[#9d9d9d]">Папка с дизайном</span>
          <input
            type="text"
            value={designFolderPath}
            onChange={(event) => setDesignFolderPath(event.target.value)}
            placeholder="design-system или C:/path/to/design"
            className="mt-1 w-full rounded border border-[#3a3a3a] bg-[#0f0f0f] px-2 py-1 text-[#e5e9f0] text-xs"
          />
          <span className="text-[10px] text-[#7a7a7a] mt-1 block">
            Для одного разработчика или команды: относительный путь в проекте или абсолютный.
          </span>
        </label>

        <label className="flex items-center gap-2 text-xs text-[#e5e9f0] cursor-pointer">
          <input
            type="checkbox"
            checked={turnsEnabled}
            onChange={(event) => setTurnsEnabled(event.target.checked)}
            className="accent-[#2563eb]"
          />
          Лимит ходов (ручная настройка команды)
        </label>

        {turnsEnabled ? (
          <>
            <div className="flex flex-wrap gap-2 text-[11px]">
              <button
                type="button"
                onClick={() => setTurnsMode('team')}
                className={`px-2 py-1 rounded border ${
                  turnsMode === 'team'
                    ? 'border-[#2563eb] bg-[#1e3a5f] text-white'
                    : 'border-[#3a3a3a] text-[#d4d4d4]'
                }`}
              >
                На всю команду
              </button>
              <button
                type="button"
                onClick={() => setTurnsMode('per_agent')}
                className={`px-2 py-1 rounded border ${
                  turnsMode === 'per_agent'
                    ? 'border-[#2563eb] bg-[#1e3a5f] text-white'
                    : 'border-[#3a3a3a] text-[#d4d4d4]'
                }`}
              >
                На каждого агента
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-[11px]">
              <label className="block">
                <span className="text-[#9d9d9d]">Ходы на всю команду</span>
                <input
                  type="number"
                  min={8}
                  max={96}
                  value={teamTotalTurns}
                  onChange={(event) => setTeamTotalTurns(Number(event.target.value) || 0)}
                  className="mt-1 w-full rounded border border-[#3a3a3a] bg-[#0f0f0f] px-2 py-1 text-[#e5e9f0]"
                />
              </label>
              {turnsMode === 'team' ? (
                <label className="block">
                  <span className="text-[#9d9d9d]">Ходы на этап (все агенты)</span>
                  <input
                    type="number"
                    min={4}
                    max={32}
                    value={teamStepTurns}
                    onChange={(event) => setTeamStepTurns(Number(event.target.value) || 0)}
                    className="mt-1 w-full rounded border border-[#3a3a3a] bg-[#0f0f0f] px-2 py-1 text-[#e5e9f0]"
                  />
                </label>
              ) : null}
            </div>

            {turnsMode === 'per_agent' && teamSteps.length > 0 ? (
              <div className="space-y-2">
                <p className="text-[10px] text-[#9d9d9d]">Команда: {settings.team_pipeline_id ?? 'design-delivery-local'}</p>
                {teamSteps.map((step) => (
                  <label key={step.agent_id} className="flex items-center justify-between gap-3 text-[11px]">
                    <span className="text-[#d4d4d4] truncate">{step.role}</span>
                    <input
                      type="number"
                      min={4}
                      max={32}
                      value={perAgentTurns[step.agent_id] ?? step.default_max_turns}
                      onChange={(event) =>
                        setPerAgentTurns((current) => ({
                          ...current,
                          [step.agent_id]: Number(event.target.value) || step.default_max_turns,
                        }))
                      }
                      className="w-20 rounded border border-[#3a3a3a] bg-[#0f0f0f] px-2 py-1 text-[#e5e9f0] tabular-nums"
                    />
                  </label>
                ))}
              </div>
            ) : null}
          </>
        ) : null}
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setSlider(settings.default_slider)}
          className="px-3 py-1.5 text-xs rounded border border-[#3a3a3a] text-[#d4d4d4] hover:bg-[#252525]"
        >
          Рекомендуемое
        </button>
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={saving}
          className="px-3 py-1.5 text-xs rounded bg-[#2563eb] text-white hover:bg-[#1d4ed8] disabled:opacity-60"
        >
          {saving ? 'Сохранение…' : 'Сохранить'}
        </button>
      </div>

      {error ? <p className="text-xs text-[#f48771] mt-3">{error}</p> : null}
    </section>
  );
}
