"""Distances on PERLA-ordinal distributions.

The PERLA scale is treated as integer positions {1, 2, ..., 11} on the real
line with unit spacing. Wasserstein-1 over this support is the proposal's
prescribed distance (§5.2 step 2): it respects ordinal closeness, which KL
and Jensen-Shannon do not.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy.stats import wasserstein_distance


def wasserstein1_perla(
    p: Sequence[float] | np.ndarray,
    q: Sequence[float] | np.ndarray,
    tones: Sequence[int] | np.ndarray | None = None,
) -> float:
    """Return W_1(p, q) on the PERLA ordinal lattice.

    Parameters
    ----------
    p, q : 1-D probability vectors of equal length aligned with ``tones``.
    tones : optional integer positions; defaults to ``np.arange(1, 12)``.

    The implementation uses ``scipy.stats.wasserstein_distance`` which, with
    shared support and per-position weights, reduces to the exact 1-D W_1
    on the ordinal positions.
    """
    p_arr = np.asarray(p, dtype=float)
    q_arr = np.asarray(q, dtype=float)
    tones_arr = np.arange(1, 12, dtype=float) if tones is None else np.asarray(tones, dtype=float)

    if p_arr.shape != q_arr.shape or p_arr.shape != tones_arr.shape:
        raise ValueError(
            f"shape mismatch: p={p_arr.shape}, q={q_arr.shape}, tones={tones_arr.shape}",
        )
    if p_arr.size == 0:
        raise ValueError("distributions must be non-empty")
    if not np.isclose(p_arr.sum(), 1.0, atol=1e-6):
        raise ValueError(f"p must sum to 1 (got {p_arr.sum():.6f})")
    if not np.isclose(q_arr.sum(), 1.0, atol=1e-6):
        raise ValueError(f"q must sum to 1 (got {q_arr.sum():.6f})")
    if (p_arr < 0).any() or (q_arr < 0).any():
        raise ValueError("probabilities must be non-negative")

    return float(wasserstein_distance(tones_arr, tones_arr, u_weights=p_arr, v_weights=q_arr))
