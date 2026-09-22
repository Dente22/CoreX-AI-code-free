'use strict';

/**
 * Packaged Electron apps ship backend under process.resourcesPath.
 * Dev mode keeps the repo root (parent of frontend/).
 */
function resolveProjectRoot(options) {
  const joinPath = options.joinPath || require('path').join;
  if (options.isPackaged) {
    return options.resourcesPath;
  }
  return joinPath(options.dirname, '..');
}

function resolveEmbeddedPythonCandidates(options) {
  const joinPath = options.joinPath || require('path').join;
  if (options.platform === 'win32') {
    return [
      joinPath(options.resourcesPath, 'python', 'python.exe'),
      joinPath(options.resourcesPath, 'python', 'Scripts', 'python.exe'),
    ];
  }
  return [
    joinPath(options.resourcesPath, 'python', 'bin', 'python3'),
    joinPath(options.resourcesPath, 'python', 'bin', 'python'),
  ];
}

/**
 * Prefer embedded runtime when present, then COREX_PYTHON, then .venv, then OS launcher.
 * Never hard-require a missing embedded binary.
 */
function resolvePythonCommand(options) {
  const joinPath = options.joinPath || require('path').join;
  const existsSync = options.existsSync || (() => false);
  const env = options.env || {};

  if (options.isPackaged) {
    for (const candidate of resolveEmbeddedPythonCandidates(options)) {
      if (existsSync(candidate)) {
        return candidate;
      }
    }
  }

  if (env.COREX_PYTHON && String(env.COREX_PYTHON).trim()) {
    return String(env.COREX_PYTHON).trim();
  }

  if (options.projectRoot) {
    const venvPython =
      options.platform === 'win32'
        ? joinPath(options.projectRoot, '.venv', 'Scripts', 'python.exe')
        : joinPath(options.projectRoot, '.venv', 'bin', 'python');
    if (existsSync(venvPython)) {
      return venvPython;
    }
  }

  if (options.platform === 'win32') {
    return 'py';
  }
  return 'python3';
}

/**
 * Bare `py` on Windows often prefers the newest (beta) install.
 * Pin to 3.13 when using the launcher so CoreX deps resolve.
 */
function resolvePythonSpawnArgs(options) {
  const port = String(options.port);
  const base = [options.mainPy, '--mode', 'server', '--port', port];
  if (options.platform === 'win32' && options.pythonCommand === 'py') {
    return ['-3.13', ...base];
  }
  return base;
}

/**
 * Only poll a real update feed. Placeholder/example URLs must stay off
 * so packaged apps do not hang or log net::ERR_NAME_NOT_RESOLVED on launch.
 */
function shouldEnableAutoUpdates(options) {
  if (options.isDev) return false;
  const url = String(options.updateUrl || '').trim();
  if (!url) return false;
  if (/updates\.example\.com/i.test(url)) return false;
  return true;
}

/**
 * Keep health waits short so a broken system Python cannot freeze launch ~45s.
 * Embedded runtime gets a bit more room for cold start.
 */
function resolveBackendHealthTimeoutMs(options = {}) {
  if (options.hasEmbeddedPython) {
    return 18000;
  }
  return 8000;
}

/** Show the Electron window immediately; backend starts in parallel. */
function shouldOpenWindowBeforeBackend() {
  return true;
}

const CHROME_USER_AGENT =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

