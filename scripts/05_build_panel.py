"""05 — Build the phenotype panel → data/processed/panel_poc.parquet."""

from __future__ import annotations

import logging
import sys

from apd.config import settings
from apd.panel.build import build_panel

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("05_panel")

META_IN = settings.images_dir / "poc" / "metadata.parquet"
PHENO_IN = settings.data_interim / "poc_phenotype.parquet"
OUT = settings.data_processed / "panel_poc.parquet"


def main() -> int:
    settings.data_processed.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        log.info("Cached: %s", OUT)
        return 0
    if not META_IN.exists() or not PHENO_IN.exists():
        log.error("Missing inputs: %s or %s", META_IN, PHENO_IN)
        return 1

    panel = build_panel(META_IN, PHENO_IN)
    panel.to_parquet(OUT, index=False)
    log.info(
        "Wrote %s — %d rows, has_face mean=%.2f",
        OUT, len(panel),
        float(panel["has_face"].fillna(False).astype(float).mean()),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
