import { describe, expect, it } from 'vitest';
import { groupSearchHits, splitSearchSnippet } from './fileSearch';

describe('groupSearchHits', () => {
  it('keeps file order and groups lines', () => {
    const groups = groupSearchHits([
      { path: 'a.ts', name: 'a.ts', line: 1, text: 'one' },
      { path: 'b.ts', name: 'b.ts', line: 4, text: 'two' },
      { path: 'a.ts', name: 'a.ts', line: 8, text: 'three' },
    ]);
    expect(groups.map((group) => group.path)).toEqual(['a.ts', 'b.ts']);
    expect(groups[0].hits.map((hit) => hit.line)).toEqual([1, 8]);
  });

  it('hides hits from the internal chat folder', () => {
    const groups = groupSearchHits([
      { path: 'src/app.ts', name: 'app.ts', line: 1, text: 'hit' },
      { path: 'chat/project_memory.md', name: 'project_memory.md', line: 4, text: 'hit' },
    ]);
    expect(groups.map((group) => group.path)).toEqual(['src/app.ts']);
  });
});

describe('splitSearchSnippet', () => {
  it('splits around a case-insensitive match', () => {
    expect(splitSearchSnippet('Hello WORLD today', 'world')).toEqual({
      before: 'Hello ',
      match: 'WORLD',
      after: ' today',
    });
  });
});
