"""Checks licences of the backend's *runtime* Python dependency closure.

Run inside the backend environment:
    cd services/backend && uv run python ../../scripts/check_py_licenses.py

Dev-only tools (pytest, ruff, nuitka, ...) are not part of the closure. Packages whose
licence is permissive but not on the short allowlist are listed in
scripts/license-exceptions-py.json with a reviewed reason.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "services" / "backend" / "pyproject.toml"
EXCEPTIONS = Path(__file__).with_name("license-exceptions-py.json")
# Packages excluded from the bundled executable (see services/backend/build_backend.py).
NOT_SHIPPED = {"av"}

ALLOWED = [
    r"\bMIT\b",
    r"Apache",
    r"\bBSD\b",
    r"BSD-[23]-Clause",
    r"\bISC\b",
    r"\bZlib\b",
    r"\b0BSD\b",
    r"Unlicense",
    r"CC0",
    r"MIT-0",
]
CLASSIFIER_OK = ("MIT License", "Apache Software License", "BSD License", "ISC License")
COPYLEFT = re.compile(r"\b(A?GPL|LGPL|GNU)\b", re.I)


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(req: str) -> tuple[str, bool]:
    """(name, applies) for a Requires-Dist entry; extras-only requirements don't apply."""
    name = re.split(r"[ ;<>=!~\[(]", req.strip(), maxsplit=1)[0]
    applies = "extra ==" not in req
    if "sys_platform" in req and "win32" not in req and "!= \"win32\"" not in req:
        applies = applies and "linux" not in req and "darwin" not in req
    return normalise(name), applies


def licence_of(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    expr = meta.get("License-Expression")
    if expr:
        return expr
    lic = (meta.get("License") or "").strip()
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    if lic and len(lic) < 120:
        return lic + (f" [{'; '.join(classifiers)}]" if classifiers else "")
    return "; ".join(classifiers) or (lic[:80] + "…" if lic else "UNKNOWN")


def is_allowed(text: str) -> bool:
    if COPYLEFT.search(text) and not re.search(r"\bOR\b|dual|/", text):
        return False
    return any(re.search(p, text, re.I) for p in ALLOWED) or any(c in text for c in CLASSIFIER_OK)


def main() -> int:
    roots = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]
    todo = [requirement_name(r)[0] for r in roots]
    seen: dict[str, metadata.Distribution] = {}
    while todo:
        name = todo.pop()
        if name in seen or name in NOT_SHIPPED:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        seen[name] = dist
        for req in dist.requires or []:
            dep, applies = requirement_name(req)
            if applies:
                todo.append(dep)

    exceptions = json.loads(EXCEPTIONS.read_text(encoding="utf-8")) if EXCEPTIONS.exists() else {}
    bad = []
    for name, dist in sorted(seen.items()):
        text = licence_of(dist)
        if is_allowed(text) or name in exceptions:
            continue
        bad.append(f"{name}=={dist.version}: {text}")
    if bad:
        print(f"[check-licenses-py] {len(bad)} runtime package(s) outside the allowlist:")
        for line in bad:
            print("  - " + line)
        return 1
    print(f"[check-licenses-py] {len(seen)} runtime packages OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
