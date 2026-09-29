import type { ClientMessage, ServerMessage, Status } from '@studymate/protocol';
import { getLang, t, tryT } from '../../shared/i18n';
import type { BackendInfo } from '../../shared/ipc';

type ServerType = ServerMessage['type'];
type Of<T extends ServerType> = Extract<ServerMessage, { type: T }>;
type Listener = (msg: ServerMessage) => void;

const RECONNECT_MS = 1500;

/**
 * A failed request. `message` is user-facing in the current UI language: known backend
 * error codes map to the shell's own text (the backend writes Korean), anything else keeps
 * the backend's message, which stays available as `backendMessage`.
 */
export class BackendError extends Error {
  readonly backendMessage: string;

  constructor(
    readonly code: string,
    message: string,
  ) {
    super(localizeError(code, message));
    this.backendMessage = message;
  }
}

/** The localized text for a backend `error {code, message}`. */
export function localizeError(code: string, message: string): string {
  return tryT(`error.${code}`) ?? message;
}

/** User-facing text for anything a request may throw. */
export function errorText(err: unknown): string {
  if (err instanceof BackendError) return err.message;
  return err instanceof Error ? err.message : String(err);
}

/**
 * WebSocket client for the Python backend. Requests carry an `id`; responses and
 * progress events with the same id are routed back to the caller, everything else
 * (drowsy_state, camera_state, pushed status) goes to type listeners.
 */
export class BackendClient {
  status: Status | null = null;
  connected = false;
  /** The user's saved address, sent in `hello` (ShellSettings.address). */
  address = '';
  /** The address the last `hello` carried (its status reply echoes the screened one). */
  helloAddress = '';
  private ws: WebSocket | null = null;
  private url = '';
  private seq = 0;
  private readonly listeners = new Map<string, Set<Listener>>();
  private readonly pending = new Map<string, (msg: ServerMessage) => void>();
  private readonly connectionListeners = new Set<(connected: boolean) => void>();

  setInfo(info: BackendInfo): void {
    if (info.state !== 'ready' || !info.url) return;
    const wsUrl = info.url.replace(/^http/, 'ws') + '/ws';
    if (wsUrl === this.url && this.ws) return;
    this.url = wsUrl;
    this.connect();
  }

  onConnection(listener: (connected: boolean) => void): void {
    this.connectionListeners.add(listener);
  }

  on<T extends ServerType>(type: T, listener: (msg: Of<T>) => void): () => void {
    let set = this.listeners.get(type);
    if (!set) {
      set = new Set();
      this.listeners.set(type, set);
    }
    set.add(listener as Listener);
    return () => set.delete(listener as Listener);
  }

  newId(prefix = 'r'): string {
    return `${prefix}${Date.now().toString(36)}${(this.seq++).toString(36)}`;
  }

  /** Fire-and-forget message. */
  send(msg: ClientMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
  }

  /**
   * Sends a request and resolves with the first message of `until` type carrying the same id.
   * Other messages with that id (progress) go to `onProgress`; an `error` rejects.
   */
  request<T extends ServerType>(
    msg: ClientMessage & { id: string },
    until: T,
    onProgress?: (msg: ServerMessage) => void,
    timeoutMs = 10 * 60_000,
  ): Promise<Of<T>> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState !== WebSocket.OPEN) {
        reject(new BackendError('offline', t('error.offline')));
        return;
      }
      const timer = setTimeout(() => {
        this.pending.delete(msg.id);
        reject(new BackendError('timeout', t('error.timeout')));
      }, timeoutMs);
      this.pending.set(msg.id, (reply) => {
        if (reply.type === 'error') {
          clearTimeout(timer);
          this.pending.delete(msg.id);
          reject(new BackendError(reply.code, reply.message));
        } else if (reply.type === until) {
          clearTimeout(timer);
          this.pending.delete(msg.id);
          resolve(reply as Of<T>);
        } else {
          onProgress?.(reply);
        }
      });
      this.ws.send(JSON.stringify(msg));
    });
  }

  private connect(): void {
    this.ws?.close();
    const ws = new WebSocket(this.url);
    this.ws = ws;
    ws.onopen = () => {
      this.setConnected(true);
      this.helloAddress = this.address;
      // The backend follows the shell's language (LLM output, TTS, STT, curriculum) and
      // the saved address (how the character calls the user).
      this.send({
        type: 'hello',
        id: this.newId('hello'),
        client: 'shell',
        lang: getLang(),
        profile: { address: this.address },
      });
    };
    ws.onmessage = (ev) => this.dispatch(String(ev.data));
    ws.onclose = () => {
      if (this.ws !== ws) return;
      this.setConnected(false);
      for (const [id, cb] of this.pending) {
        cb({ type: 'error', id, code: 'disconnected', message: t('error.disconnected') });
      }
      setTimeout(() => {
        if (this.ws === ws) this.connect();
      }, RECONNECT_MS);
    };
  }

  private setConnected(connected: boolean): void {
    this.connected = connected;
    for (const l of this.connectionListeners) l(connected);
  }

  private dispatch(raw: string): void {
    let msg: ServerMessage;
    try {
      msg = JSON.parse(raw) as ServerMessage;
    } catch {
      return;
    }
    if (msg.type === 'status') this.status = msg;
    const id = 'id' in msg ? msg.id : undefined;
    if (id && this.pending.has(id)) this.pending.get(id)?.(msg);
    for (const l of this.listeners.get(msg.type) ?? []) l(msg);
  }
}
