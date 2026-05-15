"""CLIP zero-shot context classifier for the H5 orientalism test.

Stub. Production loads ``openai/clip-vit-base-patch32`` from Hugging Face
and scores each image against the labels {rural, urban, modern office,
artisan workshop, folkloric landscape, neutral background}. Not used in
the POC.
"""

from __future__ import annotations

import numpy as np


def score_context(_bgr_image: np.ndarray):  # pragma: no cover
    raise NotImplementedError("CLIP context scoring deferred — POC does not need it.")
