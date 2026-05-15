"""02b — Build the production ground-truth panel for all 4 countries.

Loads LAPOP 2023 files for CO, MX, BR, PE; computes f_emp(t | o, c) and
status weights for each country; writes:

    data/processed/ground_truth.parquet      — long-form f_emp panel
    data/processed/status_weights.parquet    — per-country, per-occupation w

Falls back to the documented synthetic / prior values when LAPOP files
or income variables are missing (see apd.ingest.lapop and
apd.ground_truth.status_weights for the graceful-degradation logic).
"""

from __future__ import annotations

import logging
import sys

import pandas as pd

from apd.config import settings
from apd.ground_truth.crosswalks import POC_MAPPINGS
from apd.ground_truth.status_weights import (
    status_weights_from_lapop,
    status_weights_prior,
)
from apd.ingest.lapop import LAPOP_COUNTRY_CODES, _read_lapop_file, _find_real_file, load_or_synthetic

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("02b_ground_truth_main")

OUT_GT = settings.data_processed / "ground_truth.parquet"
OUT_WEIGHTS = settings.data_processed / "status_weights.parquet"

COUNTRIES: tuple[str, ...] = ("CO", "MX", "BR", "PE")


def main() -> int:
    settings.data_processed.mkdir(parents=True, exist_ok=True)
    if OUT_GT.exists() and OUT_WEIGHTS.exists():
        log.info("Cached: %s and %s", OUT_GT, OUT_WEIGHTS)
        return 0

    occupations = list(POC_MAPPINGS.keys())

    gt_rows: list[pd.DataFrame] = []
    wt_rows: list[pd.DataFrame] = []

    lapop_df = _try_load_lapop()

    for country in COUNTRIES:
        log.info("Building ground truth for %s", country)
        gt = load_or_synthetic(occupations, country=country)
        gt["country"] = country
        gt_rows.append(gt)

        if lapop_df is not None:
            wt = status_weights_from_lapop(
                lapop_df, occupations,
                country=country, country_code=LAPOP_COUNTRY_CODES[country],
            )
        else:
            wt = status_weights_prior(occupations, country=country)
        wt_rows.append(wt)

    gt_panel = pd.concat(gt_rows, ignore_index=True)
    wt_panel = pd.concat(wt_rows, ignore_index=True)

    gt_panel.to_parquet(OUT_GT, index=False)
    wt_panel.to_parquet(OUT_WEIGHTS, index=False)

    log.info(
        "Wrote %s (%d rows across %d countries × %d occupations)",
        OUT_GT, len(gt_panel),
        gt_panel["country"].nunique(),
        gt_panel["occupation"].nunique(),
    )
    log.info(
        "Wrote %s (%d weight rows; sources: %s)",
        OUT_WEIGHTS, len(wt_panel),
        wt_panel["weight_source"].unique().tolist(),
    )
    return 0


def _try_load_lapop() -> pd.DataFrame | None:
    """Attempt to load any LAPOP file in data/raw; return concat-ed DataFrame.

    The function is best-effort. If no LAPOP files are present or none
    parses cleanly, returns None and downstream loaders fall back to the
    prior. Future work: union LAPOP files from all 4 countries into a
    single DataFrame keyed by ``pais``.
    """
    found = list(settings.data_raw.glob("*.csv")) + list(settings.data_raw.glob("*.dta"))
    if not found:
        log.warning("No LAPOP files in %s — using synthetic prior", settings.data_raw)
        return None
    frames: list[pd.DataFrame] = []
    for path in found:
        try:
            frames.append(_read_lapop_file(path))
        except Exception as exc:
            log.warning("Could not read %s: %s", path.name, exc)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True, sort=False)


if __name__ == "__main__":
    sys.exit(main())
