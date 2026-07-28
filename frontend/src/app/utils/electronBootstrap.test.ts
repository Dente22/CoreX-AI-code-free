import { describe, expect, it } from 'vitest';
import {
  resolveProjectRoot,
  resolvePythonCommand,
  resolvePythonSpawnArgs,
  shouldEnableAutoUpdates,
  resolveBackendHealthTimeoutMs,
  shouldOpenWindowBeforeBackend,
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
