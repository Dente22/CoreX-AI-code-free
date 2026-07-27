import { describe, expect, it } from 'vitest';
import { extractVersionFromInstallerName, isInstallerForCoreX } from './installerUpdate';

describe('installerUpdate utils', () => {
  it('recognizes CoreX installer filenames', () => {
    expect(isInstallerForCoreX('CoreX-Setup-1.2.3.exe')).toBe(true);
    expect(isInstallerForCoreX('OtherApp-Setup-1.2.3.exe')).toBe(false);
  });

  it('extracts semantic version from installer filename', () => {
    expect(extractVersionFromInstallerName('CoreX-Setup-1.2.3.exe')).toBe('1.2.3');
    expect(extractVersionFromInstallerName('CoreX-Setup-2.0.0-beta.exe')).toBe('2.0.0');
  });

  it('returns empty version for non-matching filenames', () => {
    expect(extractVersionFromInstallerName('random-file.exe')).toBe('');
  });
});
