'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const pngToIco = require('png-to-ico').default || require('png-to-ico');

function exists(filePath) {
  try {
    return fs.existsSync(filePath);
  } catch {
    return false;
  }
}

function resolvePython(frontendRoot) {
  const candidates = [
    path.join(frontendRoot, '..', '.venv', 'Scripts', 'python.exe'),
    path.join(frontendRoot, '..', '.venv-1', 'Scripts', 'python.exe'),
    process.env.COREX_PYTHON,
    path.join(frontendRoot, 'vendor', 'python', 'Scripts', 'python.exe'),
    process.platform === 'win32' ? 'py' : 'python3',
    'python',
  ].filter(Boolean);

  for (const candidate of candidates) {
    const isLauncher = candidate === 'py' || candidate === 'python' || candidate === 'python3';
    if (!isLauncher && !exists(candidate)) {
      continue;
    }

    const probeArgs = isLauncher
      ? candidate === 'py'
        ? ['-3.13', '-c', 'import sys; print(sys.executable)']
        : ['-c', 'import sys; print(sys.executable)']
      : ['-c', 'import sys; print(sys.executable)'];

    const probe = spawnSync(candidate, probeArgs, {
      encoding: 'utf8',
      windowsHide: true,
      shell: false,
    });
    if (probe.status === 0) {
      return candidate;
    }
  }
  return null;
}

function resolvePngSource(buildDir) {
  const generated = path.join(buildDir, 'icon-source.png');
  if (exists(generated)) {
    return generated;
  }

  if (process.env.COREX_ICON_SOURCE && exists(process.env.COREX_ICON_SOURCE)) {
    return process.env.COREX_ICON_SOURCE;
  }

  const publicIcon = path.join(buildDir, '..', 'public', 'corex-icon.png');
  if (exists(publicIcon)) {
    return publicIcon;
  }

  throw new Error(
    'Icon PNG not found. Run npm run icons (sync-logo generates build/icon-source.png from public/corex-logo.svg).',
  );
}

function runTransparent(python, script, rawPng, destPng) {
  const args =
    process.platform === 'win32' && python === 'py'
      ? ['-3.13', script, rawPng, destPng]
      : [script, rawPng, destPng];
  return spawnSync(python, args, {
    stdio: 'inherit',
    windowsHide: true,
    shell: false,
  });
}

async function main() {
  const root = path.join(__dirname, '..');
  const buildDir = path.join(root, 'build');
  const publicDir = path.join(root, 'public');
  const sourceSvg = path.join(publicDir, 'corex-logo.svg');

  fs.mkdirSync(buildDir, { recursive: true });

  if (exists(sourceSvg)) {
    fs.copyFileSync(sourceSvg, path.join(buildDir, 'icon.svg'));
  }

  const pngPath = resolvePngSource(buildDir);
  console.log('[CoreX] Icon PNG source:', pngPath);

  const rawPng = path.join(buildDir, 'icon-raw.png');
  const destPng = path.join(buildDir, 'icon.png');
  const publicPng = path.join(publicDir, 'corex-icon.png');
  fs.copyFileSync(pngPath, rawPng);

  const python = resolvePython(root);
  const transparentScript = path.join(__dirname, 'icon_transparent.py');
  let transparentOk = false;

  if (python) {
    console.log('[CoreX] Icon Python:', python);
    // Pillow может отсутствовать в venv — ставим тихо, без падения всего запуска.
    spawnSync(
      python,
      process.platform === 'win32' && python === 'py'
        ? ['-3.13', '-m', 'pip', 'install', 'pillow', '-q']
        : ['-m', 'pip', 'install', 'pillow', '-q'],
      { stdio: 'ignore', windowsHide: true, shell: false },
    );
    const transparent = runTransparent(python, transparentScript, rawPng, destPng);
    transparentOk = transparent.status === 0;
    if (!transparentOk) {
      console.warn('[CoreX] icon_transparent.py failed — using source PNG as-is');
    }
  } else {
    console.warn('[CoreX] Python not found for icon transparency — using source PNG as-is');
  }

  if (!transparentOk) {
    fs.copyFileSync(rawPng, destPng);
  }

  fs.copyFileSync(destPng, publicPng);

  const ico = await pngToIco(destPng);
  fs.writeFileSync(path.join(buildDir, 'icon.ico'), ico);
  console.log('[CoreX] Icons ready:', path.join(buildDir, 'icon.ico'));
}

main().catch((error) => {
  console.error('[CoreX] prepare-icons failed:', error.message);
  process.exit(1);
});
