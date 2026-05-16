"""LAPOP AmericasBarometer ingestion.

LAPOP 2023 is the primary ground-truth source for the production grid
(DECISIONS D-014). Each country's wave is distributed by Vanderbilt
behind a free email-only registration at lapopsurveys.org/data-access.

Strategy:
    1.  Look for the user-placed file in ``data/raw/``.
    2.  If absent, fall back to the documented synthetic prior (D-003).
    3.  If present, parse with defensive validation against the published
        2023 codebook and produce f_emp(t | occupation, country).

LAPOP's occupation variable is ``OCCUP4A`` (1-digit ISCO-08 major group,
values 1-9). The study's 25 occupations live at 3-digit ISCO minor group
granularity; we therefore map each study occupation to its major group
and use the per-major-group PERLA distribution as the baseline. Multiple
study occupations within the same major group share the same f_emp.

PERLA tone is in the ``COLOR`` variable (1 = lightest, 11 = darkest),
applied by the interviewer using the physical PERLA palette card.

Country codes (``pais``) follow the LAPOP 2023 wave codebook. The
defaults below should be verified against the actual file the user
downloads; override at call time if they differ.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from apd.config import settings
from apd.ground_truth.crosswalks import POC_MAPPINGS

logger = logging.getLogger(__name__)

# Glob patterns the loader recognises in ``data/raw``. The 2023 wave
# distribution uses ISO-prefixed names of the form
# ``COL_2023_LAPOP_AmericasBarometer_v1.0_w.dta`` (one per country).
LAPOP_FILE_GLOBS: tuple[str, ...] = (
    "COL_2023_LAPOP_AmericasBarometer_*.dta",
    "MEX_2023_LAPOP_AmericasBarometer_*.dta",
    "BRA_2023_LAPOP_AmericasBarometer_*.dta",
    "PER_2023_LAPOP_AmericasBarometer_*.dta",
)

# LAPOP 2023 country codes — confirmed against the four downloaded files
# (CO=8, MX=1, BR=15, PE=11). Override per-call if a different wave uses
# different codes.
LAPOP_COUNTRY_CODES: dict[str, int] = {
    "CO": 8,    # Colombia
    "MX": 1,    # Mexico
    "BR": 15,   # Brazil
    "PE": 11,   # Peru
}

# Real LAPOP 2023 variable names, verified by inspecting the
# COL_2023_*.dta file. ``colorr`` is the interviewer-applied PERLA tone;
# ``edre`` is Nivel de educación (0..6) used as the *status proxy* in
# place of an ISCO occupation code (the 2023 wave dropped detailed
# occupation coding — see DECISIONS.md D-024); ``q10inc`` is monthly
# income, encoded as a bracket integer (the inverse-decoded bracket
# midpoints live in ``apd.ground_truth.status_weights``).
EXPECTED_COLUMNS: dict[str, str] = {
    "country": "pais",
    "perla_tone": "colorr",
    "education": "edre",
    "income_bracket": "q10inc",
    "ethnic_id": "etid",
}


# Mapping from study-occupation status tier → education-level set (edre
# values that approximate that tier). See DECISIONS.md D-024.
EDUCATION_TIER_VALUES: dict[str, tuple[int, ...]] = {
    "high":   (5, 6),         # university / superior
    "medium": (3, 4),         # secondary
    "low":    (0, 1, 2),      # primary / none
}


def _find_real_file() -> Path | None:
    """Return the first matching LAPOP file in ``data/raw``.

    The 2023 wave produces one ``.dta`` per country, so several files
    coexist. This helper returns *any* match (the caller usually filters
    by country code afterwards).
    """
    for pattern in LAPOP_FILE_GLOBS:
        matches = list(settings.data_raw.glob(pattern))
        if matches:
            return matches[0]
    # Back-compat: fall through to the original named files.
    for name in (
        "lapop_colombia_2023.csv",
        "Colombia 2023 LAPOP AmericasBarometer v1.0_W.dta",
    ):
        p = settings.data_raw / name
        if p.exists():
            return p
    return None


def _find_country_file(country: str) -> Path | None:
    """Return the LAPOP file matching ``country`` (CO / MX / BR / PE)."""
    prefixes = {"CO": "COL", "MX": "MEX", "BR": "BRA", "PE": "PER"}
    if country not in prefixes:
        return None
    for p in settings.data_raw.glob(f"{prefixes[country]}_2023_LAPOP_*.dta"):
        return p
    return None


def load_or_synthetic(
    occupations: list[str],
    *,
    country: str = "CO",
) -> pd.DataFrame:
    """Return long-form (occupation × PERLA tone × prob) for ``occupations``.

    Columns:
        occupation, perla_tone (1..11), prob (sums to 1 per occupation),
        is_synthetic (False if real LAPOP data loaded).
    """
    # Prefer the country-specific file (ISO-prefixed 2023 layout).
    real = _find_country_file(country) or _find_real_file()
    if real is not None:
        logger.info("LAPOP file for %s: %s — loading real distribution", country, real)
        try:
            df = _load_real(real, occupations, country=country)
        except (FileNotFoundError, ValueError, KeyError) as exc:
            logger.warning(
                "LAPOP real load failed (%s); falling back to synthetic prior.",
                exc,
            )
            return synthetic_prior(occupations)
        missing = set(occupations) - set(df["occupation"].unique())
        if missing:
            logger.warning(
                "LAPOP produced no rows for %s — back-filling with synthetic prior.",
                missing,
            )
            synth = synthetic_prior(list(missing))
            return pd.concat([df, synth], ignore_index=True)
        return df
    logger.warning(
        "LAPOP 2023 not present in %s — using documented synthetic prior "
        "(DECISIONS.md D-003). NEVER cite this for paper findings.",
        settings.data_raw,
    )
    return synthetic_prior(occupations)


def _read_lapop_file(path: Path) -> pd.DataFrame:
    """Read a LAPOP file, auto-detecting CSV / Stata / SAV formats."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, low_memory=False)
    if suffix == ".dta":
        return pd.read_stata(path, convert_categoricals=False)
    if suffix == ".sav":
        # SAV requires pyreadstat which is a heavier dep; we don't add it
        # by default. The user should convert to CSV or DTA upstream.
        raise NotImplementedError(
            f"SPSS .sav files not supported directly. "
            f"Convert {path.name} to .csv or .dta first.",
        )
    raise ValueError(f"unknown LAPOP file format: {suffix!r}")


