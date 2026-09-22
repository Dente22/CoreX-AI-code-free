import { describe, expect, it } from 'vitest';
import {
  buildOfflineInstallGuide,
  buildModelInstallGuide,
  buildModelProfile,
  buildOllamaInstallGuide,
  compareOfflineModels,
  recommendOfflineModel,
  resolveInitialFocusedModelId,
  sortOfflineModelsForDisplay,
  type OfflineModelInput,
} from './offlineModelGuide';

const MODELS: OfflineModelInput[] = [
  {
    id: 'ollama-qwen',
    name: 'Ollama — Qwen Coder',
    description: 'Баланс качества кода',
    model_name: 'qwen2.5-coder:3b',
    min_ram_gb: 4,
    tier: 'low',
    pull_command: 'ollama pull qwen2.5-coder:3b',
    is_default: true,
  },
  {
    id: 'ollama-qwen-7b',
    name: 'Ollama — Qwen Coder 7B',
    description: 'Домашний код',
    model_name: 'qwen2.5-coder:7b',
    min_ram_gb: 8,
    tier: 'medium',
    pull_command: 'ollama pull qwen2.5-coder:7b',
    is_default: false,
  },
  {
    id: 'ollama-claude',
    name: 'Ollama — Llama 3.1',
    description: 'Сложные задачи',
    model_name: 'llama3.1:8b',
    min_ram_gb: 10,
    tier: 'medium',
    pull_command: 'ollama pull llama3.1:8b',
    is_default: false,
  },
  {
    id: 'ollama-lite',
    name: 'Ollama Lite — Phi-3',
    description: 'Слабые ПК',
    model_name: 'phi3:mini',
    min_ram_gb: 4,
    tier: 'low',
    pull_command: 'ollama pull phi3:mini',
    is_default: false,
  },
];

describe('recommendOfflineModel', () => {
  it('recommends qwen 3b for 4GB VRAM', () => {
    const result = recommendOfflineModel(MODELS, { availableVramGb: 4, availableRamGb: 16 });
    expect(result.id).toBe('ollama-qwen');
    expect(result.reason.toLowerCase()).toMatch(/vram|qwen/);
  });

  it('recommends qwen 3b for 4GB RAM without VRAM', () => {
    const result = recommendOfflineModel(MODELS, { availableRamGb: 4 });
    expect(result.id).toBe('ollama-qwen');
  });

  it('keeps 3b on 8GB RAM without VRAM', () => {
    const result = recommendOfflineModel(MODELS, { availableRamGb: 8 });
    expect(result.id).toBe('ollama-qwen');
  });

  it('recommends 7b for 8GB VRAM', () => {
    const result = recommendOfflineModel(MODELS, { availableVramGb: 8, availableRamGb: 32 });
    expect(result.id).toBe('ollama-qwen-7b');
  });

  it('recommends 7b for 32GB RAM without VRAM', () => {
    const result = recommendOfflineModel(MODELS, { availableRamGb: 32 });
    expect(result.id).toBe('ollama-qwen-7b');
  });

  it('falls back to default when no RAM info', () => {
    const result = recommendOfflineModel(MODELS, {});
    expect(result.id).toBe('ollama-qwen');
  });
});

describe('compareOfflineModels', () => {
  it('returns comparison rows with differences', () => {
    const rows = compareOfflineModels(MODELS);
    expect(rows).toHaveLength(4);
    expect(rows.map((r) => r.id).sort()).toEqual(
      ['ollama-claude', 'ollama-lite', 'ollama-qwen', 'ollama-qwen-7b'].sort(),
    );
  });
});

describe('buildOfflineInstallGuide', () => {
  it('builds ordered install steps with selected pull command', () => {
    const guide = buildOfflineInstallGuide(MODELS[0]);
    expect(guide.title).toMatch(/установ/i);
    expect(guide.steps.length).toBeGreaterThanOrEqual(3);
    expect(guide.steps.some((s) => s.includes('ollama.com'))).toBe(true);
    expect(guide.steps.some((s) => /hugging face|скачать/i.test(s))).toBe(true);
    expect(guide.steps.some((s) => /ollama serve|запуст/i.test(s))).toBe(true);
  });

  it('includes verify step', () => {
    const guide = buildOfflineInstallGuide(MODELS[2]);
    expect(guide.steps.some((s) => /ollama list|провер/i.test(s))).toBe(true);
  });
});

describe('buildModelProfile', () => {
  it('includes detailed strengths and weaknesses', () => {
    const profile = buildModelProfile(MODELS.find((model) => model.id === 'ollama-lite')!);
    expect(profile.shortName).toBe('Phi-3');
    expect(profile.strengths.length).toBeGreaterThan(0);
    expect(profile.weaknesses.length).toBeGreaterThan(0);
  });
});

describe('resolveInitialFocusedModelId', () => {
  it('uses recommendation when selected id missing', () => {
    expect(resolveInitialFocusedModelId(MODELS, undefined, 'ollama-lite')).toBe('ollama-lite');
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
    expect(guide.pullCommand).toContain('qwen2.5-coder:3b');
    expect(guide.steps.some((s) => /hugging face|скачать/i.test(s))).toBe(true);
    expect(guide.steps.some((s) => /локально|corex/i.test(s))).toBe(true);
  });
});

describe('sortOfflineModelsForDisplay', () => {
  it('puts recommended model first', () => {
    const sorted = sortOfflineModelsForDisplay(MODELS, 'ollama-lite');
    expect(sorted[0]?.id).toBe('ollama-lite');
    expect(sorted).toHaveLength(4);
  });
});
