"""LAPOP AmericasBarometer ingestion.

The 2023 wave is the POC's primary ground-truth source. The LAPOP file is
distributed by Vanderbilt and *typically* requires a free account login;
that is not an institutional credential, so it complies with the binding
spec, but it is not scriptable from a clean clone.

Strategy:
    1.  Look for the user-placed file in ``data/raw/``.
    2.  If absent, fall back to a *documented synthetic prior* (see
        ``DECISIONS.md`` D-003) that mimics published PERLA-coded
        distributions from Telles 2014 and Campos-Vázquez & Medina-Cortina
        2019. Synthetic rows are flagged ``is_synthetic=True`` so that
        downstream code can refuse to use them in the production run.

The synthetic prior is **only** acceptable for plumbing validation in the
POC, never for paper findings.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from apd.config import settings

logger = logging.getLogger(__name__)

LAPOP_FILE_NAMES = (
    "lapop_colombia_2023.csv",
    "Colombia_LAPOP_AmericasBarometer_2023_v1.0_w.csv",
    "Colombia 2023 LAPOP AmericasBarometer v1.0_W.csv",
)


def _find_real_file() -> Path | None:
    """Return the first matching LAPOP CSV in ``data/raw``, or None."""
    for name in LAPOP_FILE_NAMES:
        p = settings.data_raw / name
        if p.exists():
            return p
    return None


def load_or_synthetic(occupations: list[str]) -> pd.DataFrame:
    """Return long-form (occupation × PERLA tone × prob) for ``occupations``.

    Columns
    -------
    occupation : str
    perla_tone : int in {1..11}
    prob       : float in [0,1] (sums to 1 within each occupation)
    is_synthetic : bool
    """
    real = _find_real_file()
    if real is not None:
        logger.info("LAPOP file found: %s — loading real distribution", real)
        return _load_real(real, occupations)
    logger.warning(
        "LAPOP 2023 Colombia not present in %s. Falling back to documented "
        "synthetic prior (see DECISIONS.md D-003). NEVER use this for paper "
        "findings.",
        settings.data_raw,
    )
    return synthetic_prior(occupations)


def _load_real(path: Path, occupations: list[str]) -> pd.DataFrame:
    """Real LAPOP loader.

    LAPOP carries ``COLOR`` (PERLA 1..11 applied by the interviewer) and
    ``OCCUP4A`` (ISCO-08 1-digit occupational group) for some country-waves.
    This implementation is intentionally minimal and will be hardened once a
    real LAPOP drop is provided; it is reachable only when the file exists.
    """
    # Real loading requires fixing the variable names against the actual
    # 2023 codebook, which we cannot do without the file. Until then, we
    # refuse to silently produce wrong output and raise a clear error.
    raise NotImplementedError(
        f"Real LAPOP loading is not yet implemented for {path.name}. "
        "Provide the codebook and rerun, or delete the file to use the "
        "synthetic prior fallback documented in DECISIONS.md D-003.",
    )


def synthetic_prior(occupations: list[str]) -> pd.DataFrame:
    """Synthetic PERLA prior calibrated against published Latin-American studies.

    Centres and spreads are chosen so that high-status occupations cluster at
    lighter PERLA tones and low-status at darker tones, in keeping with the
    qualitative findings of Telles 2014 and Campos-Vázquez & Medina-Cortina
    2019 for Colombia. The shape (truncated Gaussian) is a convenient
    discretisable family; nothing about the POC's pipeline depends on the
    specific functional form.
    """
    centres = {
        "CEO": 2.5,
        "nurse": 5.0,
        "domestic worker": 7.0,
    }
    sds = {
        "CEO": 1.4,
        "nurse": 1.7,
        "domestic worker": 1.8,
    }
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
