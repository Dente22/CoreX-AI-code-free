import { describe, expect, it } from 'vitest';
import { folderNameFromRemote, isAllowedGitRemote } from './gitClone';

describe('isAllowedGitRemote', () => {
  it('accepts https and ssh remotes', () => {
    expect(isAllowedGitRemote('https://github.com/Dente22/CoreX-AI-code-free.git')).toBe(true);
    expect(isAllowedGitRemote('git@github.com:Dente22/CoreX-AI-code-free.git')).toBe(true);
  });

  it('rejects unsafe remotes', () => {
    expect(isAllowedGitRemote('http://github.com/user/repo')).toBe(false);
    expect(isAllowedGitRemote('file:///C:/secret')).toBe(false);
    expect(isAllowedGitRemote('https://user:pass@github.com/user/repo')).toBe(false);
  });
});

describe('folderNameFromRemote', () => {
  it('uses the repo name without .git', () => {
    expect(folderNameFromRemote('https://github.com/acme/demo.git')).toBe('demo');
    expect(folderNameFromRemote('git@github.com:acme/demo.git')).toBe('demo');
  });
});
