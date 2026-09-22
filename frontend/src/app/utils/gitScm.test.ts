import { describe, expect, it } from 'vitest';
import { gitChangeLetter, splitGitFiles, type GitFileStatus } from './gitScm';

const file = (partial: Partial<GitFileStatus>): GitFileStatus => ({
  path: 'a.ts',
  name: 'a.ts',
  index: ' ',
  worktree: 'M',
  staged: false,
  unstaged: true,
  untracked: false,
  ...partial,
});

describe('gitChangeLetter', () => {
  it('marks untracked and staged separately', () => {
    expect(gitChangeLetter(file({ untracked: true, unstaged: true }))).toBe('U');
    expect(gitChangeLetter(file({ staged: true, unstaged: false, index: 'A', worktree: ' ' }))).toBe('A');
  });
});

describe('splitGitFiles', () => {
  it('splits staged and working tree lists', () => {
    const split = splitGitFiles([
      file({ path: 'staged.ts', staged: true, unstaged: false, index: 'M', worktree: ' ' }),
      file({ path: 'dirty.ts' }),
    ]);
    expect(split.staged.map((item) => item.path)).toEqual(['staged.ts']);
    expect(split.changes.map((item) => item.path)).toEqual(['dirty.ts']);
  });

  it('hides the internal chat folder', () => {
    const split = splitGitFiles([
      file({ path: 'chat/project_memory.md', untracked: true, unstaged: true }),
      file({ path: 'app.ts' }),
    ]);
    expect(split.changes.map((item) => item.path)).toEqual(['app.ts']);
  });
});
