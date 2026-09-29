#!/usr/bin/env python3
"""Stage local-only character assets into the Godot project.

Copies the default avatar (models/avatars/tsukuyomi/tsukuyomi-a.vrm, not in git)
to apps/character/avatars/, writes its import settings, and optionally runs the
Godot headless import so the web export contains it as an imported scene.

Usage:
    python apps/character/tools/prepare_assets.py [--godot PATH] [--force]

--godot (or the GODOT environment variable) points at the Godot 4.7 editor
binary; without it only the files are staged and the import happens the next
time the editor opens the project.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PROJECT_DIR.parents[1]

# (source relative to the repo, destination relative to the Godot project)
AVATARS: list[tuple[str, str]] = [
    ("models/avatars/tsukuyomi/tsukuyomi-a.vrm", "avatars/tsukuyomi-a.vrm"),
]

# Import parameters for bundled VRMs. Only these keys are pinned; Godot fills in
# defaults for the rest. LODs are disabled: the character is small on screen and
# LOD switching distorts faces with blend shapes; shadow meshes are unused.
# Mesh compression off: uncompressed vertex attributes cut the WebGL GPU-process
# time of per-frame skinning by ~10% (Tsukuyomi, Chrome/ANGLE D3D11). The big
# win, merging same-material surfaces, happens at load time in VrmBody.
IMPORT_PARAMS: dict[str, str] = {
    "meshes/generate_lods": "false",
    "meshes/create_shadow_meshes": "false",
    "meshes/light_baking": "0",
    "meshes/force_disable_compression": "true",
    "skins/use_named_skins": "true",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pin_import_params(import_file: Path) -> bool:
    """Forces IMPORT_PARAMS into an existing .import file. Returns True if changed
    (Godot re-imports on the next --import / editor start)."""
    lines = import_file.read_text(encoding="utf-8").splitlines()
    missing = dict(IMPORT_PARAMS)
    in_params = False
    changed = False
    for i, line in enumerate(lines):
        if line.startswith("["):
            in_params = line.strip() == "[params]"
            continue
        key = line.split("=", 1)[0]
        if in_params and key in missing:
            wanted = f"{key}={missing.pop(key)}"
            if line != wanted:
                lines[i] = wanted
                changed = True
    if missing:
        if "[params]" not in lines:
            lines += ["", "[params]", ""]
        index = lines.index("[params]") + 1
        lines[index:index] = [f"{k}={v}" for k, v in missing.items()]
        changed = True
    if changed:
        import_file.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return changed


def write_import_file(dest: Path) -> bool:
    """Writes a minimal .import file, or pins IMPORT_PARAMS in an existing one.
    Returns True if anything was written."""
    import_file = dest.with_name(dest.name + ".import")
    if import_file.exists():
        return pin_import_params(import_file)
    res_path = "res://" + dest.relative_to(PROJECT_DIR).as_posix()
    lines = [
        "[remap]",
        "",
        'importer="scene"',
        "importer_version=1",
        'type="PackedScene"',
        "",
        "[deps]",
        "",
        f'source_file="{res_path}"',
        "",
        "[params]",
        "",
    ]
    lines += [f"{key}={value}" for key, value in IMPORT_PARAMS.items()]
    import_file.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return True


def stage(force: bool) -> bool:
    """Copies avatars into the project. Returns True if anything changed."""
    changed = False
    for src_rel, dest_rel in AVATARS:
        src = REPO_DIR / src_rel
        dest = PROJECT_DIR / dest_rel
        if not src.exists():
            print(f"missing source (download it first): {src}", file=sys.stderr)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if force or not dest.exists() or sha256(src) != sha256(dest):
            shutil.copy2(src, dest)
            print(f"copied {src_rel} -> apps/character/{dest_rel}")
            changed = True
        if write_import_file(dest):
            print(f"updated {dest.name}.import")
            changed = True
    # Keep the editor from importing export output (index.png etc.).
    export_dir = PROJECT_DIR / "export"
    export_dir.mkdir(exist_ok=True)
    (export_dir / ".gdignore").touch()
    return changed


def run_import(godot: str) -> int:
    print(f"importing with {godot}")
    result = subprocess.run(
        [godot, "--headless", "--path", str(PROJECT_DIR), "--import"],
        check=False,
    )
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--godot", default=os.environ.get("GODOT", ""), help="Godot editor binary")
    parser.add_argument("--force", action="store_true", help="copy even if unchanged")
    args = parser.parse_args()
    stage(args.force)
    if args.godot:
        return run_import(args.godot)
    print("skipping import (pass --godot or set GODOT)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
