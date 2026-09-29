import { createReadStream, existsSync, statSync } from 'node:fs';
import { extname, resolve, sep } from 'node:path';
import { defineConfig } from 'electron-vite';
import type { Plugin } from 'vite';
import { CROSS_ORIGIN_ISOLATION_HEADERS, mimeType } from './src/shared/http';

const repoRoot = resolve(__dirname, '../..');
const characterDir = resolve(__dirname, '../character/export/web');
const protocolAlias = { '@studymate/protocol': resolve(repoRoot, 'packages/protocol/ts/generated') };

/** Serves the Godot web export at /character/ during `electron-vite dev`. */
function serveCharacter(): Plugin {
  return {
    name: 'studymate-serve-character',
    configureServer(server) {
      server.middlewares.use('/character', (req, res, next) => {
        const urlPath = decodeURIComponent((req.url ?? '/').split('?')[0] ?? '/');
        const file = resolve(characterDir, '.' + urlPath);
        if (!file.startsWith(characterDir + sep) || !existsSync(file) || !statSync(file).isFile()) {
          next();
          return;
        }
        res.setHeader('Content-Type', mimeType(extname(file)));
        createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig({
  main: {},
  preload: {},
  renderer: {
    resolve: { alias: protocolAlias },
    plugins: [serveCharacter()],
    server: {
      headers: CROSS_ORIGIN_ISOLATION_HEADERS,
      fs: { allow: [repoRoot] },
    },
  },
});
