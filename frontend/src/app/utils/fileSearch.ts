import { isCorexInternalPath } from './corexInternal';

export interface FileSearchHit {
  path: string;
  name: string;
  line: number;
  text: string;
}

export interface FileSearchGroup {
  path: string;
  name: string;
  hits: FileSearchHit[];
}

export function groupSearchHits(hits: FileSearchHit[]): FileSearchGroup[] {
  const groups: FileSearchGroup[] = [];
  const index = new Map<string, FileSearchGroup>();
  for (const hit of hits) {
    if (isCorexInternalPath(hit.path)) {
      continue;
    }
    const key = hit.path;
    let group = index.get(key);
    if (!group) {
      group = { path: hit.path, name: hit.name, hits: [] };
      index.set(key, group);
      groups.push(group);
    }
    group.hits.push(hit);
  }
  return groups;
}

export function splitSearchSnippet(text: string, query: string): { before: string; match: string; after: string } {
  const source = text ?? '';
  const needle = (query ?? '').trim();
  if (!needle) {
    return { before: source, match: '', after: '' };
  }
  const idx = source.toLowerCase().indexOf(needle.toLowerCase());
  if (idx < 0) {
    return { before: source, match: '', after: '' };
  }
  return {
    before: source.slice(0, idx),
    match: source.slice(idx, idx + needle.length),
    after: source.slice(idx + needle.length),
  };
}
