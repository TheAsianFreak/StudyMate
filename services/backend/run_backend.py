"""Entry point of the bundled backend executable (Nuitka).

faster-whisper imports PyAV at module load for file decoding, which we never use (audio
arrives as numpy arrays). PyAV bundles LGPL FFmpeg, so the bundle excludes it and a
placeholder module satisfies the import.
"""

from __future__ import annotations

import sys
import types

if "av" not in sys.modules:
    try:
        import av  # noqa: F401  (present in the development environment)
    except ImportError:
        sys.modules["av"] = types.ModuleType("av")

from studymate.main import run  # noqa: E402

if __name__ == "__main__":
    run()
