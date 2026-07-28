const path = require('path');
const fs = require('fs');
const os = require('os');
const net = require('net');
const http = require('http');
const { spawn } = require('child_process');
const { app, BrowserWindow, Menu, dialog, ipcMain } = require('electron');
let autoUpdater = null;
try {
  ({ autoUpdater } = require('electron-updater'));
} catch (error) {
  console.warn('[CoreX] electron-updater not available:', error.message);
}
const {
  resolveProjectRoot,
  resolvePythonCommand: resolvePythonCommandShared,
  resolvePythonSpawnArgs,
  shouldEnableAutoUpdates,
  resolveBackendHealthTimeoutMs,
  SHUTDOWN_HTTP_TIMEOUT_MS,
  killPidTreeSync,
  killCoreXRuntimeSync,
} = require('./electronBootstrap.cjs');

const isDev = !app.isPackaged;
const ROOT_DIR = resolveProjectRoot({
  isPackaged: app.isPackaged,
  resourcesPath: process.resourcesPath,
  dirname: __dirname,
  joinPath: path.join,
});

function resolveAppIconPath() {
  const buildIconIco = path.join(__dirname, 'build', 'icon.ico');
  const buildIconPng = path.join(__dirname, 'build', 'icon.png');
  const distIconPng = path.join(__dirname, 'dist', 'corex-icon.png');
  const publicIconPng = path.join(__dirname, 'public', 'corex-icon.png');
  const publicLogoSvg = path.join(__dirname, 'public', 'corex-logo.svg');

  const candidates =
    process.platform === 'win32'
      ? [buildIconIco, buildIconPng, distIconPng, publicIconPng, publicLogoSvg]
      : [buildIconPng, buildIconIco, distIconPng, publicIconPng, publicLogoSvg];

  return candidates.find((p) => fs.existsSync(p)) || undefined;
}

let mainWindow = null;
let splashWindow = null;
let backendProcess = null;
let backendPort = 8000;

const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
  process.exit(0);
}

app.on('second-instance', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    if (mainWindow.isMinimized()) {
      mainWindow.restore();
    }
    mainWindow.focus();
    return;
  }
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.focus();
  }
});

function isInstallerForCoreX(fileName) {
  return /^CoreX-Setup-[\d.]+(?:-[A-Za-z0-9.-]+)?\.exe$/i.test(String(fileName || '').trim());
}

function extractVersionFromInstallerName(fileName) {
  const match = /^CoreX-Setup-([0-9]+\.[0-9]+\.[0-9]+)(?:-[A-Za-z0-9.-]+)?\.exe$/i.exec(
    String(fileName || '').trim(),
  );
  return match?.[1] || '';
}

function normalizeVersion(version) {
  return String(version || '').trim().replace(/^v/i, '');
}

function isNewerVersion(nextVersion, currentVersion) {
  const a = normalizeVersion(nextVersion).split('.').map((v) => Number.parseInt(v, 10) || 0);
  const b = normalizeVersion(currentVersion).split('.').map((v) => Number.parseInt(v, 10) || 0);
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i += 1) {
    const av = a[i] ?? 0;
    const bv = b[i] ?? 0;
    if (av > bv) return true;
    if (av < bv) return false;
  }
  return false;
}

function findBestInstallerCandidate(dirPath) {
  try {
    const files = fs.readdirSync(dirPath, { withFileTypes: true });
    const installers = files
      .filter((entry) => entry.isFile() && isInstallerForCoreX(entry.name))
      .map((entry) => {
        const fullPath = path.join(dirPath, entry.name);
        const stat = fs.statSync(fullPath);
        const version = extractVersionFromInstallerName(entry.name);
        return { fullPath, version, mtimeMs: stat.mtimeMs };
      })
      .filter((item) => item.version);
    if (!installers.length) return null;
    installers.sort((x, y) => y.mtimeMs - x.mtimeMs);
    return installers[0];
  } catch {
    return null;
  }
}

function probePort(host, port, timeout = 200) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    let done = false;
    const finish = (value) => {
      if (done) return;
      done = true;
      clearTimeout(hardTimer);
      socket.destroy();
      resolve(value);
    };
    // Windows can stall connect() without firing socket timeout; hard-cap each probe.
    const hardTimer = setTimeout(() => finish(false), timeout + 150);
    socket.setTimeout(timeout);
    socket.on('connect', () => finish(true));
    socket.on('timeout', () => finish(false));
    socket.on('error', () => finish(false));
    try {
      socket.connect(port, host);
    } catch {
      finish(false);
    }
  });
}

