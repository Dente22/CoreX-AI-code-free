let cachedBackendUrl: string | null = null;

import { resolveApiHosts } from './apiHosts';

export type BackendHealth = {  ok: boolean;
  backend_version?: string;
  task_routing?: boolean;
};

export const getBackendBaseUrl = (): string | null => {
  if (cachedBackendUrl) {
    return cachedBackendUrl;
  }

  if (window.electronAPI?.backendUrl) {
    return window.electronAPI.backendUrl;
  }

  if (window.electronAPI?.backendPort) {
    return `http://127.0.0.1:${window.electronAPI.backendPort}`;
  }

  return null;
};

export async function initBackendConnection(): Promise<string | null> {
  if (window.electronAPI?.getBackendInfo) {
    try {
      const info = await window.electronAPI.getBackendInfo();
      if (info?.backendUrl) {
        cachedBackendUrl = info.backendUrl;
        return cachedBackendUrl;
      }
    } catch {
      // fallback to static preload values
    }
  }

  cachedBackendUrl = getBackendBaseUrl();
  return cachedBackendUrl;
}

export const getApiHosts = (): string[] => {
  return resolveApiHosts(getBackendBaseUrl(), Boolean(window.electronAPI?.isElectron));
};

async function readBackendHealth(host: string): Promise<BackendHealth | null> {
  try {
    const response = await fetch(`${host}/health`, { signal: AbortSignal.timeout(1500) });
    if (!response.ok) {
      return null;
    }
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      return { ok: true, task_routing: false };
    }
    return (await response.json()) as BackendHealth;
  } catch {
    return null;
  }
}

export async function waitForBackend(maxAttempts = 40, intervalMs = 400): Promise<string | null> {
  await initBackendConnection();
  const hosts = getApiHosts();

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    for (const host of hosts) {
      const health = await readBackendHealth(host);
      if (health?.ok) {
        if (health.task_routing === false && window.electronAPI?.isElectron) {
          continue;
        }
        cachedBackendUrl = host;
        return host;
      }
    }
    await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
  }

  return null;
}

export async function fetchApi(path: string, options?: RequestInit) {
  await initBackendConnection();
  let lastError: unknown;
  const hosts = getApiHosts();

  for (const host of hosts) {
    try {
      const response = await fetch(`${host}${path}`, options);
      return response;
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError;
}

export function getWebSocketUrl() {
  const base = getBackendBaseUrl();
  if (base) {
    return `ws://${new URL(base).host}/ws`;
  }

  if (window.electronAPI?.backendPort) {
    return `ws://127.0.0.1:${window.electronAPI.backendPort}/ws`;
  }

  return 'ws://127.0.0.1:8000/ws';
}
