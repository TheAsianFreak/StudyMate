"""StudyMate local AI backend."""

import os as _os

__version__ = "0.1.0"

# No network at runtime (CLAUDE.md rule 7). Set before any third-party import: albumentations
# (via pix2tex) checks PyPI on import, Hugging Face libraries would try the hub.
# NLTK's data dir is set in config.get_settings() because it depends on models_dir.
for _key in ("NO_ALBUMENTATIONS_UPDATE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
    _os.environ.setdefault(_key, "1")
