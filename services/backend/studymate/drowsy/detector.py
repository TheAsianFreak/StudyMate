"""Drowsiness decision logic (SPEC 7.3). Pure: numbers in, protocol messages out.

Rules (all thresholds from `DrowsyConfig`, times in seconds on one monotonic clock):

- Calibration: the first `calibration_s` of face time. Baseline EAR = median of the samples
  that are not blinks (>= 75 % of the overall median), floored at `min_baseline_ear`. The
  median calibration pitch is the "looking at the screen" pitch.
- Closed eye: EAR < baseline * closed_ratio. Looking down lowers the eyelids with open eyes,
  so the ratio is reduced by `ear_pitch_comp_per_deg` per degree the head is below the
  screen pitch (at most `ear_pitch_comp_max`). This is relative to calibration, not to the
  rolling baseline, so minutes of reading on the desk do not turn into "closed" eyes.
- PERCLOS: time-weighted fraction of closed samples with a face over the last
  `perclos_window_s`. It is only judged once face data covers `perclos_min_coverage` of the
  window.
- Pitch drop: pitch rises (head goes down) `pitch_drop_deg` above its rolling baseline (median
  of the last `pitch_baseline_s`); it re-arms after falling back below half of that. Drops
  are counted over the last `pitch_drop_window_s`.
- normal -> candidate: PERCLOS >= threshold and >= `pitch_drops_required` recent drops.
  candidate -> drowsy: candidate held for `candidate_hold_s`. candidate -> normal when PERCLOS
  falls below threshold * `perclos_release_ratio`; drowsy -> normal additionally needs no
  pitch drop left in the window, so the state does not flap between microsleeps.
- paused: an input happened within `activity_hold_s`. Every new input also clears the
  PERCLOS window and drop history (the user was demonstrably awake at that moment).
- no_face: no face for more than `no_face_s`. A face lost while already candidate/drowsy
  keeps that state (head down on the desk), and a candidate still escalates.

Sensitivity multiplies the "how far" thresholds by `sensitivity_scale[sensitivity]` (high <
1 < low): the closed-eye drop (1 - ear_closed_ratio), the PERCLOS threshold and the pitch
drop angle.

`drowsy_state` is emitted on every change and every `state_interval_s`; during calibration
the state is limited to normal / no_face / paused and `drowsy_calibration` reports progress.
"""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass
from typing import Literal

from studymate.config import DrowsyConfig
from studymate.protocol.backend import DrowsyCalibration, DrowsyStateMessage

State = Literal["normal", "candidate", "drowsy", "no_face", "paused"]
Sensitivity = Literal["low", "normal", "high"]
Event = DrowsyCalibration | DrowsyStateMessage

_MAX_DT = 0.5  # a sample never counts for more than this (frame gaps, stalls)
_BLINK_REJECT = 0.75  # calibration samples below this fraction of the median are blinks
_MIN_CALIB_SAMPLES = 10
_DROP_REARM = 0.5  # fraction of the drop angle to fall back below before the next drop
_INPUT_EPS = 0.25  # s; the same input reported twice differs only by transport jitter
_PITCH_BASE_EVERY = 1.0  # s between rolling-median recomputations


@dataclass(frozen=True, slots=True)
class Sample:
    t: float
    face: bool
    ear: float | None = None
    pitch: float | None = None


@dataclass(frozen=True, slots=True)
class Thresholds:
    closed_ratio: float
    perclos: float
    pitch_drop_deg: float

    @classmethod
    def from_config(cls, cfg: DrowsyConfig, sensitivity: str) -> Thresholds:
        scale = cfg.sensitivity_scale.get(sensitivity, 1.0)
        return cls(
            closed_ratio=max(0.05, 1.0 - (1.0 - cfg.ear_closed_ratio) * scale),
            perclos=min(0.95, cfg.perclos_threshold * scale),
            pitch_drop_deg=cfg.pitch_drop_deg * scale,
        )


