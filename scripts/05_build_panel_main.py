"""05b — Build the production phenotype panel.

Joins images/main/metadata.parquet with data/interim/main_phenotype.parquet
and writes data/processed/panel_main.parquet.
"""

from __future__ import annotations

import logging
import sys

from apd.config import settings
from apd.panel.build import build_panel
from apd.prompts.grid import classify_grid

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("05b_panel_main")

META_IN = settings.images_dir / "main" / "metadata.parquet"
PHENO_IN = settings.data_interim / "main_phenotype.parquet"
OUT = settings.data_processed / "panel_main.parquet"


def main() -> int:
    settings.data_processed.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        log.info("Cached: %s", OUT)
        return 0
    if not META_IN.exists() or not PHENO_IN.exists():
        log.error("Missing inputs: %s or %s", META_IN, PHENO_IN)
        return 1
    panel = build_panel(META_IN, PHENO_IN)
    panel["grid"] = [
        classify_grid(occ, lang, model)
        for occ, lang, model in zip(
            panel["occupation"], panel["language"], panel["model"], strict=True,
        )
    ]
    panel.to_parquet(OUT, index=False)
    log.info(
        "Wrote %s — %d rows, has_face mean=%.2f, grids: %s",
        OUT, len(panel),
        float(panel["has_face"].fillna(False).astype(float).mean()),
        panel["grid"].value_counts().to_dict(),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
