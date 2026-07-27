import { fetchApi } from './api';

export interface CreateProjectResult {
  success?: boolean;
  root?: string;
  name?: string;
  slug?: string;
  stack?: string;
  task?: string;
  ai_mode?: string;
  requires_online?: boolean;
  warning?: string;
  error?: string;
}

export async function createProjectWithAi(payload: {
  parentPath: string;
  name: string;
  description: string;
  stack?: string;
}): Promise<CreateProjectResult> {
  const response = await fetchApi('/api/projects/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      parent_path: payload.parentPath,
      name: payload.name,
      description: payload.description,
      stack: payload.stack || 'python',
    }),
  });
  const data = (await response.json()) as CreateProjectResult;
  if (!response.ok || data.error) {
    return { error: data.error || 'Не удалось создать проект' };
  }
  return data;
}
