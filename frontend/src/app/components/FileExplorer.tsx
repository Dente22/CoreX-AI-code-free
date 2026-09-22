import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronRight, ChevronDown, Folder, FileCode, FolderOpen, FolderPlus, FilePlus, Check, X } from 'lucide-react';
import { useFileTree, type FileNode } from '../contexts/FileTreeContext';
import { fetchApi } from '../utils/api';
import { isCorexInternalPath } from '../utils/corexInternal';
import { filenameHasExtension, NO_EXTENSION_ERROR } from '../utils/fileName';

interface EditorTab {
  id: string;
  name: string;
  path: string;
  modified: boolean;
  language: string;
}

interface FileExplorerProps {
  projectRoot: string;
  openTabs: EditorTab[];
  activeTabId: string;
  onFileSelect: (path: string, name: string) => void;
  onNotification: (message: string) => void;
}

const EXCLUDED_ENTRIES = new Set([
  '.git',
  '__pycache__',
  '.env',
  'node_modules',
  '.venv',
  '.venv-1',
  'dist',
  '.cursor',
  '.idea',
]);

function filterTreeNodes(nodes: FileNode[]): FileNode[] {
  return nodes
    .filter(
      (node) =>
        node?.name &&
        !EXCLUDED_ENTRIES.has(node.name) &&
        !node.name.startsWith('.') &&
        !isCorexInternalPath(node.path),
    )
    .map((node) =>
      node.type === 'folder' && node.children
        ? { ...node, children: filterTreeNodes(node.children) }
        : node,
    );
}

