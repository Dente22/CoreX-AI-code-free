import { fetchApi } from './api';

export type WebAccessMode = 'never' | 'ask' | 'always';

export interface WebAccessOption {
  id: WebAccessMode;
  label: string;
}

export interface WebAccessSnapshot {
  ok?: boolean;
  mode: WebAccessMode;
  label: string;
  modes: WebAccessOption[];
  error?: string;
}

export const WEB_ACCESS_MODES: WebAccessOption[] = [
  { id: 'never', label: 'Никогда' },
  { id: 'ask', label: 'Когда просите' },
  { id: 'always', label: 'Всегда' },
];

export function webAccessHint(mode: WebAccessMode): string {
  if (mode === 'always') {
    return 'Перед кодом CoreX может взять короткие сниппеты DuckDuckGo. Исходники проекта в сеть не уходят.';
  }
  if (mode === 'ask') {
    return 'Поиск только если в сообщении есть «интернет», «погугли», «в сети» и т.п.';
  }
  return 'Агент работает только с локальным проектом и своей моделью.';
}

export async function saveWebAccessMode(mode: WebAccessMode): Promise<WebAccessSnapshot> {
  const response = await fetchApi('/api/system/web-access', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  });
  const data = await response.json();
  if (!response.ok || data?.ok === false) {
    throw new Error(data?.error || 'Не удалось сохранить доступ в интернет');
  }
  return data as WebAccessSnapshot;
}
