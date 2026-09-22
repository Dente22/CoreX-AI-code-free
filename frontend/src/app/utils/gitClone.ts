export function isAllowedGitRemote(url: string): boolean {
  const raw = String(url || '').trim();
  if (!raw || /\s/.test(raw)) {
    return false;
  }
  if (/^https:\/\//i.test(raw)) {
    try {
      const parsed = new URL(raw);
      if (parsed.protocol !== 'https:') {
        return false;
      }
      if (parsed.username || parsed.password) {
        return false;
      }
      return Boolean(parsed.hostname && parsed.pathname.replace(/\/+$/, '').length > 1);
    } catch {
      return false;
    }
  }
  if (/^git@[\w.-]+:[\w./~+-]+(?:\.git)?$/i.test(raw)) {
    return true;
  }
  if (/^ssh:\/\//i.test(raw)) {
    try {
      const parsed = new URL(raw);
      return parsed.protocol === 'ssh:' && Boolean(parsed.hostname && parsed.pathname.replace(/\/+$/, ''));
    } catch {
      return false;
    }
  }
  return false;
}

export function folderNameFromRemote(url: string): string {
  const raw = String(url || '').trim().replace(/\/+$/, '').replace(/\.git$/i, '');
  if (raw.startsWith('git@') && raw.includes(':')) {
    const path = raw.slice(raw.indexOf(':') + 1);
    return path.split('/').filter(Boolean).pop() || 'repo';
  }
  try {
    const parsed = new URL(raw);
    return parsed.pathname.split('/').filter(Boolean).pop()?.replace(/\.git$/i, '') || 'repo';
  } catch {
    return 'repo';
  }
}
