import { fetchApi } from './api';

export type HardwareTier = 'low' | 'medium' | 'high';

export interface AiProviderPreset {
  id: string;
  name: string;
  description: string;
  provider_type: string;
  model_name: string;
  base_url: string;
  min_ram_gb: number;
  min_vram_gb?: number;
  size_gb?: number;
  tier: HardwareTier;
  pull_command: string;
  is_default: boolean;
  selected?: boolean;
}

export const DEFAULT_PROVIDER_ID = 'ollama-qwen';

export const CODING_PROVIDER_BY_TIER: Record<HardwareTier, string> = {
  low: 'ollama-qwen',
  medium: 'ollama-qwen-7b',
  high: 'ollama-qwen-14b',
};

export const FALLBACK_AI_PROVIDERS: AiProviderPreset[] = [
  {
    id: 'ollama-qwen',
    name: 'Ollama — Qwen Coder 3B',
    description: 'Код на слабом GPU: целиком в 4 ГБ VRAM, контекст 4096.',
    provider_type: 'ollama',
    model_name: 'qwen2.5-coder:3b',
    base_url: 'http://127.0.0.1:11435',
    min_ram_gb: 4,
    min_vram_gb: 4,
    size_gb: 1.9,
    tier: 'low',
    pull_command: 'ollama pull qwen2.5-coder:3b',
    is_default: true,
    selected: true,
  },
  {
    id: 'ollama-lite',
    name: 'Ollama Lite — Phi-3 Mini',
    description: 'Лёгкий чат для слабых ПК. В коде слабее Qwen 3B.',
    provider_type: 'ollama',
    model_name: 'phi3:mini',
    base_url: 'http://127.0.0.1:11435',
    min_ram_gb: 4,
    min_vram_gb: 4,
    size_gb: 2.2,
    tier: 'low',
    pull_command: 'ollama pull phi3:mini',
    is_default: false,
    selected: false,
  },
  {
    id: 'ollama-qwen-7b',
    name: 'Ollama — Qwen Coder 7B',
    description: 'Лучший локальный код на 8 ГБ VRAM (RTX 3050 и аналоги).',
    provider_type: 'ollama',
    model_name: 'qwen2.5-coder:7b',
    base_url: 'http://127.0.0.1:11435',
    min_ram_gb: 8,
    min_vram_gb: 6,
    size_gb: 4.7,
    tier: 'medium',
    pull_command: 'ollama pull qwen2.5-coder:7b',
    is_default: false,
    selected: false,
  },
  {
    id: 'ollama-claude',
    name: 'Ollama — Llama 3.1 8B',
    description: 'Чат и ревью на среднем ПК. Для кода слабее Qwen 7B.',
    provider_type: 'ollama',
    model_name: 'llama3.1:8b',
    base_url: 'http://127.0.0.1:11435',
    min_ram_gb: 10,
    min_vram_gb: 6,
    size_gb: 4.9,
    tier: 'medium',
    pull_command: 'ollama pull llama3.1:8b',
    is_default: false,
    selected: false,
  },
  {
    id: 'ollama-qwen-14b',
    name: 'Ollama — Qwen Coder 14B',
    description: 'Максимум качества: часть слоёв может уйти в RAM на 8 ГБ VRAM.',
    provider_type: 'ollama',
    model_name: 'qwen2.5-coder:14b',
    base_url: 'http://127.0.0.1:11435',
    min_ram_gb: 16,
    min_vram_gb: 8,
    size_gb: 9.0,
    tier: 'high',
    pull_command: 'ollama pull qwen2.5-coder:14b',
    is_default: false,
    selected: false,
  },
];

export function getFallbackProviders(selectedId = DEFAULT_PROVIDER_ID): AiProviderPreset[] {
  return FALLBACK_AI_PROVIDERS.map((provider) => ({
    ...provider,
    selected: provider.id === selectedId,
  }));
}

