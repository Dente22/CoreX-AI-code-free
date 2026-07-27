function parseVersionParts(version: string): number[] {
  const cleaned = normalizeVersion(version);
  return cleaned.split('.').map((part) => Number.parseInt(part, 10) || 0);
}

export function normalizeVersion(version: string): string {
  return (version || '').trim().replace(/^v/i, '');
}

export function isNewerVersion(nextVersion: string, currentVersion: string): boolean {
  const next = parseVersionParts(nextVersion);
  const current = parseVersionParts(currentVersion);
  const maxLen = Math.max(next.length, current.length);
  for (let idx = 0; idx < maxLen; idx += 1) {
    const a = next[idx] ?? 0;
    const b = current[idx] ?? 0;
    if (a > b) return true;
    if (a < b) return false;
  }
  return false;
}
