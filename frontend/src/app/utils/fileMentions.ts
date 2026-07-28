import { fetchApi } from './api';

const MENTION_PATTERN = /(?:^|[\s(«"'])\/([^\s/,.)»"']+)/gu;

export function extractMentionPaths(text: string): string[] {
  const seen = new Set<string>();
  const paths: string[] = [];
  for (const match of text.matchAll(MENTION_PATTERN)) {
    const path = match[1]?.replace(/\\/g, '/');
    if (!path || seen.has(path)) continue;
    seen.add(path);
    paths.push(path);
  }
  return paths;
}

export async function fetchMentionCandidates(query: string, limit = 20): Promise<string[]> {
  try {
    const params = new URLSearchParams({ q: query, limit: String(limit) });
    const response = await fetchApi(`/api/files/mentions?${params.toString()}`);
    if (!response.ok) return [];
    const data = await response.json();
    return Array.isArray(data?.files) ? data.files : [];
  } catch {
    return [];
  }
}

export function getSlashQuery(text: string, cursor: number): string | null {
  const before = text.slice(0, cursor);
  const match = /(?:^|[\s])\/([^\s/]*)$/.exec(before);
  return match ? match[1] : null;
}

export function insertMention(
  text: string,
  cursor: number,
  filePath: string,
): { text: string; cursor: number } {
  const before = text.slice(0, cursor);
  const after = text.slice(cursor);
  const match = /(?:^|[\s])\/([^\s/]*)$/.exec(before);
  if (!match) {
    const prefix = before.endsWith(' ') || !before ? '' : ' ';
    const insertion = `${prefix}/${filePath} `;
    return { text: before + insertion + after, cursor: before.length + insertion.length };
  }
  const start = before.length - match[0].length + (match[0].startsWith(' ') ? 1 : 0);
  const lead = before.slice(0, start);
  const insertion = `/${filePath} `;
  const next = lead + insertion + after;
  return { text: next, cursor: lead.length + insertion.length };
}
