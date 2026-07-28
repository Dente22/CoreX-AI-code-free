'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const { getNsisThemePaths } = require('./nsisThemeConfig.cjs');

function exists(p) {
  try {
    return fs.existsSync(p);
  } catch {
    return false;
  }
}

function run(cmd, args) {
  const result = spawnSync(cmd, args, {
    stdio: 'inherit',
    shell: false,
  });
  if (result.status !== 0) {
    throw new Error(`${cmd} ${args.join(' ')} failed with code ${result.status}`);
  }
}

function main() {
  const frontendRoot = path.join(__dirname, '..');
  const buildDir = path.join(frontendRoot, 'build');

  const iconPng = path.join(buildDir, 'icon.png');
  if (!exists(iconPng)) {
    throw new Error(`Missing ${iconPng}. Run npm run icons first.`);
  }

  const pythonExe = path.join(frontendRoot, 'vendor', 'python', 'Scripts', 'python.exe');
  if (!exists(pythonExe)) {
    throw new Error(
      `Embedded Python not found at ${pythonExe}. Run npm run python:embed first.`,
    );
  }

  const { installerHeader, installerSidebar, uninstallerSidebar } = getNsisThemePaths({
    buildDir,
  });

  const outDir = path.dirname(installerHeader);
  fs.mkdirSync(outDir, { recursive: true });

  const code = `
import os, sys
from PIL import Image

iconPng = r'''${iconPng}'''
installerHeader = r'''${installerHeader}'''
installerSidebar = r'''${installerSidebar}'''
uninstallerSidebar = r'''${uninstallerSidebar}'''

bg = (12, 22, 46)  # #0C162E

icon = Image.open(iconPng).convert('RGBA')

def paste_center(canvas_size, target_size, out_path):
    canvas = Image.new('RGB', canvas_size, bg)
    logo = icon.resize(target_size, Image.LANCZOS)
    x = (canvas_size[0] - target_size[0]) // 2
    y = (canvas_size[1] - target_size[1]) // 2
    canvas.paste(logo, (x, y), logo)
    canvas.save(out_path, format='BMP')

paste_center((150, 57), (64, 64), installerHeader)
paste_center((164, 314), (88, 88), installerSidebar)
paste_center((164, 314), (88, 88), uninstallerSidebar)
print('NSIS theme BMP ready:', os.path.dirname(installerHeader))
`;

  // Install Pillow if needed (first run only).
  const preflightCode = `
try:
    from PIL import Image
    print('pillow-ok')
except Exception:
    import subprocess, sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pillow'])
`;

  run(pythonExe, ['-c', preflightCode]);
  run(pythonExe, ['-c', code]);
}

main();

