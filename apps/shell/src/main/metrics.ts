import { app } from 'electron';
import type { ProcessMetric } from '../shared/ipc';

const INTERVAL_MS = 1000;

/** Samples per-process CPU and memory for the debug HUD (Phase 0 performance check). */
export class MetricsReporter {
  private timer: NodeJS.Timeout | null = null;

  constructor(private readonly report: (metrics: ProcessMetric[]) => void) {}

  start(): void {
    if (this.timer) return;
    this.timer = setInterval(() => this.report(sample()), INTERVAL_MS);
  }

  stop(): void {
    if (!this.timer) return;
    clearInterval(this.timer);
    this.timer = null;
  }
}

function sample(): ProcessMetric[] {
  return app.getAppMetrics().map((m) => ({
    type: m.type,
    pid: m.pid,
    cpu: m.cpu.percentCPUUsage,
    memoryMb: m.memory.workingSetSize / 1024,
  }));
}
