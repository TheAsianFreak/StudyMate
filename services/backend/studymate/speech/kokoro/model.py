# Vendored from hexgrad/kokoro 0.9.4 (kokoro/model.py), Apache-2.0 -- see README.md.
# Modified by StudyMate: loads config/weights from local paths only (no huggingface_hub,
# no loguru), strips the "module." prefix explicitly and checks the load, drops the
# phoneme-string `forward` and the ONNX wrapper. `forward_with_tokens` is unchanged.
from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from transformers import AlbertConfig

from .istftnet import Decoder
from .modules import CustomAlbert, ProsodyPredictor, TextEncoder

# Buffers some transformers versions register but the checkpoint doesn't carry.
_BENIGN_MISSING = ("embeddings.position_ids", "embeddings.token_type_ids")


def _benign_missing(module: torch.nn.Module, key: str) -> bool:
    """AdaIN1d uses InstanceNorm1d(affine=True) only as an ONNX-export workaround; its
    weight/bias are not in the checkpoint and keep their identity init (= affine=False)."""
    if key.endswith(_BENIGN_MISSING):
        return True
    owner, _, name = key.rpartition(".")
    return name in ("weight", "bias") and isinstance(module.get_submodule(owner), torch.nn.InstanceNorm1d)


class KModel(torch.nn.Module):
    def __init__(self, config: dict[str, Any], weights: Path) -> None:
        super().__init__()
        self.vocab: dict[str, int] = config["vocab"]
        self.bert = CustomAlbert(AlbertConfig(vocab_size=config["n_token"], **config["plbert"]))
        self.bert_encoder = torch.nn.Linear(self.bert.config.hidden_size, config["hidden_dim"])
        self.context_length: int = self.bert.config.max_position_embeddings
        self.predictor = ProsodyPredictor(
            style_dim=config["style_dim"], d_hid=config["hidden_dim"],
            nlayers=config["n_layer"], max_dur=config["max_dur"], dropout=config["dropout"]
        )
        self.text_encoder = TextEncoder(
            channels=config["hidden_dim"], kernel_size=config["text_encoder_kernel_size"],
            depth=config["n_layer"], n_symbols=config["n_token"]
        )
        self.decoder = Decoder(
            dim_in=config["hidden_dim"], style_dim=config["style_dim"],
            dim_out=config["n_mels"], **config["istftnet"]
        )
        checkpoint = torch.load(weights, map_location="cpu", weights_only=True)
        for key, state_dict in checkpoint.items():
            module = getattr(self, key)
            state_dict = {k.removeprefix("module."): v for k, v in state_dict.items()}
            result = module.load_state_dict(state_dict, strict=False)
            missing = [k for k in result.missing_keys if not _benign_missing(module, k)]
            if missing or result.unexpected_keys:
                raise RuntimeError(f"Kokoro {key}: missing {missing}, unexpected {result.unexpected_keys}")

    @property
    def device(self) -> torch.device:
        return self.bert.device

    @torch.no_grad()
    def forward_with_tokens(
        self,
        input_ids: torch.LongTensor,
        ref_s: torch.FloatTensor,
        speed: float = 1
    ) -> tuple[torch.FloatTensor, torch.LongTensor]:
        input_lengths = torch.full(
            (input_ids.shape[0],),
            input_ids.shape[-1],
            device=input_ids.device,
            dtype=torch.long
        )

        text_mask = torch.arange(input_lengths.max()).unsqueeze(0).expand(input_lengths.shape[0], -1).type_as(input_lengths)
        text_mask = torch.gt(text_mask+1, input_lengths.unsqueeze(1)).to(self.device)
        bert_dur = self.bert(input_ids, attention_mask=(~text_mask).int())
        d_en = self.bert_encoder(bert_dur).transpose(-1, -2)
        s = ref_s[:, 128:]
        d = self.predictor.text_encoder(d_en, s, input_lengths, text_mask)
        x, _ = self.predictor.lstm(d)
        duration = self.predictor.duration_proj(x)
        duration = torch.sigmoid(duration).sum(axis=-1) / speed
        pred_dur = torch.round(duration).clamp(min=1).long().squeeze()
        indices = torch.repeat_interleave(torch.arange(input_ids.shape[1], device=self.device), pred_dur)
        pred_aln_trg = torch.zeros((input_ids.shape[1], indices.shape[0]), device=self.device)
        pred_aln_trg[indices, torch.arange(indices.shape[0])] = 1
        pred_aln_trg = pred_aln_trg.unsqueeze(0).to(self.device)
        en = d.transpose(-1, -2) @ pred_aln_trg
        F0_pred, N_pred = self.predictor.F0Ntrain(en, s)
        t_en = self.text_encoder(input_ids, input_lengths, text_mask)
        asr = t_en @ pred_aln_trg
        audio = self.decoder(asr, F0_pred, N_pred, ref_s[:, :128]).squeeze()
        return audio, pred_dur
