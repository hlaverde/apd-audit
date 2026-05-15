"""H1 (directional sedimentation) and H2 (pigmentocratic gradient).

H1: For each (c, ℓ, m), test that the mean Δ(o) across occupations is <0.
H2: For each (c, ℓ, m), fit Δ(o) = α + β·w(o) + γ·X(o) + ε and test β<0.

In the POC, N_occupations = 3 so the regression is statistically degenerate
(2 degrees of freedom). The script still runs to validate the machinery
and produce the gradient scatter that the user will eyeball before
authorising scale-up.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GradientFit:
    alpha: float
    beta: float
    n_obs: int
    sigma: float


def fit_gradient(apd_table: pd.DataFrame) -> GradientFit:
    """OLS of Δ on w. Refuses to fit if fewer than 2 distinct w values."""
    needed = {"weight", "delta"}
    missing = needed - set(apd_table.columns)
    if missing:
        raise KeyError(f"apd_table missing columns: {missing}")
    w = apd_table["weight"].astype(float).to_numpy()
    d = apd_table["delta"].astype(float).to_numpy()
    if len(np.unique(w)) < 2:
        raise ValueError("need at least 2 distinct weights to fit a gradient")
    beta, alpha = np.polyfit(w, d, 1)
    resid = d - (alpha + beta * w)
    sigma = float(resid.std(ddof=0))
    return GradientFit(alpha=float(alpha), beta=float(beta), n_obs=len(w), sigma=sigma)