function tryListenPort(port, host = '127.0.0.1', timeoutMs = 400) {
  return new Promise((resolve) => {
    const server = net.createServer();
    let done = false;
    const finish = (ok) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      try {
        server.removeAllListeners();
        server.close();
      } catch {
        // ignore
      }
      resolve(ok);
    };
    const timer = setTimeout(() => finish(false), timeoutMs);
    server.once('error', () => finish(false));
    server.listen(port, host, () => {
      server.close(() => finish(true));
    });
  });
}

async function findFreePort(start = 8000, end = 8100, host = '127.0.0.1') {
  for (let port = start; port < end; port += 1) {
    // Prefer bind-check: more reliable than connect probes on Windows.
    if (await tryListenPort(port, host)) {
      return port;
    }
  }
  // Fallback to connect probes if bind checks were inconclusive.
  for (let port = start; port < end; port += 1) {
    const busy = await probePort(host, port);
    if (!busy) {
      return port;
    }
  }
  throw new Error(`No free port in range ${start}-${end - 1}`);
}

const LAUNCH_LOG_PATH = path.join(__dirname, '_corex-launch.log');

function launchLog(message) {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  try {
    fs.appendFileSync(LAUNCH_LOG_PATH, line, 'utf8');
  } catch {
    // ignore
  }
  console.log(`[CoreX] ${message}`);
}

function waitForHealth(port, timeoutMs = 8000) {
  return new Promise((resolve) => {
    const deadline = Date.now() + timeoutMs;

    const tick = () => {
      const req = http.get(`http://127.0.0.1:${port}/health`, (res) => {
        res.resume();
        if (res.statusCode === 200) {
          resolve(true);
          return;
        }
        retry();
      });
      req.on('error', retry);
      req.setTimeout(1200, () => {
        req.destroy();
        retry();
      });
    };

    const retry = () => {
      if (Date.now() >= deadline) {
        resolve(false);
        return;
      }
      setTimeout(tick, 250);
    };

    tick();
  });
}

function resolvePythonCommand() {
  return resolvePythonCommandShared({
    isPackaged: app.isPackaged,
    resourcesPath: process.resourcesPath,
    platform: process.platform,
    projectRoot: ROOT_DIR,
    env: process.env,
    existsSync: fs.existsSync,
    joinPath: path.join,
  });
}

function setupAutoUpdates() {
  const feedUrl = process.env.COREX_UPDATE_URL || '';
  if (!autoUpdater || !shouldEnableAutoUpdates({ isDev, updateUrl: feedUrl })) {
    return;
  }

  autoUpdater.setFeedURL({ provider: 'generic', url: feedUrl });

  autoUpdater.on('update-available', (info) => {
    mainWindow?.webContents.send('update-status', `Найдена версия ${info.version}. Загружаю обновление...`);
  });
  autoUpdater.on('update-not-available', () => {
    mainWindow?.webContents.send('update-status', 'Установлена актуальная версия.');
  });
  autoUpdater.on('update-downloaded', () => {
    dialog.showMessageBox({
      type: 'info',
      title: 'CoreX Update',
      message: 'Доступно обновление. Приложение перезапустится для установки.',
      buttons: ['Перезапустить сейчас'],
      defaultId: 0,
    }).then(() => {
      autoUpdater.quitAndInstall();
    });
  });
  autoUpdater.on('error', (error) => {
    mainWindow?.webContents.send('update-status', `Ошибка обновления: ${error.message}`);
  });

  autoUpdater.checkForUpdatesAndNotify().catch((error) => {
    mainWindow?.webContents.send('update-status', `Проверка обновлений не удалась: ${error.message}`);
  });
}

function maybeSuggestLocalInstallerUpdate() {
  if (process.platform !== 'win32') return;
  const downloadsDir = path.join(os.homedir(), 'Downloads');
  const candidate = findBestInstallerCandidate(downloadsDir);
  if (!candidate) return;
  if (!isNewerVersion(candidate.version, app.getVersion())) return;

  dialog.showMessageBox({
    type: 'info',
    title: 'Доступно локальное обновление',
    message: `Найдена новая версия ${candidate.version} в папке Загрузки.`,
    detail: candidate.fullPath,
    buttons: ['Установить', 'Позже'],
    defaultId: 0,
    cancelId: 1,
  }).then((result) => {
    if (result.response === 0) {
      spawn(candidate.fullPath, [], { detached: true, stdio: 'ignore' }).unref();
      app.quit();
    }
  });
}

