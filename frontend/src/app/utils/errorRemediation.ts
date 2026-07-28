import { fetchApi } from './api';

export type RemediateMode = 'auto' | 'fix' | 'stub';

export interface RemediateResult {
  ok: boolean;
  action?: string;
  path?: string;
  message?: string;
  error?: string;
  hints?: {
    missing_names?: string[];
    missing_modules?: string[];
    missing_files?: string[];
  };
}

export async function remediateError(
  path: string,
  errorText: string,
  mode: RemediateMode = 'auto',
): Promise<RemediateResult> {
  const response = await fetchApi('/api/errors/remediate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, error: errorText, mode }),
  });
  const data = await response.json();
  if (!response.ok) {
    return {
      ok: false,
      error: data?.error || data?.message || 'Не удалось исправить',
      ...data,
    };
  }
  return data as RemediateResult;
}

export function buildAiFixPrompt(path: string, errorText: string): string {
  const shortError = errorText.split('\n').slice(0, 6).join('\n').trim();
  return (
    `Исправь ошибку в файле ${path}. Прочитай view_file, затем write_file с полным содержимым.\n\n` +
    `Ошибка:\n${shortError}`
  );
}
