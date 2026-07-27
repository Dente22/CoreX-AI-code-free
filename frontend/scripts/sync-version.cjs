const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '..');
const projectRoot = path.resolve(frontendRoot, '..');
const packageJsonPath = path.join(frontendRoot, 'package.json');

const pkg = JSON.parse(fs.readFileSync(packageJsonPath, 'utf-8'));
const version = String(pkg.version || '0.0.1');

const backendVersionPath = path.join(projectRoot, 'backend', 'core', 'app_version.py');
const frontendVersionPath = path.join(frontendRoot, 'src', 'app', 'utils', 'appVersion.generated.ts');

fs.writeFileSync(
  backendVersionPath,
  `"""CoreX backend app version."""\n\nAPP_VERSION = "${version}"\n`,
  'utf-8',
);

fs.writeFileSync(
  frontendVersionPath,
  `export const APP_VERSION = "${version}";\n`,
  'utf-8',
);

console.log(`[CoreX] Synced app version: ${version}`);
