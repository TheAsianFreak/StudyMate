import { app } from 'electron';
import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import { existsSync, mkdirSync, openSync } from 'node:fs';
import { createServer } from 'node:net';
import { join, resolve } from 'node:path';
import type { BackendInfo } from '../shared/ipc';

const PREFERRED_PORT = 8765;
const HEALTH_TIMEOUT_MS = 120_000;
const MAX_RESTARTS = 3;

/**
 * Starts and supervises the Python backend (FastAPI on 127.0.0.1).
 * Dev: the backend's uv virtualenv. Packaged: the Nuitka-built executable in resources.
 */
export class BackendSidecar {
  private child: ChildProcess | null = null;
  private restarts = 0;
  private stopping = false;
  info: BackendInfo = { url: '', state: 'starting' };

  constructor(private readonly onChange: (info: BackendInfo) => void) {}

  async start(): Promise<void> {
    const port = await freePort(PREFERRED_PORT);
    const url = `http://127.0.0.1:${port}`;
    const { command, args, cwd } = this.command(port);
    const logDir = join(app.getPath('userData'), 'logs');
    mkdirSync(logDir, { recursive: true });
    const log = openSync(join(logDir, 'backend.log'), 'a');

    this.update({ url, state: 'starting' });
    this.child = spawn(command, args, {
      cwd,
      env: {
        ...process.env,
        STUDYMATE_PORT: String(port),
        STUDYMATE_DATA_DIR: app.getPath('userData'),
        STUDYMATE_MODELS_DIR: modelsDir(),
        PYTHONIOENCODING: 'utf-8',
        HF_HUB_OFFLINE: '1',
      },
      stdio: ['ignore', log, log],
      windowsHide: true,
    });
    this.child.once('exit', (code) => this.onExit(code));

    const healthy = await waitForHealth(
      `${url}/health`,
      HEALTH_TIMEOUT_MS,
      () => this.child === null,
    );
    this.update({ url, state: healthy ? 'ready' : 'failed' });
  }

  /** Kills the backend and every process it spawned (llama-server). */
  stop(): void {
    this.stopping = true;
    const pid = this.child?.pid;
    this.child = null;
    if (pid === undefined) return;
    if (process.platform === 'win32') {
      spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true });
    } else {
      process.kill(pid, 'SIGTERM');
    }
  }

  private onExit(code: number | null): void {
    this.child = null;
    if (this.stopping) return;
    if (this.restarts < MAX_RESTARTS) {
      this.restarts++;
      console.warn(
        `[sidecar] backend exited (${code}), restarting ${this.restarts}/${MAX_RESTARTS}`,
      );
      void this.start();
    } else {
      this.update({ ...this.info, state: 'failed' });
    }
  }

  private update(info: BackendInfo): void {
    this.info = info;
    this.onChange(info);
  }

  private command(port: number): { command: string; args: string[]; cwd: string } {
    if (app.isPackaged) {
      // Nuitka build when available, otherwise the embedded CPython bundle
      // (services/backend/build_backend.py / build_backend_embedded.py).
      const dir = join(process.resourcesPath, 'backend');
      const exe = join(dir, 'studymate-backend.exe');
      if (existsSync(exe)) return { command: exe, args: [], cwd: dir };
      return { command: join(dir, 'python', 'python.exe'), args: ['run_backend.py'], cwd: dir };
    }
    const backendDir = resolve(app.getAppPath(), '../../services/backend');
    const python = join(backendDir, '.venv', 'Scripts', 'python.exe');
    if (!existsSync(python)) {
      throw new Error(`backend virtualenv not found: run "uv sync" in ${backendDir}`);
    }
    return {
      command: python,
      args: ['-m', 'uvicorn', 'studymate.main:app', '--host', '127.0.0.1', '--port', String(port)],
      cwd: backendDir,
    };
  }
}

/** Models live in the repo during development and in the user's app data when installed. */
export function modelsDir(): string {
  if (process.env['STUDYMATE_MODELS_DIR']) return process.env['STUDYMATE_MODELS_DIR'];
  return app.isPackaged
    ? join(app.getPath('userData'), 'models')
    : resolve(app.getAppPath(), '../../models');
}

async function waitForHealth(
  url: string,
  timeoutMs: number,
  aborted: () => boolean,
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline && !aborted()) {
    try {
      const res = await fetch(url);
      if (res.ok) return true;
    } catch {
      // not listening yet
    }
    await new Promise((r) => setTimeout(r, 400));
  }
  return false;
}

function freePort(preferred: number): Promise<number> {
  const tryPort = (port: number): Promise<number | null> =>
    new Promise((resolvePort) => {
      const srv = createServer();
      srv.once('error', () => resolvePort(null));
      srv.listen(port, '127.0.0.1', () => srv.close(() => resolvePort(port)));
    });
  return (async () => {
    for (let p = preferred; p < preferred + 20; p++) {
      if ((await tryPort(p)) !== null) return p;
    }
    const any = await new Promise<number>((resolvePort) => {
      const srv = createServer();
      srv.listen(0, '127.0.0.1', () => {
        const address = srv.address();
        const port = typeof address === 'object' && address ? address.port : preferred;
        srv.close(() => resolvePort(port));
      });
    });
    return any;
  })();
}
