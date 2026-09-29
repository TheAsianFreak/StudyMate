/// <reference types="vite/client" />
import type { ShellApi } from '../shared/ipc';

declare global {
  interface Window {
    shell: ShellApi;
  }
}
