"""06 — Compute D, Δ, APD per (occupation, model, country, language) → results/tables/apd_poc.csv."""

from __future__ import annotations

import logging
import sys

import pandas as pd

from apd.apd.indicator import apd, compute_occupation_metrics
from apd.config import settings
from apd.panel.build import algorithmic_distribution
from apd.prompts.grid import POC_COUNTRY, POC_LANGUAGE, POC_MODEL, POC_OCCUPATIONS

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("06_apd")

GT_IN = settings.data_processed / "ground_truth_poc.parquet"
PANEL_IN = settings.data_processed / "panel_poc.parquet"
OUT = settings.results_tables / "apd_poc.csv"


def main() -> int:
    settings.results_tables.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        log.info("Cached: %s", OUT)
        return 0
    if not GT_IN.exists() or not PANEL_IN.exists():
        log.error("Missing inputs: %s or %s", GT_IN, PANEL_IN)
        return 1

    gt = pd.read_parquet(GT_IN)
    panel = pd.read_parquet(PANEL_IN)

    results = []
    rows = []
    for occ in POC_OCCUPATIONS:
        sub_gt = gt[gt["occupation"] == occ].sort_values("perla_tone")
        f_emp = sub_gt["prob"].to_numpy()
        weight = float(sub_gt["weight"].iloc[0])
        f_alg = algorithmic_distribution(panel, occ)
        m = compute_occupation_metrics(occ, f_alg, f_emp, weight)
        results.append(m)
        rows.append(
            {
                "country": POC_COUNTRY,
                "language": POC_LANGUAGE,
                "model": POC_MODEL,
                "occupation": occ,
                "D": m.D,
                "delta": m.delta,
                "weight": m.weight,
                "signed_D": m.signed_D,
            },
        )
    table = pd.DataFrame(rows)
    apd_value = apd(results)
    table.to_csv(OUT, index=False)
    # Persist the scalar APD alongside the per-occupation table.
    (settings.results_tables / "apd_poc_aggregate.csv").write_text(
        f"country,language,model,APD\n{POC_COUNTRY},{POC_LANGUAGE},{POC_MODEL},{apd_value:.6f}\n",
        encoding="utf-8",
    )
    log.info(
        "Wrote %s (%d rows). APD(%s, %s, %s) = %.3f",
        OUT, len(table), POC_COUNTRY, POC_LANGUAGE, POC_MODEL, apd_value,
    )
    log.info("APD = 0 means no directional sedimentation; <0 = model lightens high-status occupations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
