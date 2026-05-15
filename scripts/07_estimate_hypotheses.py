"""07 — Plot the pigmentocratic gradient → results/figures/gradient_poc.png.

With N=3 occupations the regression coefficient β is statistically
degenerate; the script still runs the OLS so the machinery is exercised,
and writes the scatter for visual inspection. **Do not interpret the POC
value of APD.**
"""

from __future__ import annotations

import logging
import sys

import pandas as pd

from apd.config import settings
from apd.estimate.h1_h2 import fit_gradient
from apd.viz.plots import plot_gradient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("07_estimate")

APD_IN = settings.results_tables / "apd_poc.csv"
OUT = settings.results_figures / "gradient_poc.png"


def main() -> int:
    settings.results_figures.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        log.info("Cached: %s", OUT)
        return 0
    if not APD_IN.exists():
        log.error("Missing %s. Run scripts/06_compute_apd.py first.", APD_IN)
        return 1

    table = pd.read_csv(APD_IN)
    try:
        fit = fit_gradient(table)
        log.info(
            "Gradient OLS (POC, %d obs): alpha=%.3f, beta=%.3f, sigma=%.3f",
            fit.n_obs, fit.alpha, fit.beta, fit.sigma,
        )
    except ValueError as exc:
        log.warning("Gradient could not be fit: %s", exc)

    plot_gradient(table, OUT)
    log.info("Wrote %s", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
