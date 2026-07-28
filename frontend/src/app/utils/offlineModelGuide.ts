import type { AiProviderPreset } from './aiProvider';
import { getModelShortLabel, tierLabel } from './aiProvider';

export type OfflineModelInput = Pick<
  AiProviderPreset,
  'id' | 'name' | 'description' | 'model_name' | 'min_ram_gb' | 'tier' | 'pull_command' | 'is_default'
>;

export interface OfflineRecommendResult {
  id: string;
  reason: string;
}

export interface OfflineModelComparisonRow {
  id: string;
  shortName: string;
  fullName: string;
  bestFor: string;
  ramLabel: string;
  tradeoff: string;
  pullCommand: string;
  recommended?: boolean;
}

export interface OfflineModelProfile {
  id: string;
  shortName: string;
  fullName: string;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  whenToUse: string;
  modelName: string;
  pullCommand: string;
  ramLabel: string;
}

export interface OfflineInstallGuide {
  title: string;
  steps: string[];
  downloadUrl: string;
}

export interface OfflineModelInstallGuide {
  title: string;
  steps: string[];
  pullCommand: string;
  modelName: string;
}

export interface OfflineHardwareHint {
  availableRamGb?: number;
}

const BEST_FOR: Record<string, string> = {
  'ollama-qwen': 'Код, правки файлов, повседневная разработка',
  'ollama-claude': 'Сложные задачи, ревью, длинные рассуждения',
  'ollama-lite': 'Слабые ПК, быстрый ответ, простые правки',
};

const MODEL_PROFILES: Record<string, Omit<OfflineModelProfile, 'id' | 'shortName' | 'fullName' | 'ramLabel' | 'pullCommand' | 'modelName'>> = {
  'ollama-qwen': {
    summary:
      'Специализированная модель для программирования. Лучший выбор для ежедневной работы с кодом в CoreX.',
    strengths: [
      'Хорошо пишет и правит Python, JS, TS, HTML',
      'Понимает структуру проекта и файловые правки',
      'Оптимальный баланс качества и требований к RAM',
    ],
    weaknesses: [
      'На слабом ПК (<8 ГБ) может тормозить',
      'Сложные архитектурные рассуждения слабее, чем у Llama',
    ],
    whenToUse: 'Когда нужно создавать проекты, править файлы и писать код каждый день.',
  },
  'ollama-claude': {
    summary:
      'Универсальная модель с сильным рассуждением. Подходит для сложных задач, ревью и длинных ответов.',
    strengths: [
      'Лучше справляется со сложными многошаговыми задачами',
      'Сильнее в ревью, объяснениях и планировании',
      'Хороша для команд (pipeline) с несколькими этапами',
    ],
    weaknesses: [
      'Требует больше RAM (от 10 ГБ)',
      'Медленнее на слабом железе',
    ],
    whenToUse: 'Когда много RAM и нужна максимальная «умность» ответов.',
  },
  'ollama-lite': {
    summary:
      'Лёгкая модель для слабых ПК и ноутбуков. Быстрый отклик, но проще по качеству кода.',
    strengths: [
      'Работает на 4–8 ГБ RAM',
      'Быстрые ответы, меньше нагрузка на ПК',
      'Подходит для простых правок и коротких задач',
    ],
    weaknesses: [
      'Слабее на больших проектах и сложном коде',
      'Может ошибаться в многофайловых задачах',
    ],
    whenToUse: 'Когда мало RAM или нужен быстрый лёгкий ассистент без онлайн API.',
  },
};

export function buildModelProfile(model: OfflineModelInput): OfflineModelProfile {
  const extra = MODEL_PROFILES[model.id];
  const shortName = getModelShortLabel(model as AiProviderPreset);
  return {
    id: model.id,
    shortName,
    fullName: model.name,
    modelName: model.model_name,
    pullCommand: model.pull_command || `ollama pull ${model.model_name}`,
    ramLabel: `${tierLabel(model.tier)} · от ${model.min_ram_gb} ГБ`,
    summary: extra?.summary ?? model.description,
    strengths: extra?.strengths ?? [],
    weaknesses: extra?.weaknesses ?? [],
    whenToUse: extra?.whenToUse ?? model.description,
  };
}

export function resolveInitialFocusedModelId(
  providers: OfflineModelInput[],
  selectedId?: string,
  recommendedId?: string,
): string {
  if (selectedId && providers.some((p) => p.id === selectedId)) return selectedId;
  if (recommendedId && providers.some((p) => p.id === recommendedId)) return recommendedId;
  return providers[0]?.id ?? '';
}

const TRADEOFFS: Record<string, string> = {
  'ollama-qwen': 'Лучший баланс качества и RAM для CoreX',
  'ollama-claude': 'Точнее на сложных задачах, но тяжелее по памяти',
  'ollama-lite': 'Легче и быстрее, но слабее на большом коде',
};