async function startBackend() {
  if (process.env.COREX_BACKEND_PORT && process.env.COREX_SKIP_BACKEND === '1') {
    backendPort = Number(process.env.COREX_BACKEND_PORT);
    process.env.COREX_BACKEND_URL = `http://127.0.0.1:${backendPort}`;
    launchLog(`Using external backend on port ${backendPort}`);
    return true;
  }

  launchLog('Resolving free backend port…');
  backendPort = await findFreePort(8000, 8100);
  process.env.COREX_BACKEND_PORT = String(backendPort);
  process.env.COREX_BACKEND_URL = `http://127.0.0.1:${backendPort}`;
  launchLog(`Backend port ${backendPort}`);

  const python = resolvePythonCommand();
  const hasEmbeddedPython =
    typeof python === 'string' &&
    python.includes(`${path.sep}python${path.sep}`) &&
    fs.existsSync(python);
  const healthTimeoutMs = resolveBackendHealthTimeoutMs({
    hasEmbeddedPython,
    isPackaged: app.isPackaged,
  });

  const mainPy = path.join(ROOT_DIR, 'main.py');
  if (!fs.existsSync(mainPy)) {
    throw new Error(`main.py not found at ${mainPy}`);
  }

  const spawnArgs = resolvePythonSpawnArgs({
    pythonCommand: python,
    platform: process.platform,
    mainPy,
    port: backendPort,
  });
  launchLog(`Spawning backend: ${python} ${spawnArgs.join(' ')}`);

  let earlyExitCode = null;
  let spawnError = null;
  let stderrTail = '';

  backendProcess = spawn(python, spawnArgs, {
    cwd: ROOT_DIR,
    env: {
      ...process.env,
      COREX_ROOT: ROOT_DIR,
      PYTHONUTF8: '1',
      PYTHONIOENCODING: 'utf-8',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });

  backendProcess.on('error', (error) => {
    spawnError = error;
    console.error(`[backend] failed to start (${python}):`, error.message);
  });
  backendProcess.stdout.on('data', (chunk) => {
    process.stdout.write(`[backend] ${chunk}`);
  });
  backendProcess.stderr.on('data', (chunk) => {
    const text = String(chunk);
    stderrTail = (stderrTail + text).slice(-2000);
    process.stderr.write(`[backend] ${chunk}`);
  });
  backendProcess.on('exit', (code) => {
    earlyExitCode = code;
    if (code !== 0 && code !== null) {
      console.error(`[backend] exited with code ${code}`);
    }
    backendProcess = null;
  });

  const ready = await new Promise((resolve) => {
    const deadline = Date.now() + healthTimeoutMs;
    const tick = () => {
      if (spawnError || (earlyExitCode !== null && earlyExitCode !== 0)) {
        resolve(false);
        return;
      }
      if (Date.now() >= deadline) {
        resolve(false);
        return;
      }
      const req = http.get(`http://127.0.0.1:${backendPort}/health`, (res) => {
        res.resume();
        if (res.statusCode === 200) {
          resolve(true);
          return;
        }
        setTimeout(tick, 250);
      });
      req.on('error', () => setTimeout(tick, 250));
      req.setTimeout(1200, () => {
        req.destroy();
        setTimeout(tick, 250);
      });
    };
    tick();
  });

  if (!ready) {
    if (backendProcess && !backendProcess.killed) {
      try {
        backendProcess.kill();
      } catch {
        // ignore
      }
    }
    const reason =
      spawnError?.message ||
      (earlyExitCode !== null
        ? `process exited with code ${earlyExitCode}${stderrTail ? `: ${stderrTail.trim().split(/\r?\n/).slice(-3).join(' | ')}` : ''}`
        : 'health timeout');
    throw new Error(
      `Backend did not respond on port ${backendPort} (${reason}). Python: ${python}. Root: ${ROOT_DIR}`,
    );
  }
  return true;
}

function requestBackendShutdown(port) {
  return new Promise((resolve) => {
    const targetPort = Number(port);
    if (!Number.isFinite(targetPort) || targetPort <= 0) {
      resolve(false);
      return;
    }
    const req = http.request(
      {
        hostname: '127.0.0.1',
        port: targetPort,
        path: '/api/system/shutdown',
        method: 'POST',
        timeout: SHUTDOWN_HTTP_TIMEOUT_MS,
      },
      (res) => {
        res.resume();
        resolve(res.statusCode >= 200 && res.statusCode < 300);
      },
    );
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
    req.end();
  });
}

async function stopBackend() {
  const port = Number(process.env.COREX_BACKEND_PORT || backendPort);
  if (port > 0) {
    await requestBackendShutdown(port);
  }

  if (backendProcess && !backendProcess.killed && backendProcess.pid) {
    killPidTreeSync(backendProcess.pid);
  }
  backendProcess = null;

  killCoreXRuntimeSync();
}

let shutdownPromise = null;
let shutdownDone = false;
let shutdownFinalizePromise = null;

function shutdownCoreX() {
  if (!shutdownPromise) {
    shutdownPromise = stopBackend().catch((error) => {
      console.error('[CoreX] Shutdown error:', error);
      killCoreXRuntimeSync();
    });
  }
  return shutdownPromise;
}

function finalizeShutdown() {
  if (shutdownDone) {
    return Promise.resolve();
  }
  if (!shutdownFinalizePromise) {
    shutdownFinalizePromise = shutdownCoreX().finally(() => {
      shutdownDone = true;
      killCoreXRuntimeSync();
      if (splashWindow && !splashWindow.isDestroyed()) {
        splashWindow.destroy();
        splashWindow = null;
      }
      for (const win of BrowserWindow.getAllWindows()) {
        if (!win.isDestroyed()) {
          win.destroy();
        }
      }
      app.exit(0);
      process.exit(0);
    });
  }
  return shutdownFinalizePromise;
}

function registerKeyboardShortcuts(window) {
  window.webContents.on('before-input-event', (event, input) => {
    if (input.type !== 'keyDown') return;

    const mod = process.platform === 'darwin' ? input.meta : input.control;
    if (!mod) return;

    const key = input.key.toLowerCase();
    if (key === 's') {
      event.preventDefault();
      window.webContents.send('menu-action', 'save-file');
      return;
    }
    if (key === 'n' && input.shift) {
      event.preventDefault();
      window.webContents.send('menu-action', 'new-folder');
      return;
    }
    if (key === 'n') {
      event.preventDefault();
      window.webContents.send('menu-action', 'new-file');
    }
  });
}

async function findVitePort(host = '127.0.0.1', start = 5173, end = 5185) {
  for (let p = start; p <= end; p += 1) {
    if (await probePort(host, p)) {
      return p;
    }
  }
  return null;
}

const SPLASH_INTRO_MS = 3200;
const SPLASH_MIN_VISIBLE_MS = 3800;
const READINESS_TIMEOUT_MS = 90 * 1000;
const READINESS_POLL_MS = 500;

let splashShownAt = 0;

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function httpGetJson(url, timeoutMs = 4000) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      let body = '';
      res.on('data', (chunk) => {
        body += chunk;
      });
      res.on('end', () => {
        try {
          resolve({
            status: res.statusCode,
            data: JSON.parse(body),
          });
        } catch (error) {
          reject(error);
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(timeoutMs, () => {
      req.destroy();
      reject(new Error('request timeout'));
    });
  });
}

async function waitForSystemReady(port) {
  const deadline = Date.now() + READINESS_TIMEOUT_MS;
  let tick = 0;
  let lastMessage = 'Подготовка модели и сервисов…';

  while (Date.now() < deadline) {
    tick += 1;
    try {
      const { status, data } = await httpGetJson(`http://127.0.0.1:${port}/api/system/ready`);
      if (status === 200 && data?.ready) {
        updateSplash({
          progress: data.phase === 'model_pending' ? 78 : 82,
          message: data.message || 'AI готов к работе',
          phase: data.phase || 'ready',
        });
        return { ok: true, data };
      }
      if (data?.message) {
        lastMessage = String(data.message);
      }
      const phase = data?.phase || 'model';
      const base = phase === 'ollama_server' ? 44 : phase === 'model' ? 52 : 48;
      updateSplash({
        progress: Math.min(78, base + (tick % 12)),
        message: lastMessage,
        phase,
      });
    } catch {
      updateSplash({
        progress: Math.min(46, 36 + (tick % 8)),
        message: tick < 3 ? 'Ожидание AI-движка…' : lastMessage,
        phase: 'backend',
      });
    }
    await delay(READINESS_POLL_MS);
  }

  return {
    ok: false,
    reason: 'timeout',
    message: `Не удалось запустить AI за отведённое время. ${lastMessage}`,
  };
}

async function abortLaunchWithSplashError(title, message, detail = '') {
  updateSplash({
    progress: 12,
    message: message || 'Не удалось запустить CoreX',
    error: true,
  });
  await delay(420);
  try {
    await dialog.showMessageBox({
      type: 'error',
      title: title || 'CoreX — запуск не удался',
      message: String(message || 'Не удалось запустить CoreX'),
      detail: String(detail || ''),
      buttons: ['Закрыть'],
    });
  } catch {
    // ignore
  }
  await finalizeShutdown();
}

async function runSplashIntro() {
  const started = Date.now();
  updateSplash({ progress: 6, message: 'CoreX', phase: 'boot' });
  while (Date.now() - started < SPLASH_INTRO_MS) {
    const elapsed = Date.now() - started;
    const pct = Math.min(22, 6 + Math.floor((elapsed / SPLASH_INTRO_MS) * 16));
    updateSplash({ progress: pct, message: 'CoreX загружается…', phase: 'boot' });
    await delay(120);
  }
  updateSplash({ progress: 24, message: 'Запуск компонентов…', phase: 'boot' });
}

async function createSplashWindow() {
  const icon = resolveAppIconPath();
  // Avoid fully transparent frameless windows on Windows — they often never
  // composite / never become visible, and the app looks "stuck" on electron .
  splashWindow = new BrowserWindow({
    width: 520,
    height: 400,
    frame: false,
    transparent: false,
    resizable: false,
    movable: true,
    center: true,
    alwaysOnTop: true,
    show: false,
    backgroundColor: '#050810',
    ...(icon ? { icon } : {}),
    webPreferences: {
      preload: path.join(__dirname, 'splash-preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      backgroundThrottling: false,
    },
  });

  // loadFile already resolves on did-finish-load. Do NOT wait again on
  // isLoading()/did-finish-load — that race hangs forever when the event
  // already fired and isLoading() briefly stays true.
  await splashWindow.loadFile(path.join(__dirname, 'splash.html'));
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.show();
    splashWindow.focus();
    splashShownAt = Date.now();
    updateSplash({ progress: 6, message: 'CoreX', phase: 'boot' });
    launchLog('Splash window shown');
  }
  return splashWindow;
}

function updateSplash(payload = {}) {
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.webContents.send('splash-update', payload);
  }
}

