"""06b — Per-(country, language, model) APD with bootstrap CIs.

Reads:
    data/processed/ground_truth.parquet
    data/processed/status_weights.parquet
    data/processed/panel_main.parquet
Writes:
    results/tables/apd_main.csv        — one row per (c, ℓ, m) cell of the
                                         main grid, APD point estimate + CI.
    results/tables/apd_robustness.csv  — same for the robustness grid.
    results/tables/_per_occupation_panel.csv — long (cell × occupation)
                                         panel of D and Δ, input to H1/H2.

The main and robustness grids are tabulated separately: robustness cells
audit 10 of the 25 occupations, so their status weights sum to ~0.42 and
their APD is not on the same scale as a main-grid cell's (see D-038).
The H5 marker grid is excluded from both — its synthetic occupation keys
have no ground truth, and it is analysed as a diff-in-diff in 07.

The proposal §6.2 step 7 prescribes 1 000 bootstrap replicates; this
script uses that as the default, deterministic seed = settings.seed.
"""

from __future__ import annotations

import logging
import sys

import pandas as pd

from apd.apd.bootstrap import bootstrap_apd_by_cell, per_occupation_panel
from apd.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("06b_apd_main")

GT_IN = settings.data_processed / "ground_truth.parquet"
WEIGHTS_IN = settings.data_processed / "status_weights.parquet"
PANEL_IN = settings.data_processed / "panel_main.parquet"
OUT = settings.results_tables / "apd_main.csv"
OUT_ROBUSTNESS = settings.results_tables / "apd_robustness.csv"
OUT_OCC_PANEL = settings.results_tables / "_per_occupation_panel.csv"
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

    if "grid" not in panel.columns:
        log.error("panel lacks the 'grid' column — rerun scripts/05_build_panel_main.py")
        return 1

    main_panel = panel[panel["grid"] == "main"]
    robustness_panel = panel[panel["grid"] == "robustness"]
    log.info(
        "Panel: %d main, %d robustness, %d H5 (H5 excluded from APD)",
        len(main_panel), len(robustness_panel), int((panel["grid"] == "h5").sum()),
    )

    occ_panel = per_occupation_panel(main_panel, gt)
    occ_panel.to_csv(OUT_OCC_PANEL, index=False)
    log.info(
        "Wrote %s — %d (cell x occupation) rows for H1/H2.",
        OUT_OCC_PANEL, len(occ_panel),
    )

    summary = bootstrap_apd_by_cell(
        main_panel, gt, n_replicates=N_REPLICATES, seed=settings.seed,
    )
    summary.to_csv(OUT, index=False)
    log.info(
        "Wrote %s — %d (country, language, model) cells, %d replicates each.",
        OUT, len(summary), N_REPLICATES,
    )

    if not robustness_panel.empty:
        rob = bootstrap_apd_by_cell(
            robustness_panel, gt, n_replicates=N_REPLICATES, seed=settings.seed,
        )
        rob.to_csv(OUT_ROBUSTNESS, index=False)
        log.info("Wrote %s — %d robustness cells.", OUT_ROBUSTNESS, len(rob))
    return 0


if __name__ == "__main__":
    sys.exit(main())
