import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityBar } from './components/ActivityBar';
import { AdminTracePanel } from './components/AdminTracePanel';
import { FileExplorer } from './components/FileExplorer';
import { SearchPanel } from './components/SearchPanel';
import { GitPanel } from './components/GitPanel';
import { EditorWorkspace } from './components/EditorWorkspace';
import type { CodeEditorHandle } from './components/CodeEditor';
import { Terminal, type TerminalLine } from './components/Terminal';
import { StatusBar } from './components/StatusBar';
import { AIChatPanel } from './components/AIChatPanel';
import { WelcomeScreen } from './components/WelcomeScreen';
import ErrorBoundary from './components/ErrorBoundary';
import { ChatProvider, useChat } from './contexts/ChatContext';
import type { FilePatchHighlight } from './types/editorPatch';
import { FileTreeProvider, useFileTree } from './contexts/FileTreeContext';
import { ViewSettingsProvider } from './contexts/ViewSettingsContext';
import { MenuBar } from './components/MenuBar';
import { AIProviderSettings } from './components/AIProviderSettings';
import { CreateAIProjectModal } from './components/CreateAIProjectModal';
import { CloneRepoModal } from './components/CloneRepoModal';
import { fetchApi, initBackendConnection } from './utils/api';
import { createProjectWithAi } from './utils/projectCreate';
import { getLanguageFromFilename } from './utils/editorLanguage';
import { filenameHasExtension, NO_EXTENSION_ERROR } from './utils/fileName';
import { isInteractiveRunnable, isRunnableFile, killTerminalSession, pollTerminalSession, runFile, sendTerminalStdin, startTerminalSession, type TerminalRunResult } from './utils/terminal';
import {
  BROWSER_TAB_LANGUAGE,
  BROWSER_TAB_PATH,
  DEFAULT_BROWSER_URL,
  isBrowserTab,
  isExternalWebUrl,
  isHttpUrl,
  shouldOpenAuthInSystemBrowser,
  shouldOpenInSystemBrowser,
} from './utils/internalBrowser';
import { isCorexInternalPath } from './utils/corexInternal';

const LAST_PROJECT_ROOT_KEY = 'corex.lastProjectRoot';

declare global {
  interface Window {
    electronAPI?: {
      isElectron: boolean;
      backendPort?: string | null;
      backendUrl?: string | null;
      projectDir?: string | null;
      onFolderSelected?: (callback: (path: string) => void) => () => void;
      onMenuAction?: (callback: (action: string) => void) => () => void;
      openFolder?: () => Promise<string | null>;
      getBackendInfo?: () => Promise<{ backendPort: string; backendUrl: string }>;
      getAppVersion?: () => Promise<string>;
      onUpdateStatus?: (callback: (status: string) => void) => () => void;
      pickInstallerUpdate?: () => Promise<{ success: boolean; reason?: string; version?: string }>;
      openExternal?: (url: string) => Promise<{ ok?: boolean }>;
      copyText?: (text: string) => Promise<{ ok?: boolean }>;
      onOpenInAppBrowser?: (callback: (url: string) => void) => () => void;
      onAuthOpenedExternally?: (callback: (url: string) => void) => () => void;
    };
  }
}

interface EditorTab {
  id: string;
  name: string;
  path: string;
  modified: boolean;
  language: string;
}

interface CoreXAppInnerProps {
  hasProject: boolean;
  projectRoot: string;
  setHasProject: (value: boolean) => void;
  setProjectRoot: (value: string) => void;
}

function createId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

function getSavedProjectRoot() {
  try {
    return window.localStorage.getItem(LAST_PROJECT_ROOT_KEY) || '';
  } catch {
    return '';
  }
}

function saveProjectRoot(root: string) {
  try {
    window.localStorage.setItem(LAST_PROJECT_ROOT_KEY, root);
  } catch {
    // Ignore localStorage failures
  }
}

