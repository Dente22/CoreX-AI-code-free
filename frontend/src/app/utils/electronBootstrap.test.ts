import { describe, expect, it } from 'vitest';
import {
  resolveProjectRoot,
  resolvePythonCommand,
  resolvePythonSpawnArgs,
  shouldEnableAutoUpdates,
  resolveBackendHealthTimeoutMs,
  shouldOpenWindowBeforeBackend,
  isOllamaLaunchSkippable,
  isHttpUrl,
  shouldOpenInSystemBrowser,
  shouldOpenAuthInSystemBrowser,
  preferIntegratedGpuForUi,
  probeAiderLaunchEnv,
} from './electronBootstrap';

describe('resolveProjectRoot', () => {
  it('uses resourcesPath when packaged (installer layout)', () => {
    expect(
      resolveProjectRoot({
        isPackaged: true,
        resourcesPath: 'C:/Program Files/CoreX/resources',
        dirname: 'C:/Program Files/CoreX/resources/app.asar',
        joinPath: (...parts) => parts.join('/'),
      }),
    ).toBe('C:/Program Files/CoreX/resources');
  });

  it('uses parent of frontend when unpackaged (dev)', () => {
    expect(
      resolveProjectRoot({
        isPackaged: false,
        resourcesPath: 'C:/ignored/resources',
        dirname: 'C:/repo/CoreX/frontend',
        joinPath: (...parts) => parts.join('/'),
      }),
    ).toBe('C:/repo/CoreX/frontend/..');
  });
});

describe('resolvePythonCommand', () => {
  it('prefers embedded python only when the binary exists', () => {
    const embedded = 'C:/app/resources/python/python.exe';
    expect(
      resolvePythonCommand({
        isPackaged: true,
        resourcesPath: 'C:/app/resources',
        platform: 'win32',
        existsSync: (p) => p === embedded,
        joinPath: (...parts) => parts.join('/'),
      }),
    ).toBe(embedded);
  });

  it('accepts Windows venv layout under resources/python/Scripts', () => {
    const embedded = 'C:/app/resources/python/Scripts/python.exe';
    expect(
      resolvePythonCommand({
        isPackaged: true,
        resourcesPath: 'C:/app/resources',
        platform: 'win32',
        existsSync: (p) => p === embedded,
        joinPath: (...parts) => parts.join('/'),
      }),
    ).toBe(embedded);
  });

  it('falls back to COREX_PYTHON when embedded python is missing', () => {
    expect(
      resolvePythonCommand({
        isPackaged: true,
        resourcesPath: 'C:/app/resources',
        platform: 'win32',
        env: { COREX_PYTHON: 'C:/CoreX/.venv/Scripts/python.exe' },
        existsSync: () => false,
        joinPath: (...parts) => parts.join('/'),
      }),
    ).toBe('C:/CoreX/.venv/Scripts/python.exe');
  });

  it('prefers repo .venv in unpackaged/dev mode', () => {
    const venvPy = 'C:/repo/CoreX/.venv/Scripts/python.exe';
    expect(
      resolvePythonCommand({
        isPackaged: false,
        resourcesPath: 'C:/ignored',
        platform: 'win32',
        projectRoot: 'C:/repo/CoreX',
        env: {},
        existsSync: (p) => p === venvPy,
        joinPath: (...parts) => parts.join('/'),
      }),
    ).toBe(venvPy);
  });

  it('falls back to py on Windows when nothing else is available', () => {
    expect(
      resolvePythonCommand({
        isPackaged: true,
        resourcesPath: 'C:/app/resources',
        platform: 'win32',
        env: {},
        existsSync: () => false,
        joinPath: (...parts) => parts.join('/'),
      }),
    ).toBe('py');
  });

  it('uses python3 on non-Windows when unpackaged', () => {
    expect(
      resolvePythonCommand({
        isPackaged: false,
        resourcesPath: '/unused',
        platform: 'linux',
        env: {},
        existsSync: () => false,
        joinPath: (...parts) => parts.join('/'),
      }),
    ).toBe('python3');
  });
});

