"""H3 — language fixed-effects test.

Proposal §6.3 specification:

    APD(c, ℓ, m) = α_m + δ_c + λ_ℓ + ε

The confirmatory test is the **joint F-test on the language fixed
effects** ``λ_ℓ`` after controlling for model and country fixed effects.
H3 is supported when the F-statistic is significant at the FDR-adjusted
α level (the *direction* of any individual language coefficient is
exploratory, per proposal §3 H3).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class H3Result:
    formula: str
    coefficients: pd.Series
    standard_errors: pd.Series
    language_f_statistic: float
    language_p_value: float
    language_df_num: int
    language_df_den: float
    n_obs: int
    r_squared: float


REQUIRED_COLUMNS: frozenset[str] = frozenset({"APD", "country", "language", "model"})


def estimate_h3(apd_panel: pd.DataFrame) -> H3Result:
    """Fit the H3 model and return the joint F-test on language FE.

    Parameters
    ----------
    apd_panel : DataFrame keyed at the (country, language, model) level with
        an ``APD`` column. Typically built from one APD scalar per cell.

    Raises
    ------
    KeyError if required columns are missing.
    ValueError if there are fewer than 2 languages (the test is degenerate).
    """
    missing = REQUIRED_COLUMNS - set(apd_panel.columns)
    if missing:
        raise KeyError(f"apd_panel missing columns: {sorted(missing)}")

    n_lang = apd_panel["language"].nunique()
    if n_lang < 2:
        raise ValueError(
            f"H3 requires at least 2 languages; got {n_lang}.",
        )

    # statsmodels lives behind a lazy import so test discovery is cheap
    # and the module can be inspected without pulling SciPy stacks.
    import statsmodels.formula.api as smf  # noqa: WPS433

    rhs_terms = ["C(language)"]
    if apd_panel["model"].nunique() > 1:
        rhs_terms.append("C(model)")
    if apd_panel["country"].nunique() > 1:
        rhs_terms.append("C(country)")
    formula = "APD ~ " + " + ".join(rhs_terms)

    fit = smf.ols(formula, data=apd_panel).fit()

    language_params = [p for p in fit.params.index if p.startswith("C(language)")]
    if not language_params:
        raise ValueError("the fitted model has no language fixed effects")
    hypothesis = ", ".join(f"{p} = 0" for p in language_params)
    f_test = fit.f_test(hypothesis)

    return H3Result(
        formula=formula,
        coefficients=fit.params,
        standard_errors=fit.bse,
        language_f_statistic=float(np.asarray(f_test.fvalue).item()),
        language_p_value=float(np.asarray(f_test.pvalue).item()),
        language_df_num=int(np.asarray(f_test.df_num).item()),
        language_df_den=float(np.asarray(f_test.df_denom).item()),
        n_obs=int(fit.nobs),
        r_squared=float(fit.rsquared),
    )
