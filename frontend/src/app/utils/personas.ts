import { fetchApi } from './api';

export interface Persona {
  id: string;
  name: string;
  description: string;
  category?: string;
  category_ru?: string;
  source?: 'library' | 'project';
  filename?: string;
}

const STORAGE_PREFIX = 'corex.selectedPersona.';

export function getSavedPersonaId(projectRoot: string): string {
  if (!projectRoot) {
    return '';
  }
  try {
    return window.localStorage.getItem(`${STORAGE_PREFIX}${projectRoot}`) || '';
  } catch {
    return '';
  }
}

export function savePersonaId(projectRoot: string, personaId: string) {
  if (!projectRoot) {
    return;
  }
  try {
    if (!personaId) {
      window.localStorage.removeItem(`${STORAGE_PREFIX}${projectRoot}`);
      return;
    }
    window.localStorage.setItem(`${STORAGE_PREFIX}${projectRoot}`, personaId);
  } catch {
    // ignore
  }
}

export async function fetchPersonas(): Promise<Persona[]> {
  const response = await fetchApi('/api/personas');
  if (!response.ok) {
    return [];
  }
  const data = await response.json();
  if (!data?.success || !Array.isArray(data.personas)) {
    return [];
  }
  return data.personas as Persona[];
}

export async function createPersona(
  name: string,
  prompt: string,
  category = '',
): Promise<{ persona?: Persona; error?: string }> {
  const response = await fetchApi('/api/personas', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, prompt, category }),
  });

  const data = await response.json();
  if (!response.ok || data?.error) {
    return { error: data?.error || 'Не удалось создать персону' };
  }

  return { persona: data.persona as Persona };
}

export async function deletePersona(personaId: string): Promise<{ error?: string }> {
  const response = await fetchApi(`/api/personas/${encodeURIComponent(personaId)}`, {
    method: 'DELETE',
  });
  const data = await response.json();
  if (!response.ok || data?.error) {
    return { error: data?.error || 'Не удалось удалить скил' };
  }
  return {};
}

export async function refreshSkillsLibrary(): Promise<void> {
  await fetchApi('/api/skills/refresh', { method: 'POST' });
}
