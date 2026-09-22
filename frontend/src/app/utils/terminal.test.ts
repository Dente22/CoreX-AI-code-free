import { describe, it, expect } from 'vitest';
import { isRunnableFile, isInteractiveRunnable } from './terminal';

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

describe('terminal.isInteractiveRunnable', () => {
  it('keeps python and js interactive', () => {
    expect(isInteractiveRunnable('main.py')).toBe(true);
    expect(isInteractiveRunnable('app.js')).toBe(true);
  });

  it('opens html/css without a stdin session', () => {
    expect(isInteractiveRunnable('index.html')).toBe(false);
    expect(isInteractiveRunnable('style.css')).toBe(false);
  });
});

