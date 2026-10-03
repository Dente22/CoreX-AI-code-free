import { fetchApi } from './api';

export type CodingEngineId = 'claude_code' | 'aider' | 'corex';

export interface CodingEngineOption {
  id: CodingEngineId;
  name: string;
  description: string;
}

export const DEFAULT_CODING_ENGINE: CodingEngineId = 'claude_code';

export const CODING_ENGINES: CodingEngineOption[] = [
  {
    id: 'claude_code',
    name: 'Claude Code',
    description:
      'Агент с командами и правками. Модель — локальная (Ollama), OmniRoute или OpenRouter; Groq/Gemini — через OmniRoute',
  },
  { id: 'aider', name: 'Aider', description: 'Правки без JSON tool-calls' },
  { id: 'corex', name: 'CoreX агент', description: 'Встроенный цикл с инструментами' },
];

const STORAGE_KEY = 'corex.codingEngine';

export function getSavedCodingEngine(): CodingEngineId {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    if (CODING_ENGINES.some((item) => item.id === value)) {
      return value as CodingEngineId;
    }
  } catch {
    // ignore
  }
  return DEFAULT_CODING_ENGINE;
}

export function saveCodingEngineLocal(engine: CodingEngineId) {
  try {
    window.localStorage.setItem(STORAGE_KEY, engine);
  } catch {
    // ignore
  }
}

export function codingEngineLabel(id: string): string {
  return CODING_ENGINES.find((item) => item.id === id)?.name || 'Claude Code';
}

export function codingEngineDescription(id: string): string {
  return CODING_ENGINES.find((item) => item.id === id)?.description || '';
}

export async function fetchCodingEngine(): Promise<{
  engine: CodingEngineId;
  engines: CodingEngineOption[];
}> {
  const response = await fetchApi('/api/project/coding-engine');
  if (!response.ok) {
    return { engine: getSavedCodingEngine(), engines: CODING_ENGINES };
  }
  const data = await response.json();
  const engine = CODING_ENGINES.some((item) => item.id === data.engine)
    ? (data.engine as CodingEngineId)
    : getSavedCodingEngine();
  const engines = Array.isArray(data.engines) && data.engines.length
    ? data.engines
    : CODING_ENGINES;
  return { engine, engines };
}

export async function persistCodingEngine(engine: CodingEngineId): Promise<CodingEngineId> {
  saveCodingEngineLocal(engine);
  const response = await fetchApi('/api/project/coding-engine', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ engine }),
  });
  if (!response.ok) return engine;
  const data = await response.json();
  return CODING_ENGINES.some((item) => item.id === data.engine)
    ? (data.engine as CodingEngineId)
    : engine;
}
