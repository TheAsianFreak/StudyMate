# Vendored MeloTTS (inference only)

- Upstream: https://github.com/myshell-ai/MeloTTS
- Commit: `209145371cff8fc3bd60d7be902ea69cbdb7965a` (2024-12-24)
- Licence: MIT, Copyright (c) 2024 MyShell.ai — full text in `LICENSE`
- Weights: `myshell-ai/MeloTTS-Korean` (MIT), downloaded to `models/tts/melo-korean/`

## Files taken from upstream

| File | Upstream path | Local changes |
|---|---|---|
| `commons.py` | `melo/commons.py` | attribution header; `@torch.jit.script` removed |
| `attentions.py` | `melo/attentions.py` | attribution header; `@torch.jit.script` removed |
| `modules.py` | `melo/modules.py` | attribution header |
| `transforms.py` | `melo/transforms.py` | attribution header |
| `models.py` | `melo/models.py` | attribution header; package-relative imports; `monotonic_align` import removed and `SynthesizerTrn.forward` (training) raises `NotImplementedError` |

`@torch.jit.script` was removed because TorchScript compiles from source at import time,
which fails in a compiled (Nuitka) bundle; the plain Python functions are numerically identical.

## Not vendored (on purpose)

- `melo/text/*` frontends: they pull in `pykakasi` (GPL-3.0), MeCab, `cn2an`, `jieba`,
  `transformers` and the `kykim/bert-kor-base` tokenizer/model (its terms require a
  commercial MOU). StudyMate runs the Korean model BERT-free (zero BERT features, the
  same thing upstream does with `disable_bert`) and uses its own frontend in
  `studymate/speech/korean.py` (g2pkk rules without MeCab).
- `melo/api.py`, `melo/utils.py`, `melo/download_utils.py`, training code, `monotonic_align`.

Upstream constants reproduced in `studymate/speech/tts.py` (from `melo/text/symbols.py`):
Korean language id `4`, Korean tone start `11` (6 zh + 1 ja + 4 en tones), blank id `0`.