function CoreXAppInner({ hasProject, projectRoot, setHasProject, setProjectRoot }: CoreXAppInnerProps) {
  const editorRef = useRef<CodeEditorHandle>(null);
  const {
    connectionStatus,
    sendMessage,
    stopGeneration,
    refreshConnection,
    messages,
    editorPatch,
    clearEditorPatch,
    setWorkMode,
    setSelectedPipelineId,
  } = useChat();
  const { refreshFileTree } = useFileTree();
  const lastMessageCountRef = useRef(0);

  const [activeView, setActiveView] = useState<'explorer' | 'chat' | 'search' | 'git' | 'debug' | 'extensions' | 'settings'>('explorer');
  const [openTabs, setOpenTabs] = useState<EditorTab[]>([]);
  const [activeTabId, setActiveTabId] = useState('');
  const [browserUrl, setBrowserUrl] = useState(DEFAULT_BROWSER_URL);
  const [fileContents, setFileContents] = useState<Record<string, string>>({});
  const [revealRequest, setRevealRequest] = useState<{ path: string; line: number; token: number } | null>(null);
  const [terminalLines, setTerminalLines] = useState<TerminalLine[]>([]);
  const [terminalExpanded, setTerminalExpanded] = useState(true);
  const [terminalRunning, setTerminalRunning] = useState(false);
  const terminalAliveRef = useRef(false);
  const [notification, setNotification] = useState('Откройте проект или файл, чтобы начать работу.');
  const [appVersion, setAppVersion] = useState('');
  const [updateStatus, setUpdateStatus] = useState('');
  const [fileHighlights, setFileHighlights] = useState<Record<string, FilePatchHighlight[]>>({});
  const [showChat, setShowChat] = useState(true);
  const [showCreateAIProjectModal, setShowCreateAIProjectModal] = useState(false);
  const [createAIProjectError, setCreateAIProjectError] = useState('');
  const [isCreatingAIProject, setIsCreatingAIProject] = useState(false);
  const [showCloneRepoModal, setShowCloneRepoModal] = useState(false);
  const [cloneRepoError, setCloneRepoError] = useState('');
  const [isCloningRepo, setIsCloningRepo] = useState(false);
  const [cloneParentPath, setCloneParentPath] = useState('');
  const [aiProjectParentPath, setAiProjectParentPath] = useState('');
  const [showCreateFileDialog, setShowCreateFileDialog] = useState(false);
  const [showCreateFolderDialog, setShowCreateFolderDialog] = useState(false);
  const [newItemName, setNewItemName] = useState('');

  const createFileRef = useRef<HTMLInputElement | null>(null);
  const createFolderRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (window.electronAPI?.getAppVersion) {
      void window.electronAPI.getAppVersion().then((value) => setAppVersion(value)).catch(() => undefined);
    }
    if (window.electronAPI?.onUpdateStatus) {
      const dispose = window.electronAPI.onUpdateStatus((status) => setUpdateStatus(status));
      return () => dispose?.();
    }
    return undefined;
  }, []);

  useEffect(() => {
    const focusActiveModal = () => {
      if (showCreateFileDialog) {
        window.setTimeout(() => createFileRef.current?.focus(), 50);
      } else if (showCreateFolderDialog) {
        window.setTimeout(() => createFolderRef.current?.focus(), 50);
      }
    };

    focusActiveModal();
    window.addEventListener('focus', focusActiveModal);
    return () => window.removeEventListener('focus', focusActiveModal);
  }, [showCreateFileDialog, showCreateFolderDialog]);

  const handleSendChat = (text: string) => {
    void (async () => {
      if (!projectRoot) {
        setNotification('Сначала откройте папку проекта (Файл → Открыть папку).');
        return;
      }
      const sent = await sendMessage(text);
      if (!sent) {
        setNotification('WebSocket отключён. Переподключение...');
        refreshConnection();
      }
    })();
  };

  const handleOpenBrowser = useCallback((rawUrl?: string) => {
    if (shouldOpenAuthInSystemBrowser(rawUrl || '')) {
      void (async () => {
        if (window.electronAPI?.openExternal) {
          await window.electronAPI.openExternal(String(rawUrl));
          setNotification('Google не принимает встроенный браузер — вход открыт в системном. После входа скопируйте ключ сюда.');
        }
      })();
      return;
    }
    const nextUrl = isHttpUrl(rawUrl || '') ? String(rawUrl) : DEFAULT_BROWSER_URL;
    setBrowserUrl(nextUrl);
    setActiveView('explorer');
    setOpenTabs((prev) => {
      const existing = prev.find((tab) => isBrowserTab(tab));
      if (existing) {
        setActiveTabId(existing.id);
        return prev;
      }
      const nextTab: EditorTab = {
        id: createId('tab'),
        name: 'Браузер',
        path: BROWSER_TAB_PATH,
        modified: false,
        language: BROWSER_TAB_LANGUAGE,
      };
      setActiveTabId(nextTab.id);
      return [...prev, nextTab];
    });
    setNotification('Открыт браузер CoreX. Ctrl+клик — системный браузер.');
  }, []);

  const handleCopyBrowserUrl = useCallback(async (url: string) => {
    const value = String(url || '').trim();
    if (!value) {
      return;
    }
    try {
      if (window.electronAPI?.copyText) {
        await window.electronAPI.copyText(value);
      } else {
        await navigator.clipboard.writeText(value);
      }
      setNotification('Ссылка скопирована.');
    } catch {
      setNotification('Не удалось скопировать ссылку.');
    }
  }, []);

  const handleOpenSystemBrowser = useCallback(async (url: string) => {
    const target = isHttpUrl(url) ? url : browserUrl;
    if (!isHttpUrl(target)) {
      return;
    }
    if (window.electronAPI?.openExternal) {
      await window.electronAPI.openExternal(target);
      setNotification('Открыто в системном браузере.');
    }
  }, [browserUrl]);

  const handleOpenFile = (path: string, name: string, line?: number) => {
    if (isHttpUrl(path)) {
      handleOpenBrowser(path);
      return;
    }
    if (isCorexInternalPath(path)) {
      setNotification('Служебные данные CoreX недоступны в редакторе.');
      return;
    }
    const reveal = (targetPath: string) => {
      if (typeof line === 'number' && Number.isFinite(line) && line > 0) {
        const request = { path: targetPath, line, token: Date.now() };
        setRevealRequest(request);
        window.setTimeout(() => editorRef.current?.revealLine(line), 80);
      }
    };
    void (async () => {
      const existingTab = openTabs.find((tab) => tab.path === path);
      if (existingTab) {
        setActiveTabId(existingTab.id);
        reveal(path);
        setNotification(`Файл ${name} уже открыт.`);
        return;
      }

      try {
        const response = await fetchApi(`/api/files/read?path=${encodeURIComponent(path)}`);
        const data = await response.json();

        if (data?.error) {
          setNotification(`Ошибка при чтении файла: ${data.error}`);
          return;
        }

        const content = data.content ?? '';
        const nextTab: EditorTab = {
          id: createId('tab'),
          name,
          path,
          modified: false,
          language: getLanguageFromFilename(path),
        };

        setFileContents((prev) => ({ ...prev, [path]: content }));
        setOpenTabs((prev) => [...prev, nextTab]);
        setActiveTabId(nextTab.id);
        reveal(path);
        setNotification(`Открыт файл ${name}.`);
      } catch (error) {
        setNotification(`Ошибка сети при чтении файла: ${String(error)}`);
      }
    })();
  };

  const handleCloseTab = (id: string) => {
    setOpenTabs((prev) => {
      const updated = prev.filter((tab) => tab.id !== id);
      if (activeTabId === id) {
        setActiveTabId(updated[0]?.id ?? '');
      }
      return updated;
    });
  };

  const handleCloseOtherTabs = (keepId: string) => {
    setOpenTabs((prev) => prev.filter((tab) => tab.id === keepId));
    setActiveTabId(keepId);
  };

  const handleCloseAllTabs = () => {
    setOpenTabs([]);
    setActiveTabId('');
  };

  const handleEditFile = (path: string, value: string) => {
    setFileContents((prev) => ({ ...prev, [path]: value }));
    setOpenTabs((prev) => prev.map((tab) => (tab.path === path ? { ...tab, modified: true } : tab)));
    setFileHighlights((prev) => {
      if (!prev[path]) {
        return prev;
      }
      const next = { ...prev };
      delete next[path];
      return next;
    });
  };

  const handleSaveSuccess = (path: string) => {
    setOpenTabs((prev) => prev.map((tab) => (tab.path === path ? { ...tab, modified: false } : tab)));
  };

  const appendTerminalLine = useCallback((kind: TerminalLine['kind'], text: string) => {
    setTerminalLines((prev) => [...prev, { id: createId('term'), kind, text }]);
  }, []);

  const appendRunResult = useCallback(
    (result: TerminalRunResult) => {
      if (result.command) {
        appendTerminalLine('command', `$ ${result.command}`);
      }
      if (result.output?.trim()) {
        appendTerminalLine('output', result.output);
      }
      if (result.error) {
        appendTerminalLine('error', result.error);
      }
      if (result.success) {
        appendTerminalLine('info', `✓ Готово (код ${result.exit_code ?? 0})`);
      } else if (!result.error && result.exit_code !== undefined) {
        appendTerminalLine('error', `✗ Код выхода: ${result.exit_code}`);
      }
    },
    [appendTerminalLine],
  );

  const handleOpenTerminal = () => {
    setTerminalExpanded(true);
  };

  const handleClearTerminal = () => {
    setTerminalLines([]);
  };

  const pumpTerminalSession = useCallback(
    async (path?: string) => {
      terminalAliveRef.current = true;
      while (terminalAliveRef.current) {
        const snap = await pollTerminalSession(path);
        if (snap.output) {
          appendTerminalLine('output', snap.output);
        }
        if (snap.error && !snap.running) {
          appendTerminalLine('error', snap.error);
        }
        if (!snap.running) {
          if (snap.success) {
            appendTerminalLine('info', `✓ Готово (код ${snap.exit_code ?? 0})`);
          } else if (snap.exit_code !== undefined && snap.exit_code !== 0 && !snap.error) {
            appendTerminalLine('error', `✗ Код выхода: ${snap.exit_code}`);
          }
          break;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 80));
      }
    },
    [appendTerminalLine],
  );

  const handleStopTerminal = useCallback(async () => {
    terminalAliveRef.current = false;
    const result = await killTerminalSession();
    if (result.output) {
      appendTerminalLine('output', result.output);
    }
    appendTerminalLine('info', '■ Процесс остановлен');
    setTerminalRunning(false);
  }, [appendTerminalLine]);

  const handleTerminalCommand = async (command: string) => {
    if (!projectRoot) {
      setNotification('Сначала откройте папку проекта.');
      return;
    }
    setTerminalExpanded(true);
    if (terminalRunning) {
      appendTerminalLine('output', command);
      const sent = await sendTerminalStdin(command);
      if (!sent.success && sent.error) {
        appendTerminalLine('error', sent.error);
      }
      return;
    }
    setTerminalRunning(true);
    appendTerminalLine('command', `$ ${command}`);
    try {
      const started = await startTerminalSession({ command });
      if (started.command && started.command !== command) {
        appendTerminalLine('command', `$ ${started.command}`);
      }
      if (!started.success) {
        appendTerminalLine('error', started.error || 'Не удалось запустить команду');
        return;
      }
      await pumpTerminalSession();
    } catch (error) {
      appendTerminalLine('error', `Ошибка: ${String(error)}`);
    } finally {
      terminalAliveRef.current = false;
      setTerminalRunning(false);
    }
  };

  const handleRunFile = async () => {
    const tab = openTabs.find((t) => t.id === activeTabId);
    if (!tab) {
      setNotification('Нет открытого файла для запуска.');
      return;
    }
    if (!projectRoot) {
      setNotification('Сначала откройте папку проекта.');
      return;
    }
    if (!isRunnableFile(tab.path)) {
      setNotification(`Тип файла «${tab.name}» нельзя запустить напрямую.`);
      return;
    }

    setTerminalExpanded(true);
    appendTerminalLine('info', `▶ Запуск ${tab.path}`);

    try {
      if (tab.modified) {
        appendTerminalLine('info', 'Сохранение перед запуском...');
        const saved = await editorRef.current?.save();
        if (!saved) {
          appendTerminalLine('error', 'Не удалось сохранить файл перед запуском.');
          return;
        }
      }

      if (!isInteractiveRunnable(tab.path)) {
        setTerminalRunning(true);
        const result = await runFile(tab.path);
        appendRunResult(result);
        setNotification(result.success ? `Выполнено: ${tab.name}` : `Ошибка запуска: ${tab.name}`);
        return;
      }

      setTerminalRunning(true);
      const started = await startTerminalSession({ path: tab.path });
      if (started.command) {
        appendTerminalLine('command', `$ ${started.command}`);
      }
      if (!started.success) {
        appendTerminalLine('error', started.error || 'Не удалось запустить файл');
        setNotification(`Ошибка запуска: ${tab.name}`);
        return;
      }
      setNotification(`Запущено: ${tab.name} — вводите в консоль внизу`);
      await pumpTerminalSession(tab.path);
    } catch (error) {
      appendTerminalLine('error', `Ошибка: ${String(error)}`);
      setNotification(`Ошибка запуска: ${String(error)}`);
    } finally {
      terminalAliveRef.current = false;
      setTerminalRunning(false);
    }
  };

  const handleCreateFolder = () => {
    if (!hasProject) {
      setNotification('Откройте проект перед созданием папки.');
      return;
    }
    setNewItemName('');
    setShowCreateFolderDialog(true);
  };

  const submitCreateFolder = async () => {
    const name = newItemName.trim();
    if (!name) return;

    try {
      const response = await fetchApi('/api/files/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: name, isDir: true }),
      });
      const data = await response.json();
      if (data?.success) {
        await refreshFileTree();
        setNotification(`Папка создана: ${name}`);
      } else {
        setNotification(`Ошибка при создании папки: ${data?.error ?? 'Unknown error'}`);
      }
    } catch (error) {
      setNotification(`Ошибка сети: ${String(error)}`);
    } finally {
      setShowCreateFolderDialog(false);
      setNewItemName('');
    }
  };

  const handleCreateFile = () => {
    if (!hasProject) {
      setNotification('Откройте проект перед созданием файла.');
      return;
    }
    setNewItemName('');
    setShowCreateFileDialog(true);
  };

  const submitCreateFile = async () => {
    const name = newItemName.trim();
    if (!name) return;
    if (!filenameHasExtension(name)) {
      setNotification(NO_EXTENSION_ERROR);
      return;
    }

    try {
      const response = await fetchApi('/api/files/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: name, content: '' }),
      });
      const data = await response.json();
      if (data?.success) {
        await refreshFileTree();
        setNotification(`Файл создан: ${name}`);
      } else {
        setNotification(`Ошибка при создании файла: ${data?.error ?? 'Unknown error'}`);
      }
    } catch (error) {
      setNotification(`Ошибка сети: ${String(error)}`);
    } finally {
      setShowCreateFileDialog(false);
      setNewItemName('');
    }
  };

  const openProjectAtPath = async (path: string) => {
    if (!path) {
      setNotification('Открытие папки отменено или не удалось.');
      return;
    }

    try {
      const response = await fetchApi('/api/files/set_root', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      });
      const data = await response.json();

      if (data?.success) {
        const root = data.root ?? path;
        setHasProject(true);
        setProjectRoot(root);
        saveProjectRoot(root);
        let profileHint = '';
        try {
          const profileRes = await fetchApi('/api/system/profile');
          const profile = await profileRes.json();
          if (profile?.limits_summary) {
            profileHint = ` · ${profile.limits_summary}`;
          }
        } catch {
          // ignore profile errors
        }
        setNotification(`Открыта папка проекта: ${root}${profileHint}`);
      } else {
        setNotification(`Не удалось открыть папку: ${data?.error ?? 'Unknown error'}`);
      }
    } catch (error) {
      setNotification(`Ошибка сети при открытии папки: ${String(error)}`);
    }
  };

  useEffect(() => {
    void (async () => {
      await initBackendConnection();
      const savedRoot = getSavedProjectRoot();
      const electronRoot = window.electronAPI?.projectDir;
      const initialRoot = savedRoot || electronRoot;
      if (!initialRoot) {
        return;
      }
      await openProjectAtPath(initialRoot);
    })();
  }, []);

  useEffect(() => {
    if (!editorPatch?.path) {
      return;
    }

    const patchPath = editorPatch.path.replace(/\\/g, '/');
    const fileName = patchPath.split('/').pop() ?? patchPath;

    setFileContents((prev) => ({ ...prev, [patchPath]: editorPatch.content }));
    setFileHighlights((prev) => ({ ...prev, [patchPath]: editorPatch.highlights }));

    setOpenTabs((prev) => {
      const existing = prev.find((tab) => tab.path === patchPath);
      if (existing) {
        setActiveTabId(existing.id);
        return prev.map((tab) =>
          tab.path === patchPath ? { ...tab, modified: false } : tab,
        );
      }
      const nextTab: EditorTab = {
        id: createId('tab'),
        name: fileName,
        path: patchPath,
        modified: false,
        language: getLanguageFromFilename(patchPath),
      };
      setActiveTabId(nextTab.id);
      return [...prev, nextTab];
    });

    setNotification(`AI изменил ${patchPath}`);
    void refreshFileTree();
    clearEditorPatch();
  }, [editorPatch, clearEditorPatch, refreshFileTree]);

  useEffect(() => {
    const newMessages = messages.slice(lastMessageCountRef.current);
    lastMessageCountRef.current = messages.length;

    const fileWasCreated = newMessages.some(
      (message) =>
        message.role === 'assistant' &&
        (message.content.includes('Файл создан') ||
          message.content.includes('Файл записан') ||
          message.content.includes('Файл обновлён') ||
          message.content.includes('Файл изменён') ||
          message.content.includes('patch') ||
          message.content.includes('Авто-исправление') ||
          message.content.includes('Создана заготовка') ||
          message.content.includes('успешно создан') ||
          message.content.includes('successfully created')),
    );

    if (fileWasCreated) {
      void refreshFileTree();
    }
  }, [messages, refreshFileTree]);

  const openLastProject = async () => {
    const lastRoot = getSavedProjectRoot();
    if (!lastRoot) {
      setNotification('Последний проект не найден.');
      return;
    }
    await openProjectAtPath(lastRoot);
  };

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      const anchor = target?.closest?.('a[href]') as HTMLAnchorElement | null;
      if (!anchor) {
        return;
      }
      const href = anchor.href;
      if (!isExternalWebUrl(href, window.location.origin)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      if (shouldOpenInSystemBrowser(event)) {
        void handleOpenSystemBrowser(href);
        return;
      }
      handleOpenBrowser(href);
    };

    const originalOpen = window.open.bind(window);
    window.open = ((url?: string | URL, target?: string, features?: string) => {
      const href = typeof url === 'string' ? url : url?.toString?.() || '';
      if (isExternalWebUrl(href, window.location.origin)) {
        handleOpenBrowser(href);
        return null;
      }
      return originalOpen(url, target, features);
    }) as typeof window.open;

    document.addEventListener('click', onClick, true);
    return () => {
      document.removeEventListener('click', onClick, true);
      window.open = originalOpen;
    };
  }, [handleOpenBrowser, handleOpenSystemBrowser]);

  useEffect(() => {
    if (!window.electronAPI?.onOpenInAppBrowser) {
      return;
    }
    return window.electronAPI.onOpenInAppBrowser((url: string) => {
      handleOpenBrowser(url);
    });
  }, [handleOpenBrowser]);

  useEffect(() => {
    if (!window.electronAPI?.onAuthOpenedExternally) {
      return;
    }
    return window.electronAPI.onAuthOpenedExternally(() => {
      setNotification('Google не принимает встроенный браузер — вход открыт в системном. После входа скопируйте ключ сюда.');
    });
  }, []);

  useEffect(() => {
    if (!window.electronAPI?.onFolderSelected) {
      return;
    }
    const unsubscribe = window.electronAPI.onFolderSelected((selectedPath: string) => {
      void openProjectAtPath(selectedPath);
    });
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    if (!window.electronAPI?.onMenuAction) {
      return;
    }
    const unsubscribe = window.electronAPI.onMenuAction((action: string) => {
      handleMenuAction(action);
    });
    return () => unsubscribe();
  }, []);

  const handleMenuAction = (action: string) => {
    switch (action) {
      case 'exit':
        setHasProject(false);
        setProjectRoot('');
        setActiveView('explorer');
        setOpenTabs([]);
        setActiveTabId('');
        setFileContents({});
        setNotification('Проект закрыт. Возвращаемся на главное меню.');
        break;
      case 'open-folder':
        void handleOpenProject();
        break;
      case 'new-terminal':
        handleOpenTerminal();
        break;
      case 'new-file':
        handleCreateFile();
        break;
      case 'new-folder':
        handleCreateFolder();
        break;
      case 'save-file':
        void editorRef.current?.save();
        break;
      case 'run-file':
        void handleRunFile();
        break;
      case 'open-browser':
        handleOpenBrowser();
        break;
      case 'help':
      case 'помощь':
        if (window.electronAPI?.pickInstallerUpdate) {
          void window.electronAPI.pickInstallerUpdate().then((result) => {
            if (result.success) {
              setNotification(`Запускаю установщик CoreX v${result.version}...`);
              return;
            }
            if (result.reason === 'not_newer') {
              setNotification('Выбранный установщик не новее текущей версии.');
              return;
            }
            if (result.reason === 'invalid_installer') {
              setNotification('Выбран неподходящий установщик. Нужен файл CoreX-Setup-*.exe');
            }
          });
        }
        break;
      default:
        break;
    }
  };

  const handleViewChange = (view: string) => {
    setActiveView(view as typeof activeView);
  };

  const handleCreateProject = () => {
    setCreateAIProjectError('');
    setAiProjectParentPath(projectRoot || getSavedProjectRoot());
    setShowCreateAIProjectModal(true);
  };

  const handleCreateAIProject = () => {
    setCreateAIProjectError('');
    setAiProjectParentPath(projectRoot || getSavedProjectRoot());
    setShowCreateAIProjectModal(true);
  };

  const handleSubmitNewAIProject = async (payload: {
    parentPath: string;
    name: string;
    description: string;
    stack: string;
  }) => {
    setIsCreatingAIProject(true);
    setCreateAIProjectError('');
    try {
      const result = await createProjectWithAi(payload);
      if (result.error || !result.root || !result.task) {
        throw new Error(result.error || 'Не удалось создать проект');
      }

      setHasProject(true);
      setProjectRoot(result.root);
      saveProjectRoot(result.root);
      await refreshFileTree();

      await fetchApi('/api/ai/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'online' }),
      });

      setWorkMode('pipeline');
      setSelectedPipelineId('lib-team:dev-team');
      setActiveView('chat');
      setShowChat(true);
      setShowCreateAIProjectModal(false);

      const sent = await sendMessage(result.task, { projectRoot: result.root });
      if (!sent) {
        setNotification('Проект создан, но WebSocket недоступен. Переподключитесь и повторите запрос.');
      } else {
        const hint = result.warning ? ` ${result.warning}` : '';
        setNotification(`Проект «${result.name}» создан. AI генерирует файлы…${hint}`);
      }
    } catch (error) {
      setCreateAIProjectError(error instanceof Error ? error.message : 'Ошибка создания проекта');
    } finally {
      setIsCreatingAIProject(false);
    }
  };

  const handleOpenProject = async () => {
    if (window.electronAPI?.openFolder) {
      const selectedPath = await window.electronAPI.openFolder();
      await openProjectAtPath(selectedPath ?? '');
      return;
    }
    setNotification('Выберите папку проекта через Electron или укажите путь вручную.');
  };

  const handleCloneRepo = () => {
    setCloneRepoError('');
    setCloneParentPath(projectRoot || getSavedProjectRoot());
    setShowCloneRepoModal(true);
  };

  const handleSubmitCloneRepo = async (payload: { url: string; parentPath: string }) => {
    setIsCloningRepo(true);
    setCloneRepoError('');
    try {
      const response = await fetchApi('/api/git/clone', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: payload.url, parent_path: payload.parentPath }),
      });
      const data = await response.json();
      if (!response.ok || data?.error || !data?.root) {
        throw new Error(data?.error || 'Не удалось клонировать репозиторий');
      }
      setShowCloneRepoModal(false);
      await openProjectAtPath(data.root);
      await refreshFileTree();
      setActiveView('explorer');
      setNotification(`Репозиторий «${data.name || 'проект'}» склонирован.`);
    } catch (error) {
      setCloneRepoError(error instanceof Error ? error.message : 'Ошибка клонирования');
    } finally {
      setIsCloningRepo(false);
    }
  };

  const handleRefreshConnection = () => {
    setNotification('Переподключение WebSocket...');
    refreshConnection();
  };

  const handleStopGeneration = () => {
    stopGeneration();
    setNotification('Запрос остановки отправлен AI.');
  };

  const handleCloseChatPanel = () => {
    setShowChat(false);
    setNotification('Панель чат скрыта. Переключитесь на CoreX AI, чтобы открыть снова.');
  };

  const selectedTab = openTabs.find((tab) => tab.id === activeTabId);
  const activeFileContent = selectedTab ? fileContents[selectedTab.path] ?? '' : '';

  const createAIProjectModal = (
    <CreateAIProjectModal
      open={showCreateAIProjectModal}
      initialParentPath={aiProjectParentPath}
      onClose={() => {
        if (!isCreatingAIProject) {
          setShowCreateAIProjectModal(false);
          setCreateAIProjectError('');
        }
      }}
      onSubmit={handleSubmitNewAIProject}
      isSubmitting={isCreatingAIProject}
      error={createAIProjectError}
    />
  );

  const cloneRepoModal = (
    <CloneRepoModal
      open={showCloneRepoModal}
      initialParentPath={cloneParentPath}
      onClose={() => {
        if (!isCloningRepo) {
          setShowCloneRepoModal(false);
          setCloneRepoError('');
        }
      }}
      onSubmit={handleSubmitCloneRepo}
      isSubmitting={isCloningRepo}
      error={cloneRepoError}
    />
  );

  const createFileModal = showCreateFileDialog ? (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="corex-surface-elevated w-full max-w-xl rounded-2xl p-6">
        <div className="text-xl font-semibold text-[var(--corex-text)]">Создать новый файл</div>
        <input
          ref={createFileRef}
          type="text"
          value={newItemName}
          onChange={(e) => setNewItemName(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') void submitCreateFile(); }}
          className="corex-input-field mt-4 w-full"
          placeholder="Имя файла с расширением, например snake.py"
          autoFocus
        />
        <div className="mt-5 flex justify-end gap-3">
          <button onClick={() => setShowCreateFileDialog(false)} className="corex-btn-ghost px-4 py-2 text-xs">Отмена</button>
          <button onClick={() => void submitCreateFile()} className="corex-btn-primary px-5 py-2 text-xs">Создать</button>
        </div>
      </div>
    </div>
  ) : null;

  const createFolderModal = showCreateFolderDialog ? (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="corex-surface-elevated w-full max-w-xl rounded-2xl p-6">
        <div className="text-xl font-semibold text-[var(--corex-text)]">Создать новую папку</div>
        <input
          ref={createFolderRef}
          type="text"
          value={newItemName}
          onChange={(e) => setNewItemName(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') void submitCreateFolder(); }}
          className="corex-input-field mt-4 w-full"
          autoFocus
        />
        <div className="mt-5 flex justify-end gap-3">
          <button onClick={() => setShowCreateFolderDialog(false)} className="corex-btn-ghost px-4 py-2 text-xs">Отмена</button>
          <button onClick={() => void submitCreateFolder()} className="corex-btn-primary px-5 py-2 text-xs">Создать</button>
        </div>
      </div>
    </div>
  ) : null;

  if (!hasProject) {
    return (
      <div className="corex-app min-h-screen flex flex-col">
        <WelcomeScreen
          onOpenProject={() => void handleOpenProject()}
          onCreateProject={handleCreateProject}
          onCloneRepo={handleCloneRepo}
          onCreateAIProject={handleCreateAIProject}
          onOpenLastProject={() => void openLastProject()}
          lastProject={getSavedProjectRoot()}
        />
        <StatusBar
          isOnline={connectionStatus === 'open'}
          appVersion={appVersion}
          updateStatus={updateStatus}
        />
        {createAIProjectModal}
        {cloneRepoModal}
      </div>
    );
  }

  return (
    <div className="corex-app h-screen flex flex-col">
      <MenuBar onMenuAction={handleMenuAction} />
      <div className="corex-app-body">
        <div className="flex-shrink-0 h-full">
          <ActivityBar activeView={activeView} onViewChange={handleViewChange} />
        </div>

        {activeView !== 'chat' && activeView !== 'settings' && (
          <div className="w-64 flex-shrink-0 h-full min-h-0 overflow-hidden">
            {activeView === 'explorer' && (
              <ErrorBoundary>
                <FileExplorer
                  projectRoot={projectRoot}
                  openTabs={openTabs}
                  activeTabId={activeTabId}
                  onFileSelect={handleOpenFile}
                  onNotification={setNotification}
                />
              </ErrorBoundary>
            )}
            {activeView === 'search' && (
              <ErrorBoundary>
                <SearchPanel projectRoot={projectRoot} onOpenFile={handleOpenFile} />
              </ErrorBoundary>
            )}
            {activeView === 'git' && (
              <ErrorBoundary>
                <GitPanel
                  projectRoot={projectRoot}
                  onOpenFile={handleOpenFile}
                  onNotification={setNotification}
                />
              </ErrorBoundary>
            )}
            {activeView === 'debug' && (
              <div className="h-full corex-sidebar-panel p-4 text-xs text-[var(--corex-text-muted)] space-y-3">
                <p className="text-[var(--corex-spark)] font-semibold uppercase tracking-wider text-[10px]">Нейротрасса</p>
                <p>Живая схема: что CoreX отправляет модели, какие инструменты вызывает и что возвращает.</p>
                <ul className="space-y-1.5 list-none">
                  <li><span className="text-[var(--corex-spark)]">●</span> активный шаг</li>
                  <li><span className="text-emerald-400">●</span> выполнено</li>
                  <li><span className="text-red-400">●</span> ошибка</li>
                </ul>
              </div>
            )}
            {activeView === 'extensions' && (
              <div className="h-full corex-sidebar-panel p-4">
                <div className="text-[var(--corex-text-muted)] text-sm">Популярные расширения</div>
              </div>
            )}
          </div>
        )}

        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex-1 flex min-h-0">
            {activeView === 'chat' ? (
              <div className="flex-1 h-full min-h-0">
                {showChat ? (
                  <ErrorBoundary>
                    <AIChatPanel
                      variant="full"
                      onSend={handleSendChat}
                      onStop={handleStopGeneration}
                      onRefresh={handleRefreshConnection}
                      onClosePanel={handleCloseChatPanel}
                      onCreateProject={handleCreateAIProject}
                      projectRoot={projectRoot}
                      onOpenFile={handleOpenFile}
                      onNotification={setNotification}
                      onFileChanged={(_path, message) => {
                        setNotification(message);
                        void refreshFileTree();
                      }}
                    />
                  </ErrorBoundary>
                ) : (
                  <div className="h-full flex items-center justify-center bg-[var(--corex-panel)]">
                    <button onClick={() => setShowChat(true)} className="corex-btn-primary px-5 py-2.5">Открыть чат</button>
                  </div>
                )}
              </div>
            ) : activeView === 'debug' ? (
              <div className="flex-1 h-full min-h-0 bg-[var(--corex-panel)]">
                <ErrorBoundary>
                  <AdminTracePanel />
                </ErrorBoundary>
              </div>
            ) : activeView === 'settings' ? (
              <div className="flex-1 bg-[var(--corex-panel)] p-8 overflow-y-auto">
                <h2 className="text-2xl font-bold text-[var(--corex-text)] mb-6">Настройки</h2>
                <AIProviderSettings onNotification={setNotification} />
              </div>
            ) : (
              <>
                <div className="flex-1 flex flex-col min-w-0 min-h-0">
                  <div className="flex-1 min-h-0">
                    <ErrorBoundary>
                      <EditorWorkspace
                        ref={editorRef}
                        tabs={openTabs}
                        activeTabId={activeTabId}
                        onSelectTab={setActiveTabId}
                        onCloseTab={handleCloseTab}
                        onCloseOtherTabs={handleCloseOtherTabs}
                        onCloseAllTabs={handleCloseAllTabs}
                        content={activeFileContent}
                        path={selectedTab?.path ?? ''}
                        language={selectedTab?.language ?? 'plaintext'}
                        onContentChange={handleEditFile}
                        onSaveSuccess={handleSaveSuccess}
                        onRun={() => void handleRunFile()}
                        canRun={selectedTab ? isRunnableFile(selectedTab.path) : false}
                        projectRoot={projectRoot}
                        hasOpenTabs={openTabs.length > 0}
                        onOpenDiagramFile={(diagramPath) => {
                          const name = diagramPath.split('/').pop() ?? 'workflow.mmd';
                          handleOpenFile(diagramPath, name);
                        }}
                        browserUrl={browserUrl}
                        onBrowserUrlChange={setBrowserUrl}
                        onCopyBrowserUrl={(url) => void handleCopyBrowserUrl(url)}
                        onOpenBrowserExternal={(url) => void handleOpenSystemBrowser(url)}
                        patchHighlights={
                          selectedTab ? fileHighlights[selectedTab.path] ?? [] : []
                        }
                        revealRequest={revealRequest}
                      />
                    </ErrorBoundary>
                  </div>
                  <Terminal
                    isExpanded={terminalExpanded}
                    onToggle={() => setTerminalExpanded((v) => !v)}
                    lines={terminalLines}
                    onCommand={(cmd) => void handleTerminalCommand(cmd)}
                    onClear={handleClearTerminal}
                    onStop={() => void handleStopTerminal()}
                    isRunning={terminalRunning}
                    projectRoot={projectRoot}
                    onFixWithAI={handleSendChat}
                    onOpenFile={handleOpenFile}
                    onRemediated={(_path, message) => {
                      setNotification(message);
                      void refreshFileTree();
                    }}
                  />
                </div>
                <div className="w-80 flex-shrink-0 h-full min-h-0">
                  {showChat ? (
                    <ErrorBoundary>
                      <AIChatPanel
                        onSend={handleSendChat}
                        onStop={handleStopGeneration}
                        onRefresh={handleRefreshConnection}
                        onClosePanel={handleCloseChatPanel}
                        onCreateProject={handleCreateAIProject}
                        projectRoot={projectRoot}
                        onOpenFile={handleOpenFile}
                        onNotification={setNotification}
                        onFileChanged={(_path, message) => {
                          setNotification(message);
                          void refreshFileTree();
                        }}
                      />
                    </ErrorBoundary>
                  ) : (
                    <div className="h-full flex items-center justify-center">
                      <button onClick={() => setShowChat(true)} className="corex-btn-primary px-5 py-2.5">Открыть чат</button>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="corex-notification-bar flex items-center justify-between">
        <div>{notification}</div>
        <div className="text-[var(--corex-text-dim)]">Активен: {selectedTab?.name ?? 'нет файла'}</div>
      </div>

      <StatusBar
        isOnline={connectionStatus === 'open'}
        appVersion={appVersion}
        updateStatus={updateStatus}
      />

      {createAIProjectModal}
      {createFileModal}
      {createFolderModal}
    </div>
  );
}

export default function CoreXApp() {
  const [hasProject, setHasProject] = useState(false);
  const [projectRoot, setProjectRoot] = useState('');

  return (
    <ViewSettingsProvider>
      <ChatProvider projectRoot={projectRoot}>
        <FileTreeProvider projectRoot={projectRoot} hasProject={hasProject}>
          <CoreXAppInner
            hasProject={hasProject}
            projectRoot={projectRoot}
            setHasProject={setHasProject}
            setProjectRoot={setProjectRoot}
          />
        </FileTreeProvider>
      </ChatProvider>
    </ViewSettingsProvider>
  );
}
