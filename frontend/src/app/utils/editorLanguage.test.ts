import { describe, it, expect } from 'vitest';
import { getLanguageFromFilename } from './editorLanguage';

describe('getLanguageFromFilename', () => {
  it('maps web files', () => {
    expect(getLanguageFromFilename('index.html')).toBe('html');
    expect(getLanguageFromFilename('styles.css')).toBe('css');
    expect(getLanguageFromFilename('app.js')).toBe('javascript');
    expect(getLanguageFromFilename('App.tsx')).toBe('typescript');
  });

  it('maps python and json', () => {
    expect(getLanguageFromFilename('main.py')).toBe('python');
    expect(getLanguageFromFilename('package.json')).toBe('json');
  });

  it('falls back to plaintext', () => {
    expect(getLanguageFromFilename('README')).toBe('plaintext');
  });
});
