export interface FileNode {
  name: string;
  type: 'file' | 'folder';
  path: string;
  expanded?: boolean;
  children?: FileNode[];
}

const EXPANDED_FOLDERS_KEY_PREFIX = 'corex.expandedFolders.';

export function isValidFileTree(nodes: unknown): nodes is FileNode[] {
  if (!Array.isArray(nodes)) {
    return false;
  }

  return nodes.every((node) => {
    if (!node || typeof node !== 'object') {
      return false;
    }
    const n = node as FileNode;
    return (
      typeof n.name === 'string' &&
      typeof n.path === 'string' &&
      (n.type === 'file' || n.type === 'folder')
    );
  });
}

function normalizeNodeType(node: { type?: string; children?: unknown[] }): 'file' | 'folder' {
  if (node.type === 'folder' || node.type === 'directory') {
    return 'folder';
  }
  if ((node.children?.length ?? 0) > 0) {
    return 'folder';
  }
  return 'file';
}

export function convertApiNode(node: {
  name?: string;
  type?: string;
  path?: string;
  children?: ReturnType<typeof convertApiNode>[];
}): FileNode {
  const name = node.name ?? 'unknown';
  const nodeType = normalizeNodeType(node);
  return {
    name,
    type: nodeType,
    path: node.path ?? name,
    expanded: false,
    children: node.children?.map(convertApiNode),
  };
}

export function collectExpandedPaths(nodes: FileNode[]): Set<string> {
  const paths = new Set<string>();

  const walk = (items: FileNode[]) => {
    for (const node of items) {
      if (node.type === 'folder' && node.expanded) {
        paths.add(node.path);
      }
      if (node.children?.length) {
        walk(node.children);
      }
    }
  };

  walk(nodes);
  return paths;
}

export function applyExpandedPaths(nodes: FileNode[], expandedPaths: Set<string>): FileNode[] {
  return nodes.map((node) => {
    if (node.type !== 'folder') {
      return node;
    }

    return {
      ...node,
      expanded: expandedPaths.has(node.path),
      children: node.children ? applyExpandedPaths(node.children, expandedPaths) : undefined,
    };
  });
}

export function mergeTreePreservingExpansion(
  newNodes: FileNode[],
  expandedPaths: Set<string>,
): FileNode[] {
  return applyExpandedPaths(newNodes, expandedPaths);
}

export function loadExpandedFolders(projectRoot: string): Set<string> {
  if (!projectRoot) {
    return new Set();
  }

  try {
    const raw = window.localStorage.getItem(`${EXPANDED_FOLDERS_KEY_PREFIX}${projectRoot}`);
    if (!raw) {
      return new Set();
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return new Set();
    }
    return new Set(parsed.filter((p): p is string => typeof p === 'string'));
  } catch {
    return new Set();
  }
}

export function saveExpandedFolders(projectRoot: string, expandedPaths: Set<string>) {
  if (!projectRoot) {
    return;
  }

  try {
    window.localStorage.setItem(
      `${EXPANDED_FOLDERS_KEY_PREFIX}${projectRoot}`,
      JSON.stringify([...expandedPaths]),
    );
  } catch {
    // Ignore localStorage failures
  }
}

export function toggleExpandedInTree(nodes: FileNode[], targetPath: string): FileNode[] {
  return nodes.map((node) => {
    if (node.type !== 'folder') {
      return node;
    }

    if (node.path === targetPath) {
      return { ...node, expanded: !node.expanded };
    }

    if (node.children?.length) {
      return { ...node, children: toggleExpandedInTree(node.children, targetPath) };
    }

    return node;
  });
}
