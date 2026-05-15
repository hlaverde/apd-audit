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

# Default LAPOP file names the loader will recognise.
LAPOP_FILE_NAMES: tuple[str, ...] = (
    "lapop_colombia_2023.csv",
    "Colombia_LAPOP_AmericasBarometer_2023_v1.0_w.csv",
    "Colombia_LAPOP_AmericasBarometer_2023_v1.0_w.dta",
    "Colombia 2023 LAPOP AmericasBarometer v1.0_W.csv",
    "Colombia 2023 LAPOP AmericasBarometer v1.0_W.dta",
)

# LAPOP 2023 country codes (verify against the file's codebook on first
# load — log a warning if the value distribution suggests they differ).
LAPOP_COUNTRY_CODES: dict[str, int] = {
    "CO": 8,    # Colombia
    "MX": 1,    # Mexico
    "BR": 15,   # Brazil
    "PE": 11,   # Peru
}

# Expected column names. The loader validates these and falls back to a
# clear error if the file's columns differ — at which point the user
# adjusts the mapping for the wave they downloaded.
EXPECTED_COLUMNS: dict[str, str] = {
    "country": "pais",
    "perla_tone": "COLOR",
    "occupation_major": "OCCUP4A",
}


def _find_real_file() -> Path | None:
    """Return the first matching LAPOP file in ``data/raw``, or None."""
    for name in LAPOP_FILE_NAMES:
        p = settings.data_raw / name
        if p.exists():
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
        is_synthetic (True if no LAPOP file was found).
    """
    real = _find_real_file()
    if real is not None:
        logger.info("LAPOP file found: %s — loading real distribution", real)
        try:
            df = _load_real(real, occupations, country=country)
        except (FileNotFoundError, ValueError, KeyError) as exc:
            logger.warning(
                "LAPOP real load failed (%s); falling back to synthetic prior. "
                "Fix the issue above and rerun for the real ground truth.",
                exc,
            )
            return synthetic_prior(occupations)
        # Defensive: ensure every requested occupation got a row.
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

    Defensive: validates that the expected columns exist, that the
    country code is present in the file, and that the resulting cells
    have at least one valid PERLA tone observation.
    """
    cols = {**EXPECTED_COLUMNS, **(columns or {})}
    cc = {**LAPOP_COUNTRY_CODES, **(country_codes or {})}

    df = _read_lapop_file(path)

    # 1. Column validation.
    missing_cols = [v for v in cols.values() if v not in df.columns]
    if missing_cols:
        raise KeyError(
            f"LAPOP file {path.name} missing expected columns: {missing_cols}. "
            f"Available columns: {sorted(df.columns)[:20]}{'…' if len(df.columns) > 20 else ''}. "
            f"Override via the `columns=` argument if the wave's variable names differ.",
        )

    # 2. Country filter.
    if country not in cc:
        raise KeyError(f"no LAPOP country code registered for {country!r}")
    country_code = cc[country]
    country_col = cols["country"]
    cell = df[df[country_col] == country_code]
    if cell.empty:
        # Sometimes country codes ship as strings; try that path too.
        cell = df[df[country_col].astype(str) == str(country_code)]
    if cell.empty:
        raise ValueError(
            f"LAPOP file has no rows for country code {country_code} "
            f"in column {country_col!r}. Verify LAPOP_COUNTRY_CODES "
            f"against the file's codebook.",
        )

    # 3. Drop missing PERLA tones (LAPOP uses 88/98/99 for missing).
    perla_col = cols["perla_tone"]
    cell = cell[cell[perla_col].between(1, 11, inclusive="both")].copy()
    cell[perla_col] = cell[perla_col].astype(int)
    if cell.empty:
        raise ValueError(
            f"no valid PERLA tone observations in column {perla_col!r} "
            f"for country {country!r}",
        )

    # 4. Drop missing occupation majors.
    occ_col = cols["occupation_major"]
    cell = cell[cell[occ_col].between(1, 9, inclusive="both")].copy()
    cell[occ_col] = cell[occ_col].astype(int)

    # 5. Per study-occupation, look up the ISCO major and compute f_emp.
    tones = np.arange(1, 12)
    rows: list[dict] = []
    for occ in occupations:
        if occ not in POC_MAPPINGS:
            raise KeyError(f"occupation {occ!r} not registered in crosswalks")
        major = int(POC_MAPPINGS[occ].derived_major)
        major_cell = cell[cell[occ_col] == major]
        if len(major_cell) < 5:
            logger.warning(
                "LAPOP %s × ISCO-major %d: only %d observations. The f_emp "
                "for occupation %r will be noisy; consider collapsing further "
                "or supplementing with the national survey (D-014 robustness).",
                country, major, len(major_cell), occ,
            )
            if major_cell.empty:
                continue
        counts = major_cell[perla_col].value_counts().reindex(tones, fill_value=0)
        total = int(counts.sum())
        probs = counts.to_numpy(dtype=float) / total if total > 0 else np.zeros(11)
        for tone, prob in zip(tones, probs, strict=True):
            rows.append(
                {
                    "occupation": occ,
                    "perla_tone": int(tone),
                    "prob": float(prob),
                    "is_synthetic": False,
                    "n_respondents": total,
                    "isco_major": major,
                },
            )
    if not rows:
        raise ValueError(
            f"LAPOP load produced no rows. Country {country!r} present but "
            f"no study occupation matched any ISCO major in the data.",
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
