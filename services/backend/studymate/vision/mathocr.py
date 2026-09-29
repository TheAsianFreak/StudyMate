"""pix2tex (LaTeX-OCR) formula recognition, loaded from models/ only.

`pix2tex.cli.LatexOCR` is not used on purpose: it downloads checkpoints when missing,
changes the process working directory and copies every result to the user's clipboard.
This wrapper rebuilds the same model from the package config with explicit paths.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)


def _offline_env() -> None:
    # albumentations (imported by pix2tex) checks PyPI for updates on import; transformers
    # may contact the Hub. Neither is allowed at runtime (CLAUDE.md rule 7).
    os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def _minmax_size(img: Image.Image, max_dims: list[int], min_dims: list[int]) -> Image.Image:
    ratios = [a / b for a, b in zip(img.size, max_dims, strict=True)]
    if any(r > 1 for r in ratios):
        size = np.array(img.size) // max(ratios)
        img = img.resize(tuple(size.astype(int)), Image.Resampling.BILINEAR)
    padded = [max(d, m) for d, m in zip(img.size, min_dims, strict=True)]
    if padded != list(img.size):
        canvas = Image.new("L", (padded[0], padded[1]), 255)
        canvas.paste(img, img.getbbox())
        img = canvas
    return img


class MathOcr:
    """Image of a formula -> LaTeX string (CPU)."""

    def __init__(self, weights: Path, resizer: Path | None) -> None:
        _offline_env()
        import pix2tex
        import torch
        import yaml
        from munch import Munch
        from pix2tex.models import get_model
        from pix2tex.utils import parse_args
        from transformers import PreTrainedTokenizerFast

        pkg = Path(pix2tex.__file__).parent / "model"
        with (pkg / "settings" / "config.yaml").open(encoding="utf-8") as fp:
            params = yaml.safe_load(fp)
        args = parse_args(Munch(params), no_cuda=True)
        args.update(wandb=False, device="cpu", no_cuda=True, checkpoint=str(weights))
        self.args = args
        self._torch = torch
        self.model = get_model(args)
        self.model.load_state_dict(torch.load(str(weights), map_location="cpu", weights_only=True))
        self.model.eval()
        self.resizer: Any = None
        if resizer is not None and resizer.exists():
            from timm.models.layers import StdConv2dSame
            from timm.models.resnetv2 import ResNetV2

            self.resizer = ResNetV2(
                layers=[2, 3, 3],
                num_classes=max(args.max_dimensions) // 32,
                global_pool="avg",
                in_chans=1,
                drop_rate=0.05,
                preact=True,
                stem_type="same",
                conv_layer=StdConv2dSame,
            )
            self.resizer.load_state_dict(torch.load(str(resizer), map_location="cpu", weights_only=True))
            self.resizer.eval()
        tok_file = str(pkg / "dataset" / "tokenizer.json")
        self.tokenizer = PreTrainedTokenizerFast(tokenizer_file=tok_file)  # type: ignore[no-untyped-call]
        self._lock = threading.Lock()

    def __call__(self, img: Image.Image) -> str:
        from pix2tex.dataset.transforms import test_transform
        from pix2tex.utils import pad, post_process, token2str

        torch = self._torch
        args = self.args
        with self._lock, torch.no_grad():
            torch.manual_seed(0)
            img = _minmax_size(pad(img), args.max_dimensions, args.min_dimensions)
            if self.resizer is not None:
                src = img.convert("RGB").copy()
                r, w, h = 1.0, src.size[0], src.size[1]
                for _ in range(10):
                    h = int(h * r)
                    resample = Image.Resampling.BILINEAR if r > 1 else Image.Resampling.LANCZOS
                    img = pad(
                        _minmax_size(src.resize((w, h), resample), args.max_dimensions, args.min_dimensions)
                    )
                    t = test_transform(image=np.array(img.convert("RGB")))["image"][:1].unsqueeze(0)
                    w = (self.resizer(t).argmax(-1).item() + 1) * 32
                    if w == img.size[0]:
                        break
                    r = w / img.size[0]
            else:
                arr = np.array(pad(img).convert("RGB"))
                t = test_transform(image=arr)["image"][:1].unsqueeze(0)
            dec = self.model.generate(t, temperature=args.get("temperature", 0.25))
            return str(post_process(token2str(dec, self.tokenizer)[0]))