export interface AiProviderListResponse {
  success: boolean;
  selected_id: string;
  providers: AiProviderPreset[];
  install_hint?: string;
  error?: string;
}

export interface AiProviderSetResponse {
  success: boolean;
  selected_id?: string;
  preset?: AiProviderPreset;
  error?: string;
}

export type AiMode = 'local' | 'online';

export interface OnlineAiProvider {
  id: string;
  name: string;
  base_url: string;
  model_name: string;
  api_type: 'openai' | 'gemini';
  api_key_masked: string;
  source?: string;
  selected?: boolean;
}

export interface AiRuntimeSnapshot {
  success?: boolean;
  mode: AiMode;
  active_name?: string;
  active_model?: string;
  local: {
    selected_id: string;
    providers: AiProviderPreset[];
    install_hint?: string;
  };
  online: {
    selected_id: string;
    providers: OnlineAiProvider[];
    empty_hint?: string;
  };
  error?: string;
}

export async function fetchAiRuntime(): Promise<AiRuntimeSnapshot> {
  const response = await fetchApi('/api/ai/runtime');
  return response.json();
}

export async function setAiMode(mode: AiMode): Promise<AiRuntimeSnapshot & { success: boolean; error?: string }> {
  const response = await fetchApi('/api/ai/mode', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  });
  return response.json();
}

export async function createOnlineProvider(payload: {
  name: string;
  base_url: string;
  api_key: string;
  model_name: string;
  api_type: 'openai' | 'gemini';
}): Promise<AiRuntimeSnapshot & { success: boolean; provider?: OnlineAiProvider; error?: string }> {
  const response = await fetchApi('/api/ai/online/providers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return response.json();
}

export async function setOnlineProvider(
  providerId: string,
): Promise<AiRuntimeSnapshot & { success: boolean; error?: string }> {
  const response = await fetchApi('/api/ai/online/provider', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider_id: providerId }),
  });
  return response.json();
}

export async function deleteOnlineProvider(
  providerId: string,
): Promise<AiRuntimeSnapshot & { success: boolean; error?: string }> {
  const response = await fetchApi(`/api/ai/online/providers/${encodeURIComponent(providerId)}`, {
    method: 'DELETE',
  });
  return response.json();
}

export function buildFallbackRuntime(selectedLocalId = DEFAULT_PROVIDER_ID): AiRuntimeSnapshot {
  return {
    mode: 'local',
    active_name: FALLBACK_AI_PROVIDERS.find((item) => item.id === selectedLocalId)?.name ?? '',
    active_model:
      FALLBACK_AI_PROVIDERS.find((item) => item.id === selectedLocalId)?.model_name ?? '',
    local: {
      selected_id: selectedLocalId,
      providers: getFallbackProviders(selectedLocalId),
      install_hint: 'Модели не устанавливаются автоматически.',
    },
    online: {
      selected_id: '',
      providers: [],
      empty_hint: 'Добавьте API-провайдера вручную.',
    },
  };
}

export async function fetchAiProviders(): Promise<AiProviderListResponse> {
  const response = await fetchApi('/api/ai/providers');
  return response.json();
}

export async function setAiProvider(providerId: string): Promise<AiProviderSetResponse> {
  const response = await fetchApi('/api/ai/provider', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider_id: providerId }),
  });
  return response.json();
}

export interface OllamaModelCatalogItem extends AiProviderPreset {
  installed: boolean;
  installed_in_corex?: boolean;
  installed_in_desktop?: boolean;
  needs_import?: boolean;
}

export interface OllamaModelsSnapshot {
  success: boolean;
  catalog?: OllamaModelCatalogItem[];
  models?: { name: string }[];
  models_dir?: string;
  base_url?: string;
  error?: string;
  warning?: string;
}

export interface OllamaModelActionResult {
  success: boolean;
  output?: string;
  error?: string;
  provider_id?: string;
  model_name?: string;
  models_dir?: string;
}