function isHttpUrl(value) {
  try {
    const parsed = new URL(String(value || ''));
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

function shouldOpenInSystemBrowser(input) {
  return Boolean(input && (input.ctrlKey || input.metaKey));
}

function shouldOpenAuthInSystemBrowser(value) {
  try {
    const parsed = new URL(String(value || ''));
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return false;
    }
    const host = parsed.hostname.toLowerCase();
    if (host === 'accounts.google.com' || host.endsWith('.accounts.google.com')) {
      return true;
    }
    if (host === 'accounts.youtube.com' || host === 'oauth2.googleapis.com') {
      return true;
    }
    return /^accounts\.google\.[a-z.]+$/.test(host);
  } catch {
    return false;
  }
}

function isOllamaLaunchSkippable(data) {
  if (!data || data.ready === true) {
    return false;
  }
  if (data.skippable === true) {
    return true;
  }
  return data.phase === 'ollama_server';
}

const COREX_OLLAMA_PORT = 11435;
const DESKTOP_OLLAMA_PORT = 11434;
const SHUTDOWN_HTTP_TIMEOUT_MS = 2500;
const SHUTDOWN_KILL_TIMEOUT_MS = 5000;

function parseWindowsListeningPid(netstatText, port) {
  const targetPort = Number(port);
  if (!Number.isFinite(targetPort) || targetPort <= 0) {
    return null;
  }
  const token = `:${targetPort}`;
  const lines = String(netstatText || '').split(/\r?\n/);
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || !line.toUpperCase().includes('LISTENING')) {
      continue;
    }
    const parts = line.split(/\s+/);
    const localAddress = parts[1] || '';
    if (!localAddress.endsWith(token)) {
      continue;
    }
    const pid = Number(parts[parts.length - 1]);
    if (Number.isFinite(pid) && pid > 0) {
      return pid;
    }
  }
  return null;
}

function killPidTreeSync(pid, options = {}) {
  const normalized = Number(pid);
  if (!Number.isFinite(normalized) || normalized <= 0) {
    return false;
  }
  const spawnSync = options.spawnSync || require('child_process').spawnSync;
  const platform = options.platform || process.platform;
  if (platform === 'win32') {
    const result = spawnSync(
      'taskkill',
      ['/PID', String(normalized), '/T', '/F'],
      { windowsHide: true, stdio: 'ignore' },
    );
    return result.status === 0 || result.status === 128;
  }
  try {
    process.kill(normalized, 'SIGTERM');
    return true;
  } catch {
    return false;
  }
}

function findListeningPidSync(port, options = {}) {
  const platform = options.platform || process.platform;
  if (platform !== 'win32') {
    return null;
  }
  const spawnSync = options.spawnSync || require('child_process').spawnSync;
  const result = spawnSync('netstat', ['-ano'], {
    encoding: 'utf8',
    windowsHide: true,
  });
  if (result.error || result.status !== 0) {
    return null;
  }
  return parseWindowsListeningPid(result.stdout, port);
}

function killCoreXOllamaSync(options = {}) {
  const rootPid = findListeningPidSync(options.port || COREX_OLLAMA_PORT, options);
  if (!rootPid) {
    return false;
  }

  const rows = listWindowsProcessesSync(options);
  const targets = collectDescendantPids(rootPid, rows);
  targets.add(rootPid);

  let killed = false;
  for (const pid of targets) {
    killed = killPidTreeSync(pid, options) || killed;
  }
  return killed;
}

function parsePowerShellProcessRows(stdout) {
  const rows = [];
  const trimmed = String(stdout || '').trim();
  if (!trimmed) {
    return rows;
  }
  let payload;
  try {
    payload = JSON.parse(trimmed);
  } catch {
    return rows;
  }
  const items = Array.isArray(payload) ? payload : [payload];
  for (const item of items) {
    if (!item || typeof item !== 'object') {
      continue;
    }
    const name = String(item.Name || '').trim();
    const parentPid = Number(item.ParentProcessId);
    const pid = Number(item.ProcessId);
    if (!name || !Number.isFinite(pid) || pid <= 0) {
      continue;
    }
    rows.push({
      name,
      parentPid: Number.isFinite(parentPid) ? parentPid : 0,
      pid,
    });
  }
  return rows;
}

