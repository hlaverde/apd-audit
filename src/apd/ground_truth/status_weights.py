"""Status weights ``w(o, c)`` from real microdata.

Replaces the hard-coded Colombia 2023 prior in ``build.py`` with a
computation from the LAPOP income variable, country by country. The
weights are the **percentile rank of the mean monthly labour income**
of the occupation's ISCO major group within the country, normalised so
that ``Σ_o w(o, c) = 1`` for each country.

Two entry points:

* ``status_weights_from_lapop(df, occupations, country_code, ...)`` —
  the production path; runs against a LAPOP DataFrame.
* ``status_weights_prior(occupations, country='CO')`` — the documented
  fallback prior (DECISIONS D-003), kept for the POC and for testing.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from apd.ground_truth.crosswalks import POC_MAPPINGS

logger = logging.getLogger(__name__)

# Defensible income priors (monthly, local currency at 2023 levels).
# Per-occupation rather than per-ISCO-major because the prior reflects
# the proposal's status tier expectations (high / medium / low) before
# LAPOP data arrives. Replaced by status_weights_from_lapop in
# production.
_PRIOR_INCOME: dict[str, dict[str, float]] = {
    "CO": {  # Colombian pesos
        "CEO": 18_000_000, "doctor": 8_500_000, "software engineer": 7_500_000,
        "lawyer": 6_800_000, "university professor": 6_500_000,
        "architect": 6_000_000, "accountant": 4_200_000, "journalist": 3_500_000,
        "nurse": 3_200_000, "police officer": 2_500_000, "mechanic": 2_400_000,
        "salesperson": 2_000_000, "secretary": 2_300_000, "cook": 1_800_000,
        "hairdresser": 1_700_000, "driver": 2_200_000, "security guard": 1_700_000,
        "farmer": 1_400_000, "nanny": 1_200_000,
        "construction worker": 1_600_000, "seamstress": 1_300_000,
        "janitor": 1_400_000, "domestic worker": 950_000,
        "street vendor": 900_000, "waste collector": 1_100_000,
    },
    # Per-country priors (Mexican peso, Brazilian real, Peruvian sol);
    # rounded for plausibility, refined by LAPOP at run time.
    "MX": {  # Mexican pesos
        "CEO": 250_000, "doctor": 90_000, "software engineer": 75_000,
        "lawyer": 70_000, "university professor": 65_000, "architect": 60_000,
        "accountant": 35_000, "journalist": 28_000, "nurse": 28_000,
        "police officer": 22_000, "mechanic": 18_000, "salesperson": 15_000,
        "secretary": 18_000, "cook": 12_000, "hairdresser": 12_000,
        "driver": 16_000, "security guard": 12_000, "farmer": 10_000,
        "nanny": 9_000, "construction worker": 13_000, "seamstress": 11_000,
        "janitor": 11_000, "domestic worker": 7_500, "street vendor": 7_000,
        "waste collector": 9_000,
    },
    "BR": {  # Brazilian reais
        "CEO": 60_000, "doctor": 22_000, "software engineer": 18_000,
        "lawyer": 17_000, "university professor": 16_000, "architect": 14_000,
        "accountant": 8_500, "journalist": 7_500, "nurse": 6_500,
        "police officer": 5_500, "mechanic": 4_500, "salesperson": 4_000,
        "secretary": 4_500, "cook": 3_200, "hairdresser": 3_000,
        "driver": 4_500, "security guard": 3_200, "farmer": 2_400,
        "nanny": 2_200, "construction worker": 3_400, "seamstress": 2_800,
        "janitor": 2_800, "domestic worker": 1_700, "street vendor": 1_800,
        "waste collector": 2_500,
    },
    "PE": {  # Peruvian soles
        "CEO": 35_000, "doctor": 12_000, "software engineer": 9_000,
        "lawyer": 8_500, "university professor": 8_000, "architect": 7_500,
        "accountant": 4_500, "journalist": 3_800, "nurse": 3_500,
        "police officer": 2_800, "mechanic": 2_500, "salesperson": 2_200,
        "secretary": 2_400, "cook": 1_800, "hairdresser": 1_700,
        "driver": 2_400, "security guard": 1_700, "farmer": 1_400,
        "nanny": 1_200, "construction worker": 1_900, "seamstress": 1_500,
        "janitor": 1_500, "domestic worker": 1_050, "street vendor": 1_000,
        "waste collector": 1_300,
    },
}


def status_weights_prior(occupations: list[str], *, country: str = "CO") -> pd.DataFrame:
    """Defensible income-based prior; returns long DataFrame keyed by occupation."""
    if country not in _PRIOR_INCOME:
        raise KeyError(f"no income prior for country {country!r}")
    incomes_dict = _PRIOR_INCOME[country]
    missing = [o for o in occupations if o not in incomes_dict]
    if missing:
        raise KeyError(f"no income prior for occupations: {missing}")
    incomes = pd.Series({o: incomes_dict[o] for o in occupations}, name="income")
    return _percentile_rank_weights(incomes, country=country)


def status_weights_from_lapop(
    lapop_df: pd.DataFrame,
    occupations: list[str],
    *,
    country: str,
    country_code: int,
    income_column: str = "Q10NEW",
    occupation_column: str = "OCCUP4A",
    country_column: str = "pais",
) -> pd.DataFrame:
    """Compute status weights from a LAPOP-shaped DataFrame.

    Falls back to ``status_weights_prior`` (with a warning) when the
    requested income column is absent or the country has no rows.
    """
    missing_cols = {country_column, occupation_column} - set(lapop_df.columns)
    if missing_cols:
        logger.warning(
            "LAPOP DataFrame missing %s — falling back to prior status weights.",
            missing_cols,
        )
        return status_weights_prior(occupations, country=country)
    if income_column not in lapop_df.columns:
        logger.warning(
            "LAPOP DataFrame has no income column %r — falling back to prior weights.",
            income_column,
        )
        return status_weights_prior(occupations, country=country)

    cell = lapop_df[lapop_df[country_column] == country_code].copy()
    if cell.empty:
        logger.warning(
            "No LAPOP rows for country %s (code %d) — falling back to prior weights.",
            country, country_code,
        )
        return status_weights_prior(occupations, country=country)

    # LAPOP income sentinels for missing / refused. Drop them.
    sentinels = {88, 98, 99, 888888, 999999, -1}
    cell = cell[~cell[income_column].isin(sentinels)]
    cell = cell[pd.to_numeric(cell[income_column], errors="coerce").notna()]
    cell[income_column] = pd.to_numeric(cell[income_column])
    if cell.empty:
        logger.warning(
            "All LAPOP income values for %s were sentinels — using prior weights.",
            country,
        )
        return status_weights_prior(occupations, country=country)

    mean_income = cell.groupby(occupation_column)[income_column].mean()
    overall_median = float(cell[income_column].median())

    rows: list[dict] = []
    for occ in occupations:
        if occ not in POC_MAPPINGS:
            raise KeyError(f"occupation {occ!r} not in crosswalks")
        major = int(POC_MAPPINGS[occ].derived_major)
        income = float(mean_income.loc[major]) if major in mean_income.index else overall_median
        rows.append({"occupation": occ, "income": income})
    incomes = pd.DataFrame(rows).set_index("occupation")["income"]
    return _percentile_rank_weights(incomes, country=country, source="lapop")


def _percentile_rank_weights(
    incomes: pd.Series,
    *,
    country: str,
    source: str = "prior",
) -> pd.DataFrame:
    """Compute normalised percentile-rank weights from an income series."""
    if (incomes <= 0).any():
        raise ValueError("incomes must be strictly positive")
    ranks = incomes.rank(pct=True)
    weights = ranks / ranks.sum()
    df = pd.DataFrame(
        {
            "country": country,
            "occupation": incomes.index,
            "income": incomes.values,
            "weight": weights.values,
            "weight_source": source,
        },
    ).reset_index(drop=True)
    return df
