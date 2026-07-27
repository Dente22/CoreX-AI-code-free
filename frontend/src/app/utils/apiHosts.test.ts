import { describe, expect, it } from 'vitest';
import { resolveApiHosts } from './apiHosts';

describe('resolveApiHosts', () => {
  it('does not fall back to port 8000 in Electron mode', () => {
    expect(resolveApiHosts('http://127.0.0.1:8011', true)).toEqual([
      'http://127.0.0.1:8011',
    ]);
  });

  it('keeps dev fallbacks outside Electron', () => {
    expect(resolveApiHosts(null, false)).toEqual([
      'http://127.0.0.1:8000',
      'http://localhost:8000',
    ]);
  });
});
