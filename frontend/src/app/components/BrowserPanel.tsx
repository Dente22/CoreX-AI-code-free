import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Copy, ExternalLink, Globe, RefreshCw } from 'lucide-react';
import { CHROME_USER_AGENT, DEFAULT_BROWSER_URL, needsGuestNavigation, safeWebviewCall, shouldOpenAuthInSystemBrowser } from '../utils/internalBrowser';

type GuestWebview = HTMLElement & {
  src?: string;
  getURL?: () => string;
  loadURL?: (url: string) => void;
  goBack?: () => void;
  goForward?: () => void;
  reload?: () => void;
  canGoBack?: () => boolean;
  canGoForward?: () => boolean;
};

declare global {
  namespace React {
    namespace JSX {
      interface IntrinsicElements {
        webview: React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
          src?: string;
          allowpopups?: boolean | string;
          partition?: string;
          useragent?: string;
        };
      }
    }
  }
}

interface BrowserPanelProps {
  url: string;
  onUrlChange: (url: string) => void;
  onCopyUrl: (url: string) => void;
  onOpenExternal: (url: string) => void;
}

export function BrowserPanel({ url, onUrlChange, onCopyUrl, onOpenExternal }: BrowserPanelProps) {
  const viewRef = useRef<GuestWebview | null>(null);
  const readyRef = useRef(false);
  const initialSrcRef = useRef(url || DEFAULT_BROWSER_URL);
  const [guestReady, setGuestReady] = useState(false);
  const [address, setAddress] = useState(url || DEFAULT_BROWSER_URL);
  const [canBack, setCanBack] = useState(false);
  const [canForward, setCanForward] = useState(false);

  const markReady = useCallback(() => {
    if (readyRef.current) {
      return;
    }
    readyRef.current = true;
    setGuestReady(true);
  }, []);

  const setView = useCallback((node: GuestWebview | null) => {
    viewRef.current = node;
    if (!node) {
      readyRef.current = false;
      setGuestReady(false);
      return;
    }
    node.addEventListener('dom-ready', markReady);
  }, [markReady]);

  const readGuestUrl = useCallback(() => {
    const view = viewRef.current;
    if (!view || !readyRef.current) {
      return view?.getAttribute('src') || '';
    }
    return safeWebviewCall(() => (typeof view.getURL === 'function' ? view.getURL() : '') || '', view.getAttribute('src') || '');
  }, []);

  const navigateGuest = useCallback((nextUrl: string) => {
    const view = viewRef.current;
    const target = String(nextUrl || '').trim();
    if (!view || !target || !readyRef.current) {
      return;
    }
    if (shouldOpenAuthInSystemBrowser(target)) {
      onOpenExternal(target);
      return;
    }
    const current = readGuestUrl();
    if (!needsGuestNavigation(current, target)) {
      return;
    }
    safeWebviewCall(() => {
      if (typeof view.loadURL === 'function') {
        view.loadURL(target);
        return true;
      }
      view.setAttribute('src', target);
      return true;
    }, false);
  }, [onOpenExternal, readGuestUrl]);

  useEffect(() => {
    setAddress(url || DEFAULT_BROWSER_URL);
    if (guestReady) {
      navigateGuest(url || DEFAULT_BROWSER_URL);
    }
  }, [url, guestReady, navigateGuest]);

  useEffect(() => {
    const view = viewRef.current;
    if (!view) {
      return;
    }

    const sync = () => {
      const next = readGuestUrl();
      if (next) {
        setAddress(next);
        onUrlChange(next);
      }
      setCanBack(safeWebviewCall(() => (typeof view.canGoBack === 'function' ? view.canGoBack() : false), false));
      setCanForward(safeWebviewCall(() => (typeof view.canGoForward === 'function' ? view.canGoForward() : false), false));
    };

    view.addEventListener('dom-ready', sync);
    view.addEventListener('did-navigate', sync);
    view.addEventListener('did-navigate-in-page', sync);
    view.addEventListener('did-finish-load', sync);
    return () => {
      view.removeEventListener('dom-ready', sync);
      view.removeEventListener('did-navigate', sync);
      view.removeEventListener('did-navigate-in-page', sync);
      view.removeEventListener('did-finish-load', sync);
    };
  }, [guestReady, onUrlChange, readGuestUrl]);

  const submitAddress = () => {
    const raw = address.trim();
    if (!raw) {
      return;
    }
    const next = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
    if (shouldOpenAuthInSystemBrowser(next)) {
      onOpenExternal(next);
      return;
    }
    onUrlChange(next);
  };

  const runGuestAction = (action: (view: GuestWebview) => void) => {
    const view = viewRef.current;
    if (!view || !readyRef.current) {
      return;
    }
    safeWebviewCall(() => {
      action(view);
      return true;
    }, false);
  };

  return (
    <div className="h-full min-h-0 flex flex-col rounded-b-xl border border-[var(--corex-border)] bg-[var(--corex-panel)] overflow-hidden">
      <div className="flex items-center gap-1.5 px-2 py-1.5 border-b border-[var(--corex-border)] bg-[var(--corex-surface)]">
        <button
          type="button"
          className="p-1.5 rounded-md text-[var(--corex-text-muted)] hover:text-white hover:bg-[var(--corex-surface-hover)] disabled:opacity-30"
          disabled={!canBack}
          title="Назад"
          onClick={() => runGuestAction((view) => view.goBack?.())}
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <button
          type="button"
          className="p-1.5 rounded-md text-[var(--corex-text-muted)] hover:text-white hover:bg-[var(--corex-surface-hover)] disabled:opacity-30"
          disabled={!canForward}
          title="Вперёд"
          onClick={() => runGuestAction((view) => view.goForward?.())}
        >
          <ArrowRight className="w-4 h-4" />
        </button>
        <button
          type="button"
          className="p-1.5 rounded-md text-[var(--corex-text-muted)] hover:text-white hover:bg-[var(--corex-surface-hover)]"
          title="Обновить"
          onClick={() => runGuestAction((view) => view.reload?.())}
        >
          <RefreshCw className="w-4 h-4" />
        </button>
        <Globe className="w-3.5 h-3.5 text-[var(--corex-text-dim)] shrink-0 ml-1" />
        <form
          className="flex-1 min-w-0"
          onSubmit={(event) => {
            event.preventDefault();
            submitAddress();
          }}
        >
          <input
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            className="w-full h-8 rounded-md border border-[var(--corex-border)] bg-[var(--corex-bg)] px-2.5 text-xs text-[var(--corex-text)] outline-none focus:border-[var(--corex-brand)]"
            spellCheck={false}
            aria-label="Адрес страницы"
          />
        </form>
        <button
          type="button"
          className="p-1.5 rounded-md text-[var(--corex-text-muted)] hover:text-white hover:bg-[var(--corex-surface-hover)]"
          title="Скопировать ссылку"
          onClick={() => onCopyUrl(address)}
        >
          <Copy className="w-4 h-4" />
        </button>
        <button
          type="button"
          className="p-1.5 rounded-md text-[var(--corex-text-muted)] hover:text-white hover:bg-[var(--corex-surface-hover)]"
          title="Открыть в системном браузере (Ctrl+клик по ссылке)"
          onClick={() => onOpenExternal(address)}
        >
          <ExternalLink className="w-4 h-4" />
        </button>
      </div>
      <webview
        ref={setView}
        className="flex-1 min-h-0 w-full"
        src={initialSrcRef.current}
        allowpopups="true"
        partition="persist:corex-browser"
        useragent={CHROME_USER_AGENT}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
}