export interface OllamaPullProgress {
  job_id: string;
  provider_id?: string;
  model_name: string;
  download_method?: 'direct' | 'registry' | string;
  status: string;
  message: string;
  completed_bytes: number;
  total_bytes: number;
  percent: number;
  percent_label?: string;
  completed_label: string;
  total_label: string;
  speed_label?: string;
  eta_label?: string;
  elapsed_sec?: number;
  indeterminate?: boolean;
  done: boolean;
  success: boolean;
  resumed?: boolean;
  error?: string;
}

export interface OllamaPullStartResult {
  success: boolean;
  started?: boolean;
  already_running?: boolean;
  job_id?: string;
  provider_id?: string;
  model_name?: string;
  progress?: OllamaPullProgress;
  error?: string;
}

export async function fetchOllamaModels(): Promise<OllamaModelsSnapshot> {
  const response = await fetchApi('/api/ai/ollama/models');
  return response.json();
}

export async function startOllamaPull(providerId: string): Promise<OllamaPullStartResult> {
  const response = await fetchApi('/api/ai/ollama/pull', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider_id: providerId }),
  });
  return response.json();
}

export async function fetchOllamaPullProgress(jobId: string): Promise<OllamaPullProgress> {
  const response = await fetchApi(`/api/ai/ollama/pull/progress?job_id=${encodeURIComponent(jobId)}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || 'Не удалось получить прогресс скачивания');
  }
  return data as OllamaPullProgress;
}

export async function pullOllamaModel(providerId: string): Promise<OllamaModelActionResult> {
  const response = await fetchApi('/api/ai/ollama/pull', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider_id: providerId, wait: true }),
  });
  return response.json();
}

export async function deleteOllamaModel(providerId: string): Promise<OllamaModelActionResult> {
  const response = await fetchApi('/api/ai/ollama/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider_id: providerId }),
  });
  return response.json();
}

export function tierLabel(tier: HardwareTier): string {
  if (tier === 'low') return 'Слабый ПК';
  if (tier === 'high') return 'Мощный ПК';
  return 'Средний ПК';
}

export function recommendHardwareTier(
  vramGb?: number,
  ramGb?: number,
): HardwareTier {
  if (typeof vramGb === 'number' && Number.isFinite(vramGb) && vramGb > 0) {
    if (vramGb <= 4.5) return 'low';
    if (vramGb <= 10) return 'medium';
    return 'high';
  }
  if (typeof ramGb === 'number' && ramGb >= 24) return 'medium';
  return 'low';
}

export function recommendedProviderId(vramGb?: number, ramGb?: number): string {
  return CODING_PROVIDER_BY_TIER[recommendHardwareTier(vramGb, ramGb)];
}

const SHORT_LABELS: Record<string, string> = {
  'ollama-qwen': 'Qwen 3B',
  'ollama-qwen-7b': 'Qwen 7B',
  'ollama-qwen-14b': 'Qwen 14B',
  'ollama-claude': 'Llama 8B',
  'ollama-lite': 'Phi-3',
};

const TIER_COLORS: Record<AiProviderPreset['tier'], string> = {
  low: '#059669',
  medium: '#2563eb',
  high: '#7c3aed',
};

export function getModelShortLabel(provider: AiProviderPreset): string {
  return SHORT_LABELS[provider.id] ?? provider.name.split('—')[0]?.trim() ?? provider.name;
}

export function getModelTierColor(tier: AiProviderPreset['tier']): string {
  return TIER_COLORS[tier] ?? TIER_COLORS.medium;
}

export function getModelTooltip(provider: AiProviderPreset): string {
  const vram = provider.min_vram_gb ? ` · от ${provider.min_vram_gb} ГБ VRAM` : '';
  return `${provider.name} · ${provider.model_name} · ${tierLabel(provider.tier)} · от ${provider.min_ram_gb} ГБ RAM${vram}`;
}