function parseWmicProcessRows(stdout) {
  const rows = [];
  for (const rawLine of String(stdout || '').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.toLowerCase().startsWith('node,')) {
      continue;
    }
    const parts = line.split(',');
    if (parts.length < 4) {
      continue;
    }
    const name = String(parts[1] || '').trim();
    const parentPid = Number(parts[2]);
    const pid = Number(parts[3]);
    if (!name || !Number.isFinite(pid) || pid <= 0) {
      continue;
    }
    rows.push({
      name,
      parentPid: Number.isFinite(parentPid) ? parentPid : 0,
      pid,
    });
  }
  return rows;
}

function listWindowsProcessesSync(options = {}) {
  const platform = options.platform || process.platform;
  if (platform !== 'win32') {
    return [];
  }
  const spawnSync = options.spawnSync || require('child_process').spawnSync;
  const ps = spawnSync(
    'powershell',
    [
      '-NoProfile',
      '-ExecutionPolicy',
      'Bypass',
      '-Command',
      'Get-CimInstance Win32_Process | Select-Object Name,ParentProcessId,ProcessId | ConvertTo-Json -Compress',
    ],
    { encoding: 'utf8', windowsHide: true },
  );
  if (!ps.error && ps.status === 0 && String(ps.stdout || '').trim()) {
    const rows = parsePowerShellProcessRows(ps.stdout);
    if (rows.length > 0) {
      return rows;
    }
  }
  const result = spawnSync(
    'wmic',
    ['process', 'get', 'Name,ParentProcessId,ProcessId', '/FORMAT:CSV'],
    { encoding: 'utf8', windowsHide: true },
  );
  if (result.error || result.status !== 0) {
    return [];
  }
  return parseWmicProcessRows(result.stdout);
}

function collectDescendantPids(rootPid, rows) {
  const descendants = new Set();
  const normalizedRoot = Number(rootPid);
  if (!Number.isFinite(normalizedRoot) || normalizedRoot <= 0) {
    return descendants;
  }
  const stack = [normalizedRoot];
  while (stack.length > 0) {
    const current = stack.pop();
    for (const row of rows) {
      if (row.parentPid === current && !descendants.has(row.pid)) {
        descendants.add(row.pid);
        stack.push(row.pid);
      }
    }
  }
  return descendants;
}

function killZombieLlamaServersSync(options = {}) {
  const rows = listWindowsProcessesSync(options);
  if (!rows.length) {
    return false;
  }
  const desktopPid = findListeningPidSync(options.desktopPort || DESKTOP_OLLAMA_PORT, options);
  const protectedPids = new Set();
  if (desktopPid) {
    protectedPids.add(desktopPid);
    for (const pid of collectDescendantPids(desktopPid, rows)) {
      protectedPids.add(pid);
    }
  }

  let killed = false;
  for (const row of rows) {
    if (String(row.name || '').toLowerCase() !== 'llama-server.exe') {
      continue;
    }
    if (protectedPids.has(row.pid)) {
      continue;
    }
    killed = killPidTreeSync(row.pid, options) || killed;
  }
  return killed;
}

function killResidualLlamaServersSync(options = {}) {
  return killZombieLlamaServersSync(options);
}

function killCoreXRuntimeSync(options = {}) {
  killCoreXOllamaSync(options);
  killZombieLlamaServersSync(options);
  return true;
}

/**
 * Hybrid Intel+NVIDIA: keep the Chromium window on the iGPU.
 * Pinning the UI to NVIDIA made both GPUs busy (dGPU renders, iGPU copies
 * frames to the display) and stole T600 time from Ollama.
 */
function preferIntegratedGpuForUi(options = {}) {
  const platform = options.platform || process.platform;
  if (platform !== 'win32') {
    return { applied: false };
  }
  const commandLine = options.commandLine;
  if (commandLine && typeof commandLine.appendSwitch === 'function') {
    commandLine.appendSwitch('force_low_power_gpu');
  }
  const spawnFn = options.spawn;
  const execPath = options.execPath;
  if (execPath && typeof spawnFn === 'function') {
    try {
      const child = spawnFn(
        'reg',
        [
          'add',
          'HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences',
          '/v',
          String(execPath),
          '/t',
          'REG_SZ',
          '/d',
          'GpuPreference=1;',
          '/f',
        ],
        { windowsHide: true, stdio: 'ignore', detached: true },
      );
      if (child && typeof child.unref === 'function') {
        child.unref();
      }
    } catch (_error) {
      // Graphics preference is best-effort; the window still opens.
    }
  }
  return { applied: true };
}

