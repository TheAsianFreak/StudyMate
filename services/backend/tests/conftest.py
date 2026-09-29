"""Test isolation: each test session gets its own data dir."""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("STUDYMATE_DATA_DIR", tempfile.mkdtemp(prefix="studymate-test-"))
