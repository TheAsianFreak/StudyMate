"""Synthetic numeric traces for exercising the detector (no camera, no images).

    python -m studymate.drowsy.synth alert  out/alert.jsonl  --minutes 240 --seed 1
    python -m studymate.drowsy.synth drowsy out/drowsy.jsonl --seed 1

alert:  a study session mixing typing (glances at the keyboard), screen reading, paper work
        (head down for minutes, lids lowered, glances up), yawns, eyes closed to think,
        look-aways and breaks away from the desk. Blinks 14-22/min. Labelled "alert".
drowsy: `alert_min` alert minutes, then `drowsy_min` minutes of dozing whose severity ramps
        from `severity0` to 1 over `ramp_min` (droopy lids, long blinks, slow closures,
        microsleeps where the head sinks and snaps back), then `wake_min` alert minutes with
        input again. At severity 0.5 the eyes are closed ~25 % of the time, at 1 ~50 %.

The generative model is a rough stand-in for real behaviour; tune on recorded traces
(`settings.drowsy.record_trace`) before trusting absolute numbers.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from studymate.drowsy.trace import TraceRow, write_trace


@dataclass
class _Timeline:
    t: np.ndarray
    closure: np.ndarray = field(init=False)  # 0 = open .. 1 = fully closed
    pitch: np.ndarray = field(init=False)  # degrees below upright (down = positive)
    lid: np.ndarray = field(init=False)  # extra multiplicative lid lowering (1 = none)
    away: np.ndarray = field(init=False)  # face not visible
    drowsy: np.ndarray = field(init=False)
    inputs: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        n = len(self.t)
        self.closure = np.zeros(n)
        self.pitch = np.zeros(n)
        self.lid = np.ones(n)
        self.away = np.zeros(n, dtype=bool)
        self.drowsy = np.zeros(n, dtype=bool)

    def span(self, start: float, end: float) -> slice:
        return slice(int(np.searchsorted(self.t, start)), int(np.searchsorted(self.t, end)))

    def trapezoid(
        self, start: float, dur: float, ramp_in: float, ramp_out: float
    ) -> tuple[slice, np.ndarray]:
        end = start + dur
        sl = self.span(start, end)
        tt = self.t[sl]
        ramp_in = max(min(ramp_in, dur / 2), 1e-3)
        ramp_out = max(min(ramp_out, dur / 2), 1e-3)
        shape = np.minimum(1.0, np.minimum((tt - start) / ramp_in, (end - tt) / ramp_out))
        return sl, np.clip(shape, 0.0, 1.0)

    def close_eyes(self, start: float, dur: float, depth: float, ramp: float) -> None:
        sl, shape = self.trapezoid(start, dur, ramp, ramp)
        self.closure[sl] = np.maximum(self.closure[sl], depth * shape)

    def move_head(self, start: float, dur: float, amp: float, ramp_in: float, ramp_out: float) -> None:
        sl, shape = self.trapezoid(start, dur, ramp_in, ramp_out)
        self.pitch[sl] += amp * shape


def _grid(seconds: float, fps: float, rng: np.random.Generator) -> np.ndarray:
    n = int(seconds * fps * 1.1) + 10
    steps = np.clip(rng.normal(1.0, 0.08, n), 0.7, 1.3) / fps
    steps[rng.random(n) < 0.005] *= 3.0  # occasional stalls
    t = np.cumsum(steps)
    return t[t < seconds]


def _poisson(rng: np.random.Generator, start: float, end: float, per_min: float) -> list[float]:
    if per_min <= 0:
        return []
    out: list[float] = []
    cur = start + rng.exponential(60.0 / per_min)
    while cur < end:
        out.append(cur)
        cur += rng.exponential(60.0 / per_min)
    return out


@dataclass
class _Person:
    ear0: float
    pitch0: float
    lid_k: float  # fractional EAR loss per degree of looking down (open eyes)
    blink_rate: float

    @classmethod
    def random(cls, rng: np.random.Generator) -> _Person:
        return cls(
            ear0=rng.uniform(0.24, 0.32),
            pitch0=rng.uniform(-5.0, 12.0),
            lid_k=rng.uniform(0.008, 0.013),
            blink_rate=rng.uniform(14.0, 22.0),
        )


def _blinks(
    tl: _Timeline, rng: np.random.Generator, start: float, end: float, rate: float, long: float = 0.0
) -> None:
    for s in _poisson(rng, start, end, rate):
        dur = rng.uniform(0.15, 0.4) + long * rng.uniform(0.0, 0.5)
        tl.close_eyes(s, dur, rng.uniform(0.75, 1.0), dur / 2)


def _alert_block(tl: _Timeline, rng: np.random.Generator, p: _Person, start: float, end: float) -> None:
    """Alert studying between `start` and `end`."""
    cur = start
    while cur < end:
        kind = rng.choice(["typing", "screen", "paper", "away"], p=[0.38, 0.34, 0.22, 0.06])
        dur = {
            "typing": rng.uniform(120, 600),
            "screen": rng.uniform(120, 600),
            "paper": rng.uniform(60, 480),
        }.get(str(kind), rng.uniform(30, 180))
        seg_end = min(cur + dur, end)
        if kind == "away":
            tl.away[tl.span(cur, seg_end)] = True
            cur = seg_end
            continue
        if kind == "typing":
            tl.inputs.extend(_poisson(rng, cur, seg_end, 40.0))
            for g in _poisson(rng, cur, seg_end, 2.0):  # look at the keyboard
                d = rng.uniform(0.5, 3.0)
                tl.move_head(g, d, rng.uniform(12.0, 30.0), 0.25, 0.25)
                tl.lid[tl.span(g, g + d)] *= rng.uniform(0.9, 1.0)
            _blinks(tl, rng, cur, seg_end, p.blink_rate)
        elif kind == "screen":
            tl.inputs.extend(_poisson(rng, cur, seg_end, 4.0))  # scrolling, clicks
            for g in _poisson(rng, cur, seg_end, 0.4):
                tl.move_head(g, rng.uniform(0.5, 3.0), rng.uniform(10.0, 25.0), 0.3, 0.3)
            _blinks(tl, rng, cur, seg_end, p.blink_rate * 0.6)
        else:  # paper: head down for minutes, eyes lower than the head, glances up to the screen
            amp = rng.uniform(15.0, 32.0)
            tl.move_head(cur, seg_end - cur, amp, 1.0, 1.0)
            tl.lid[tl.span(cur, seg_end)] *= rng.uniform(0.9, 1.0)
            for g in _poisson(rng, cur, seg_end, 2.5):
                tl.move_head(g, rng.uniform(1.0, 5.0), -amp * rng.uniform(0.7, 1.0), 0.4, 0.4)
            sl = tl.span(cur, seg_end)
            tl.pitch[sl] += 3.0 * np.sin(tl.t[sl] * rng.uniform(0.5, 1.5))  # writing bob
            _blinks(tl, rng, cur, seg_end, p.blink_rate)
        cur = seg_end
    for y in _poisson(rng, start, end, 1 / 12):  # yawn: squint and head back
        d = rng.uniform(2.0, 5.0)
        tl.close_eyes(y, d, rng.uniform(0.5, 0.9), 0.5)
        tl.move_head(y, d, -rng.uniform(5.0, 15.0), 0.8, 0.8)
    for c in _poisson(rng, start, end, 1 / 30):  # eyes closed to think / rest
        tl.close_eyes(c, rng.uniform(2.0, 6.0), 1.0, 0.2)
    for a in _poisson(rng, start, end, 1 / 8):  # turning away, rubbing eyes, stretching
        tl.away[tl.span(a, a + rng.uniform(1.0, 8.0))] = True


def _drowsy_block(
    tl: _Timeline, rng: np.random.Generator, start: float, end: float, severity0: float, ramp: float
) -> None:
    tl.drowsy[tl.span(start, end)] = True

    def severity(t: np.ndarray | float) -> np.ndarray:
        return np.minimum(1.0, severity0 + (1.0 - severity0) * (np.asarray(t) - start) / max(ramp, 1e-3))

    sl = tl.span(start, end)
    sev = severity(tl.t[sl])
    tl.lid[sl] *= 1.0 - 0.12 * sev  # droopy lids
    tl.pitch[sl] += 5.0 * sev  # slouching
    step = 30.0
    cur = start
    while cur < end:  # event rates follow the severity in 30 s steps
        nxt = min(cur + step, end)
        s = float(severity(cur))
        _blinks(tl, rng, cur, nxt, rng.uniform(18.0, 25.0), long=s)
        for c in _poisson(rng, cur, nxt, 0.5 + 3.0 * s):  # slow closures
            tl.close_eyes(c, rng.uniform(1.0, 1.5 + 2.5 * s), 0.95, 0.3)
        for m in _poisson(rng, cur, nxt, 0.3 + 2.2 * s):  # microsleep with a nod
            d = rng.uniform(2.0, 3.0 + 7.0 * s)
            tl.close_eyes(m, d, 1.0, 0.3)
            tl.move_head(m, d, rng.uniform(15.0, 40.0), d * rng.uniform(0.5, 0.8), 0.35)
        cur = nxt


def _render(tl: _Timeline, rng: np.random.Generator, p: _Person) -> list[TraceRow]:
    n = len(tl.t)
    drift = 1.0 + 0.03 * np.sin(tl.t / rng.uniform(200.0, 600.0) + rng.uniform(0, 6.28))  # lighting
    looking_down = np.clip(tl.pitch, 0.0, 40.0)
    ear_open = p.ear0 * drift * tl.lid * np.maximum(0.5, 1.0 - p.lid_k * looking_down)
    ear = ear_open * (1.0 - 0.92 * tl.closure) * (1.0 + rng.normal(0.0, 0.045, n))
    sway = 2.0 * np.sin(tl.t / rng.uniform(20.0, 60.0))
    pitch = p.pitch0 + tl.pitch + sway + rng.normal(0.0, 1.0, n)
    face = ~tl.away & (tl.pitch < 38.0) & (rng.random(n) > 0.003)  # steep nods lose the face
    rows = [
        TraceRow(
            t=float(tl.t[i]),
            face=bool(face[i]),
            ear=float(max(ear[i], 0.0)) if face[i] else None,
            pitch=float(pitch[i]) if face[i] else None,
            label="drowsy" if tl.drowsy[i] else "alert",
        )
        for i in range(n)
    ]
    rows.extend(TraceRow(t=float(x), input=True) for x in tl.inputs)
    rows.sort(key=lambda r: r.t)
    return rows


def alert_session(minutes: float = 240.0, seed: int = 0, fps: float = 12.0) -> list[TraceRow]:
    rng = np.random.default_rng(seed)
    p = _Person.random(rng)
    seconds = minutes * 60.0
    tl = _Timeline(_grid(seconds, fps, rng))
    _blinks(tl, rng, 0.0, 8.0, p.blink_rate)  # calibration: looking at the screen
    _alert_block(tl, rng, p, 8.0, seconds)
    return _render(tl, rng, p)


def drowsy_session(
    seed: int = 0,
    fps: float = 12.0,
    alert_min: float = 5.0,
    drowsy_min: float = 15.0,
    wake_min: float = 5.0,
    severity0: float = 0.5,
    ramp_min: float = 3.0,
) -> list[TraceRow]:
    rng = np.random.default_rng(seed)
    p = _Person.random(rng)
    a, d = alert_min * 60.0, drowsy_min * 60.0
    total = a + d + wake_min * 60.0
    tl = _Timeline(_grid(total, fps, rng))
    _blinks(tl, rng, 0.0, 8.0, p.blink_rate)
    _alert_block(tl, rng, p, 8.0, a)
    tl.away[tl.span(8.0, a)] = False  # keep the user at the desk before dozing off
    _drowsy_block(tl, rng, a, a + d, severity0, ramp_min * 60.0)
    tl.inputs.extend(_poisson(rng, a + d + 1.0, total, 30.0))  # woken up, typing again
    _blinks(tl, rng, a + d, total, p.blink_rate)
    return _render(tl, rng, p)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Write a synthetic numeric drowsiness trace (JSONL).")
    ap.add_argument("kind", choices=["alert", "drowsy"])
    ap.add_argument("out", type=Path)
    ap.add_argument("--minutes", type=float, default=240.0, help="alert trace length")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fps", type=float, default=12.0)
    args = ap.parse_args(argv)
    rows = (
        alert_session(args.minutes, args.seed, args.fps)
        if args.kind == "alert"
        else drowsy_session(args.seed, args.fps)
    )
    n = write_trace(args.out, rows)
    print(f"{args.out}: {n} rows")


if __name__ == "__main__":
    main()
