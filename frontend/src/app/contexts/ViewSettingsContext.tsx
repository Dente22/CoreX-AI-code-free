import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

const STORAGE_KEY = 'corex.terminalVisio';

interface ViewSettingsContextValue {
  terminalVisio: boolean;
  setTerminalVisio: (value: boolean) => void;
  toggleTerminalVisio: () => void;
}

const ViewSettingsContext = createContext<ViewSettingsContextValue | null>(null);

function readSavedTerminalVisio(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

function persistTerminalVisio(value: boolean) {
  try {
    window.localStorage.setItem(STORAGE_KEY, value ? '1' : '0');
  } catch {
    // ignore
  }
}

export function ViewSettingsProvider({ children }: { children: ReactNode }) {
  const [terminalVisio, setTerminalVisioState] = useState(readSavedTerminalVisio);

  const setTerminalVisio = useCallback((value: boolean) => {
    setTerminalVisioState(value);
    persistTerminalVisio(value);
  }, []);

  const toggleTerminalVisio = useCallback(() => {
    setTerminalVisio(!terminalVisio);
  }, [setTerminalVisio, terminalVisio]);

  const value = useMemo(
    () => ({ terminalVisio, setTerminalVisio, toggleTerminalVisio }),
    [terminalVisio, setTerminalVisio, toggleTerminalVisio],
  );

  return <ViewSettingsContext.Provider value={value}>{children}</ViewSettingsContext.Provider>;
}

export function useViewSettings() {
  const context = useContext(ViewSettingsContext);
  if (!context) {
    throw new Error('useViewSettings must be used within ViewSettingsProvider');
  }
  return context;
}
