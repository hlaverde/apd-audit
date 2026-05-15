"""Image-generation backends and orchestrator.

Backends:
    HFBackend         Hugging Face Inference API (free tier), requires HF_TOKEN.
    LocalBackend      ``diffusers`` running on local CPU/GPU (network-free fallback).
    ColabBackend      Generation on a Google Colab notebook (stub).
    KaggleBackend     Generation on a Kaggle notebook (stub).

The orchestrator picks a backend and caches every image to disk so reruns
are idempotent.
"""

from .hf_backend import HFBackend, HFGenerationError
from .orchestrator import generate_poc, image_path

__all__ = ["HFBackend", "HFGenerationError", "generate_poc", "image_path"]
