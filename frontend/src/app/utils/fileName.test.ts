import { describe, expect, it } from 'vitest';
import { filenameHasExtension } from './fileName';

describe('filenameHasExtension', () => {
  it('allows name.ext and dotfiles', () => {
    expect(filenameHasExtension('snake.py')).toBe(true);
    expect(filenameHasExtension('test1/app.py')).toBe(true);
    expect(filenameHasExtension('.env')).toBe(true);
  });

  it('rejects a bare name', () => {
    expect(filenameHasExtension('test')).toBe(false);
    expect(filenameHasExtension('test1')).toBe(false);
    expect(filenameHasExtension('readme.')).toBe(false);
  });
});
