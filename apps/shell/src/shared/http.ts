// HTTP helpers shared by the app:// protocol handler and the Vite dev server.

/** Lets a threaded Godot export use SharedArrayBuffer; harmless for single-threaded builds. */
export const CROSS_ORIGIN_ISOLATION_HEADERS: Record<string, string> = {
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Cross-Origin-Embedder-Policy': 'require-corp',
};

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json',
  '.wasm': 'application/wasm',
  '.pck': 'application/octet-stream',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
};

export function mimeType(ext: string): string {
  return MIME[ext.toLowerCase()] ?? 'application/octet-stream';
}
