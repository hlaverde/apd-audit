"""02 — Build f_emp(t|o, c=CO) + status weights → data/processed/ground_truth_poc.parquet."""

from __future__ import annotations

import logging
import sys

from apd.config import settings
from apd.ground_truth.build import build_poc_ground_truth

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("02_ground_truth")

OUT = settings.data_processed / "ground_truth_poc.parquet"


def main() -> int:
    settings.data_processed.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        log.info("Cached: %s", OUT)
        return 0
    panel = build_poc_ground_truth()
    panel.to_parquet(OUT, index=False)
    log.info(
        "Wrote %s (%d rows, %d occupations, synthetic=%s)",
        OUT, len(panel),
        panel["occupation"].nunique(),
        bool(panel["is_synthetic"].any()),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
