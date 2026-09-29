"""Hardware detection and tier recommendation (SPEC section 8)."""

from __future__ import annotations

import json
import logging
import platform
import subprocess
import sys

import psutil

from studymate.config import Tier
from studymate.i18n import tr

log = logging.getLogger(__name__)
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_INTEGRATED_HINTS = (
    "radeon(tm) graphics",
    "radeon graphics",
    "intel(r) uhd",
    "intel(r) iris",
    "intel(r) graphics",
)


def detect() -> dict[str, object]:
    ram_gb = round(psutil.virtual_memory().total / 2**30, 1)
    gpus = _gpus()
    tier, reason = recommend(ram_gb, gpus)
    return {
        "cpu": _cpu_name(),
        "cores": psutil.cpu_count(logical=True) or 1,
        "ram_gb": ram_gb,
        "gpus": gpus,
        "recommended_tier": tier,
        "reason": reason,
    }


def recommend(ram_gb: float, gpus: list[dict[str, object]]) -> tuple[Tier, str]:
    discrete = [g for g in gpus if not _is_integrated(str(g["name"]))]
    vram = max((float(g["vram_gb"]) for g in discrete), default=0.0)  # type: ignore[arg-type]
    if vram >= 15.5 and ram_gb >= 30:  # 16 GB cards report 15.9-16.0
        reason = tr(
            f"VRAM {vram:.0f}GB, RAM {ram_gb:.0f}GB: 가장 정확한 14B 언어 모델을 쓸 수 있어요.",
            f"VRAM {vram:.0f}GB, RAM {ram_gb:.0f}GB: いちばん正確な 14B の言語モデルを使えます。",
            f"VRAM {vram:.0f} GB, RAM {ram_gb:.0f} GB: the most accurate 14B language model can run.",
        )
        if vram < 20:  # 14B + Qwen2.5-VL need about 17 GB together (llm/server.py swaps them)
            reason += tr(
                " 이미지 문제는 비전 모델과 번갈아 불러와서 10초쯤 더 걸려요 (빠른 쪽을 원하면 Pro).",
                "画像の問題は画像認識モデルと入れ替えて読み込むため、10秒ほど長くかかります（速さ重視なら Pro）。",
                " Image problems take about 10 seconds longer while it swaps with the vision model (Pro is faster).",
            )
        return "max", reason
    if vram >= 12 and ram_gb >= 30:
        return (
            "pro",
            tr(
                f"VRAM {vram:.0f}GB, RAM {ram_gb:.0f}GB: 8B 언어 모델과 비전 모델을 상시 사용할 수 있어요.",
                f"VRAM {vram:.0f}GB, RAM {ram_gb:.0f}GB: 8B の言語モデルと画像認識モデルを常に使えます。",
                f"VRAM {vram:.0f} GB, RAM {ram_gb:.0f} GB: the 8B language model and the vision model can stay loaded.",
            ),
        )
    if vram >= 8 and ram_gb >= 15:
        return "standard", tr(
            f"VRAM {vram:.0f}GB: 8B 언어 모델과 비전 모델(필요할 때)을 쓸 수 있어요.",
            f"VRAM {vram:.0f}GB: 8B の言語モデルと画像認識モデル（必要なとき）を使えます。",
            f"VRAM {vram:.0f} GB: the 8B language model and the vision model (when needed) can run.",
        )
    return "lite", tr(
        "전용 GPU 메모리가 부족해 4B 모델을 CPU로 실행해요.",
        "専用 GPU メモリが足りないため、4B モデルを CPU で動かします。",
        "Not enough dedicated GPU memory, so the 4B model runs on the CPU.",
    )


def localized(hw: dict[str, object]) -> dict[str, object]:
    """Detected hardware with the recommendation reason in the current request language."""
    ram = hw.get("ram_gb")
    gpus = hw.get("gpus")
    if not isinstance(ram, int | float) or not isinstance(gpus, list):
        return hw
    return {**hw, "reason": recommend(float(ram), gpus)[1]}


def _is_integrated(name: str) -> bool:
    lowered = name.lower()
    return any(h in lowered for h in _INTEGRATED_HINTS)


def _cpu_name() -> str:
    if sys.platform == "win32":
        name = _powershell("(Get-CimInstance Win32_Processor | Select-Object -First 1).Name")
        if name:
            return name.strip()
    return platform.processor() or platform.machine()


def _gpus() -> list[dict[str, object]]:
    """GPU names with dedicated memory. Win32_VideoController caps AdapterRAM at 4GB,
    so the registry's 64-bit qwMemorySize is preferred when present."""
    if sys.platform != "win32":
        return []
    script = (
        "$r=@(); Get-ItemProperty 'HKLM:\\SYSTEM\\ControlSet001\\Control\\Class\\"
        "{4d36e968-e325-11ce-bfc1-08002be10318}\\0*' -ErrorAction SilentlyContinue | "
        "ForEach-Object { if ($_.DriverDesc) { $r += [pscustomobject]@{name=$_.DriverDesc; "
        "mem=[uint64]($_.'HardwareInformation.qwMemorySize')} } }; $r | ConvertTo-Json -Compress"
    )
    raw = _powershell(script)
    gpus: list[dict[str, object]] = []
    try:
        data = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        data = []
    if isinstance(data, dict):
        data = [data]
    seen: set[str] = set()
    for item in data:
        name = str(item.get("name", "")).strip()
        if not name or name in seen or "virtual" in name.lower() or "basic" in name.lower():
            continue
        seen.add(name)
        gpus.append({"name": name, "vram_gb": round(float(item.get("mem") or 0) / 2**30, 1)})
    return gpus


def _powershell(script: str) -> str:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=_CREATE_NO_WINDOW,
        )
        return out.stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("powershell probe failed: %s", exc)
        return ""
