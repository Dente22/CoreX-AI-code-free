import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityBar } from './components/ActivityBar';
import { AdminTracePanel } from './components/AdminTracePanel';
import { FileExplorer } from './components/FileExplorer';
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
import { fetchApi, initBackendConnection } from './utils/api';
import { createProjectWithAi } from './utils/projectCreate';
import { getLanguageFromFilename } from './utils/editorLanguage';
import { isRunnableFile, runCommand, runFile, type TerminalRunResult } from './utils/terminal';

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
  const [fileContents, setFileContents] = useState<Record<string, string>>({});
  const [terminalLines, setTerminalLines] = useState<TerminalLine[]>([]);
  const [terminalExpanded, setTerminalExpanded] = useState(true);
  const [terminalRunning, setTerminalRunning] = useState(false);
  const [notification, setNotification] = useState('Откройте проект или файл, чтобы начать работу.');
  const [appVersion, setAppVersion] = useState('');
  const [updateStatus, setUpdateStatus] = useState('');
  const [fileHighlights, setFileHighlights] = useState<Record<string, FilePatchHighlight[]>>({});
  const [showChat, setShowChat] = useState(true);
  const [showCreateAIProjectModal, setShowCreateAIProjectModal] = useState(false);
  const [createAIProjectError, setCreateAIProjectError] = useState('');
  const [isCreatingAIProject, setIsCreatingAIProject] = useState(false);
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

  const handleOpenFile = (path: string, name: string) => {
    void (async () => {
      const existingTab = openTabs.find((tab) => tab.path === path);
      if (existingTab) {
        setActiveTabId(existingTab.id);
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

  const handleTerminalCommand = async (command: string) => {
    if (!projectRoot) {
      setNotification('Сначала откройте папку проекта.');
      return;
    }
    setTerminalExpanded(true);
    setTerminalRunning(true);
    appendTerminalLine('command', `$ ${command}`);
    try {
      const result = await runCommand(command);
      appendRunResult(result);
    } catch (error) {
      appendTerminalLine('error', `Ошибка: ${String(error)}`);
    } finally {
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
    setTerminalRunning(true);
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

      const result = await runFile(tab.path);
      appendRunResult(result);
      setNotification(result.success ? `Выполнено: ${tab.name}` : `Ошибка запуска: ${tab.name}`);
    } catch (error) {
      appendTerminalLine('error', `Ошибка: ${String(error)}`);
      setNotification(`Ошибка запуска: ${String(error)}`);
    } finally {
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
    setHasProject(true);
    setActiveView('explorer');
    setOpenTabs([]);
    setActiveTabId('');
    setFileContents({});
    setNotification('Запущено клонирование репозитория.');
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
              <div className="h-full corex-sidebar-panel p-4">
                <div className="text-[var(--corex-text)] text-xs font-semibold uppercase tracking-wider mb-4">Поиск</div>
                <input type="text" placeholder="Поиск в файлах..." className="corex-input-field w-full text-sm" />
              </div>
            )}
            {activeView === 'git' && (
              <div className="h-full corex-sidebar-panel p-4">
                <div className="text-[var(--corex-text-muted)] text-sm">Нет изменений</div>
              </div>
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
                        patchHighlights={
                          selectedTab ? fileHighlights[selectedTab.path] ?? [] : []
                        }
                      />
                    </ErrorBoundary>
                  </div>
                  <Terminal
                    isExpanded={terminalExpanded}
                    onToggle={() => setTerminalExpanded((v) => !v)}
                    lines={terminalLines}
                    onCommand={(cmd) => void handleTerminalCommand(cmd)}
                    onClear={handleClearTerminal}
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
