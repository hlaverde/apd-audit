"""Google Colab T4 backend (stub).

Production runs distribute the 12 000-image grid across Colab T4 free tier,
Kaggle GPU free tier, and HF Inference API. This module will hold the
Colab-specific glue (notebook drop scripts, drive sync, etc.). The POC
does not use Colab.
"""

from __future__ import annotations


class ColabBackend:  # pragma: no cover
    name = "colab"

    def __init__(self, *_args, **_kwargs) -> None:
        raise NotImplementedError("Colab backend deferred — see proposal §4.1.")
