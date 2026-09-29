"""Builds the standalone backend with Nuitka: `uv run python build_backend.py`.

Output: dist/run_backend.dist/studymate-backend.exe (+ libraries), copied into the
installer by electron-builder. LGPL binaries (FFmpeg via PyAV / OpenCV videoio) are
excluded or deleted so the bundle stays within the licence allowlist.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = HERE / "dist"
OUT = DIST / "run_backend.dist"
ICON = HERE.parents[1] / "apps" / "shell" / "build" / "icon.ico"

# Packages whose non-Python data files (configs, onnx, tflite, yaml) must ship.
DATA_PACKAGES = [
    "studymate", "faster_whisper", "mediapipe", "rapidocr", "pix2tex", "sympy", "g2pkk", "jamo",
    "misaki", "pyopenjtalk", "spacy", "thinc",
]  # fmt: skip
# Never needed at runtime; keeps the bundle small and avoids copyleft pieces.
NO_FOLLOW = ["av", "pytest", "IPython", "matplotlib", "tkinter", "notebook", "datamodel_code_generator", "nuitka"]
# LGPL FFmpeg shipped inside OpenCV wheels (camera capture uses MSMF/DirectShow only).
DELETE_GLOBS = [
    "**/opencv_videoio_ffmpeg*.dll", "**/av.libs/**", "**/avcodec*.dll", "**/avformat*.dll",
    "**/pyopenjtalk/htsvoice/**",  # CC BY 3.0 HTS voice; only OpenJTalk's text frontend is used
]  # fmt: skip


def main() -> int:
    from studymate import __version__

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--msvc=latest",
        "--assume-yes-for-downloads",
        f"--output-dir={DIST}",
        "--output-filename=studymate-backend.exe",
        "--include-package=studymate",
        "--windows-console-mode=attach",
        "--company-name=StudyMate",
        "--product-name=StudyMate Backend",
        f"--file-version={__version__}",
        f"--product-version={__version__}",
        "--noinclude-pytest-mode=nofollow",
        "--noinclude-setuptools-mode=nofollow",
        "--noinclude-unittest-mode=nofollow",
        "--jobs=16",
        "--noinclude-dlls=opencv_videoio_ffmpeg*",
        # torch aborts on import in standalone mode when its JIT is stubbed out.
        "--module-parameter=torch-disable-jit=no",
    ]
    if ICON.exists():
        cmd.append(f"--windows-icon-from-ico={ICON}")
    cmd += [f"--include-package-data={p}" for p in DATA_PACKAGES]
    cmd += [f"--nofollow-import-to={p}" for p in NO_FOLLOW]
    cmd.append(str(HERE / "run_backend.py"))

    started = time.time()
    print(" ".join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=HERE)
    if result.returncode != 0:
        return result.returncode

    removed = 0
    for pattern in DELETE_GLOBS:
        for path in OUT.glob(pattern):
            if path.is_file():
                path.unlink()
                removed += 1
            elif path.is_dir():
                shutil.rmtree(path)
                removed += 1
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"[build] done in {(time.time() - started) / 60:.1f} min, {size / 1e9:.2f} GB, removed {removed} LGPL files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