function pickDefault(models: OfflineModelInput[]): OfflineModelInput {
  return models.find((m) => m.is_default) ?? models[0];
}

function fitByRam(models: OfflineModelInput[], ram: number): OfflineModelInput | null {
  const sorted = [...models].sort((a, b) => b.min_ram_gb - a.min_ram_gb);
  for (const model of sorted) {
    if (ram >= model.min_ram_gb) {
      return model;
    }
  }
  return models.find((m) => m.tier === 'low') ?? models[models.length - 1] ?? null;
}

export function recommendOfflineModel(
  models: OfflineModelInput[],
  hardware: OfflineHardwareHint = {},
): OfflineRecommendResult {
  if (!models.length) {
    return { id: '', reason: 'Нет доступных локальных моделей.' };
  }

  const ram = hardware.availableRamGb;
  if (typeof ram === 'number' && Number.isFinite(ram) && ram > 0) {
    const fitted = fitByRam(models, ram);
    if (fitted) {
      if (fitted.tier === 'low') {
        return {
          id: fitted.id,
          reason: `Мало RAM (~${ram} ГБ) — лучше лёгкая модель ${getModelShortLabel(fitted as AiProviderPreset)}.`,
        };
      }
      if (fitted.tier === 'high') {
        return {
          id: fitted.id,
          reason: `Достаточно RAM (~${ram} ГБ) — можно взять более сильную модель ${getModelShortLabel(fitted as AiProviderPreset)}.`,
        };
      }
      return {
        id: fitted.id,
        reason: `Для ~${ram} ГБ RAM рекомендуем ${getModelShortLabel(fitted as AiProviderPreset)} — баланс качества и скорости.`,
      };
    }
  }

  const fallback = pickDefault(models);
  return {
    id: fallback.id,
    reason: `Без данных о RAM рекомендуем ${getModelShortLabel(fallback as AiProviderPreset)} по умолчанию.`,
  };
}

export function compareOfflineModels(
  models: OfflineModelInput[],
  recommendedId?: string,
): OfflineModelComparisonRow[] {
  return sortOfflineModelsForDisplay(models, recommendedId).map((model) => ({
    id: model.id,
    shortName: getModelShortLabel(model as AiProviderPreset),
    fullName: model.name,
    bestFor: BEST_FOR[model.id] ?? model.description,
    ramLabel: `${tierLabel(model.tier)} · от ${model.min_ram_gb} ГБ`,
    tradeoff: TRADEOFFS[model.id] ?? model.description,
    pullCommand: model.pull_command,
    recommended: recommendedId ? model.id === recommendedId : model.is_default,
  }));
}

export function sortOfflineModelsForDisplay(
  models: OfflineModelInput[],
  recommendedId?: string,
): OfflineModelInput[] {
  const copy = [...models];
  if (!recommendedId) return copy;
  return copy.sort((a, b) => {
    if (a.id === recommendedId) return -1;
    if (b.id === recommendedId) return 1;
    return a.min_ram_gb - b.min_ram_gb;
  });
}

export function buildOllamaInstallGuide(): OfflineInstallGuide {
  return {
    title: 'Установка Ollama',
    downloadUrl: 'https://ollama.com/download',
    steps: [
      'Скачайте Ollama с ollama.com/download (Windows / macOS / Linux).',
      'Установите и перезапустите CoreX, чтобы терминал увидел команду `ollama`.',
      'Проверьте в терминале: `ollama --version` — должна показаться версия.',
      'Запустите Ollama (`ollama serve` или через приложение Ollama в трее).',
    ],
  };
}

export function buildModelInstallGuide(model: OfflineModelInput): OfflineModelInstallGuide {
  const pull = model.pull_command || `curl -L -o models/${model.id}/model.gguf "<url>"`;
  const label = getModelShortLabel(model as AiProviderPreset);
  return {
    title: `Установка модели ${label}`,
    modelName: model.model_name,
    pullCommand: pull,
    steps: [
      'Нажмите «Скачать» — CoreX загрузит GGUF с Hugging Face в папку models/ (без registry.ollama.ai).',
      'Дождитесь окончания загрузки и регистрации в Ollama (первый раз может занять несколько минут).',
      'Проверьте: `ollama list` — модель должна появиться в списке.',
      `В CoreX: режим «Локально» → выберите «${label}» в списке моделей.`,
      'Отправьте тестовое сообщение в чат — если ответ пришёл, всё готово.',
    ],
  };
}

/** @deprecated use buildOllamaInstallGuide + buildModelInstallGuide */
export function buildOfflineInstallGuide(model: OfflineModelInput): OfflineInstallGuide {
  const ollama = buildOllamaInstallGuide();
  const modelGuide = buildModelInstallGuide(model);
  return {
    title: `${ollama.title} и ${modelGuide.title.toLowerCase()}`,
    downloadUrl: ollama.downloadUrl,
    steps: [...ollama.steps, ...modelGuide.steps],
  };
}
