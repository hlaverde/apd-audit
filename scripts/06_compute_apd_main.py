"""06b — Per-(country, language, model) APD with bootstrap CIs.

Reads:
    data/processed/ground_truth.parquet
    data/processed/status_weights.parquet
    data/processed/panel_main.parquet
Writes:
    results/tables/apd_main.csv  — one row per (c, ℓ, m) cell with
                                   APD point estimate and 95% percentile CI.

The proposal §6.2 step 7 prescribes 1 000 bootstrap replicates; this
script uses that as the default, deterministic seed = settings.seed.
"""

from __future__ import annotations

import logging
import sys

import pandas as pd

from apd.apd.bootstrap import bootstrap_apd_by_cell
from apd.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("06b_apd_main")

GT_IN = settings.data_processed / "ground_truth.parquet"
WEIGHTS_IN = settings.data_processed / "status_weights.parquet"
PANEL_IN = settings.data_processed / "panel_main.parquet"
OUT = settings.results_tables / "apd_main.csv"
N_REPLICATES = 1000


def main() -> int:
    settings.results_tables.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        log.info("Cached: %s", OUT)
        return 0
    for required in (GT_IN, WEIGHTS_IN, PANEL_IN):
        if not required.exists():
            log.error("Missing %s", required)
            return 1

    gt = pd.read_parquet(GT_IN)
    weights = pd.read_parquet(WEIGHTS_IN)
    panel = pd.read_parquet(PANEL_IN)

    # Attach per-(country, occupation) weights onto the ground-truth panel.
    if "weight" not in gt.columns:
        gt = gt.merge(weights[["country", "occupation", "weight"]],
                      on=["country", "occupation"], how="left")
    missing_weights = gt["weight"].isna().sum()
    if missing_weights:
        log.warning("%d ground-truth rows missing a weight — APD will skip those occupations",
                    missing_weights)

    summary = bootstrap_apd_by_cell(
        panel, gt, n_replicates=N_REPLICATES, seed=settings.seed,
    )
    summary.to_csv(OUT, index=False)
    log.info(
        "Wrote %s — %d (country, language, model) cells, %d replicates each.",
        OUT, len(summary), N_REPLICATES,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
