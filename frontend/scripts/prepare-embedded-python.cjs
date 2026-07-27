'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

function exists(p) {
  try {
    return fs.existsSync(p);
  } catch {
    return false;
  }
}

function run(cmd, args, opts = {}) {
  const result = spawnSync(cmd, args, {
    stdio: 'inherit',
    // Keep shell off so Windows does not split python -c arguments on commas.
    shell: false,
    ...opts,
  });
  if (result.status !== 0) {
    throw new Error(`${cmd} ${args.join(' ')} failed with code ${result.status}`);
  }
}

function main() {
  if (process.env.COREX_SKIP_EMBEDDED_PYTHON === '1') {
    console.log('[CoreX] Skipping embedded Python (COREX_SKIP_EMBEDDED_PYTHON=1)');
    return;
  }

  const frontendRoot = path.join(__dirname, '..');
  const repoRoot = path.join(frontendRoot, '..');
  const outDir = path.join(frontendRoot, 'vendor', 'python');
  const marker = path.join(outDir, '.corex-python-ready');
  const requirements = path.join(repoRoot, 'backend', 'requirements.txt');
  const force = process.argv.includes('--force') || process.env.COREX_FORCE_PYTHON === '1';

  if (!force && exists(marker) && exists(path.join(outDir, 'Scripts', 'python.exe'))) {
    console.log('[CoreX] Embedded Python already prepared:', outDir);
    return;
  }

  const pyExisting = path.join(outDir, 'Scripts', 'python.exe');
  if (!exists(pyExisting)) {
    if (exists(outDir)) {
      fs.rmSync(outDir, { recursive: true, force: true });
    }
    fs.mkdirSync(path.dirname(outDir), { recursive: true });

    const creators = [
      ['py', ['-3.13', '-m', 'venv', outDir, '--copies']],
      ['py', ['-3', '-m', 'venv', outDir, '--copies']],
      [path.join(repoRoot, '.venv', 'Scripts', 'python.exe'), ['-m', 'venv', outDir, '--copies']],
    ];

    let created = false;
    for (const [cmd, args] of creators) {
      if (cmd.includes('python.exe') && !exists(cmd)) continue;
      console.log('[CoreX] Creating embedded venv via', cmd, args.join(' '));
      const result = spawnSync(cmd, args, {
        stdio: 'inherit',
        shell: false,
      });
      if (result.status === 0) {
        created = true;
        break;
      }
    }
    if (!created) {
      throw new Error('Could not create embedded Python venv. Install Python 3.13.');
    }
  }

  const py = path.join(outDir, 'Scripts', 'python.exe');
  if (!exists(py)) {
    throw new Error(`venv python missing: ${py}`);
  }

  run(py, ['-m', 'pip', 'install', '--upgrade', 'pip']);
  run(py, ['-m', 'pip', 'install', '-r', requirements]);
  run(py, ['-c', 'import aiohttp, pydantic; print("embedded-ok")']);

  fs.writeFileSync(
    marker,
    JSON.stringify(
      {
        preparedAt: new Date().toISOString(),
        python: py,
        requirements,
      },
      null,
      2,
    ),
  );
  console.log('[CoreX] Embedded Python ready at', outDir);
}

main();