def _load_real(
    path: Path,
    occupations: list[str],
    *,
    country: str = "CO",
    country_codes: dict[str, int] | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Parse a LAPOP file and emit the f_emp panel.

    Strategy (DECISIONS.md D-024):
    1. Filter to country.
    2. Drop missing PERLA tones from ``colorr``.
    3. Map each study occupation to its status tier
       (``crosswalks.POC_MAPPINGS[occ].status_tier``) and look up the
       corresponding LAPOP ``edre`` levels in
       ``EDUCATION_TIER_VALUES``.
    4. Compute the PERLA distribution among respondents whose ``edre``
       falls in that set. That distribution becomes f_emp for every
       study occupation in the tier.

    Defensive: validates columns, country presence, and per-tier sample
    sizes.
    """
    cols = {**EXPECTED_COLUMNS, **(columns or {})}
    cc = {**LAPOP_COUNTRY_CODES, **(country_codes or {})}

    df = _read_lapop_file(path)

    # 1. Column validation (only the required trio — etid/income are optional).
    required = ("country", "perla_tone", "education")
    missing_cols = [cols[k] for k in required if cols[k] not in df.columns]
    if missing_cols:
        raise KeyError(
            f"LAPOP file {path.name} missing expected columns: {missing_cols}. "
            f"Available columns (first 25): {sorted(df.columns)[:25]}…. "
            f"Override via the `columns=` argument if the wave's variable names differ.",
        )

    # 2. Country filter.
    if country not in cc:
        raise KeyError(f"no LAPOP country code registered for {country!r}")
    country_code = cc[country]
    country_col = cols["country"]
    cell = df[df[country_col] == country_code]
    if cell.empty:
        cell = df[df[country_col].astype(str) == str(country_code)]
    if cell.empty:
        raise ValueError(
            f"LAPOP file has no rows for country code {country_code} "
            f"in column {country_col!r}. Verify LAPOP_COUNTRY_CODES.",
        )

    # 3. Drop missing PERLA tones (LAPOP missing sentinels for `colorr`
    #    are large ints — the inclusive 1..11 filter catches that).
    perla_col = cols["perla_tone"]
    cell = cell[cell[perla_col].between(1, 11, inclusive="both")].copy()
    cell[perla_col] = cell[perla_col].astype(int)
    if cell.empty:
        raise ValueError(
            f"no valid PERLA tone observations in column {perla_col!r} for {country!r}",
        )

    # 4. Build per-tier f_emp distributions.
    edu_col = cols["education"]
    cell = cell[cell[edu_col].between(0, 6, inclusive="both")].copy()
    cell[edu_col] = cell[edu_col].astype(int)

    tones = np.arange(1, 12)
    tier_distributions: dict[str, tuple[np.ndarray, int]] = {}
    for tier, edu_values in EDUCATION_TIER_VALUES.items():
        tier_cell = cell[cell[edu_col].isin(edu_values)]
        n = len(tier_cell)
        if n == 0:
            logger.warning(
                "LAPOP %s × education tier %r (edre ∈ %s): 0 observations; "
                "using uniform f_emp for occupations in this tier.",
                country, tier, edu_values,
            )
            tier_distributions[tier] = (np.full(11, 1.0 / 11), 0)
            continue
        counts = tier_cell[perla_col].value_counts().reindex(tones, fill_value=0)
        probs = counts.to_numpy(dtype=float) / counts.sum()
        tier_distributions[tier] = (probs, n)
        if n < 30:
            logger.warning(
                "LAPOP %s × tier %r: only %d obs; f_emp will be noisy.",
                country, tier, n,
            )

    # 5. Map each study occupation to its tier-level f_emp.
    rows: list[dict] = []
    for occ in occupations:
        if occ not in POC_MAPPINGS:
            raise KeyError(f"occupation {occ!r} not registered in crosswalks")
        tier = POC_MAPPINGS[occ].status_tier
        if tier not in tier_distributions:
            raise KeyError(
                f"occupation {occ!r} has status_tier {tier!r} not in "
                f"EDUCATION_TIER_VALUES",
            )
        probs, n = tier_distributions[tier]
        for tone, prob in zip(tones, probs, strict=True):
            rows.append(
                {
                    "occupation": occ,
                    "perla_tone": int(tone),
                    "prob": float(prob),
                    "is_synthetic": False,
                    "n_respondents": int(n),
                    "education_tier": tier,
                },
            )
    if not rows:
        raise ValueError(
            f"LAPOP load produced no rows for country {country!r}.",
        )
    return pd.DataFrame(rows)


def synthetic_prior(occupations: list[str]) -> pd.DataFrame:
    """Documented synthetic prior calibrated against published LatAm studies.

    Centres and spreads chosen so that high-status occupations cluster at
    lighter PERLA tones and low-status at darker tones, consistent with
    Telles 2014 *Pigmentocracies* and Campos-Vázquez & Medina-Cortina 2019.
    """
    centres = {
        "CEO": 2.5, "doctor": 3.0, "software engineer": 3.5, "lawyer": 3.0,
        "university professor": 3.5, "architect": 3.5, "accountant": 4.0,
        "journalist": 4.0,
        "nurse": 5.0, "police officer": 5.5, "mechanic": 6.0,
        "salesperson": 5.5, "secretary": 4.5, "cook": 5.5, "hairdresser": 5.0,
        "driver": 6.0, "security guard": 6.0,
        "farmer": 7.0, "nanny": 6.5, "construction worker": 7.0,
        "seamstress": 5.5, "janitor": 7.0, "domestic worker": 7.0,
        "street vendor": 7.0, "waste collector": 7.5,
    }
    sds = {o: 1.7 for o in centres}  # uniform spread; tighten per-occupation if needed
    missing = [o for o in occupations if o not in centres]
    if missing:
        raise KeyError(f"no synthetic prior calibrated for occupations: {missing}")

    tones = np.arange(1, 12)
    rows: list[dict] = []
    for occ in occupations:
        density = np.exp(-0.5 * ((tones - centres[occ]) / sds[occ]) ** 2)
        probs = density / density.sum()
        rows.extend(
            {
                "occupation": occ,
                "perla_tone": int(t),
                "prob": float(p),
                "is_synthetic": True,
            }
            for t, p in zip(tones, probs, strict=True)
        )
    return pd.DataFrame(rows)
