import { describe, expect, it } from 'vitest';
import {
  buildModelInstallGuide,
  buildModelProfile,
  buildOllamaInstallGuide,
  compareOfflineModels,
  resolveInitialFocusedModelId,
  sortOfflineModelsForDisplay,
} from '../utils/offlineModelGuide';
import type { OfflineModelInput } from '../utils/offlineModelGuide';
import { renderToStaticMarkup } from 'react-dom/server';
import { OfflineModelGuide } from './OfflineModelGuide';
import { OfflineModelHelpModal } from './OfflineModelHelpModal';
import type { AiProviderPreset } from '../utils/aiProvider';

const MODELS: OfflineModelInput[] = [
  {
    id: 'ollama-qwen',
    name: 'Ollama — Qwen Coder',
    description: 'Баланс',
    model_name: 'qwen2.5-coder:7b',
    min_ram_gb: 8,
    tier: 'medium',
    pull_command: 'ollama pull qwen2.5-coder:7b',
    is_default: true,
  },
  {
    id: 'ollama-claude',
    name: 'Ollama — Llama 3.1',
    description: 'Сложные задачи',
    model_name: 'llama3.1:8b',
    min_ram_gb: 10,
    tier: 'high',
    pull_command: 'ollama pull llama3.1:8b',
    is_default: false,
  },
  {
    id: 'ollama-lite',
    name: 'Ollama Lite — Phi-3',
    description: 'Lite',
    model_name: 'phi3:mini',
    min_ram_gb: 4,
    tier: 'low',
    pull_command: 'ollama pull phi3:mini',
    is_default: false,
  },
];

const PROVIDERS = MODELS as AiProviderPreset[];

describe('sortOfflineModelsForDisplay', () => {
  it('puts recommended model first', () => {
    const sorted = sortOfflineModelsForDisplay(MODELS, 'ollama-lite');
    expect(sorted[0]?.id).toBe('ollama-lite');
    expect(sorted).toHaveLength(3);
  });
});

describe('buildOllamaInstallGuide', () => {
  it('contains ollama download steps only', () => {
    const guide = buildOllamaInstallGuide();
    expect(guide.steps.some((s) => s.includes('ollama.com'))).toBe(true);
    expect(guide.steps.some((s) => s.includes('ollama pull'))).toBe(false);
  });
});

describe('buildModelInstallGuide', () => {
  it('contains direct download and corex selection steps', () => {
    const guide = buildModelInstallGuide(MODELS[0]);
    expect(guide.pullCommand).toContain('qwen2.5-coder:7b');
    expect(guide.steps.some((s) => /hugging face|скачать/i.test(s))).toBe(true);
    expect(guide.steps.some((s) => /локально|corex/i.test(s))).toBe(true);
  });
});

describe('OfflineModelGuide', () => {
  it('renders only compact trigger without inline expanded content', () => {
    const html = renderToStaticMarkup(
      <OfflineModelGuide providers={PROVIDERS} selectedId="ollama-qwen" availableRamGb={8} />,
    );
    expect(html).toContain('Помощь: какую модель выбрать');
    expect(html).not.toContain('Скачать Ollama');
    expect(html).not.toContain('max-h-');
    expect(compareOfflineModels(MODELS).every((row) => !html.includes(row.bestFor))).toBe(true);
  });
});

describe('buildModelProfile', () => {
  it('returns strengths and weaknesses for each model', () => {
    const profile = buildModelProfile(MODELS[0]);
    expect(profile.strengths.length).toBeGreaterThan(0);
    expect(profile.weaknesses.length).toBeGreaterThan(0);
    expect(profile.whenToUse).toBeTruthy();
  });
});

describe('resolveInitialFocusedModelId', () => {
  it('prefers selected model over recommendation', () => {
    expect(resolveInitialFocusedModelId(MODELS, 'ollama-claude', 'ollama-lite')).toBe(
      'ollama-claude',
    );
  });
});

describe('OfflineModelHelpModal', () => {
  it('shows all model cards when open', () => {
    const html = renderToStaticMarkup(
      <OfflineModelHelpModal
        open
        onClose={() => {}}
        providers={PROVIDERS}
        selectedId="ollama-qwen"
        availableRamGb={8}
      />,
    );
    expect(html).toContain('Qwen');
    expect(html).toContain('Llama');
    expect(html).toContain('Phi-3');
    expect(html).toContain('Подробнее');
    expect(html).toContain('Скачать Ollama');
    expect(html).toContain('выбрана для просмотра');
    expect(html).toContain('max-h-[85vh]');
  });

  it('returns null when closed', () => {
    const html = renderToStaticMarkup(
      <OfflineModelHelpModal
        open={false}
        onClose={() => {}}
        providers={PROVIDERS}
      />,
    );
    expect(html).toBe('');
  });
});
