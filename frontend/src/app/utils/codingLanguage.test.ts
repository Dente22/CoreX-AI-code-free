import { describe, expect, it } from 'vitest';
import { CODING_LANGUAGES, languageLabel } from './codingLanguage';

describe('codingLanguage', () => {
  it('lists auto plus the supported languages', () => {
    expect(CODING_LANGUAGES.map((item) => item.id)).toEqual([
      'auto',
      'python',
      'javascript',
      'html',
      'css',
      'typescript',
      'react',
    ]);
  });

  it('shows a Russian label for the picker', () => {
    expect(languageLabel('python')).toBe('Python');
    expect(languageLabel('auto')).toBe('Авто');
    expect(languageLabel('unknown')).toBe('Авто');
  });
});
