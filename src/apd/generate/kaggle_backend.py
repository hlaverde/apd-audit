"""Kaggle Notebooks GPU backend (stub).

Production distributes the main study image generation across Colab T4,
Kaggle GPU and HF Inference. The POC does not use Kaggle.
"""

from __future__ import annotations


class KaggleBackend:  # pragma: no cover
    name = "kaggle"

    def __init__(self, *_args, **_kwargs) -> None:
        raise NotImplementedError("Kaggle backend deferred — see proposal §4.1.")
