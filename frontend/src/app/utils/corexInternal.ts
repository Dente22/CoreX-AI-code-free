/** Служебная папка CoreX: не показываем в дереве, поиске, Git и группах файлов чата. */
export const COREX_INTERNAL_DIRS = new Set(['chat']);

export function isCorexInternalPath(relPath: string): boolean {
  const norm = (relPath || '').replace(/\\/g, '/').replace(/^\/+/, '').trim();
  if (!norm || norm === '.') {
    return false;
  }
  return COREX_INTERNAL_DIRS.has(norm.split('/')[0]);
}

export function isCorexInternalEntryName(name: string): boolean {
  return COREX_INTERNAL_DIRS.has((name || '').trim());
}
