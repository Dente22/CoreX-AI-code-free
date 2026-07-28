import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { fetchApi } from '../utils/api';
import {
  collectExpandedPaths,
  convertApiNode,
  isValidFileTree,
  loadExpandedFolders,
  mergeTreePreservingExpansion,
  saveExpandedFolders,
  toggleExpandedInTree,
  type FileNode,
} from '../utils/fileTree';

interface FileTreeContextValue {
  fileTree: FileNode[];
  expandedFolders: Set<string>;
  treeLoading: boolean;
  treeError: string;
  treeVersion: number;
  isTreeValid: boolean;
  loadFileTree: (rootPath?: string) => Promise<void>;
  refreshFileTree: () => Promise<void>;
  toggleFolderExpanded: (path: string) => void;
  setExpandedFolders: (paths: Set<string>) => void;
}

const FileTreeContext = createContext<FileTreeContextValue | null>(null);

interface FileTreeProviderProps {
  projectRoot: string;
  hasProject: boolean;
  children: ReactNode;
}

export function FileTreeProvider({ projectRoot, hasProject, children }: FileTreeProviderProps) {
  const [fileTree, setFileTree] = useState<FileNode[]>([]);
  const [expandedFolders, setExpandedFoldersState] = useState<Set<string>>(new Set());
  const [treeLoading, setTreeLoading] = useState(false);
  const [treeError, setTreeError] = useState('');
  const [treeVersion, setTreeVersion] = useState(0);

  const isTreeValid = isValidFileTree(fileTree);

  const setExpandedFolders = useCallback(
    (paths: Set<string>) => {
      setExpandedFoldersState(paths);
      if (projectRoot) {
        saveExpandedFolders(projectRoot, paths);
      }
    },
    [projectRoot],
  );

  const loadFileTree = useCallback(
    async (rootPath = projectRoot) => {
      if (!rootPath) {
        setFileTree([]);
        setTreeError('');
        return;
      }

      setTreeLoading(true);
      setTreeError('');

      const savedExpanded = loadExpandedFolders(rootPath);

      try {
        const response = await fetchApi('/api/files/tree');
        if (!response.ok) {
          const text = await response.text();
          console.error('[FileTreeContext] Tree request failed:', response.status, text);
          setTreeError('Не удалось загрузить дерево файлов.');
          return;
        }

        const data = await response.json();

        if (!data?.success || !data?.tree) {
          const message = data?.error ?? 'Не удалось загрузить дерево файлов.';
          console.error('[FileTreeContext] Tree API error:', message);
          setTreeError(message);
          setFileTree([]);
          return;
        }

        const rawChildren = data.tree.children
          ? (data.tree.children as Parameters<typeof convertApiNode>[0][]).map(convertApiNode)
          : [convertApiNode(data.tree)];

        const merged = mergeTreePreservingExpansion(rawChildren, savedExpanded);

        if (!isValidFileTree(merged)) {
          setTreeError('Получены некорректные данные дерева.');
          setFileTree([]);
          setTreeVersion((prev) => prev + 1);
          return;
        }

        setExpandedFoldersState(savedExpanded);
        setFileTree(merged);
        setTreeVersion((prev) => prev + 1);
      } catch (error) {
        console.error('[FileTreeContext] Failed to load file tree:', error);
        setTreeError('Не удалось загрузить дерево файлов.');
        setFileTree([]);
      } finally {
        setTreeLoading(false);
      }
    },
    [projectRoot],
  );

  const refreshFileTree = useCallback(async () => {
    const currentExpanded = collectExpandedPaths(fileTree);
    const mergedPaths = new Set([...expandedFolders, ...currentExpanded]);
    setExpandedFolders(mergedPaths);

    if (!projectRoot) {
      return;
    }

    setTreeLoading(true);
    setTreeError('');

    try {
      const response = await fetchApi('/api/files/tree');
      if (!response.ok) {
        setTreeError('Не удалось обновить дерево файлов.');
        return;
      }

      const data = await response.json();
      if (!data?.success || !data?.tree) {
        setTreeError(data?.error ?? 'Не удалось обновить дерево файлов.');
        return;
      }

      const rawChildren = data.tree.children
        ? (data.tree.children as Parameters<typeof convertApiNode>[0][]).map(convertApiNode)
        : [convertApiNode(data.tree)];

      const merged = mergeTreePreservingExpansion(rawChildren, mergedPaths);

      if (!isValidFileTree(merged)) {
        setTreeError('Получены некорректные данные дерева.');
        setTreeVersion((prev) => prev + 1);
        return;
      }

      setFileTree(merged);
      setTreeVersion((prev) => prev + 1);
    } catch (error) {
      console.error('[FileTreeContext] Failed to refresh file tree:', error);
      setTreeError('Не удалось обновить дерево файлов.');
    } finally {
      setTreeLoading(false);
    }
  }, [fileTree, expandedFolders, projectRoot, setExpandedFolders]);

  const toggleFolderExpanded = useCallback(
    (path: string) => {
      setFileTree((prev) => {
        const next = toggleExpandedInTree(prev, path);
        const nextExpanded = collectExpandedPaths(next);
        setExpandedFoldersState(nextExpanded);
        if (projectRoot) {
          saveExpandedFolders(projectRoot, nextExpanded);
        }
        return next;
      });
    },
    [projectRoot],
  );

  useEffect(() => {
    if (!hasProject || !projectRoot) {
      setFileTree([]);
      setTreeError('');
      setExpandedFoldersState(new Set());
      return;
    }

    const saved = loadExpandedFolders(projectRoot);
    setExpandedFoldersState(saved);
    void loadFileTree(projectRoot);
  }, [hasProject, projectRoot, loadFileTree]);

  const value = useMemo(
    () => ({
      fileTree,
      expandedFolders,
      treeLoading,
      treeError,
      treeVersion,
      isTreeValid,
      loadFileTree,
      refreshFileTree,
      toggleFolderExpanded,
      setExpandedFolders,
    }),
    [
      fileTree,
      expandedFolders,
      treeLoading,
      treeError,
      treeVersion,
      isTreeValid,
      loadFileTree,
      refreshFileTree,
      toggleFolderExpanded,
      setExpandedFolders,
    ],
  );

  return <FileTreeContext.Provider value={value}>{children}</FileTreeContext.Provider>;
}

export function useFileTree() {
  const context = useContext(FileTreeContext);
  if (!context) {
    throw new Error('useFileTree must be used within FileTreeProvider');
  }
  return context;
}

export type { FileNode };
