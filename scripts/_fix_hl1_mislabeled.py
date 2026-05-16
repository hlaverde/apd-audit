"""One-shot fix: delete the 20 mislabelled SD-1.5 rows from hl#1 shift.

The 2026-05-15 production shift (commit ``d956c3e``) iterated
``main_cells()`` in order and crossed the model boundary from
``pollinations/flux`` into ``runwayml/stable-diffusion-v1-5``. The
old ``select_backend`` silently routed those SD-1.5 cells through
``PollinationsBackend(model="flux")`` (no HF_TOKEN, no ml extras), so
the 20 cells in question were generated as FLUX images but stored with
``model="runwayml/stable-diffusion-v1-5"``. See D-029 (post-mortem) and
D-030 (this cleanup) in ``docs/DECISIONS.md``.

Removing those 20 rows is required so that ``pending_cells`` does not
treat them as "done" — otherwise Layer 3 (Kaggle scheduled, local
``diffusers``) would never regenerate them as real SD-1.5 images, and
the SD-1.5 × CEO × en cell would be permanently missing from the
production grid.

The script is idempotent: running it on already-cleaned metadata is a
no-op.

Run
---
    python scripts/_fix_hl1_mislabeled.py            # write
    python scripts/_fix_hl1_mislabeled.py --dry-run  # report only
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from apd.config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("fix_hl1")

# Pre-conditions used to recognise the bug imprint. A row is "mislabelled"
# iff BOTH conditions hold:
#   model == "runwayml/stable-diffusion-v1-5" AND backend == "pollinations"
# (because no legitimate SD-1.5 row should ever carry backend="pollinations"
# — pollinations only serves FLUX/Turbo/etc.).
MISLABEL_MODEL = "runwayml/stable-diffusion-v1-5"
MISLABEL_BACKEND = "pollinations"


def find_mislabeled(df: pd.DataFrame) -> pd.Series:
    """Return a boolean mask of rows matching the hl#1 mislabel imprint."""
    return (df["model"] == MISLABEL_MODEL) & (df["backend"] == MISLABEL_BACKEND)


def run(metadata: Path, dry_run: bool) -> int:
    if not metadata.exists():
        log.error("metadata not found: %s", metadata)
        return 2
    df = pd.read_parquet(metadata)
    n_before = len(df)
    mask = find_mislabeled(df)
    n_to_drop = int(mask.sum())
    log.info("read %s: %d rows total, %d mislabelled", metadata, n_before, n_to_drop)
    if n_to_drop == 0:
        log.info("nothing to fix — metadata already clean")
        return 0
    df_clean = df.loc[~mask].reset_index(drop=True)
    log.info(
        "would drop %d rows (model=%s & backend=%s); keeping %d",
        n_to_drop,
        MISLABEL_MODEL,
        MISLABEL_BACKEND,
        len(df_clean),
    )
    if dry_run:
        log.info("--dry-run: not writing")
        return 0
    tmp = metadata.with_suffix(metadata.suffix + ".tmp")
    df_clean.to_parquet(tmp, index=False)
    tmp.replace(metadata)
    log.info("wrote %s (%d rows)", metadata, len(df_clean))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--metadata",
        type=Path,
        default=settings.images_dir / "main" / "metadata.parquet",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return run(args.metadata, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
