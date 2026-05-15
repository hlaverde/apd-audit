"""H5 — quantifiable digital orientalism.

Proposal §3 specification:

    Prompts that append a Latin-American geographic marker
    ("Colombian doctor", "Mexican engineer") produce contexts with
    higher CLIP zero-shot probability of {rural, folkloric, premodern}
    backgrounds than equivalent prompts with US or European markers,
    holding occupation and language constant.

We operationalise this as a regression of an aggregated *orientalist
probability* on the marker indicator, holding occupation and model
fixed:

    P_orientalist  =  α  +  β·marker_LatAm  +  γ·marker_US
                       +  occ_FE  +  model_FE  +  ε

where ``P_orientalist = P(rural) + P(folkloric) + P(workshop)`` is the
sum of the three "orientalist-leaning" CLIP labels from
``apd.classify.context_clip``. The H5 test is whether
``β_LatAm > β_US`` (LatAm markers tilt the context more orientally than
US markers) — implemented as a one-sided F-test on the linear
restriction ``β_LatAm − β_US = 0``.

The estimator uses **HC1 robust standard errors** because the panel mixes
multiple images per (occupation × marker × model) cell with
heteroskedasticity in CLIP probabilities.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

# Default "orientalist" CLIP-label triple from proposal §3 H5.
DEFAULT_ORIENTALIST_LABELS: tuple[str, ...] = (
    "a rural scene",
    "a folkloric landscape",
    "an artisan workshop",
)


@dataclass(frozen=True)
class H5Result:
    formula: str
    coefficients: pd.Series
    standard_errors: pd.Series
    diff_in_diff: float
    diff_in_diff_se: float
    diff_in_diff_p_value: float
    n_obs: int
    r_squared: float


def estimate_h5(
    image_panel: pd.DataFrame,
    *,
    orientalist_labels: Sequence[str] = DEFAULT_ORIENTALIST_LABELS,
    reference_marker: str = "unmarked",
) -> H5Result:
    """Fit the H5 regression and return the LatAm-vs-US marker contrast.

    Parameters
    ----------
    image_panel : per-image DataFrame with columns
        ``image_id``, ``marker`` (str, e.g. 'LatAm', 'US', 'unmarked'),
        ``occupation``, ``model``, and one float column per CLIP label
        listed in ``orientalist_labels`` carrying the per-image CLIP
        probability for that label.
    orientalist_labels : the CLIP-label triple summed into the outcome.
    reference_marker : the marker level used as the regression reference;
        defaults to ``'unmarked'``.

    Returns the regression result plus the linear-contrast estimate
    ``β_LatAm − β_US`` (the diff-in-diff that operationalises H5) with
    its SE and one-sided p-value.
    """
    required = {"marker", "occupation", "model"} | set(orientalist_labels)
    missing = required - set(image_panel.columns)
    if missing:
        raise KeyError(f"image_panel missing columns: {sorted(missing)}")

    panel = image_panel.copy()
    panel["P_orientalist"] = panel[list(orientalist_labels)].sum(axis=1)
    if not panel["P_orientalist"].between(0.0, 1.0, inclusive="both").all():
        raise ValueError(
            "P_orientalist values outside [0, 1] — check that the input "
            "columns hold softmax probabilities, not raw logits.",
        )

    if panel["marker"].nunique() < 2:
        raise ValueError(
            f"H5 requires at least 2 marker levels; got "
            f"{panel['marker'].nunique()}.",
        )

    import statsmodels.formula.api as smf  # noqa: WPS433

    rhs = [f"C(marker, Treatment(reference={reference_marker!r}))"]
    if panel["occupation"].nunique() > 1:
        rhs.append("C(occupation)")
    if panel["model"].nunique() > 1:
        rhs.append("C(model)")
    formula = "P_orientalist ~ " + " + ".join(rhs)

    fit = smf.ols(formula, data=panel).fit(cov_type="HC1")

    # Linear contrast: β_LatAm - β_US.
    lat_param = _find_marker_param(fit.params.index, "LatAm")
    us_param = _find_marker_param(fit.params.index, "US")
    diff = float(fit.params[lat_param] - fit.params[us_param])

    # SE via t_test on the linear restriction.
    t_test = fit.t_test(f"{lat_param} - {us_param} = 0")
    diff_se = float(np.asarray(t_test.sd).item())
    # The proposal's H5 is *directional* (LatAm > US), so report the
    # one-sided p-value.
    two_sided_p = float(np.asarray(t_test.pvalue).item())
    one_sided_p = two_sided_p / 2.0 if diff > 0 else 1.0 - two_sided_p / 2.0

    return H5Result(
        formula=formula,
        coefficients=fit.params,
        standard_errors=fit.bse,
        diff_in_diff=diff,
        diff_in_diff_se=diff_se,
        diff_in_diff_p_value=one_sided_p,
        n_obs=int(fit.nobs),
        r_squared=float(fit.rsquared),
    )


def _find_marker_param(param_index, marker_label: str) -> str:
    matches = [p for p in param_index if p.startswith("C(marker") and marker_label in p]
    if not matches:
        raise KeyError(
            f"no fitted coefficient for marker {marker_label!r}; "
            f"available: {list(param_index)}",
        )
    if len(matches) > 1:
        raise ValueError(f"ambiguous match for marker {marker_label!r}: {matches}")
    return matches[0]
