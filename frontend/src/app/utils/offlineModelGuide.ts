import type { AiProviderPreset, HardwareTier } from './aiProvider';
import {
  CODING_PROVIDER_BY_TIER,
  getModelShortLabel,
  recommendHardwareTier,
  recommendedProviderId,
  tierLabel,
} from './aiProvider';

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
  availableVramGb?: number;
}

const BEST_FOR: Record<string, string> = {
  'ollama-qwen': 'Код на 4 ГБ VRAM, повседневные правки',
  'ollama-qwen-7b': 'Код на 8 ГБ VRAM, основной домашний вариант',
  'ollama-qwen-14b': 'Максимум качества кода, нагрузка выше',
  'ollama-claude': 'Чат, ревью, рассуждения',
  'ollama-lite': 'Слабые ПК, быстрый ответ, простые правки',
};

const MODEL_PROFILES: Record<string, Omit<OfflineModelProfile, 'id' | 'shortName' | 'fullName' | 'ramLabel' | 'pullCommand' | 'modelName'>> = {
  'ollama-qwen': {
    summary:
      'Специализированная 3B-модель для кода на 4 ГБ VRAM. Контекст строго 4096 токенов.',
    strengths: [
      'Влезает в NVIDIA T600 4 ГБ (Q4)',
      'Хорошо пишет и правит Python, JS, TS, HTML',
      'Быстрее 7B на слабом GPU',
    ],
    weaknesses: [
      'Короткое окно контекста (4096 токенов)',
      'Сложные архитектурные рассуждения слабее, чем у Llama 8B',
    ],
    whenToUse: 'Когда нужно писать код локально на видеокарте 4 ГБ без облака.',
  },
  'ollama-qwen-7b': {
    summary: '7B-кодер для видеокарт 8 ГБ. Сильнее 3B, ещё целиком на GPU.',
    strengths: [
      'Влезает в RTX 3050 8 ГБ при контексте 4096',
      'Заметно умнее 3B на многофайловых задачах',
      'Главная модель для домашнего ПК',
    ],
    weaknesses: [
      'Не влезет в T600 4 ГБ без выгрузки в RAM',
      'Скачивается ~4.7 ГБ',
    ],
    whenToUse: 'Домашний ПК с 8 ГБ VRAM и 16+ ГБ RAM.',
  },
  'ollama-qwen-14b': {
    summary: '14B-кодер: максимум локального качества. На 8 ГБ часть слоёв уйдёт в RAM.',
    strengths: [
      'Лучшее качество кода в каталоге CoreX',
      '32 ГБ RAM выдерживают выгрузку слоёв',
    ],
    weaknesses: [
      'Медленнее 7B',
      'На 4 ГБ VRAM практически не работает',
    ],
    whenToUse: 'Когда нужен предел качества и есть 8+ ГБ VRAM и 32 ГБ RAM.',
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
  'ollama-qwen': 'Целиком в 4 ГБ VRAM, слабее 7B',
  'ollama-qwen-7b': 'Лучший баланс на 8 ГБ VRAM',
  'ollama-qwen-14b': 'Умнее, но медленнее; часть в RAM',
  'ollama-claude': 'Сильнее в чате, слабее в коде, чем Qwen 7B',
  'ollama-lite': 'Легче и быстрее, но слабее на большом коде',
};

function pickDefault(models: OfflineModelInput[]): OfflineModelInput {
  return models.find((m) => m.is_default) ?? models[0];
}

export function recommendOfflineModel(
  models: OfflineModelInput[],
  hardware: OfflineHardwareHint = {},
): OfflineRecommendResult {
  if (!models.length) {
    return { id: '', reason: 'Нет доступных локальных моделей.' };
  }

  const vram = hardware.availableVramGb;
  const ram = hardware.availableRamGb;
  const hasVram = typeof vram === 'number' && Number.isFinite(vram) && vram > 0;
  const hasRam = typeof ram === 'number' && Number.isFinite(ram) && ram > 0;
  const preferredId =
    hasVram || hasRam ? recommendedProviderId(hasVram ? vram : undefined, hasRam ? ram : undefined) : '';
  const preferred = preferredId ? models.find((model) => model.id === preferredId) : undefined;
  if (preferred) {
    const label = getModelShortLabel(preferred as AiProviderPreset);
    if (hasVram) {
      return {
        id: preferred.id,
        reason: `По VRAM (~${vram} ГБ) рекомендуем ${label}.`,
      };
    }
    return {
      id: preferred.id,
      reason: `По RAM (~${ram} ГБ, без VRAM) рекомендуем ${label}.`,
    };
  }

  const tier: HardwareTier = recommendHardwareTier(hasVram ? vram : undefined, hasRam ? ram : undefined);
  const onTier = models.filter((model) => model.tier === tier);
  const codingId = CODING_PROVIDER_BY_TIER[tier];
  const coding = onTier.find((model) => model.id === codingId) ?? onTier[0];
  if (coding) {
    return {
      id: coding.id,
      reason: `Для вкладки «${tierLabel(tier)}» рекомендуем ${getModelShortLabel(coding as AiProviderPreset)}.`,
    };
  }

  const fallback = pickDefault(models);
  return {
    id: fallback.id,
    reason: `Без данных о железе рекомендуем ${getModelShortLabel(fallback as AiProviderPreset)} по умолчанию.`,
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
      `В CoreX: Настройки → Модели → выберите «${label}».`,
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
