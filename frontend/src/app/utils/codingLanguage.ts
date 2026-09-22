import { fetchApi } from './api';

export type CodingLanguageId =
  | 'auto'
  | 'python'
  | 'javascript'
  | 'html'
  | 'css'
  | 'typescript'
  | 'react';

export interface CodingLanguageOption {
  id: CodingLanguageId;
  name: string;
  description: string;
}

export const CODING_LANGUAGES: CodingLanguageOption[] = [
  { id: 'auto', name: 'Авто', description: 'По сообщению' },
  { id: 'python', name: 'Python', description: 'файлы .py' },
  { id: 'javascript', name: 'JavaScript', description: 'файлы .js' },
  { id: 'html', name: 'HTML', description: 'страницы / сайт' },
  { id: 'css', name: 'CSS', description: 'стили' },
  { id: 'typescript', name: 'TypeScript', description: 'файлы .ts' },
  { id: 'react', name: 'React', description: 'JSX / TSX' },
];

const STORAGE_PREFIX = 'corex.codingLanguage.';

export function getSavedCodingLanguage(projectRoot: string): CodingLanguageId {
  if (!projectRoot) return 'auto';
  try {
    const value = window.localStorage.getItem(`${STORAGE_PREFIX}${projectRoot}`);
    if (CODING_LANGUAGES.some((item) => item.id === value)) {
      return value as CodingLanguageId;
    }
  } catch {
    // ignore
  }
  return 'auto';
}

export function saveCodingLanguageLocal(projectRoot: string, language: CodingLanguageId) {
  if (!projectRoot) return;
  try {
    window.localStorage.setItem(`${STORAGE_PREFIX}${projectRoot}`, language);
  } catch {
    // ignore
  }
}

export function languageLabel(id: string): string {
  return CODING_LANGUAGES.find((item) => item.id === id)?.name || 'Авто';
}

export async function fetchCodingLanguage(): Promise<{
  language: CodingLanguageId;
  languages: CodingLanguageOption[];
}> {
  const response = await fetchApi('/api/project/coding-language');
  if (!response.ok) {
    return { language: 'auto', languages: CODING_LANGUAGES };
  }
  const data = await response.json();
  const language = CODING_LANGUAGES.some((item) => item.id === data?.language)
    ? (data.language as CodingLanguageId)
    : 'auto';
  const languages = Array.isArray(data?.languages) && data.languages.length
    ? (data.languages as CodingLanguageOption[])
    : CODING_LANGUAGES;
  return { language, languages };
}

export async function saveCodingLanguage(language: CodingLanguageId): Promise<void> {
  await fetchApi('/api/project/coding-language', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ language }),
  });
}
