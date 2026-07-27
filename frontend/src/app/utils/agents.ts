import { fetchApi } from './api';

export interface Agent {
  id: string;
  name: string;
  description: string;
  category?: string;
  category_ru?: string;
  source?: 'library' | 'project';
  filename?: string;
}

const STORAGE_PREFIX = 'corex.selectedAgent.';

export function getSavedAgentId(projectRoot: string): string {
  if (!projectRoot) return '';
  try {
    return window.localStorage.getItem(`${STORAGE_PREFIX}${projectRoot}`) || '';
  } catch {
    return '';
  }
}

export function saveAgentId(projectRoot: string, agentId: string) {
  if (!projectRoot) return;
  try {
    if (!agentId) {
      window.localStorage.removeItem(`${STORAGE_PREFIX}${projectRoot}`);
      return;
    }
    window.localStorage.setItem(`${STORAGE_PREFIX}${projectRoot}`, agentId);
  } catch {
    // ignore
  }
}

export async function fetchAgents(): Promise<Agent[]> {
  const response = await fetchApi('/api/agents');
  if (!response.ok) return [];
  const data = await response.json();
  if (!data?.success || !Array.isArray(data.agents)) return [];
  return data.agents as Agent[];
}

export async function createAgent(
  name: string,
  prompt: string,
  categoryRu = 'Мои агенты',
): Promise<{ agent?: Agent; error?: string }> {
  const response = await fetchApi('/api/agents', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, prompt, category_ru: categoryRu }),
  });

  const data = await response.json();
  if (!response.ok || data?.error) {
    return { error: data?.error || 'Не удалось создать агента' };
  }

  return { agent: data.agent as Agent };
}

export async function deleteAgent(agentId: string): Promise<{ error?: string }> {
  const response = await fetchApi(`/api/agents/${encodeURIComponent(agentId)}`, {
    method: 'DELETE',
  });
  const data = await response.json();
  if (!response.ok || data?.error) {
    return { error: data?.error || 'Не удалось удалить агента' };
  }
  return {};
}
