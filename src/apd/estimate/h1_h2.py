"""H1 (directional sedimentation) and H2 (pigmentocratic gradient).

H1: For each (c, ℓ, m), test that the mean Δ(o) across occupations is <0.
H2: For each (c, ℓ, m), fit Δ(o) = α + β·w(o) + γ·X(o) + ε and test β<0.

For production runs the per-cell H2 fit is supplemented by a **pooled
gradient** that stacks every (c, ℓ, m) cell and reports β with
cluster-robust standard errors clustered by occupation. The proposal
§6.3 prescribes this pooled specification with two-way clustering by
occupation and model; here we report one-way clustering by occupation
(the more conservative of the two given our small number of models).
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


@dataclass(frozen=True)
class PooledGradientFit:
    """Pooled H2 fit with cluster-robust standard errors."""

    beta: float
    standard_error: float
    t_statistic: float
    p_value_two_sided: float
    p_value_one_sided: float  # for H2: β < 0
    cluster_variable: str
    n_obs: int
    n_clusters: int
    r_squared: float


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


def pooled_gradient(
    apd_panel: pd.DataFrame,
    *,
    cluster_by: str = "occupation",
) -> PooledGradientFit:
    """Pool across cells and fit Δ ~ β·w with cluster-robust SEs.

    Parameters
    ----------
    apd_panel : DataFrame with one row per (occupation × c × ℓ × m) cell,
        carrying at minimum ``weight``, ``delta`` and the column named
        in ``cluster_by`` (default ``"occupation"``).
    cluster_by : column to cluster standard errors on. Use ``"occupation"``
        when occupations repeat across cells; ``"model"`` if instead
        you want to cluster by model.

    Returns the pooled β, its cluster-robust SE, the t-statistic, and
    both two- and one-sided p-values. H2 supports β < 0, so the
    one-sided p (for "less than 0") is the headline number.
    """
    needed = {"weight", "delta", cluster_by}
    missing = needed - set(apd_panel.columns)
    if missing:
        raise KeyError(f"apd_panel missing columns: {sorted(missing)}")
    n_clusters = apd_panel[cluster_by].nunique()
    if n_clusters < 2:
        raise ValueError(
            f"need at least 2 distinct values of {cluster_by!r} to cluster; "
            f"got {n_clusters}",
        )

    import statsmodels.formula.api as smf  # noqa: WPS433

    fit = smf.ols(
        "delta ~ weight",
        data=apd_panel,
    ).fit(
        cov_type="cluster",
        cov_kwds={"groups": apd_panel[cluster_by]},
    )

    beta = float(fit.params["weight"])
    se = float(fit.bse["weight"])
    t = float(fit.tvalues["weight"])
    p_two = float(fit.pvalues["weight"])
    # One-sided p for β < 0: if β is negative, t is negative, two-sided
    # p splits symmetrically, so one-sided = two-sided / 2 if t < 0,
    # else 1 - two-sided / 2.
    p_one = p_two / 2.0 if t < 0 else 1.0 - p_two / 2.0

    return PooledGradientFit(
        beta=beta,
        standard_error=se,
        t_statistic=t,
        p_value_two_sided=p_two,
        p_value_one_sided=p_one,
        cluster_variable=cluster_by,
        n_obs=int(fit.nobs),
        n_clusters=int(n_clusters),
        r_squared=float(fit.rsquared),
    )
