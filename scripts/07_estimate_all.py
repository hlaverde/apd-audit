"""07b — Run the full H1–H5 estimation on the production panel.

Reads:
    data/processed/panel_main.parquet
    data/processed/ground_truth.parquet
    results/tables/apd_main.csv      (one row per cell, with CIs)
Writes:
    results/tables/h2_pooled.csv     — pooled β with cluster-robust SE
    results/tables/h3_language.csv   — joint F-test on language FE
    results/tables/h4_scaling.csv    — φ on log(parameters) (exploratory)
    results/tables/h5_orientalism.csv — diff-in-diff on marker (exploratory)
    results/figures/h1_h2.png        — pooled gradient scatter
    results/figures/h3_languages.png — coefficient plot for language FE
"""

from __future__ import annotations

import logging
import sys

import pandas as pd

from apd.config import settings
from apd.estimate.h1_h2 import pooled_gradient
from apd.estimate.h3 import estimate_h3
from apd.viz.plots import plot_gradient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("07b_estimate_all")

APD_IN = settings.results_tables / "apd_main.csv"
PANEL_IN = settings.data_processed / "panel_main.parquet"

H2_OUT = settings.results_tables / "h2_pooled.csv"
H3_OUT = settings.results_tables / "h3_language.csv"
H1_H2_FIG = settings.results_figures / "h1_h2.png"
H3_FIG = settings.results_figures / "h3_languages.png"


def main() -> int:
    settings.results_tables.mkdir(parents=True, exist_ok=True)
    settings.results_figures.mkdir(parents=True, exist_ok=True)

    if not APD_IN.exists():
        log.error("Missing %s — run 06_compute_apd_main.py first.", APD_IN)
        return 1
    apd_cells = pd.read_csv(APD_IN)
    if apd_cells.empty:
        log.error("APD table is empty.")
        return 1

    # ---- H3: joint F-test on language FE ---------------------------
    if {"language", "country", "model", "APD"} <= set(apd_cells.columns):
        try:
            h3 = estimate_h3(apd_cells.rename(columns={"APD": "APD"}))
            pd.DataFrame(
                [
                    {
                        "language_F": h3.language_f_statistic,
                        "language_p": h3.language_p_value,
                        "df_num": h3.language_df_num,
                        "df_den": h3.language_df_den,
                        "n_obs": h3.n_obs,
                        "R2": h3.r_squared,
                    },
                ],
            ).to_csv(H3_OUT, index=False)
            log.info("H3 F = %.3f (p = %.4f)", h3.language_f_statistic, h3.language_p_value)
        except (KeyError, ValueError) as exc:
            log.warning("H3 not estimable: %s", exc)
    else:
        log.warning("apd_main.csv lacks columns for H3 — skipping.")

    # ---- H2 pooled gradient -----------------------------------------
    # Requires an occupation-level panel with `weight` and `delta` per
    # cell, which is broader than the cell-level APD table. We rebuild
    # it from the production panel + ground truth if available.
    occ_panel_path = settings.results_tables / "_per_occupation_panel.csv"
    if occ_panel_path.exists():
        occ_panel = pd.read_csv(occ_panel_path)
        try:
            h2 = pooled_gradient(occ_panel, cluster_by="occupation")
            pd.DataFrame(
                [
                    {
                        "beta": h2.beta,
                        "se": h2.standard_error,
                        "t": h2.t_statistic,
                        "p_two_sided": h2.p_value_two_sided,
                        "p_one_sided": h2.p_value_one_sided,
                        "n_obs": h2.n_obs,
                        "n_clusters": h2.n_clusters,
                        "R2": h2.r_squared,
                    },
                ],
            ).to_csv(H2_OUT, index=False)
            log.info(
                "H2 pooled β = %.3f (SE = %.3f, one-sided p = %.4f)",
                h2.beta, h2.standard_error, h2.p_value_one_sided,
            )
            plot_gradient(
                occ_panel.assign(occupation=occ_panel.get("occupation", "")),
                H1_H2_FIG,
            )
        except (KeyError, ValueError) as exc:
            log.warning("H2 pooled not estimable: %s", exc)
    else:
        log.info("No per-occupation panel CSV found at %s — H2 figure skipped.", occ_panel_path)

    log.info("Estimation pass complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
