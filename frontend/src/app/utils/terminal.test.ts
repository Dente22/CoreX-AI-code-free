import { describe, it, expect } from 'vitest';
import { isRunnableFile } from './terminal';

describe('terminal.isRunnableFile', () => {
  it('marks html/css as runnable (open in browser)', () => {
    expect(isRunnableFile('index.html')).toBe(true);
    expect(isRunnableFile('style.css')).toBe(true);
    expect(isRunnableFile('page.htm')).toBe(true);
  });

  it('marks js/ts as runnable', () => {
    expect(isRunnableFile('app.js')).toBe(true);
    expect(isRunnableFile('app.ts')).toBe(true);
    expect(isRunnableFile('app.tsx')).toBe(true);
  });

  it('does not mark markdown as runnable', () => {
    expect(isRunnableFile('README.md')).toBe(false);
  });
});

