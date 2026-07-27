import { describe, it, expect } from 'vitest';

// eslint-disable-next-line @typescript-eslint/no-var-requires
const { getNsisThemePaths } = (() => {
  // Lazy require so RED fails with a clear "module not found" first.
  // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
  return require('./nsisThemeConfig.cjs');
})();

describe('nsisThemeConfig', () => {
  it('produces expected asset paths under frontend/build/nsis', () => {
    const paths = getNsisThemePaths({ buildDir: 'C:/repo/CoreX/frontend/build' });
    expect(paths.installerHeader).toBe(
      'C:/repo/CoreX/frontend/build/nsis/installerHeader.bmp',
    );
    expect(paths.installerSidebar).toBe(
      'C:/repo/CoreX/frontend/build/nsis/installerSidebar.bmp',
    );
    expect(paths.uninstallerSidebar).toBe(
      'C:/repo/CoreX/frontend/build/nsis/uninstallerSidebar.bmp',
    );
  });
});

