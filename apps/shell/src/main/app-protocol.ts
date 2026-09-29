import { app, protocol } from 'electron';
import { readFile } from 'node:fs/promises';
import { extname, join, resolve, sep } from 'node:path';
import { CROSS_ORIGIN_ISOLATION_HEADERS, mimeType } from '../shared/http';

export const APP_SCHEME = 'app';
export const APP_ORIGIN = `${APP_SCHEME}://studymate`;

/** Godot web export directory. Overridable for testing other builds. */
function characterRoot(): string {
  const override = process.env['STUDYMATE_CHARACTER_DIR'];
  if (override) return resolve(override);
  if (app.isPackaged) return join(process.resourcesPath, 'character');
  return resolve(app.getAppPath(), '../character/export/web');
}

function rendererRoot(): string {
  return resolve(__dirname, '../renderer');
}

/** Maps a URL path to a file under root; null if it escapes root. */
function resolveInside(root: string, urlPath: string): string | null {
  const file = resolve(root, '.' + urlPath);
  return file.startsWith(root + sep) ? file : null;
}

/**
 * Serves the built renderer at app://studymate/ and the Godot export at
 * app://studymate/character/, both with cross-origin isolation headers.
 */
export function registerAppProtocol(): void {
  const renderer = rendererRoot();
  const character = characterRoot();

  protocol.handle(APP_SCHEME, async (request) => {
    const { pathname } = new URL(request.url);
    const path = decodeURIComponent(pathname);
    const file = path.startsWith('/character/')
      ? resolveInside(character, path.slice('/character'.length))
      : resolveInside(renderer, path);
    if (!file) return new Response('Forbidden', { status: 403 });

    try {
      const body = await readFile(file);
      return new Response(body, {
        headers: { 'Content-Type': mimeType(extname(file)), ...CROSS_ORIGIN_ISOLATION_HEADERS },
      });
    } catch {
      return new Response('Not Found', { status: 404 });
    }
  });
}
