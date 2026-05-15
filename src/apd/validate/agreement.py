"""Inter-rater agreement statistics for the visual-validation labels.

Cohen's κ on the 11-tone PERLA scale, treated as nominal categories
(reviewer-defensible; PERLA's ordinal structure is preserved separately
by the W₁ distance in APD). We also expose a function comparing the
human labels against the algorithmic 2-of-3 consensus.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score


@dataclass(frozen=True)
class AgreementResult:
    statistic: str
    value: float
    n: int
    note: str = ""


def _drop_unlabelled(a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series]:
    df = pd.DataFrame({"a": a, "b": b}).dropna()
    return df["a"].astype(int), df["b"].astype(int)


def cohens_kappa(
    rater_a: pd.Series,
    rater_b: pd.Series,
    *,
    weights: str | None = "linear",
) -> AgreementResult:
    """Cohen's κ between two raters.

    Defaults to **linearly-weighted** κ because PERLA is ordinal: a 1-tone
    disagreement is less wrong than a 6-tone disagreement. Pass
    ``weights=None`` for the unweighted (nominal) variant.
    """
    a, b = _drop_unlabelled(rater_a, rater_b)
    n = len(a)
    if n < 2:
        return AgreementResult(
            statistic="cohens_kappa_linear" if weights == "linear" else "cohens_kappa",
            value=float("nan"),
            n=n,
            note="too few jointly labelled rows",
        )
    k = float(cohen_kappa_score(a, b, weights=weights))
    return AgreementResult(
        statistic="cohens_kappa_linear" if weights == "linear" else "cohens_kappa",
        value=k,
        n=n,
    )


def compare_to_consensus(
    human_labels: pd.Series,
    algorithmic_consensus: pd.Series,
) -> AgreementResult:
    """Linearly-weighted κ of one human rater vs the algorithmic 2-of-3.

    This is the headline number that supports (or fails to support) the
    construct-validity claim of the algorithmic phenotype stack.
    """
    return cohens_kappa(human_labels, algorithmic_consensus, weights="linear")
