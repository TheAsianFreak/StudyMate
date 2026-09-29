"""Model downloader: resumable HTTP downloads with sha256 verification.

Standard library only, so it also runs before the backend environment exists:

    python -m studymate.system.downloader --models-dir ../../models qwen3-4b bge-m3
    python -m studymate.system.downloader --models-dir ../../models --all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).with_name("models.json")
CHUNK = 1024 * 1024
USER_AGENT = "StudyMate-ModelDownloader/1"

ProgressCallback = Callable[["Progress"], None]


@dataclass(frozen=True)
class ModelFile:
    url: str
    path: str
    size: int | None = None
    sha256: str | None = None
    extract: bool = False


@dataclass(frozen=True)
class ModelEntry:
    id: str
    title: str
    category: str
    tiers: tuple[str, ...]
    required: bool
    license: str
    license_url: str
    files: tuple[ModelFile, ...]
    langs: tuple[str, ...] | None = None  # languages that use it; None = every language

    @property
    def total_size(self) -> int:
        return sum(f.size or 0 for f in self.files)

    def for_lang(self, lang: str) -> bool:
        return self.langs is None or lang in self.langs


@dataclass
class Progress:
    model_id: str
    file: str
    downloaded: int
    total: int | None
    done: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class ChecksumError(Exception):
    pass


def load_registry(path: Path = REGISTRY_PATH) -> list[ModelEntry]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        ModelEntry(
            id=m["id"],
            title=m["title"],
            category=m["category"],
            tiers=tuple(m["tiers"]),
            required=bool(m.get("required", False)),
            license=m["license"],
            license_url=m["license_url"],
            files=tuple(ModelFile(**f) for f in m["files"]),
            langs=tuple(m["langs"]) if m.get("langs") is not None else None,
        )
        for m in data["models"]
    ]


def _marker(target: Path) -> Path:
    return target.with_name(target.name + ".ok")


def is_installed(entry: ModelEntry, models_dir: Path) -> bool:
    return all(_marker(models_dir / f.path).exists() for f in entry.files)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        while chunk := fp.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def download_file(
    model_id: str,
    spec: ModelFile,
    models_dir: Path,
    on_progress: ProgressCallback | None = None,
    retries: int = 5,
) -> Path:
    """Downloads one file, resuming a previous partial download (`.part`)."""
    target = models_dir / spec.path
    if _marker(target).exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")

    for attempt in range(retries):
        try:
            _fetch(model_id, spec, part, on_progress)
            break
        except (OSError, urllib.error.URLError) as exc:
            if attempt == retries - 1:
                raise
            print(f"[downloader] {spec.path}: {exc}, retrying", file=sys.stderr)
            time.sleep(2 * (attempt + 1))

    if spec.size is not None and part.stat().st_size != spec.size:
        raise ChecksumError(f"{spec.path}: size {part.stat().st_size} != {spec.size}")
    if spec.sha256 and sha256_of(part) != spec.sha256:
        part.unlink()
        raise ChecksumError(f"{spec.path}: sha256 mismatch, partial file removed")
    part.replace(target)

    if spec.extract:
        with zipfile.ZipFile(target) as zf:
            _safe_extract(zf, target.parent)
        target.unlink()
    _marker(target).write_text(spec.sha256 or "unverified", encoding="utf-8")
    if on_progress:
        on_progress(Progress(model_id, spec.path, spec.size or 0, spec.size, done=True))
    return target


def _fetch(model_id: str, spec: ModelFile, part: Path, on_progress: ProgressCallback | None) -> None:
    have = part.stat().st_size if part.exists() else 0
    if spec.size is not None and have == spec.size:
        return
    headers = {"User-Agent": USER_AGENT}
    if have:
        headers["Range"] = f"bytes={have}-"
    req = urllib.request.Request(spec.url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        if have and resp.status != 206:
            have = 0  # server ignored Range: start over
        mode = "ab" if have else "wb"
        total = spec.size
        with part.open(mode) as fp:
            last = 0.0
            while chunk := resp.read(CHUNK):
                fp.write(chunk)
                have += len(chunk)
                now = time.monotonic()
                if on_progress and now - last > 0.5:
                    last = now
                    on_progress(Progress(model_id, spec.path, have, total))


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    root = dest.resolve()
    for member in zf.infolist():
        out = (dest / member.filename).resolve()
        if not out.is_relative_to(root):
            raise ChecksumError(f"unsafe path in archive: {member.filename}")
        if member.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member) as src, out.open("wb") as dst:
            shutil.copyfileobj(src, dst)


def install(entry: ModelEntry, models_dir: Path, on_progress: ProgressCallback | None = None) -> None:
    for spec in entry.files:
        download_file(entry.id, spec, models_dir, on_progress)


def remove(entry: ModelEntry, models_dir: Path) -> None:
    for spec in entry.files:
        for p in (models_dir / spec.path, _marker(models_dir / spec.path)):
            if p.exists():
                p.unlink()


def _cli() -> int:
    parser = argparse.ArgumentParser(description="StudyMate model downloader")
    parser.add_argument("ids", nargs="*", help="model ids from models.json")
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    registry = load_registry()
    if args.list:
        for m in registry:
            state = "installed" if is_installed(m, args.models_dir) else "-"
            langs = ",".join(m.langs) if m.langs else "all"
            print(f"{m.id:22} {m.total_size / 1e9:6.2f} GB  {m.license:12} {langs:8} {state}")
        return 0
    chosen = registry if args.all else [m for m in registry if m.id in args.ids]
    unknown = set(args.ids) - {m.id for m in registry}
    if unknown:
        print(f"unknown model ids: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    def report(p: Progress) -> None:
        pct = f"{100 * p.downloaded / p.total:5.1f}%" if p.total else f"{p.downloaded / 1e6:.0f} MB"
        print(f"[{p.model_id}] {p.file} {'done' if p.done else pct}", flush=True)

    for m in chosen:
        install(m, args.models_dir, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
