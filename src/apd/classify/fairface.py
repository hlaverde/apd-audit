"""FairFace gender / age / race classifier (Karkkainen & Joo 2021).

Stub. Production downloads the FairFace weights from its public GitHub
release and runs it on every face crop to produce gender, age-band, and a
7-class race label (used as a categorical control in the H1-H2 regressions).
Not needed for the POC.
"""

from __future__ import annotations

import numpy as np


def predict_fairface(_bgr_patch: np.ndarray):  # pragma: no cover
    raise NotImplementedError("FairFace deferred — POC does not need it.")
