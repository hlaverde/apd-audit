"""CASCo PERLA classifier (Rejón Piña 2023).

Stub. The reference repository for CASCo must be vendored under
``third_party/casco/`` once we resolve its licence and packaging. The POC
runs without CASCo (see DECISIONS.md D-005); the two-of-three concordance
rule across {CASCo, ITA, MST} becomes effective when CASCo lands.
"""

from __future__ import annotations

import numpy as np


def compute_casco_perla(_bgr_patch: np.ndarray) -> int:  # pragma: no cover
    raise NotImplementedError(
        "CASCo classifier not yet vendored — see DECISIONS.md D-005.",
    )
