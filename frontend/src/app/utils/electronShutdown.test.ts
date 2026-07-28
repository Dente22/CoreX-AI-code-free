import { describe, expect, it } from 'vitest';
import {
  COREX_OLLAMA_PORT,
  collectDescendantPids,
  killCoreXOllamaSync,
  killPidTreeSync,
  killZombieLlamaServersSync,
  parseWindowsListeningPid,
  parseWmicProcessRows,
} from './electronBootstrap';

describe('parseWindowsListeningPid', () => {
  it('finds pid for CoreX ollama port', () => {
    const sample = `
  TCP    127.0.0.1:11435        0.0.0.0:0              LISTENING       9912
  TCP    127.0.0.1:11434        0.0.0.0:0              LISTENING       1234
`;
    expect(parseWindowsListeningPid(sample, COREX_OLLAMA_PORT)).toBe(9912);
    expect(parseWindowsListeningPid(sample, 11434)).toBe(1234);
  });

  it('returns null when port is not listening', () => {
    expect(parseWindowsListeningPid('TCP 127.0.0.1:8000 LISTENING 42', 11435)).toBeNull();
  });
});

describe('killPidTreeSync', () => {
  it('uses taskkill /T on Windows', () => {
    const calls: string[][] = [];
    const spawnSync = (_cmd: string, args: string[]) => {
      calls.push(args);
      return { status: 0 };
    };
    const ok = killPidTreeSync(4242, { platform: 'win32', spawnSync });
    expect(ok).toBe(true);
    expect(calls[0]).toEqual(['/PID', '4242', '/T', '/F']);
  });
});

describe('killCoreXOllamaSync', () => {
  it('kills listener on CoreX ollama port', () => {
    const spawnSync = (cmd: string, args: string[]) => {
      if (cmd === 'netstat') {
        return {
          status: 0,
          stdout: '  TCP    127.0.0.1:11435        0.0.0.0:0              LISTENING       7777\n',
        };
      }
      if (cmd === 'powershell' || cmd === 'wmic') {
        return {
          status: 0,
          stdout:
            '[{"Name":"llama-server.exe","ParentProcessId":7777,"ProcessId":8888},' +
            '{"Name":"ollama.exe","ParentProcessId":1234,"ProcessId":7777}]',
        };
      }
      if (cmd === 'taskkill') {
        return { status: 0 };
      }
      return { status: 1 };
    };
    expect(killCoreXOllamaSync({ platform: 'win32', spawnSync, port: 11435 })).toBe(true);
  });
});

describe('collectDescendantPids', () => {
  it('finds nested child processes', () => {
    const rows = [
      { name: 'ollama.exe', parentPid: 100, pid: 200 },
      { name: 'llama-server.exe', parentPid: 200, pid: 300 },
    ];
    const descendants = collectDescendantPids(200, rows);
    expect(descendants.has(300)).toBe(true);
  });
});

describe('killZombieLlamaServersSync', () => {
  it('kills orphan llama-server but keeps desktop ollama workers', () => {
    const calls: string[][] = [];
    const spawnSync = (cmd: string, args: string[]) => {
      if (cmd === 'netstat') {
        return {
          status: 0,
          stdout: '  TCP    127.0.0.1:11434        0.0.0.0:0              LISTENING       9001\n',
        };
      }
      if (cmd === 'powershell' || cmd === 'wmic') {
        return {
          status: 0,
          stdout:
            '[{"Name":"ollama.exe","ParentProcessId":1,"ProcessId":9001},' +
            '{"Name":"llama-server.exe","ParentProcessId":9001,"ProcessId":9002},' +
            '{"Name":"llama-server.exe","ParentProcessId":5000,"ProcessId":7777}]',
        };
      }
      if (cmd === 'taskkill') {
        calls.push(args);
        return { status: 0 };
      }
      return { status: 1 };
    };
    expect(killZombieLlamaServersSync({ platform: 'win32', spawnSync })).toBe(true);
    expect(calls).toEqual([['/PID', '7777', '/T', '/F']]);
  });
});