class DrowsyDetector:
    def __init__(self, cfg: DrowsyConfig, sensitivity: str = "normal") -> None:
        self.cfg = cfg
        self.thresholds = Thresholds.from_config(cfg, sensitivity)
        self.state: State | None = None
        self.baseline_ear: float | None = None
        self.perclos = 0.0
        self.pitch_offset = 0.0
        self._t_start: float | None = None
        self._t_prev: float | None = None
        self._last_face_t: float | None = None
        self._last_pitch: float | None = None
        # calibration
        self._calib_ears: list[float] = []
        self._calib_pitches: list[float] = []
        self._calib_time = 0.0
        self._last_calib_emit: float | None = None
        # evidence
        self._window: deque[tuple[float, float, bool]] = deque()  # (t, dt, closed)
        self._win_time = 0.0
        self._win_closed = 0.0
        self._drops: deque[float] = deque()
        self._drop_armed = True
        self._pitch_hist: deque[tuple[float, float]] = deque()
        self._pitch_base: float | None = None
        self._pitch_base_t = float("-inf")
        self._screen_pitch: float | None = None
        self._candidate_since: float | None = None
        # activity
        self._last_input: float | None = None
        self._input_pending = False
        self._last_state_emit: float | None = None

    # ---- inputs -------------------------------------------------------------------------

    @property
    def calibrated(self) -> bool:
        return self.baseline_ear is not None

    @property
    def drop_count(self) -> int:
        return len(self._drops)

    def note_input(self, t: float) -> None:
        """A keyboard/mouse/pen input happened at time `t` (same clock as samples)."""
        if self._last_input is None or t > self._last_input + _INPUT_EPS:
            self._input_pending = True
        if self._last_input is None or t > self._last_input:
            self._last_input = t

    def update(self, s: Sample) -> list[Event]:
        events: list[Event] = []
        if self._t_start is None:
            self._t_start = s.t
        dt = 0.0 if self._t_prev is None else min(max(s.t - self._t_prev, 0.0), _MAX_DT)
        self._t_prev = s.t

        face_ok = s.face and s.ear is not None
        if face_ok:
            self._last_face_t = s.t
        if s.face and s.pitch is not None:
            self._last_pitch = s.pitch
        missing_for = s.t - (self._last_face_t if self._last_face_t is not None else self._t_start)
        if self._input_pending:
            self._input_pending = False
            self._reset_evidence()
        paused = self._last_input is not None and s.t - self._last_input < self.cfg.activity_hold_s

        if not self.calibrated:
            new_state = self._calibrate(s, dt, face_ok, paused, missing_for, events)
        else:
            if face_ok:
                self._add_evidence(s, dt)
            self._prune(s.t)
            new_state = self._decide(s.t, paused, missing_for, face_ok)
        self._emit_state(new_state, s, face_ok, events)
        return events

    # ---- calibration --------------------------------------------------------------------

    def _calibrate(
        self, s: Sample, dt: float, face_ok: bool, paused: bool, missing_for: float, events: list[Event]
    ) -> State:
        if face_ok and s.ear is not None:
            self._calib_ears.append(s.ear)
            if s.pitch is not None:
                self._calib_pitches.append(s.pitch)
            self._calib_time += dt
        progress = min(self._calib_time / self.cfg.calibration_s, 1.0) if self.cfg.calibration_s > 0 else 1.0
        if progress >= 1.0 and len(self._calib_ears) >= _MIN_CALIB_SAMPLES:
            median = statistics.median(self._calib_ears)
            opened = [e for e in self._calib_ears if e >= median * _BLINK_REJECT] or self._calib_ears
            self.baseline_ear = max(statistics.median(opened), self.cfg.min_baseline_ear)
            if self._calib_pitches:
                self._pitch_base = self._screen_pitch = statistics.median(self._calib_pitches)
                self._pitch_base_t = s.t
                self._pitch_hist.extend((s.t, p) for p in self._calib_pitches)
            self._calib_ears.clear()
            self._calib_pitches.clear()
            self._reset_evidence()
            events.append(
                DrowsyCalibration(
                    type="drowsy_calibration",
                    progress=1.0,
                    done=True,
                    baseline_ear=round(self.baseline_ear, 4),
                )
            )
        elif self._last_calib_emit is None or s.t - self._last_calib_emit >= self.cfg.state_interval_s:
            self._last_calib_emit = s.t
            events.append(
                DrowsyCalibration(
                    type="drowsy_calibration", progress=round(min(progress, 0.99), 3), done=False
                )
            )
        if paused:
            return "paused"
        return "no_face" if missing_for > self.cfg.no_face_s else "normal"

    # ---- evidence -----------------------------------------------------------------------

    def _reset_evidence(self) -> None:
        self._window.clear()
        self._win_time = 0.0
        self._win_closed = 0.0
        self._drops.clear()
        self._drop_armed = True
        self.perclos = 0.0

    def _pitch_baseline(self, t: float) -> float | None:
        if self._pitch_hist and t - self._pitch_base_t >= _PITCH_BASE_EVERY:
            self._pitch_base = statistics.median(p for _, p in self._pitch_hist)
            self._pitch_base_t = t
        return self._pitch_base

    def _add_evidence(self, s: Sample, dt: float) -> None:
        assert s.ear is not None and self.baseline_ear is not None
        cfg, thr = self.cfg, self.thresholds
        offset = look_down = 0.0
        if s.pitch is not None:
            self._pitch_hist.append((s.t, s.pitch))
            base = self._pitch_baseline(s.t)
            if base is None:
                self._pitch_base = base = s.pitch
                self._pitch_base_t = s.t
            offset = s.pitch - base
            if self._screen_pitch is None:
                self._screen_pitch = s.pitch
            look_down = max(s.pitch - self._screen_pitch, 0.0)
            if offset >= thr.pitch_drop_deg and self._drop_armed:
                self._drops.append(s.t)
                self._drop_armed = False
            elif offset <= thr.pitch_drop_deg * _DROP_REARM:
                self._drop_armed = True
        self.pitch_offset = offset
        ratio = thr.closed_ratio - min(look_down * cfg.ear_pitch_comp_per_deg, cfg.ear_pitch_comp_max)
        closed = s.ear < self.baseline_ear * ratio
        self._window.append((s.t, dt, closed))
        self._win_time += dt
        if closed:
            self._win_closed += dt

    def _prune(self, t: float) -> None:
        horizon = t - self.cfg.perclos_window_s
        while self._window and self._window[0][0] <= horizon:
            _, dt, closed = self._window.popleft()
            self._win_time -= dt
            if closed:
                self._win_closed -= dt
        drop_horizon = t - self.cfg.pitch_drop_window_s
        while self._drops and self._drops[0] <= drop_horizon:
            self._drops.popleft()
        pitch_horizon = t - self.cfg.pitch_baseline_s
        while self._pitch_hist and self._pitch_hist[0][0] <= pitch_horizon:
            self._pitch_hist.popleft()
        if not self._window:
            self._win_time = self._win_closed = 0.0
        self.perclos = self._win_closed / self._win_time if self._win_time > 1e-9 else 0.0

    # ---- state machine ------------------------------------------------------------------

    def _decide(self, t: float, paused: bool, missing_for: float, face_ok: bool) -> State:
        cfg, thr = self.cfg, self.thresholds
        current = self.state
        if paused:
            self._candidate_since = None
            return "paused"
        face_lost = missing_for > cfg.no_face_s
        if current in ("candidate", "drowsy") and not face_ok:
            # Face gone while nodding off (head on the desk): hold the state, keep escalating.
            if current == "candidate" and self._held(t):
                return "drowsy"
            return current
        if face_lost:
            self._candidate_since = None
            return "no_face"
        covered = self._win_time >= cfg.perclos_min_coverage * cfg.perclos_window_s
        if current in ("candidate", "drowsy"):
            calm = self.perclos < thr.perclos * cfg.perclos_release_ratio
            if calm and (current == "candidate" or not self._drops):
                self._candidate_since = None
                return "normal"
            if current == "candidate" and self._held(t):
                return "drowsy"
            return current
        if covered and self.perclos >= thr.perclos and len(self._drops) >= cfg.pitch_drops_required:
            self._candidate_since = t
            return "drowsy" if cfg.candidate_hold_s <= 0 else "candidate"
        return "normal"

    def _held(self, t: float) -> bool:
        return self._candidate_since is not None and t - self._candidate_since >= self.cfg.candidate_hold_s

    def _emit_state(self, new_state: State, s: Sample, face_ok: bool, events: list[Event]) -> None:
        changed = new_state != self.state
        self.state = new_state
        due = self._last_state_emit is None or s.t - self._last_state_emit >= self.cfg.state_interval_s
        if not (changed or due):
            return
        self._last_state_emit = s.t
        pitch = self._last_pitch if self._last_pitch is not None else 0.0
        events.append(
            DrowsyStateMessage(
                type="drowsy_state",
                state=new_state,
                perclos=round(self.perclos, 3),
                pitch=round(pitch, 1),
                ear=round(s.ear, 4) if face_ok and s.ear is not None else None,
            )
        )