async function closeSplashWindow() {
  if (!splashWindow || splashWindow.isDestroyed()) {
    return;
  }
  // Не закрываем splash раньше минимальной длительности анимации.
  const elapsed = splashShownAt ? Date.now() - splashShownAt : 0;
  if (elapsed < SPLASH_MIN_VISIBLE_MS) {
    const remain = SPLASH_MIN_VISIBLE_MS - elapsed;
    updateSplash({
      progress: Math.min(94, 70 + Math.floor((elapsed / SPLASH_MIN_VISIBLE_MS) * 20)),
      message: 'Загрузка интерфейса…',
      phase: 'ui',
    });
    await delay(remain);
  }
  updateSplash({ progress: 100, message: 'Готово!' });
  await delay(420);
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.close();
  }
  splashWindow = null;
}

async function createMainWindow() {
  const icon = resolveAppIconPath();
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: 'CoreX',
    show: false,
    ...(icon ? { icon } : {}),
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  Menu.setApplicationMenu(null);
  registerKeyboardShortcuts(mainWindow);

  const frontendUrl = process.env.COREX_FRONTEND_URL || null;

  if (frontendUrl) {
    await mainWindow.loadURL(frontendUrl);
    if (process.env.COREX_OPEN_DEVTOOLS === '1') {
      try {
        mainWindow.webContents.openDevTools({ mode: 'detach' });
      } catch {
        // ignore
      }
    }
  } else {
    await mainWindow.loadFile(path.join(__dirname, 'dist', 'index.html'));
  }

  mainWindow.once('ready-to-show', () => {
    // Показываем главное окно только после закрытия splash (см. app.whenReady).
  });

  mainWindow.on('close', (event) => {
    if (shutdownDone) {
      return;
    }
    event.preventDefault();
    finalizeShutdown();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

ipcMain.handle('get-backend-info', () => ({
  backendPort: process.env.COREX_BACKEND_PORT || String(backendPort),
  backendUrl: process.env.COREX_BACKEND_URL || `http://127.0.0.1:${backendPort}`,
}));

ipcMain.handle('get-app-version', () => app.getVersion());
ipcMain.handle('pick-installer-update', async () => {
  const window = mainWindow;
  const result = await dialog.showOpenDialog(window, {
    title: 'Выберите установщик CoreX',
    properties: ['openFile'],
    filters: [{ name: 'CoreX Installer', extensions: ['exe'] }],
    defaultPath: path.join(os.homedir(), 'Downloads'),
  });
  if (result.canceled || !result.filePaths?.length) return { success: false, reason: 'cancelled' };

  const installerPath = result.filePaths[0];
  const fileName = path.basename(installerPath);
  if (!isInstallerForCoreX(fileName)) {
    return { success: false, reason: 'invalid_installer' };
  }
  const version = extractVersionFromInstallerName(fileName);
  if (!version || !isNewerVersion(version, app.getVersion())) {
    return { success: false, reason: 'not_newer', version };
  }

  spawn(installerPath, [], { detached: true, stdio: 'ignore' }).unref();
  setTimeout(() => app.quit(), 300);
  return { success: true, version };
});

ipcMain.handle('open-folder', async (event) => {
  const window = BrowserWindow.fromWebContents(event.sender);
  if (!window) {
    return null;
  }

  const result = await dialog.showOpenDialog(window, {
    properties: ['openDirectory'],
    title: 'Select Project Folder',
  });

  if (result.canceled || !result.filePaths?.length) {
    return null;
  }

  return result.filePaths[0];
});

app.whenReady().then(async () => {
  try {
    try {
      fs.writeFileSync(LAUNCH_LOG_PATH, '', 'utf8');
    } catch {
      // ignore
    }
    launchLog(`App ready. Root=${ROOT_DIR}`);
    await createSplashWindow();
  } catch (error) {
    console.error('[CoreX] Splash startup failed:', error);
    launchLog(`Splash failed: ${error?.message || error}`);
    app.quit();
    return;
  }

  let backendOk = false;

  try {
    await Promise.all([
      runSplashIntro(),
      (async () => {
        updateSplash({ progress: 28, message: 'Запуск AI-движка…', phase: 'backend' });
        await startBackend();
        backendOk = true;
        launchLog('Backend healthy, waiting for system ready…');
        updateSplash({ progress: 40, message: 'Подготовка модели и сервисов…', phase: 'ollama_server' });
        const ready = await waitForSystemReady(backendPort);
        if (!ready.ok) {
          throw new Error(ready.message || ready.reason || 'AI не готов');
        }
        launchLog(`System ready: ${ready.data?.phase || 'ok'}`);
      })(),
    ]);
  } catch (error) {
    console.error('[CoreX] Launch failed:', error);
    launchLog(`Launch failed: ${error?.message || error}`);
    const detail = String(error?.message || error || '');
    await abortLaunchWithSplashError(
      'CoreX — запуск не удался',
      backendOk
        ? 'Модель или сервисы AI не успели запуститься. Проверьте Ollama и выбранную модель.'
        : 'Не удалось запустить backend CoreX.',
      detail,
    );
    return;
  }

  updateSplash({ progress: 88, message: 'Загрузка интерфейса…', phase: 'ui' });
  try {
    await createMainWindow();
  } catch (error) {
    console.error('[CoreX] Window startup failed:', error);
    await abortLaunchWithSplashError(
      'CoreX — не удалось открыть окно',
      String(error?.message || error),
    );
    return;
  }

  if (!mainWindow) {
    await abortLaunchWithSplashError('CoreX', 'Главное окно не создано.');
    return;
  }

  updateSplash({ progress: 96, message: 'Почти готово…', phase: 'ui' });
  await closeSplashWindow();

  if (!mainWindow.isDestroyed()) {
    mainWindow.show();
    mainWindow.focus();
  }

  setupAutoUpdates();
  maybeSuggestLocalInstallerUpdate();
});

app.on('activate', async () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    await createMainWindow();
  }
});

app.on('before-quit', (event) => {
  if (shutdownDone) {
    return;
  }
  event.preventDefault();
  finalizeShutdown();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    finalizeShutdown();
  }
});

process.on('exit', () => {
  killCoreXRuntimeSync();
});