const PYTHON311_INSTALLER_URL = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe';

function resolveAiderSidecarPath(options) {
  const joinPath = options.joinPath || require('path').join;
  const root = options.projectRoot || '';
  if (options.platform === 'win32') {
    return joinPath(root, '.venv-aider', 'Scripts', 'aider.exe');
  }
  return joinPath(root, '.venv-aider', 'bin', 'aider');
}

function listAiderPythonCandidates(options) {
  const joinPath = options.joinPath || require('path').join;
  const localAppData = options.localAppData || '';
  const programFiles = options.programFiles || '';
  const candidates = [];
  if (options.platform !== 'win32') {
    return candidates;
  }
  for (const ver of ['Python311', 'Python312', 'Python310']) {
    if (localAppData) {
      candidates.push(joinPath(localAppData, 'Programs', 'Python', ver, 'python.exe'));
    }
    if (programFiles) {
      candidates.push(joinPath(programFiles, ver, 'python.exe'));
    }
  }
  candidates.push('C:\\Python311\\python.exe');
  return candidates;
}

function probeAiderLaunchEnv(options) {
  const existsSync = options.existsSync || (() => false);
  const aiderPath = resolveAiderSidecarPath(options);
  if (existsSync(aiderPath)) {
    return { ready: true, need: null, aiderPath };
  }

  let pythonPath = '';
  const execFileSync = options.execFileSync;
  if (typeof execFileSync === 'function' && options.platform === 'win32') {
    for (const ver of ['-3.11', '-3.12', '-3.10']) {
      try {
        const out = String(
          execFileSync('py', [ver, '-c', 'import sys; print(sys.executable)'], {
            encoding: 'utf8',
            timeout: 8000,
            windowsHide: true,
          }),
        ).trim();
        if (out && existsSync(out)) {
          pythonPath = out;
          break;
        }
      } catch {
        // py launcher / version missing
      }
    }
  }
  if (!pythonPath) {
    pythonPath = listAiderPythonCandidates(options).find((candidate) => existsSync(candidate)) || '';
  }
  if (!pythonPath) {
    return { ready: false, need: 'python311', aiderPath };
  }
  return { ready: false, need: 'aider', aiderPath, pythonPath };
}

module.exports = {
  resolveProjectRoot,
  resolvePythonCommand,
  resolvePythonSpawnArgs,
  shouldEnableAutoUpdates,
  resolveBackendHealthTimeoutMs,
  shouldOpenWindowBeforeBackend,
  isOllamaLaunchSkippable,
  CHROME_USER_AGENT,
  isHttpUrl,
  shouldOpenInSystemBrowser,
  shouldOpenAuthInSystemBrowser,
  resolveEmbeddedPythonCandidates,
  COREX_OLLAMA_PORT,
  DESKTOP_OLLAMA_PORT,
  SHUTDOWN_HTTP_TIMEOUT_MS,
  SHUTDOWN_KILL_TIMEOUT_MS,
  parseWindowsListeningPid,
  killPidTreeSync,
  findListeningPidSync,
  killCoreXOllamaSync,
  killCoreXRuntimeSync,
  collectDescendantPids,
  parseWmicProcessRows,
  parsePowerShellProcessRows,
  listWindowsProcessesSync,
  killZombieLlamaServersSync,
  killResidualLlamaServersSync,
  preferIntegratedGpuForUi,
  PYTHON311_INSTALLER_URL,
  resolveAiderSidecarPath,
  listAiderPythonCandidates,
  probeAiderLaunchEnv,
};
