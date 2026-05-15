"""H4 — does scaling resolve the bias?

Proposal §3 H4: controlling for architecture family, model versions with
more parameters do **not** produce a monotone reduction in ``|APD|``.

Specification:

    APD  =  θ  +  φ·log(parameters)  +  ψ·debias_explicit  +  family_FE  +  ε

The confirmatory test is whether ``φ`` is *not* significantly negative.
A failure-to-reject of ``φ ≥ 0`` is the evidence supporting H4.

Implementation note: with at most 4 main + 4 robustness models, the
sample size for this regression is tiny (n = 8 per (c, ℓ) stratum). The
proposal explicitly tags H4 as exploratory in §3; the function below
provides the machinery so that H4 *can* be tested when the panel is
ready, but the manuscript reports it as exploratory.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class H4Result:
    formula: str
    phi_estimate: float
    phi_standard_error: float
    phi_p_value_one_sided: float
    coefficients: pd.Series
    standard_errors: pd.Series
    n_obs: int
    r_squared: float


REQUIRED_COLUMNS: frozenset[str] = frozenset({"APD", "log_parameters", "architecture_family"})


def estimate_h4(
    model_panel: pd.DataFrame,
    *,
    debias_column: str | None = "debias_explicit",
) -> H4Result:
    """Fit the H4 specification and report a one-sided test on ``φ``.

    Parameters
    ----------
    model_panel : DataFrame at the model level (or model × c × ℓ level)
        with columns:
            APD : float — the (signed) APD value for the cell.
            log_parameters : float — natural log of trainable parameters.
            architecture_family : str — e.g. 'SD', 'FLUX', 'Kandinsky'.
            debias_explicit : 0/1 — optional binary indicator that the
                model ships an explicit debias variant.
    debias_column : pass ``None`` to skip the debias term.
    """
    missing = REQUIRED_COLUMNS - set(model_panel.columns)
    if missing:
        raise KeyError(f"model_panel missing columns: {sorted(missing)}")
    if len(model_panel) < 4:
        raise ValueError(
            f"H4 requires at least 4 observations; got {len(model_panel)}",
        )

    import statsmodels.formula.api as smf  # noqa: WPS433

    rhs = ["log_parameters"]
    if debias_column and debias_column in model_panel.columns:
        rhs.append(debias_column)
    if model_panel["architecture_family"].nunique() > 1:
        rhs.append("C(architecture_family)")
    formula = "APD ~ " + " + ".join(rhs)

    fit = smf.ols(formula, data=model_panel).fit()
    phi = float(fit.params["log_parameters"])
    phi_se = float(fit.bse["log_parameters"])
    # H4 supports "scaling does NOT resolve the bias", i.e. we want to
    # test the *one-sided* hypothesis φ ≥ 0 (vs the alternative φ < 0).
    # Report the one-sided p-value for φ < 0.
    t = float(np.asarray(fit.t_test("log_parameters = 0").tvalue).item())
    # one-sided p for "less than 0"
    from scipy import stats as scs  # noqa: WPS433

    p_one_sided = float(scs.t.cdf(t, df=fit.df_resid))

    return H4Result(
        formula=formula,
        phi_estimate=phi,
        phi_standard_error=phi_se,
        phi_p_value_one_sided=p_one_sided,
        coefficients=fit.params,
        standard_errors=fit.bse,
        n_obs=int(fit.nobs),
        r_squared=float(fit.rsquared),
    )
