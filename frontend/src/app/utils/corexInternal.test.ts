import { describe, expect, it } from 'vitest';
import { isCorexInternalEntryName, isCorexInternalPath } from './corexInternal';

describe('isCorexInternalPath', () => {
  it('hides the project chat folder and its files', () => {
    expect(isCorexInternalPath('chat')).toBe(true);
    expect(isCorexInternalPath('chat/project_memory.md')).toBe(true);
    expect(isCorexInternalPath('chat\\visio\\workflow.mmd')).toBe(true);
  });

  it('keeps ordinary project files', () => {
    expect(isCorexInternalPath('src/app.ts')).toBe(false);
    expect(isCorexInternalPath('src/chat/notes.md')).toBe(false);
    expect(isCorexInternalPath('')).toBe(false);
  });
});

describe('isCorexInternalEntryName', () => {
  it('matches the reserved folder name', () => {
    expect(isCorexInternalEntryName('chat')).toBe(true);
    expect(isCorexInternalEntryName('src')).toBe(false);
  });
});
