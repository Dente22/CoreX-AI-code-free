import { describe, expect, it } from 'vitest';
import { isNewerVersion, normalizeVersion } from './appVersion';

describe('appVersion utils', () => {
  it('normalizes versions with or without v prefix', () => {
    expect(normalizeVersion('v1.2.3')).toBe('1.2.3');
    expect(normalizeVersion('1.2.3')).toBe('1.2.3');
  });

  it('detects newer patch and minor versions', () => {
    expect(isNewerVersion('1.2.4', '1.2.3')).toBe(true);
    expect(isNewerVersion('1.3.0', '1.2.9')).toBe(true);
  });

  it('does not treat same or older versions as newer', () => {
    expect(isNewerVersion('1.2.3', '1.2.3')).toBe(false);
    expect(isNewerVersion('1.2.2', '1.2.3')).toBe(false);
  });
});
