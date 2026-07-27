'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const frontendRoot = path.join(__dirname, '..');
const repoRoot = path.join(frontendRoot, '..');
const sourceSvg = path.join(frontendRoot, 'public', 'corex-logo.svg');

function copySvg(targetPath) {
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  fs.copyFileSync(sourceSvg, targetPath);
}

function runResvg(outputPath, fitWidth) {
  const args = ['--yes', '@resvg/resvg-js-cli'];
  if (fitWidth) {
    args.push('--fit-width', String(fitWidth));
  }
  args.push(sourceSvg, outputPath);

  const result = spawnSync('npx', args, {
    cwd: frontendRoot,
    stdio: 'inherit',
    shell: true,
  });
  if (result.status !== 0) {
    throw new Error(`resvg failed for ${outputPath}`);
  }
}

function main() {
  if (!fs.existsSync(sourceSvg)) {
    throw new Error(`Missing source SVG: ${sourceSvg}`);
  }

  const svgTargets = [
    path.join(frontendRoot, 'build', 'icon.svg'),
    path.join(repoRoot, 'ui-design-backup', 'public', 'corex-logo.svg'),
    path.join(repoRoot, 'ui-design-backup', 'build', 'icon.svg'),
  ];

  for (const target of svgTargets) {
    copySvg(target);
    console.log('[CoreX] SVG synced:', target);
  }

  const logoPng = path.join(frontendRoot, 'public', 'corex-logo.png');
  const iconSource = path.join(frontendRoot, 'build', 'icon-source.png');
  const publicIcon = path.join(frontendRoot, 'public', 'corex-icon.png');
  const legacyAsset = path.join(
    process.env.USERPROFILE || '',
    '.cursor',
    'projects',
    'c-Users-Paapa-Documents-Project-Project-CoreX',
    'assets',
    'corex-icon-1024.png',
  );

  runResvg(logoPng, 256);
  runResvg(iconSource, 1024);
  runResvg(publicIcon, 1024);
  if (legacyAsset) {
    fs.mkdirSync(path.dirname(legacyAsset), { recursive: true });
    fs.copyFileSync(iconSource, legacyAsset);
  }
  console.log('[CoreX] PNG generated:', logoPng);
  console.log('[CoreX] PNG generated:', iconSource);
  console.log('[CoreX] PNG generated:', publicIcon);
}

main();
