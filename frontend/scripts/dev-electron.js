import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import net from 'node:net';

const __filename = fileURLToPath(import.meta.url);
const root = path.resolve(path.dirname(__filename), '..');

const procs = [];

function spawnCommand({ name, command, args, options }) {
  const proc = spawn(command, args, options);

  proc.stdout?.on('data', (chunk) => {
    process.stdout.write(`[${name}] ${chunk}`);
  });

  proc.stderr?.on('data', (chunk) => {
    process.stderr.write(`[${name}] ${chunk}`);
  });

  proc.on('exit', (code, signal) => {
    console.log(`[${name}] exited with code=${code} signal=${signal}`);
    if (signal !== 'SIGTERM' && signal !== 'SIGINT') {
      shutdown();
    }
  });

  return proc;
}

function shutdown() {
  for (const proc of procs) {
    if (!proc.killed) {
      proc.kill('SIGTERM');
    }
  }
}

async function checkTcpPort(host, port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host, port }, () => {
      socket.destroy();
      resolve(true);
    });

    socket.on('error', () => {
      resolve(false);
    });

    socket.setTimeout(500, () => {
      socket.destroy();
      resolve(false);
    });
  });
}

async function waitForDevServer() {
  const ports = [5173, 5174, 5175, 4173, 3000];
  const deadline = Date.now() + 20000;

  while (Date.now() < deadline) {
    for (const port of ports) {
      if (await checkTcpPort('127.0.0.1', port)) {
        return `http://127.0.0.1:${port}`;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error('Dev-server did not become available in time');
}

function spawnElectron(env = {}) {
  const command = 'npm';
  const args = ['run', 'start:dev'];
  const options = { cwd: root, shell: true, env: { ...process.env, ...env } };
  return spawnCommand({ name: 'electron', command, args, options });
}

function spawnVite() {
  const command = 'npm';
  const args = ['run', 'dev'];
  const options = { cwd: root, shell: true, env: { ...process.env } };
  return spawnCommand({ name: 'vite', command, args, options });
}

process.on('SIGINT', () => {
  shutdown();
  process.exit(0);
});

process.on('SIGTERM', () => {
  shutdown();
});

(async () => {
  const viteProc = spawnVite();
  procs.push(viteProc);

  try {
    const devUrl = await waitForDevServer();
    console.log(`Dev server is ready at ${devUrl}`);
    const electronEnv = {
      COREX_FRONTEND_URL: devUrl,
      COREX_OPEN_DEVTOOLS: '1',
    };
    procs.push(spawnElectron(electronEnv));
  } catch (error) {
    console.error(error);
    shutdown();
    process.exit(1);
  }
})();
