export type OnlineApiType = 'openai' | 'gemini';

export interface OnlineProviderGuideStep {
  title: string;
  detail: string;
  url?: string;
  urlLabel?: string;
}

export interface OnlineProviderTemplate {
  id: string;
  label: string;
  apiType: OnlineApiType;
  defaultBaseUrl: string;
  defaultModel: string;
  /** Featured free base option shown first in UI. */
  isFreeBase?: boolean;
  badge?: string;
  keyPlaceholder?: string;
  modelHint?: string;
  guide?: {
    summary: string;
    limits?: string;
    steps: OnlineProviderGuideStep[];
    modelExamples?: string[];
  };
}

export const ONLINE_PROVIDER_TEMPLATES: OnlineProviderTemplate[] = [
  {
    id: 'openrouter-free',
    label: 'OpenRouter (бесплатно)',
    apiType: 'openai',
    defaultBaseUrl: 'https://openrouter.ai/api/v1',
    // openrouter/free auto-picks an available zero-cost model — specific :free
    // slugs rotate and disappear (e.g. llama-3.3-70b-instruct:free retired).
    defaultModel: 'openrouter/free',
    isFreeBase: true,
    badge: 'FREE',
    keyPlaceholder: 'sk-or-v1-...',
    modelHint: 'Рекомендуем openrouter/free или модели с суффиксом :free',
    guide: {
      summary:
        'OpenRouter даёт бесплатные токены без карты. Ключ хранится только на этом ПК.',
      limits:
        'Обычно ~20 запросов/мин и ~50/день на free-моделях. Список free-моделей часто меняется.',
      steps: [
        {
          title: '1. Создайте аккаунт',
          detail: 'Зайдите на OpenRouter и войдите через Google / GitHub / email. Карта не нужна.',
          url: 'https://openrouter.ai/',
          urlLabel: 'openrouter.ai',
        },
        {
          title: '2. Создайте API-ключ',
          detail: 'Profile → Keys → Create Key. Скопируйте ключ сразу (показывается один раз).',
          url: 'https://openrouter.ai/keys',
          urlLabel: 'Открыть Keys',
        },
        {
          title: '3. Выберите free-модель',
          detail:
            'По умолчанию openrouter/free сам выбирает доступную бесплатную модель. Или возьмите актуальную :free из каталога.',
          url: 'https://openrouter.ai/models?q=free',
          urlLabel: 'Каталог free',
        },
        {
          title: '4. Вставьте в CoreX',
          detail:
            'Вставьте ключ ниже, оставьте Base URL и модель openrouter/free, затем нажмите «Добавить».',
        },
      ],
      modelExamples: [
        'openrouter/free',
        'google/gemma-4-31b-it:free',
        'openai/gpt-oss-20b:free',
        'nvidia/nemotron-3-nano-30b-a3b:free',
      ],
    },
  },
  {
    id: 'openrouter',
    label: 'OpenRouter',
    apiType: 'openai',
    defaultBaseUrl: 'https://openrouter.ai/api/v1',
    defaultModel: 'openai/gpt-4o-mini',
    keyPlaceholder: 'sk-or-v1-...',
    guide: {
      summary: 'Тот же OpenRouter, но без ограничения только free-моделями.',
      steps: [
        {
          title: 'Ключи',
          detail: 'Создайте ключ на openrouter.ai/keys и вставьте сюда.',
          url: 'https://openrouter.ai/keys',
          urlLabel: 'Keys',
        },
        {
          title: 'Модели',
          detail: 'Для платных моделей может понадобиться пополнить кредиты.',
          url: 'https://openrouter.ai/models',
          urlLabel: 'Models',
        },
      ],
    },
  },
  {
    id: 'openai',
    label: 'OpenAI',
    apiType: 'openai',
    defaultBaseUrl: 'https://api.openai.com/v1',
    defaultModel: 'gpt-4o-mini',
    keyPlaceholder: 'sk-...',
  },
  {
    id: 'groq',
    label: 'Groq',
    apiType: 'openai',
    defaultBaseUrl: 'https://api.groq.com/openai/v1',
    defaultModel: 'llama-3.1-8b-instant',
    keyPlaceholder: 'gsk_...',
  },
  {
    id: 'together',
    label: 'Together',
    apiType: 'openai',
    defaultBaseUrl: 'https://api.together.xyz/v1',
    defaultModel: 'meta-llama/Llama-3.1-8B-Instruct-Turbo',
  },
  {
    id: 'gemini',
    label: 'Google Gemini',
    apiType: 'gemini',
    defaultBaseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    defaultModel: 'gemini-2.5-flash',
    keyPlaceholder: 'AIza...',
  },
];

export function getProviderTemplateById(templateId: string): OnlineProviderTemplate | undefined {
  return ONLINE_PROVIDER_TEMPLATES.find((template) => template.id === templateId);
}

export function getDefaultOnlineProviderTemplate(): OnlineProviderTemplate {
  return (
    ONLINE_PROVIDER_TEMPLATES.find((template) => template.isFreeBase) ||
    ONLINE_PROVIDER_TEMPLATES[0]
  );
}

export function getFreeBaseOnlineProviderTemplate(): OnlineProviderTemplate | undefined {
  return ONLINE_PROVIDER_TEMPLATES.find((template) => template.isFreeBase);
}