describe('resolvePythonSpawnArgs', () => {
  it('adds -3.13 for bare py launcher on Windows', () => {
    expect(
      resolvePythonSpawnArgs({
        pythonCommand: 'py',
        platform: 'win32',
        mainPy: 'C:/app/main.py',
        port: 8010,
      }),
    ).toEqual(['-3.13', 'C:/app/main.py', '--mode', 'server', '--port', '8010']);
  });

  it('does not inject version flag for absolute python.exe', () => {
    expect(
      resolvePythonSpawnArgs({
        pythonCommand: 'C:/CoreX/.venv/Scripts/python.exe',
        platform: 'win32',
        mainPy: 'C:/app/main.py',
        port: 8010,
      }),
    ).toEqual(['C:/app/main.py', '--mode', 'server', '--port', '8010']);
  });
});

describe('shouldEnableAutoUpdates', () => {
  it('is disabled in development', () => {
    expect(
      shouldEnableAutoUpdates({
        isDev: true,
        updateUrl: 'https://updates.example.com/corex/',
      }),
    ).toBe(false);
  });

  it('is disabled for placeholder example.com feed from package.json', () => {
    expect(
      shouldEnableAutoUpdates({
        isDev: false,
        updateUrl: 'https://updates.example.com/corex/',
      }),
    ).toBe(false);
  });

  it('is disabled when update URL is empty', () => {
    expect(shouldEnableAutoUpdates({ isDev: false, updateUrl: '' })).toBe(false);
    expect(shouldEnableAutoUpdates({ isDev: false, updateUrl: null })).toBe(false);
  });

  it('is enabled for a real custom feed URL', () => {
    expect(
      shouldEnableAutoUpdates({
        isDev: false,
        updateUrl: 'https://cdn.mycompany.com/corex/',
      }),
    ).toBe(true);
  });
});

describe('resolveBackendHealthTimeoutMs', () => {
  it('uses a short timeout so failed python does not freeze UI for ~45s', () => {
    expect(
      resolveBackendHealthTimeoutMs({
        hasEmbeddedPython: false,
        isPackaged: true,
      }),
    ).toBeLessThanOrEqual(12000);
  });

  it('allows a bit more time when embedded python is present', () => {
    const withEmbedded = resolveBackendHealthTimeoutMs({
      hasEmbeddedPython: true,
      isPackaged: true,
    });
    const without = resolveBackendHealthTimeoutMs({
      hasEmbeddedPython: false,
      isPackaged: true,
    });
    expect(withEmbedded).toBeGreaterThan(without);
    expect(withEmbedded).toBeLessThanOrEqual(25000);
  });
});

describe('shouldOpenWindowBeforeBackend', () => {
  it('opens the UI first so startup feels instant', () => {
    expect(shouldOpenWindowBeforeBackend()).toBe(true);
  });
});

describe('isOllamaLaunchSkippable', () => {
  it('treats a missing Ollama server as a non-blocking choice', () => {
    expect(
      isOllamaLaunchSkippable({
        ready: false,
        phase: 'ollama_server',
        skippable: true,
      }),
    ).toBe(true);
  });

  it('skips even without the skippable flag when phase is ollama_server', () => {
    expect(isOllamaLaunchSkippable({ ready: false, phase: 'ollama_server' })).toBe(true);
  });

  it('does not skip a ready system', () => {
    expect(isOllamaLaunchSkippable({ ready: true, phase: 'ready' })).toBe(false);
  });

  it('does not skip other blocked phases', () => {
    expect(isOllamaLaunchSkippable({ ready: false, phase: 'online_config' })).toBe(false);
  });
});

