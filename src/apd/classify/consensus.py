"""Phenotype consensus rule for the 2-of-3 concordance.

The proposal §6.2 prescribes a 2-of-3 concordance rule across CASCo, ITA
→ PERLA, and MST → PERLA. We implement it as:

    consensus = median of the available classifier outputs
    concordant_2of3 = True iff at least 2 classifiers are within
                      ±``tolerance`` PERLA tones of the consensus

The tolerance is configurable; we default to 1 because the three
classifiers measure on the same ordinal lattice but via different
heuristics (k-means in HSV vs CIE-Lab angle vs nearest reference RGB),
so a small tolerance avoids over-rejecting genuinely close calls while
still flagging large disagreements.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class ConsensusResult:
    perla: int | None
    n_available: int
    n_concordant: int
    concordant_2of3: bool


def consensus_perla(
    values: list[int | None],
    *,
    tolerance: int = 1,
) -> ConsensusResult:
    """Aggregate per-classifier PERLA outputs into a single tone + a flag."""
    valid = [int(v) for v in values if v is not None]
    if not valid:
        return ConsensusResult(perla=None, n_available=0, n_concordant=0, concordant_2of3=False)
    median = int(round(statistics.median(valid)))
    n_concordant = sum(1 for v in valid if abs(v - median) <= tolerance)
    return ConsensusResult(
        perla=median,
        n_available=len(valid),
        n_concordant=n_concordant,
        concordant_2of3=n_concordant >= 2,
    )
