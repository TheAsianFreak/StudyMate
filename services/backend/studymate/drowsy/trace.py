"""Numeric drowsiness traces (JSON Lines) for replay and tuning.

A trace holds numbers only, never pixels:

    {"t": 12.345, "ear": 0.281, "pitch": 7.2, "face": true}      one analysed frame
    {"t": 13.0, "input": true}                                   a keyboard/mouse/pen input
    optional "label": "alert" | "drowsy" on frame lines          ground truth (synthetic traces)

`t` is seconds from the start of the session. Recording real sessions is opt-in
(`settings.drowsy.record_trace`, off by default) and stays on this PC.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import IO, Literal

Label = Literal["alert", "drowsy"]


@dataclass(frozen=True, slots=True)
class TraceRow:
    t: float
    face: bool = False
    ear: float | None = None
    pitch: float | None = None
    input: bool = False
    label: Label | None = None


def encode_row(row: TraceRow) -> str:
    if row.input:
        return json.dumps({"t": round(row.t, 3), "input": True})
    obj: dict[str, object] = {"t": round(row.t, 3), "face": row.face}
    if row.ear is not None:
        obj["ear"] = round(row.ear, 4)
    if row.pitch is not None:
        obj["pitch"] = round(row.pitch, 2)
    if row.label is not None:
        obj["label"] = row.label
    return json.dumps(obj)


def decode_row(line: str) -> TraceRow | None:
    line = line.strip()
    if not line:
        return None
    obj = json.loads(line)
    t = float(obj["t"])
    if obj.get("input"):
        return TraceRow(t=t, input=True)
    ear = obj.get("ear")
    pitch = obj.get("pitch")
    label = obj.get("label")
    return TraceRow(
        t=t,
        face=bool(obj.get("face", ear is not None)),
        ear=float(ear) if ear is not None else None,
        pitch=float(pitch) if pitch is not None else None,
        label=label if label in ("alert", "drowsy") else None,
    )


def read_trace(path: Path) -> Iterator[TraceRow]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            row = decode_row(line)
            if row is not None:
                yield row


def write_trace(path: Path, rows: Iterator[TraceRow] | list[TraceRow]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(encode_row(row) + "\n")
            n += 1
    return n


class TraceRecorder:
    """Appends numeric samples of one live session to `<dir>/drowsy-<timestamp>.jsonl`."""

    def __init__(self, directory: Path, t0: float) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"drowsy-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
        self._t0 = t0
        self._lock = threading.Lock()
        self._file: IO[str] | None = self.path.open("a", encoding="utf-8")

    def sample(self, t: float, face: bool, ear: float | None, pitch: float | None) -> None:
        self._write(TraceRow(t=t - self._t0, face=face, ear=ear, pitch=pitch))

    def input(self, t: float) -> None:
        self._write(TraceRow(t=t - self._t0, input=True))

    def _write(self, row: TraceRow) -> None:
        with self._lock:
            if self._file is not None:
                self._file.write(encode_row(row) + "\n")

    def close(self) -> None:
        with self._lock:
            f, self._file = self._file, None
        if f is not None:
            f.close()
