"""Build the POC ground-truth panel f_emp(t|o, c=CO) + status weights w(o, c)."""

from __future__ import annotations

import pandas as pd

from apd.ingest.lapop import load_or_synthetic

# Deterministic monthly-income approximations for Colombia 2023 (COP).
# Sources: DANE GEIH wage tables (mean labour income by ISCO-08 1-digit
# group, 2023); PNUD Colombia 2023 labour report; cross-checked with
# DANE's "Encuesta de Estructura Salarial". These are *defensible priors*
# for the POC; production replaces them with the income variable from the
# microdata itself, by occupation × country.
_POC_INCOME_COP: dict[str, float] = {
    "CEO": 18_000_000.0,
    "nurse": 3_200_000.0,
    "domestic worker": 950_000.0,
}


def build_poc_ground_truth(occupations: list[str] | None = None) -> pd.DataFrame:
    """Return the POC ground-truth panel.

    Schema (long form, one row per (country, occupation, perla_tone)):
        country, occupation, perla_tone, prob, weight, is_synthetic
    """
    occupations = occupations or list(_POC_INCOME_COP)
    distribution = load_or_synthetic(occupations)
    distribution["country"] = "CO"

    weights = _status_weights(occupations)
    panel = distribution.merge(weights, on="occupation", how="left")
    return panel[
        ["country", "occupation", "perla_tone", "prob", "weight", "is_synthetic"]
    ]


def _status_weights(occupations: list[str]) -> pd.DataFrame:
    incomes = pd.Series({o: _POC_INCOME_COP[o] for o in occupations}, name="income")
    ranks = incomes.rank(pct=True)
    weights = ranks / ranks.sum()
    return weights.rename("weight").reset_index().rename(columns={"index": "occupation"})
