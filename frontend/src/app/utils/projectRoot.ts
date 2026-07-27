import { fetchApi } from './api';

export async function syncProjectRoot(path: string): Promise<{
  success: boolean;
  root?: string;
  error?: string;
}> {
  const trimmed = path?.trim();
  if (!trimmed) {
    return { success: false, error: 'Папка проекта не выбрана' };
  }

  try {
    const response = await fetchApi('/api/files/set_root', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: trimmed }),
    });
    const data = await response.json();
    if (data?.success) {
      return { success: true, root: data.root ?? trimmed };
    }
    return { success: false, error: data?.error ?? 'Не удалось синхронизировать папку проекта' };
  } catch (error) {
    return { success: false, error: String(error) };
  }
}

export function buildAiProjectTask(description: string, projectRoot: string): string {
  const folder = projectRoot.trim();
  return (
    `Создай проект по описанию: ${description}\n\n` +
    `ВАЖНО — рабочая папка уже открыта в CoreX:\n` +
    `${folder}\n\n` +
    'Создавай ВСЕ файлы прямо в этой папке (в её корне). ' +
    'Не создавай отдельную подпапку с именем проекта, если я явно не попросил. ' +
    'Используй относительные пути: main.py, app.py, README.md, src/index.js и т.д.'
  );
}
