import { isCorexInternalPath } from './corexInternal';

export interface GitFileStatus {
  path: string;
  name: string;
  index: string;
  worktree: string;
  staged: boolean;
  unstaged: boolean;
  untracked: boolean;
}

export interface GitStatusPayload {
  success?: boolean;
  error?: string;
  is_repo?: boolean;
  branch?: string;
  files?: GitFileStatus[];
  has_origin?: boolean;
  upstream?: boolean;
  staged_count?: number;
  unstaged_count?: number;
  committed?: boolean;
  pushed?: boolean;
}

export function gitChangeLetter(file: GitFileStatus): string {
  if (file.untracked) {
    return 'U';
  }
  const mark = file.staged ? file.index : file.worktree;
  if (mark === 'M') {
    return 'M';
  }
  if (mark === 'A') {
    return 'A';
  }
  if (mark === 'D') {
    return 'D';
  }
  if (mark === 'R') {
    return 'R';
  }
  return mark.trim() || 'M';
}

export function splitGitFiles(files: GitFileStatus[] | undefined): {
  staged: GitFileStatus[];
  changes: GitFileStatus[];
} {
  const list = (files ?? []).filter((file) => !isCorexInternalPath(file.path));
  return {
    staged: list.filter((file) => file.staged),
    changes: list.filter((file) => file.unstaged),
  };
}
