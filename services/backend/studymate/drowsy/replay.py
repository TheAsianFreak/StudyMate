"""Replay numeric traces through the detector: state transitions, false alarms, latency.

    python -m studymate.drowsy.replay a.jsonl [b.jsonl ...] [--sensitivity normal]
        [--ignore-input] [--set perclos_threshold=0.35 ...] [--quiet]

An alarm is an entry into "drowsy". With ground-truth labels (synthetic traces), an alarm
while the label is "alert" is a false positive, and latency is measured from the start of each
"drowsy"-labelled episode to the first alarm inside it. Without labels, every alarm is
reported per hour (record an alert session to measure its false-positive rate).
Thresholds come from settings (STUDYMATE_DROWSY__* env vars work) plus --set overrides.
"""

from __future__ import annotations

import argparse
import statistics
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from studymate.config import DrowsyConfig
from studymate.drowsy.detector import DrowsyDetector, Sample
from studymate.drowsy.trace import TraceRow, read_trace


@dataclass
class Transition:
    t: float
    before: str | None
    after: str
    perclos: float
    drops: int
    pitch_offset: float


@dataclass
class Episode:
    onset: float
    end: float
    detected: float | None = None

    @property
    def latency(self) -> float | None:
        return None if self.detected is None else self.detected - self.onset


@dataclass
class ReplayResult:
    name: str
    duration_s: float = 0.0
    alert_s: float = 0.0
    labelled: bool = False
    baseline_ear: float | None = None
    transitions: list[Transition] = field(default_factory=list)
    alarms: list[float] = field(default_factory=list)
    false_alarms: list[float] = field(default_factory=list)
    episodes: list[Episode] = field(default_factory=list)


def replay(
    rows: Iterable[TraceRow],
    cfg: DrowsyConfig,
    sensitivity: str = "normal",
    use_input: bool = True,
    name: str = "trace",
) -> ReplayResult:
    det = DrowsyDetector(cfg, sensitivity)
    res = ReplayResult(name=name)
    t_first: float | None = None
    t_prev: float | None = None
    label_prev: str | None = None
    for row in rows:
        if row.input:
            if use_input:
                det.note_input(row.t)
            continue
        if t_first is None:
            t_first = row.t
        dt = 0.0 if t_prev is None else max(row.t - t_prev, 0.0)
        t_prev = row.t
        if row.label is not None:
            res.labelled = True
            if row.label == "alert":
                res.alert_s += dt
            if row.label == "drowsy" and label_prev != "drowsy":
                res.episodes.append(Episode(onset=row.t, end=row.t))
            if row.label == "drowsy":
                res.episodes[-1].end = row.t
            label_prev = row.label
        before = det.state
        det.update(Sample(t=row.t, face=row.face, ear=row.ear, pitch=row.pitch))
        if det.baseline_ear is not None and res.baseline_ear is None:
            res.baseline_ear = det.baseline_ear
        if det.state != before and det.state is not None:
            res.transitions.append(
                Transition(row.t, before, det.state, det.perclos, det.drop_count, det.pitch_offset)
            )
            if det.state == "drowsy":
                res.alarms.append(row.t)
                if row.label == "alert":
                    res.false_alarms.append(row.t)
                elif row.label == "drowsy" and res.episodes and res.episodes[-1].detected is None:
                    res.episodes[-1].detected = row.t
    if t_first is not None and t_prev is not None:
        res.duration_s = t_prev - t_first
    if not res.labelled:
        res.alert_s = res.duration_s
    return res


def _per_hour(count: int, seconds: float) -> float:
    return count / (seconds / 3600.0) if seconds > 0 else 0.0


def summarize(results: list[ReplayResult]) -> str:
    lines: list[str] = []
    alert_s = sum(r.alert_s for r in results)
    fa = sum(len(r.false_alarms) if r.labelled else len(r.alarms) for r in results)
    episodes = [e for r in results for e in r.episodes]
    latencies = [e.latency for e in episodes if e.latency is not None]
    lines.append(
        f"TOTAL alert/unlabelled time {alert_s / 3600:.2f} h, "
        f"false alarms {fa} ({_per_hour(fa, alert_s):.2f}/h)"
    )
    if episodes:
        missed = sum(1 for e in episodes if e.detected is None)
        if latencies:
            lines.append(
                f"drowsy episodes {len(episodes)}, detected {len(latencies)}, missed {missed}; latency "
                f"median {statistics.median(latencies):.1f} s, min {min(latencies):.1f} s, "
                f"max {max(latencies):.1f} s"
            )
        else:
            lines.append(f"drowsy episodes {len(episodes)}, none detected")
    return "\n".join(lines)


def _parse_overrides(pairs: list[str], base: DrowsyConfig) -> DrowsyConfig:
    update: dict[str, object] = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        if key not in DrowsyConfig.model_fields:
            raise SystemExit(f"unknown drowsy setting: {key}")
        update[key] = value
    return DrowsyConfig.model_validate({**base.model_dump(), **update})


def main(argv: list[str] | None = None) -> None:
    from studymate.config import get_settings

    ap = argparse.ArgumentParser(description="Replay numeric drowsiness traces through the detector.")
    ap.add_argument("traces", nargs="+", type=Path)
    ap.add_argument("--sensitivity", choices=["low", "normal", "high"], default="normal")
    ap.add_argument("--ignore-input", action="store_true", help="drop input events (worst case)")
    ap.add_argument("--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--quiet", action="store_true", help="summaries only")
    args = ap.parse_args(argv)

    cfg = _parse_overrides(args.overrides, get_settings().drowsy)
    results = []
    for path in args.traces:
        r = replay(read_trace(path), cfg, args.sensitivity, not args.ignore_input, path.name)
        results.append(r)
        if not args.quiet:
            print(f"== {r.name}")
            for tr in r.transitions:
                print(
                    f"  {tr.t:9.1f}s  {tr.before or '-':>9} -> {tr.after:<9} "
                    f"perclos={tr.perclos:.2f} drops={tr.drops} pitch_offset={tr.pitch_offset:+.1f}"
                )
        n_fa = len(r.false_alarms) if r.labelled else len(r.alarms)
        lat = ", ".join(f"{e.latency:.1f}s" if e.latency is not None else "missed" for e in r.episodes)
        print(
            f"{r.name}: {r.duration_s / 3600:.2f} h, baseline_ear={r.baseline_ear or 0:.3f}, "
            f"alarms {len(r.alarms)}, false {n_fa} ({_per_hour(n_fa, r.alert_s):.2f}/h)"
            + (f", latency {lat}" if r.episodes else "")
        )
    if len(results) > 1 or results[0].episodes:
        print(summarize(results))


if __name__ == "__main__":
    main()
