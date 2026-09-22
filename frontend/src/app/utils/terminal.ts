import { fetchApi } from './api';

export interface TerminalRunResult {
  success: boolean;
  command?: string;
  file?: string;
  cwd?: string;
  output?: string;
  exit_code?: number;
  error?: string;
}

async function parseTerminalResponse(response: Response): Promise<TerminalRunResult> {
  const text = await response.text();
  if (!text.trim()) {
    return {
      success: false,
      error: response.ok ? 'Пустой ответ сервера' : `HTTP ${response.status}`,
    };
  }
  try {
    return JSON.parse(text) as TerminalRunResult;
  } catch {
    return {
      success: false,
      error: text.slice(0, 500) || `HTTP ${response.status}: неверный ответ сервера`,
    };
  }
}

export async function runFile(path: string): Promise<TerminalRunResult> {
  const response = await fetchApi('/api/terminal/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  return parseTerminalResponse(response);
}

export async function runCommand(command: string, cwd?: string): Promise<TerminalRunResult> {
  const response = await fetchApi('/api/terminal/exec', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command, cwd }),
  });
  return parseTerminalResponse(response);
}

export interface TerminalSessionSnapshot extends TerminalRunResult {
  running?: boolean;
}

export function isInteractiveRunnable(path: string): boolean {
  const lower = path.toLowerCase();
  if (!isRunnableFile(path)) {
    return false;
  }
  return !(lower.endsWith('.html') || lower.endsWith('.htm') || lower.endsWith('.css'));
}

export async function startTerminalSession(payload: {
  path?: string;
  command?: string;
  cwd?: string;
}): Promise<TerminalSessionSnapshot> {
  const response = await fetchApi('/api/terminal/session/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseTerminalResponse(response);
}

export async function pollTerminalSession(path?: string): Promise<TerminalSessionSnapshot> {
  const query = path ? `?path=${encodeURIComponent(path)}` : '';
  const response = await fetchApi(`/api/terminal/session${query}`);
  return parseTerminalResponse(response);
}

export async function sendTerminalStdin(text: string): Promise<TerminalRunResult> {
  const response = await fetchApi('/api/terminal/session/stdin', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  return parseTerminalResponse(response);
}

export async function killTerminalSession(): Promise<TerminalRunResult> {
  const response = await fetchApi('/api/terminal/session/kill', { method: 'POST' });
  return parseTerminalResponse(response);
}

export function isRunnableFile(path: string): boolean {
  const lower = path.toLowerCase();
  return (
    lower.endsWith('.py') ||
    lower.endsWith('.pyw') ||
    lower.endsWith('.html') ||
    lower.endsWith('.htm') ||
    lower.endsWith('.css') ||
    lower.endsWith('.js') ||
    lower.endsWith('.mjs') ||
    lower.endsWith('.cjs') ||
    lower.endsWith('.ts') ||
    lower.endsWith('.tsx') ||
    lower.endsWith('.jsx') ||
    lower.endsWith('.ps1') ||
    lower.endsWith('.bat') ||
    lower.endsWith('.cmd') ||
    lower.endsWith('.sh')
  );
}
