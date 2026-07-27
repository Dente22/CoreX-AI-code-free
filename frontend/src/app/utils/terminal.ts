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
