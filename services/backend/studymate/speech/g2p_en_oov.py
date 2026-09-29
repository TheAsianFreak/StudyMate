"""Neural spelling -> ARPAbet for English words no dictionary knows (names, rare words).

Inference for the GRU encoder-decoder of g2p_en (Kyubyong Park & Jongseok Kim,
https://github.com/Kyubyong/g2p, Apache-2.0), re-implemented in NumPy after
`g2p_en/g2p.py` v2.1.0. Only the trained weights (`checkpoint20.npz`, model id
`g2p-en-oov`) are used; the g2p_en package itself is not a dependency (it pulls in the
GPL `distance` package and downloads NLTK data at import).
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

GRAPHEMES = ["<pad>", "<unk>", "</s>", *"abcdefghijklmnopqrstuvwxyz"]
PHONEMES = [
    "<pad>", "<unk>", "<s>", "</s>",
    "AA0", "AA1", "AA2", "AE0", "AE1", "AE2", "AH0", "AH1", "AH2", "AO0", "AO1", "AO2", "AW0", "AW1",
    "AW2", "AY0", "AY1", "AY2", "B", "CH", "D", "DH", "EH0", "EH1", "EH2", "ER0", "ER1", "ER2", "EY0",
    "EY1", "EY2", "F", "G", "HH", "IH0", "IH1", "IH2", "IY0", "IY1", "IY2", "JH", "K", "L", "M", "N",
    "NG", "OW0", "OW1", "OW2", "OY0", "OY1", "OY2", "P", "R", "S", "SH", "T", "TH", "UH0", "UH1",
    "UH2", "UW", "UW0", "UW1", "UW2", "V", "W", "Y", "Z", "ZH",
]  # fmt: skip
_G2I = {g: i for i, g in enumerate(GRAPHEMES)}
_MAX_PHONES = 20


def _sigmoid(x: np.ndarray) -> np.ndarray:
    out: np.ndarray = 1.0 / (1.0 + np.exp(-x))
    return out


class OovG2p:
    """Thread-safe; weights are loaded on first use."""

    def __init__(self, checkpoint: Path) -> None:
        self.checkpoint = checkpoint
        self._w: dict[str, np.ndarray] | None = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.checkpoint.is_file()

    def _weights(self) -> dict[str, np.ndarray]:
        with self._lock:
            if self._w is None:
                with np.load(self.checkpoint) as z:
                    self._w = {k: z[k].astype(np.float32) for k in z.files}
            return self._w

    @staticmethod
    def _cell(x: np.ndarray, h: np.ndarray, w: dict[str, np.ndarray], p: str) -> np.ndarray:
        gi = x @ w[f"{p}_w_ih"].T + w[f"{p}_b_ih"]
        gh = h @ w[f"{p}_w_hh"].T + w[f"{p}_b_hh"]
        k = gi.shape[-1] // 3
        r = _sigmoid(gi[:, :k] + gh[:, :k])
        z = _sigmoid(gi[:, k : 2 * k] + gh[:, k : 2 * k])
        n = np.tanh(gi[:, 2 * k :] + r * gh[:, 2 * k :])
        out: np.ndarray = (1 - z) * n + z * h
        return out

    def predict(self, word: str) -> list[str]:
        """ARPAbet phones (with stress digits) for a lowercase a-z word."""
        letters = [c for c in word.lower() if "a" <= c <= "z"]
        if not letters:
            return []
        w = self._weights()
        ids = [_G2I[c] for c in letters] + [_G2I["</s>"]]
        h = np.zeros((1, w["enc_w_hh"].shape[1]), np.float32)
        for i in ids:
            h = self._cell(w["enc_emb"][[i]], h, w, "enc")
        dec = w["dec_emb"][[2]]  # <s>
        out: list[str] = []
        for _ in range(_MAX_PHONES):
            h = self._cell(dec, h, w, "dec")
            pred = int(np.argmax(h @ w["fc_w"].T + w["fc_b"]))
            if pred == 3:  # </s>
                break
            out.append(PHONEMES[pred])
            dec = w["dec_emb"][[pred]]
        return [p for p in out if not p.startswith("<")]
