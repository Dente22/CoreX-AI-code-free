export const BROWSER_TAB_PATH = 'corex://browser';
export const BROWSER_TAB_LANGUAGE = 'browser';
export const DEFAULT_BROWSER_URL = 'https://openrouter.ai/keys';
export const CHROME_USER_AGENT =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

export function isBrowserTab(tab: { language?: string; path?: string } | null | undefined): boolean {
  if (!tab) return false;
  return tab.language === BROWSER_TAB_LANGUAGE || tab.path === BROWSER_TAB_PATH;
}

export function isHttpUrl(href: string): boolean {
  try {
    const parsed = new URL(href);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export function shouldOpenInSystemBrowser(input: { ctrlKey?: boolean; metaKey?: boolean } | null | undefined): boolean {
  return Boolean(input && (input.ctrlKey || input.metaKey));
}

export function shouldOpenAuthInSystemBrowser(href: string): boolean {
  try {
    const parsed = new URL(String(href || ''));
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return false;
    }
    const host = parsed.hostname.toLowerCase();
    if (host === 'accounts.google.com' || host.endsWith('.accounts.google.com')) {
      return true;
    }
    if (host === 'accounts.youtube.com' || host === 'oauth2.googleapis.com') {
      return true;
    }
    return /^accounts\.google\.[a-z.]+$/.test(host);
  } catch {
    return false;
  }
}

export function isExternalWebUrl(href: string, appOrigin = ''): boolean {
  try {
    const parsed = new URL(href);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return false;
    }
    if (appOrigin && parsed.origin === appOrigin) {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

export function isWebviewNotReadyError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error || '');
  return /must be attached to the DOM/i.test(message) || /dom-ready event emitted/i.test(message);
}

export function safeWebviewCall<T>(run: () => T, fallback: T): T {
  try {
    return run();
  } catch (error) {
    if (isWebviewNotReadyError(error)) {
      return fallback;
    }
    throw error;
  }
}

export function needsGuestNavigation(currentUrl: string, nextUrl: string): boolean {
  const current = String(currentUrl || '').trim();
  const next = String(nextUrl || '').trim();
  return Boolean(next) && current !== next;
}
