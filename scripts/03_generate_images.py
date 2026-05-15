"""03 — Generate 30 SD 1.5 images via HF free Inference API → images/poc/."""

from __future__ import annotations

import logging
import sys
import time

import pandas as pd

from apd.config import settings
from apd.generate.orchestrator import generate_poc
from apd.prompts.grid import poc_cells

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("03_generate")

OUT_DIR = settings.images_dir / "poc"
META_OUT = OUT_DIR / "metadata.parquet"
COST_LOG = settings.project_root / "docs" / "COST_LOG.md"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if META_OUT.exists():
        # Validate the cache: every image referenced must exist on disk.
        cached = pd.read_parquet(META_OUT)
        missing = [row for _, row in cached.iterrows() if not (OUT_DIR / row["path"]).exists()]
        if not missing and len(cached) == len(list(poc_cells())):
            log.info("Cached: %s (%d images)", META_OUT, len(cached))
            return 0
        log.info("Cache exists but is partial — regenerating missing images.")

    started = time.time()
    cells = list(poc_cells())
    log.info("POC grid: %d cells", len(cells))

    df = generate_poc(cells, out_dir=OUT_DIR)
    df.to_parquet(META_OUT, index=False)
    elapsed = time.time() - started

    log.info("Wrote %s (%d rows) in %.1fs", META_OUT, len(df), elapsed)
    _append_cost_log(n_images=len(df), elapsed_s=elapsed, backend=df["backend"].iloc[0])
    return 0


def _append_cost_log(*, n_images: int, elapsed_s: float, backend: str) -> None:
    line = (
        f"| {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} | generate POC | "
        f"{backend} free | {n_images} imgs / {elapsed_s:.0f}s | $0.00 | **$0.00** |\n"
    )
    try:
        with COST_LOG.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        log.warning("Could not append to %s: %s", COST_LOG, exc)


if __name__ == "__main__":
    sys.exit(main())
