"""Signed lightness shift Δ(o,c,ℓ,m).

A negative Δ means the algorithmic distribution sits at *lighter* tones than
the empirical distribution — the directional sense of pigmentocratic
sedimentation (H1).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def expected_perla(
    distribution: Sequence[float] | np.ndarray,
    tones: Sequence[int] | np.ndarray | None = None,
) -> float:
    """Expected value E[t | distribution] over the PERLA ordinal."""
    p = np.asarray(distribution, dtype=float)
    tones_arr = np.arange(1, 12, dtype=float) if tones is None else np.asarray(tones, dtype=float)
    if p.shape != tones_arr.shape:
        raise ValueError(f"shape mismatch: distribution={p.shape}, tones={tones_arr.shape}")
    if not np.isclose(p.sum(), 1.0, atol=1e-6):
        raise ValueError(f"distribution must sum to 1 (got {p.sum():.6f})")
    return float(np.dot(p, tones_arr))


def signed_delta(
    f_alg: Sequence[float] | np.ndarray,
    f_emp: Sequence[float] | np.ndarray,
    tones: Sequence[int] | np.ndarray | None = None,
) -> float:
    """Δ = E[t | f_alg] − E[t | f_emp]. Negative ⇒ model lightens."""
    return expected_perla(f_alg, tones) - expected_perla(f_emp, tones)
