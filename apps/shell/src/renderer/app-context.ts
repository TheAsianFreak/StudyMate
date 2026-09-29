import type { ShellSettings } from '../shared/ipc';
import type { BackendClient } from './backend/client';
import type { Conversation } from './director/conversation';
import type { Director } from './director/director';
import type { SolveFlow } from './director/solve';
import type { Timeline } from './director/timeline';
import type { WakeUp } from './director/wake';
import type { Sfx } from './ui/sfx';
import type { Toasts } from './ui/toast';

/** Shared services handed to UI panels. */
export interface AppContext {
  director: Director;
  backend: BackendClient;
  timeline: Timeline;
  conversation: Conversation;
  solve: SolveFlow;
  wake: WakeUp;
  sfx: Sfx;
  toasts: Toasts;
  overlay: HTMLElement;
  settings(): ShellSettings;
  patchSettings(patch: Partial<ShellSettings>): Promise<void>;
  /** Voice preset chosen by the user (backend default when undefined). */
  voice(): string | undefined;
  setVoice(presetId: string): void;
  /** The current EULA was accepted in the onboarding (installs and AI features allowed). */
  eulaAccepted(): boolean;
  /** Shows the first-run onboarding card (EULA consent → install). */
  openOnboarding(): void;
}