export function FileExplorer({
  projectRoot,
  openTabs,
  activeTabId,
  onFileSelect,
  onNotification,
}: FileExplorerProps) {
  const {
    fileTree,
    treeLoading,
    treeError,
    treeVersion,
    isTreeValid,
    refreshFileTree,
    toggleFolderExpanded,
  } = useFileTree();

  const files = filterTreeNodes(fileTree ?? []);
  const treeKey = isTreeValid ? `tree-${projectRoot}-v${treeVersion}` : `tree-invalid-${treeVersion}`;

  const [selectedFolderPath, setSelectedFolderPath] = useState<string>('.');
  const [createFormKey, setCreateFormKey] = useState(0);
  const [createState, setCreateState] = useState<{
    type: 'file' | 'folder' | null;
    name: string;
    isSubmitting: boolean;
  }>({ type: null, name: '', isSubmitting: false });
  const [contextMenu, setContextMenu] = useState<{ visible: boolean; x: number; y: number; node?: FileNode }>({
    visible: false,
    x: 0,
    y: 0,
  });
  const [confirmDeleteNode, setConfirmDeleteNode] = useState<FileNode | null>(null);
  const createInputRef = useRef<HTMLInputElement | null>(null);

  const startCreate = (type: 'file' | 'folder') => {
    setCreateState({ type, name: '', isSubmitting: false });
    setCreateFormKey((prev) => prev + 1);
    window.setTimeout(() => {
      createInputRef.current?.focus();
      createInputRef.current?.select();
    }, 50);
  };

  const cancelCreate = () => {
    setCreateState({ type: null, name: '', isSubmitting: false });
    setCreateFormKey((prev) => prev + 1);
  };

  useEffect(() => {
    const focusInput = () => {
      if (createState.type) {
        createInputRef.current?.focus();
        createInputRef.current?.select();
      }
    };

    focusInput();
    window.addEventListener('focus', focusInput);
    return () => window.removeEventListener('focus', focusInput);
  }, [createState.type, createFormKey, selectedFolderPath]);

  const normalizePath = (path: string) => path.replace(/\\/g, '/');

  const getParentPath = (path: string) => {
    const normalized = normalizePath(path || '');
    if (!normalized || normalized === '.' || !normalized.includes('/')) {
      return '.';
    }
    return normalized.split('/').slice(0, -1).join('/') || '.';
  };

  const buildTargetPath = (name: string) => {
    const sanitized = name.trim().replace(/^\/+/, '');
    if (!sanitized) return '';
    if (!selectedFolderPath || selectedFolderPath === '.' || selectedFolderPath === '') {
      return sanitized;
    }
    return `${selectedFolderPath}/${sanitized}`;
  };

  const submitCreate = async () => {
    if (!createState.type) {
      return;
    }

    const trimmed = createState.name.trim();
    if (!trimmed) {
      onNotification('Введите имя файла или папки.');
      return;
    }

    const targetPath = buildTargetPath(trimmed);
    if (!targetPath) {
      onNotification('Неверное имя.');
      return;
    }
    if (isCorexInternalPath(targetPath)) {
      onNotification('Это имя зарезервировано системой.');
      return;
    }
    if (createState.type === 'file' && !filenameHasExtension(targetPath)) {
      onNotification(NO_EXTENSION_ERROR);
      return;
    }

    setCreateState((prev) => ({ ...prev, isSubmitting: true }));

    try {
      const res = await fetchApi('/api/files/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: targetPath,
          isDir: createState.type === 'folder',
          content: createState.type === 'file' ? '' : undefined,
        }),
      });
      const data = await res.json();

      if (!data?.success) {
        onNotification('Ошибка: ' + (data?.error ?? 'Unknown'));
        return;
      }

      try {
        await refreshFileTree();
      } catch (refreshError) {
        console.error('[FileExplorer] Failed to refresh file tree after creation:', refreshError);
      }

      if (createState.type === 'file') {
        setSelectedFolderPath(getParentPath(targetPath));
        onFileSelect(targetPath, trimmed.split('/').pop() ?? trimmed);
      } else {
        setSelectedFolderPath(targetPath);
      }

      setCreateState({ type: null, name: '', isSubmitting: false });
      setCreateFormKey((prev) => prev + 1);
      onNotification(`${createState.type === 'folder' ? 'Папка' : 'Файл'} создан${createState.type === 'folder' ? 'а' : ''}: ${targetPath}`);
    } catch (error) {
      onNotification('Ошибка сети: ' + String(error));
    } finally {
      setCreateState((prev) => ({ ...prev, isSubmitting: false }));
    }
  };

  const handleConfirmDelete = async () => {
    const node = confirmDeleteNode;
    setConfirmDeleteNode(null);

    if (!node?.path) {
      setContextMenu({ visible: false, x: 0, y: 0 });
      return;
    }

    try {
      const r = await fetchApi('/api/files/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: node.path }),
      });
      const j = await r.json();

      if (j?.success) {
        onNotification('Удалено');
        await refreshFileTree();
      } else {
        onNotification('Ошибка: ' + (j?.error ?? 'Unknown'));
      }
    } catch {
      onNotification('Ошибка при удалении');
    } finally {
      setContextMenu({ visible: false, x: 0, y: 0 });
    }
  };

  const openTabPaths = useMemo(() => {
    const paths = new Set<string>();
    for (const tab of openTabs ?? []) {
      if (tab?.path) paths.add(normalizePath(tab.path));
    }
    return paths;
  }, [openTabs]);

  const activeTabPath = useMemo(() => {
    const active = (openTabs ?? []).find((t) => t.id === activeTabId);
    return active?.path ? normalizePath(active.path) : '';
  }, [openTabs, activeTabId]);

  const renderNode = (node: FileNode | null | undefined, depth: number, path: number[]) => {
    if (!node?.name || !node?.path) {
      return null;
    }

    const isFolder = node.type === 'folder';
    const Icon = isFolder ? (node.expanded ? FolderOpen : Folder) : FileCode;
    const normalizedPath = normalizePath(node.path);
    const isSelected = normalizedPath === selectedFolderPath;
    const isOpenFile = !isFolder && openTabPaths.has(normalizedPath);
    const isActiveFile = !isFolder && normalizedPath === activeTabPath;

    const handleNodeClick = () => {
      if (isFolder) {
        toggleFolderExpanded(node.path);
        setSelectedFolderPath(normalizedPath || '.');
      } else {
        setSelectedFolderPath(getParentPath(normalizedPath));
        onFileSelect(node.path, node.name);
      }
    };

    return (
      <div key={`${node.path}-${depth}`}>
        <button
          onClick={handleNodeClick}
          onContextMenu={(e) => {
            e.preventDefault();
            setContextMenu({ visible: true, x: e.clientX, y: e.clientY, node });
            if (isFolder) {
              setSelectedFolderPath(normalizedPath || '.');
            } else {
              setSelectedFolderPath(getParentPath(normalizedPath));
            }
          }}
          className={`w-full flex items-center gap-1 px-2 py-1 text-[var(--corex-text-muted)] transition-colors text-left text-sm rounded-md mx-1 ${
            isActiveFile
              ? 'corex-tree-file-active'
              : isOpenFile
                ? 'corex-tree-file-open bg-[rgba(154,94,255,0.08)]'
                : isSelected
                  ? 'bg-[rgba(0,210,255,0.1)] text-[var(--corex-spark)]'
                  : 'hover:bg-[var(--corex-surface-hover)] hover:text-[var(--corex-text)]'
          }`}
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
        >
          {isFolder ? (
            <span className="text-[#858585]">
              {node.expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </span>
          ) : (
            <span className="w-4" />
          )}
          <Icon className={`w-4 h-4 ${isFolder ? 'text-[#dcb67a]' : 'text-[#519aba]'}`} />
          <span className="truncate flex-1">{node.name}</span>
          {isOpenFile && !isFolder && (
            <span
              className={`w-1.5 h-1.5 rounded-full shrink-0 ${isActiveFile ? 'bg-[var(--corex-spark)]' : 'bg-[var(--corex-brand)]'}`}
              title={isActiveFile ? 'Активная вкладка' : 'Открыт в редакторе'}
            />
          )}
        </button>
        {isFolder && node.expanded && (node.children?.length ?? 0) > 0 && (
          <div>
            {node.children?.map((child, index) => renderNode(child, depth + 1, [...path, index]))}
          </div>
        )}
      </div>
    );
  };

  const rootName = projectRoot ? projectRoot.replace(/\\/g, '/').split('/').pop() ?? '' : '';

  const renderTreeBody = () => {
    if (!projectRoot) {
      return (
        <div className="text-[#858585] text-sm">
          Папка не выбрана. Откройте проект или папку, чтобы увидеть структуру.
        </div>
      );
    }

    if (treeLoading) {
      return <div className="text-[#858585] text-sm">Загрузка дерева проекта...</div>;
    }

    if (treeError) {
      return (
        <div className="text-sm text-red-400">
          Ошибка загрузки дерева: {treeError}
        </div>
      );
    }

    if (files.length === 0) {
      return (
        <div className="text-[#858585] text-sm">
          Проект открыт, но папка пуста или не содержит видимых файлов.
        </div>
      );
    }

    return files.map((node, index) => renderNode(node, 0, [index]));
  };

  return (
    <div className="flex flex-col h-full corex-sidebar-panel">
      <div className="px-4 py-3 border-b border-[var(--corex-border)]">
        <div className="flex items-center gap-2 text-[var(--corex-spark)] text-xs font-semibold uppercase tracking-wider">
          <FolderPlus className="w-4 h-4" />
          Проект
        </div>
        {projectRoot ? (
          <div className="mt-2">
            <div className="text-sm font-semibold text-[var(--corex-text)] break-words">{rootName}</div>
            <div className="text-xs text-[var(--corex-text-dim)] truncate break-all font-mono mt-0.5">{projectRoot}</div>
          </div>
        ) : (
          <div className="mt-2 text-sm text-[var(--corex-text-muted)]">Папка проекта не выбрана</div>
        )}
        <div className="mt-2 text-xs text-[var(--corex-text-dim)] break-words">
          Создание в: {selectedFolderPath === '.' ? 'корне проекта' : selectedFolderPath}
        </div>
        <div className="mt-3 space-y-2">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => startCreate('file')}
              disabled={createState.isSubmitting || !projectRoot}
              className="corex-icon-btn border border-[var(--corex-border)] disabled:cursor-not-allowed disabled:opacity-50"
              title="Создать файл"
            >
              <FilePlus className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => startCreate('folder')}
              disabled={createState.isSubmitting || !projectRoot}
              className="corex-icon-btn border border-[var(--corex-border)] disabled:cursor-not-allowed disabled:opacity-50"
              title="Создать папку"
            >
              <FolderPlus className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => void refreshFileTree()}
              disabled={!projectRoot || treeLoading}
              className="text-xs text-[var(--corex-text-dim)] hover:text-[var(--corex-text)] disabled:opacity-50"
              title="Обновить дерево"
            >
              Обновить
            </button>
          </div>
          {createState.type && (
            <div className="flex min-w-0 items-center gap-2 corex-surface rounded-lg px-2 py-1 text-sm text-[var(--corex-text)]">
              <input
                key={createFormKey}
                ref={createInputRef}
                autoFocus
                value={createState.name}
                onChange={(e) => setCreateState((prev) => ({ ...prev, name: e.target.value }))}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void submitCreate();
                  if (e.key === 'Escape') cancelCreate();
                }}
                placeholder={createState.type === 'file' ? 'Имя файла с расширением' : 'Имя папки'}
                className="min-w-0 flex-1 bg-transparent text-sm text-[#e5e9f0] outline-none placeholder:text-[#6b7280]"
              />
              <button type="button" onClick={() => void submitCreate()} disabled={createState.isSubmitting} className="inline-flex h-8 w-8 items-center justify-center rounded border border-[#212733]">
                <Check className="w-4 h-4" />
              </button>
              <button type="button" onClick={cancelCreate} disabled={createState.isSubmitting} className="inline-flex h-8 w-8 items-center justify-center rounded border border-[#212733]">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>

      <div key={treeKey} className="flex-1 overflow-y-auto p-3">
        {renderTreeBody()}
      </div>

      {contextMenu.visible && contextMenu.node && (
        <div
          style={{ left: contextMenu.x, top: contextMenu.y }}
          className="absolute z-50 bg-[#0b1220] border border-[#212733] rounded shadow-lg text-sm"
          onMouseLeave={() => setContextMenu({ visible: false, x: 0, y: 0 })}
        >
          <button
            className="block px-3 py-2 hover:bg-[#131824] w-48 text-left"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(contextMenu.node?.path ?? '');
                onNotification('Путь скопирован в буфер обмена');
              } catch {
                onNotification('Не удалось скопировать');
              }
              setContextMenu({ visible: false, x: 0, y: 0 });
            }}
          >
            Копировать путь
          </button>
          <button
            className="block px-3 py-2 hover:bg-[#131824] w-48 text-left"
            onClick={async () => {
              const node = contextMenu.node;
              if (!node?.path || !node?.name) {
                setContextMenu({ visible: false, x: 0, y: 0 });
                return;
              }

              const copyName = node.name + '_copy';
              try {
                const r = await fetchApi(`/api/files/read?path=${encodeURIComponent(node.path)}`);
                const d = await r.json();
                const content = d?.content ?? '';
                const targetPath = node.path.replace(/[^/]+$/, copyName);
                const w = await fetchApi('/api/files/create', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ path: targetPath, content }),
                });
                const wj = await w.json();
                if (wj?.success) {
                  onNotification('Файл продублирован');
                  await refreshFileTree();
                } else {
                  onNotification('Ошибка: ' + (wj?.error ?? 'Unknown'));
                }
              } catch {
                onNotification('Ошибка при дублировании файла');
              }
              setContextMenu({ visible: false, x: 0, y: 0 });
            }}
          >
            Дублировать
          </button>
          <button
            className="block px-3 py-2 hover:bg-[#131824] w-48 text-left text-destructive"
            onClick={() => {
              if (contextMenu.node) {
                setConfirmDeleteNode(contextMenu.node);
              }
            }}
          >
            Удалить
          </button>
          {confirmDeleteNode?.path === contextMenu.node?.path && (
            <div className="border-t border-[#212733] px-3 py-2">
              <div className="text-xs text-[#9aa4bf] mb-2">Подтвердите удаление элемента</div>
              <div className="flex gap-2">
                <button className="flex-1 rounded bg-[#b91c1c] px-3 py-2 text-left text-xs font-semibold text-white" onClick={() => void handleConfirmDelete()}>
                  Удалить
                </button>
                <button className="flex-1 rounded border border-[#212733] px-3 py-2 text-left text-xs" onClick={() => setConfirmDeleteNode(null)}>
                  Отмена
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
