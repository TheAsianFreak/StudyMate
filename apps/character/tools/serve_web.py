#!/usr/bin/env python3
"""Serves the web export (apps/character/export/web) for local testing.

/perf.html is tools/perf_harness.html (a stand-in Director that measures frame
times); everything else comes from the export directory. Single-threaded
export, so no COOP/COEP headers are needed. Responses are not cached, so a
re-export is picked up on reload.

Usage: python apps/character/tools/serve_web.py [--port 8060]
Then open http://127.0.0.1:8060/perf.html (?avatar=placeholder, ?phase=8).
"""

from __future__ import annotations

import argparse
import functools
import http.server
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
EXPORT_DIR = PROJECT_DIR / "export" / "web"
HARNESS = PROJECT_DIR / "tools" / "perf_harness.html"


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".pck": "application/octet-stream",
    }

    def translate_path(self, path: str) -> str:
        if path.split("?", 1)[0] == "/perf.html":
            return str(HARNESS)
        return super().translate_path(path)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8060)
    args = parser.parse_args()
    handler = functools.partial(Handler, directory=str(EXPORT_DIR))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"serving {EXPORT_DIR} on http://127.0.0.1:{args.port}/perf.html")
        server.serve_forever()


if __name__ == "__main__":
    main()
