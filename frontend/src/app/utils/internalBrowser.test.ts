import { describe, expect, it } from 'vitest';
import {
  BROWSER_TAB_LANGUAGE,
  BROWSER_TAB_PATH,
  isBrowserTab,
  isExternalWebUrl,
  isHttpUrl,
  isWebviewNotReadyError,
  needsGuestNavigation,
  safeWebviewCall,
  shouldOpenInSystemBrowser,
  shouldOpenAuthInSystemBrowser,
} from './internalBrowser';

describe('isBrowserTab', () => {
  it('detects the in-app browser tab', () => {
    expect(isBrowserTab({ language: BROWSER_TAB_LANGUAGE, path: BROWSER_TAB_PATH })).toBe(true);
  });

  it('ignores editor tabs', () => {
    expect(isBrowserTab({ language: 'typescript', path: 'D:/app/main.ts' })).toBe(false);
    expect(isBrowserTab(null)).toBe(false);
  });
});

describe('isHttpUrl', () => {
  it('accepts http and https', () => {
    expect(isHttpUrl('https://openrouter.ai/keys')).toBe(true);
    expect(isHttpUrl('http://127.0.0.1:3000')).toBe(true);
  });

  it('rejects non-web URLs', () => {
    expect(isHttpUrl('javascript:alert(1)')).toBe(false);
  });
});

describe('shouldOpenInSystemBrowser', () => {
  it('uses the OS browser on Ctrl click', () => {
    expect(shouldOpenInSystemBrowser({ ctrlKey: true })).toBe(true);
    expect(shouldOpenInSystemBrowser({})).toBe(false);
  });
});

describe('shouldOpenAuthInSystemBrowser', () => {
  it('keeps OpenRouter inside CoreX', () => {
    expect(shouldOpenAuthInSystemBrowser('https://openrouter.ai/keys')).toBe(false);
  });

  it('sends Google sign-in to the OS browser', () => {
    expect(shouldOpenAuthInSystemBrowser('https://accounts.google.com/o/oauth2/auth?client_id=x')).toBe(true);
  });
});

describe('isExternalWebUrl', () => {
  it('opens https pages in the in-app browser', () => {
    expect(isExternalWebUrl('https://openrouter.ai/keys', 'http://127.0.0.1:5173')).toBe(true);
  });

  it('does not hijack the CoreX UI origin', () => {
    expect(isExternalWebUrl('http://127.0.0.1:5173/#chat', 'http://127.0.0.1:5173')).toBe(false);
  });
});

describe('safeWebviewCall', () => {
  it('swallows Electron not-ready errors', () => {
    expect(
      isWebviewNotReadyError(
        new Error('The Webview must be attached to the DOM and the dom-ready event emitted before this method can be called.'),
      ),
    ).toBe(true);
    expect(
      safeWebviewCall(() => {
        throw new Error('The Webview must be attached to the DOM and the dom-ready event emitted before this method can be called.');
      }, 'fallback'),
    ).toBe('fallback');
  });

  it('navigates only when the guest URL actually changed', () => {
    expect(needsGuestNavigation('https://openrouter.ai/keys', 'https://openrouter.ai/keys')).toBe(false);
    expect(needsGuestNavigation('', 'https://accounts.google.com')).toBe(true);
  });
});
