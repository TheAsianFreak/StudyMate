import js from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['out/**', 'dist/**', 'release/**', 'release-*/**', 'node_modules/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['src/renderer/**/*.ts'],
    rules: {
      // Renderer must not touch Node APIs directly; go through the preload `window.shell` API.
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['node:*', 'electron', 'fs', 'path', 'child_process', 'os'],
              message: 'Use the preload API.',
            },
          ],
        },
      ],
    },
  },
);
