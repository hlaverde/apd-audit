"""APD indicator — status-weighted aggregation of D · sign(Δ).

For each occupation o, country c, prompt language ℓ and model m:

    D(o,c,ℓ,m)   = W_1(f_alg, f_emp)
    Δ(o,c,ℓ,m)   = E[t | f_alg] − E[t | f_emp]
    APD(c,ℓ,m)   = Σ_o w(o,c) · D(o,c,ℓ,m) · sign(Δ(o,c,ℓ,m))

A negative APD means the model systematically *lightens* high-status
occupations relative to the empirical labour market.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np

from .delta import signed_delta
from .distances import wasserstein1_perla


@dataclass(frozen=True)
class OccupationResult:
    """Per-(o, c, ℓ, m) APD components."""

    occupation: str
    D: float
    delta: float
    weight: float

    @property
    def signed_D(self) -> float:
        if self.delta == 0:
            return 0.0
        return self.D * float(np.sign(self.delta))


def compute_occupation_metrics(
    occupation: str,
    f_alg: Sequence[float] | np.ndarray,
    f_emp: Sequence[float] | np.ndarray,
    weight: float,
) -> OccupationResult:
    return OccupationResult(
        occupation=occupation,
        D=wasserstein1_perla(f_alg, f_emp),
        delta=signed_delta(f_alg, f_emp),
        weight=float(weight),
    )


def apd(results: Iterable[OccupationResult]) -> float:
    """APD = Σ_o w(o) · D(o) · sign(Δ(o))."""
    return float(sum(r.weight * r.signed_D for r in results))