describe('probeAiderLaunchEnv', () => {
  const joinPath = (...parts: string[]) => parts.join('/');

  it('is ready when sidecar aider.exe exists', () => {
    const result = probeAiderLaunchEnv({
      projectRoot: 'D:/CoreX',
      platform: 'win32',
      joinPath,
      existsSync: (p) => p === 'D:/CoreX/.venv-aider/Scripts/aider.exe',
    });
    expect(result.ready).toBe(true);
    expect(result.need).toBeNull();
  });

  it('asks for Python 3.11 when sidecar and 3.11 are missing', () => {
    const result = probeAiderLaunchEnv({
      projectRoot: 'D:/CoreX',
      platform: 'win32',
      localAppData: 'C:/Users/me/AppData/Local',
      programFiles: 'C:/Program Files',
      joinPath,
      existsSync: () => false,
      execFileSync: () => {
        throw new Error('no py');
      },
    });
    expect(result.ready).toBe(false);
    expect(result.need).toBe('python311');
  });

  it('asks to install Aider when Python 3.11 is present', () => {
    const py = 'C:/Users/me/AppData/Local/Programs/Python/Python311/python.exe';
    const result = probeAiderLaunchEnv({
      projectRoot: 'D:/CoreX',
      platform: 'win32',
      localAppData: 'C:/Users/me/AppData/Local',
      programFiles: 'C:/Program Files',
      joinPath,
      existsSync: (p) => p === py,
    });
    expect(result.ready).toBe(false);
    expect(result.need).toBe('aider');
    expect(result.pythonPath).toBe(py);
  });
});

describe('isHttpUrl', () => {
  it('accepts http and https', () => {
    expect(isHttpUrl('https://openrouter.ai/keys')).toBe(true);
    expect(isHttpUrl('http://127.0.0.1:3000')).toBe(true);
  });

  it('rejects non-web URLs', () => {
    expect(isHttpUrl('file:///C:/tmp')).toBe(false);
    expect(isHttpUrl('javascript:alert(1)')).toBe(false);
    expect(isHttpUrl('not a url')).toBe(false);
  });
});

describe('shouldOpenInSystemBrowser', () => {
  it('uses the OS browser on Ctrl or Cmd click', () => {
    expect(shouldOpenInSystemBrowser({ ctrlKey: true })).toBe(true);
    expect(shouldOpenInSystemBrowser({ metaKey: true })).toBe(true);
  });

  it('keeps a normal click inside CoreX', () => {
    expect(shouldOpenInSystemBrowser({ ctrlKey: false })).toBe(false);
  });
});

describe('preferIntegratedGpuForUi', () => {
  it('keeps Chromium on the integrated GPU on Windows', () => {
    const switches: string[] = [];
    const spawnCalls: unknown[][] = [];
    const result = preferIntegratedGpuForUi({
      platform: 'win32',
      commandLine: { appendSwitch: (name: string) => switches.push(name) },
      execPath: 'C:\\CoreX\\electron.exe',
      spawn: (...args: unknown[]) => {
        spawnCalls.push(args);
        return { unref() {} };
      },
    });
    expect(result.applied).toBe(true);
    expect(switches).toEqual(['force_low_power_gpu']);
    expect(spawnCalls[0][0]).toBe('reg');
    expect(spawnCalls[0][1]).toContain('GpuPreference=1;');
    expect(spawnCalls[0][1]).toContain('C:\\CoreX\\electron.exe');
  });

  it('does nothing on non-Windows', () => {
    const switches: string[] = [];
    const result = preferIntegratedGpuForUi({
      platform: 'darwin',
      commandLine: { appendSwitch: (name: string) => switches.push(name) },
    });
    expect(result.applied).toBe(false);
    expect(switches).toEqual([]);
  });
});

describe('shouldOpenAuthInSystemBrowser', () => {
  it('keeps OpenRouter and docs inside the in-app browser', () => {
    expect(shouldOpenAuthInSystemBrowser('https://openrouter.ai/keys')).toBe(false);
    expect(shouldOpenAuthInSystemBrowser('https://google.com/search?q=corex')).toBe(false);
  });

  it('sends Google sign-in to the system browser', () => {
    expect(shouldOpenAuthInSystemBrowser('https://accounts.google.com/o/oauth2/v2/auth?client_id=x')).toBe(true);
    expect(shouldOpenAuthInSystemBrowser('https://accounts.google.de/signin')).toBe(true);
    expect(shouldOpenAuthInSystemBrowser('https://oauth2.googleapis.com/token')).toBe(true);
  });
});
