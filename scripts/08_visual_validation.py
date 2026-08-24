"""08 — Stratified visual-validation sampling.

Reads the production panel (``data/processed/panel_main.parquet`` when
present, else the POC ``panel_poc.parquet``) and emits a labelling
parquet under ``results/validation/labelling.parquet`` for CL and YP to
fill in offline. Once both columns are populated the second pass of
this script (with ``--analyse``) computes Cohen's κ and compares both
raters against the algorithmic 2-of-3 consensus.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from apd.config import settings
from apd.validate.agreement import cohens_kappa, compare_to_consensus
from apd.validate.sampling import StratificationPlan, sample_for_validation

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("08_validation")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PANEL_MAIN = settings.data_processed / "panel_main.parquet"
PANEL_POC = settings.data_processed / "panel_poc.parquet"
OUT_DIR = settings.results_tables.parent / "validation"
LABELLING_OUT = OUT_DIR / "labelling.parquet"


def _eligible_for_labelling(panel: pd.DataFrame) -> pd.DataFrame:
    """Drop rows a human cannot actually label.

    Two exclusions, both required for the sample to mean what the
    protocol says it means:

    * rows outside the main grid — the H5 rows carry synthetic
      ``marker:<MARKER>:<occupation>`` keys, which would turn 25
      occupation strata into 57 and put marker variants in a sample
      meant to validate the classifier on the main grid;
    * rows whose PNG is no longer on disk (D-036) — 110 of them, which
      would otherwise appear in the labelling sheet as broken images.
    """
    out = panel
    if "grid" in out.columns:
        out = out[out["grid"] == "main"]
    exists = [
        (Path(p) if Path(p).is_absolute() else PROJECT_ROOT / p).exists()
        for p in out["path"]
    ]
    n_missing = len(exists) - sum(exists)
    if n_missing:
        log.info("Excluding %d rows whose PNG is not on disk (D-036).", n_missing)
    return out[exists]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--n-per-occupation", type=int, default=12,
        help="Sample size per occupation stratum (default 12 → ~300 total for the main grid).",
    )
    parser.add_argument(
        "--seed", type=int, default=settings.seed,
        help="RNG seed for the stratified sample.",
    )
    parser.add_argument(
        "--analyse", action="store_true",
        help="Skip sampling; read the existing labelling.parquet and report agreement.",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.analyse:
        return _analyse_labels()

    panel_path = PANEL_MAIN if PANEL_MAIN.exists() else PANEL_POC
    if not panel_path.exists():
        log.error(
            "No panel found at %s or %s. Run the pipeline up to make panel first.",
            PANEL_MAIN, PANEL_POC,
        )
        return 1

    panel = pd.read_parquet(panel_path)
    log.info("Sampling for validation from %s (%d rows)", panel_path.name, len(panel))
    eligible = _eligible_for_labelling(panel)
    log.info("%d rows eligible for labelling.", len(eligible))
    plan = StratificationPlan(n_per_occupation=args.n_per_occupation, seed=args.seed)
    labelling = sample_for_validation(eligible, plan)
    labelling.to_parquet(LABELLING_OUT, index=False)
    log.info(
        "Wrote %s — %d rows across %d occupations. "
        "Hand to CL and YP to fill cl_perla / yp_perla columns.",
        LABELLING_OUT, len(labelling), labelling["occupation"].nunique(),
    )
    return 0


def _analyse_labels() -> int:
    if not LABELLING_OUT.exists():
        log.error("No labelling.parquet at %s — run without --analyse first.", LABELLING_OUT)
        return 1
    labels = pd.read_parquet(LABELLING_OUT)

    kappa_human = cohens_kappa(labels["cl_perla"], labels["yp_perla"])
    log.info("Cohen's κ_linear (CL ⟷ YP) = %.3f over n=%d images.",
             kappa_human.value, kappa_human.n)
    if kappa_human.note:
        log.warning("  note: %s", kappa_human.note)

    # If the panel carries the algorithmic 2-of-3 consensus, compare both
    # human raters against it.
    panel_path = PANEL_MAIN if PANEL_MAIN.exists() else PANEL_POC
    if panel_path.exists():
        panel = pd.read_parquet(panel_path)
        joined = labels.merge(
            panel[["image_id", "perla_consensus"]],
            on="image_id", how="left",
        )
        for rater in ("cl_perla", "yp_perla"):
            res = compare_to_consensus(joined[rater], joined["perla_consensus"])
            log.info(
                "Cohen's κ_linear (%s ⟷ algorithmic) = %.3f over n=%d.",
                rater, res.value, res.n,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
