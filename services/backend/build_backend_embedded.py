"""Fallback backend bundle: a relocatable CPython (python-build-standalone, the one uv
manages) with the runtime dependencies installed into it. No compilation, so packages
that don't survive Nuitka (torch 2.14 aborts on import in standalone mode) keep working.

    uv run python build_backend_embedded.py   ->  dist/embedded/{python/, run_backend.py}

The shell runs `python/python.exe run_backend.py` when no studymate-backend.exe exists.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "dist" / "embedded"
PY_DIR = OUT / "python"
TORCH_INDEX = "https://download.pytorch.org/whl/cpu"
# LGPL FFmpeg ships inside PyAV and OpenCV; the backend needs neither (see run_backend.py).
REMOVE_PACKAGES = ["av"]
DELETE_GLOBS = [
    "Lib/site-packages/cv2/opencv_videoio_ffmpeg*.dll",
    # pyopenjtalk-plus bundles the HTS voice "Mei" (CC BY 3.0) for its own vocoder; we only
    # use its text frontend (Kokoro speaks), so the voice is not shipped.
    "Lib/site-packages/pyopenjtalk/htsvoice",
    # spaCy/thinc wheels carry their Cython-generated C++ sources (~85 MB) and test suites
    "Lib/site-packages/spacy/**/*.cpp",
    "Lib/site-packages/thinc/**/*.cpp",
    "Lib/site-packages/spacy/tests",
    "Lib/site-packages/thinc/tests",
    "Lib/test",
    "Lib/idlelib",
    "Lib/tkinter",
    "tcl",
]


def run(*cmd: str) -> None:
    print(">", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=HERE)


def main() -> int:
    started = time.time()
    base = Path(sys.base_prefix)  # the uv-managed standalone CPython behind .venv
    if not (base / "python.exe").exists():
        print(f"not a standalone CPython: {base}", file=sys.stderr)
        return 1
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(base, PY_DIR, ignore=shutil.ignore_patterns("__pycache__", "site-packages"))
    (PY_DIR / "Lib" / "site-packages").mkdir(parents=True, exist_ok=True)
    python = str(PY_DIR / "python.exe")

    req = OUT / "requirements.txt"
    run("uv", "export", "--no-dev", "--no-hashes", "--no-emit-project", "--format", "requirements-txt", "-o", str(req))
    install = ["uv", "pip", "install", "--python", python, "--break-system-packages", "--extra-index-url", TORCH_INDEX,
               "--index-strategy", "unsafe-best-match"]
    run(*install, "-r", str(req))
    run(*install, "--no-deps", str(HERE))
    run("uv", "pip", "uninstall", "--python", python, "--break-system-packages", *REMOVE_PACKAGES)

    for pattern in DELETE_GLOBS:
        for path in PY_DIR.glob(pattern):
            shutil.rmtree(path) if path.is_dir() else path.unlink()
    shutil.copy2(HERE / "run_backend.py", OUT / "run_backend.py")
    run(python, "-m", "compileall", "-q", "-j", "0", str(PY_DIR / "Lib" / "site-packages" / "studymate"))

    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"[build-embedded] done in {(time.time() - started) / 60:.1f} min, {size / 1e9:.2f} GB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
