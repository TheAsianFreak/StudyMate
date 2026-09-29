# Vendored Kokoro-82M inference + misaki English G2P

- Kokoro code: https://github.com/hexgrad/kokoro, PyPI `kokoro` 0.9.4 — Apache-2.0,
  Copyright hexgrad. Full licence text in `LICENSE` (the same Apache-2.0 text covers misaki).
- misaki code/data: https://github.com/hexgrad/misaki, PyPI `misaki` 0.9.4 — Apache-2.0.
  The `misaki` package itself is a dependency (lexicons `us_gold/us_silver/gb_gold/gb_silver`
  and `MToken`); only `en.py` is vendored because the upstream module imports `num2words`
  (LGPL) at import time.
- Weights: `hexgrad/Kokoro-82M` v1.0 (Apache-2.0), downloaded to `models/tts/kokoro-82m/`
  by the model downloader (ids `kokoro-82m`, `kokoro-voices-ja`, `kokoro-voices-en`).

## Files

| File | Upstream | Local changes |
|---|---|---|
| `istftnet.py` | `kokoro/istftnet.py` | header; `CustomSTFT` (ONNX-export path) removed |
| `modules.py` | `kokoro/modules.py` | header only |
| `model.py` | `kokoro/model.py` | rewritten loader: local config/weights only (no `huggingface_hub`, no `loguru`), explicit `module.` prefix strip with a checked load; `forward_with_tokens` unchanged; phoneme-string `forward` and `KModelForONNX` dropped |
| `misaki_en.py` | `misaki/en.py` | header; `num2words` replaced by `studymate.speech.english` number words; `G2P` takes a loaded spaCy pipeline (no `spacy.cli.download`); imports point at the installed `misaki` package; a debug `print` removed |
| `ja_kana.py` | `misaki/cutlet.py` (`HEPBURN` table) | data only, regenerated as a Python dict. misaki adapted it from polm/cutlet (MIT, © 2020 Paul O'Leary McCann) |

## Not vendored (on purpose)

- `kokoro/pipeline.py`: pulls `misaki[en]` → `phonemizer-fork` + `espeakng-loader` (GPL-3.0
  espeak-ng) and `num2words` (LGPL), and downloads voices from the Hub at runtime.
  StudyMate's own frontends are `studymate/speech/japanese.py` and `english.py`; the
  chunking/timestamp logic is re-implemented in `studymate/speech/kokoro_tts.py`.
- `misaki/espeak.py` (espeak-ng fallback) — English OOV words go to CMUdict, a romaji rule
  or the g2p_en neural model instead (`studymate/speech/english.py`, `g2p_en_oov.py`).
- `misaki/ja.py` second-gen (pitch-accent) mapping and the cutlet tokenizer (fugashi +
  unidic): the v1.0 Japanese voices were trained on the first-gen IPA of `ja_kana.py`;
  readings come from pyopenjtalk-plus instead of UniDic.
