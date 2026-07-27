/**
 * Shared path helper for NSIS theme assets.
 * Used by unit tests and by prepare-*.cjs scripts.
 */
function getNsisThemePaths(options = {}) {
  const buildDir = String(options.buildDir || 'build').replace(/\\/g, '/');

  return {
    installerHeader: `${buildDir}/nsis/installerHeader.bmp`,
    installerSidebar: `${buildDir}/nsis/installerSidebar.bmp`,
    uninstallerSidebar: `${buildDir}/nsis/uninstallerSidebar.bmp`,
  };
}

module.exports = {
  getNsisThemePaths,
};

