import { fetchApi } from './api';

export interface Pipeline {
  id: string;
  name: string;
  description: string;
  steps_count: number;
  step_labels?: string[];
  limits: Record<string, number>;
  source?: 'library' | 'project';
  category_ru?: string;
  filename?: string;
}

export interface PipelineStepInput {
  persona_id: string;
  role?: string;
  goal?: string;
  max_turns?: number;
  allow_writes?: boolean;
}

const STORAGE_PREFIX = 'corex.workMode.';
const PIPELINE_PREFIX = 'corex.pipeline.';

export type WorkMode = 'single' | 'agent' | 'pipeline';

export function getSavedWorkMode(projectRoot: string): WorkMode {
  if (!projectRoot) return 'single';
  try {
    const value = window.localStorage.getItem(`${STORAGE_PREFIX}${projectRoot}`);
    if (value === 'pipeline' || value === 'agent') return value;
    return 'single';
  } catch {
    return 'single';
  }
}

export function saveWorkMode(projectRoot: string, mode: WorkMode) {
  if (!projectRoot) return;
  try {
    window.localStorage.setItem(`${STORAGE_PREFIX}${projectRoot}`, mode);
  } catch {
    // ignore
  }
}

export function getSavedPipelineId(projectRoot: string): string {
  if (!projectRoot) return '';
  try {
    return window.localStorage.getItem(`${PIPELINE_PREFIX}${projectRoot}`) || '';
  } catch {
    return '';
  }
}

export function savePipelineId(projectRoot: string, pipelineId: string) {
  if (!projectRoot) return;
  try {
    if (!pipelineId) {
      window.localStorage.removeItem(`${PIPELINE_PREFIX}${projectRoot}`);
      return;
    }
    window.localStorage.setItem(`${PIPELINE_PREFIX}${projectRoot}`, pipelineId);
  } catch {
    // ignore
  }
}

export async function fetchPipelines(): Promise<Pipeline[]> {
  const response = await fetchApi('/api/pipelines');
  if (!response.ok) return [];
  const data = await response.json();
  if (!data?.success || !Array.isArray(data.pipelines)) return [];
  return data.pipelines as Pipeline[];
}

export async function createPipeline(
  name: string,
  description: string,
  steps: PipelineStepInput[],
): Promise<{ pipeline?: Pipeline; error?: string }> {
  const response = await fetchApi('/api/pipelines', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description, steps }),
  });
  const data = await response.json();
  if (!response.ok || data?.error) {
    return { error: data?.error || 'Не удалось создать команду' };
  }
  return { pipeline: data.pipeline as Pipeline };
}

export async function deletePipeline(pipelineId: string): Promise<{ error?: string }> {
  const response = await fetchApi(`/api/pipelines/${encodeURIComponent(pipelineId)}`, {
    method: 'DELETE',
  });
  const data = await response.json();
  if (!response.ok || data?.error) {
    return { error: data?.error || 'Не удалось удалить команду' };
  }
  return {};
}
