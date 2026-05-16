"""Merge worker metadata shards into the canonical ``metadata.parquet``.

Workers across the 3-layer automation (GH Actions Layer 1, local async
Layer 2, Kaggle scheduled Layer 3) each write their own shard to
``images/main/metadata_<source>_<timestamp>.parquet``. This script
consolidates them into ``images/main/metadata.parquet``:

1. Glob every shard plus the canonical file.
2. Concatenate. Order rows by ``timestamp`` descending so the most
   recent row for any duplicated ``image_id`` is kept.
3. Drop duplicates on ``image_id`` (last-write-wins).
4. Validate: every ``image_id`` corresponds to exactly one
   ``(model, occupation, seed)`` tuple, and exactly one row remains
   per id.
5. Write atomically (tmp + rename) back to the canonical path.

The script is idempotent: running it twice produces byte-identical
output (modulo timestamp tie-breaking, which is deterministic given
the same input shards).

Usage
-----
    python scripts/merge_worker_shards.py                # default paths
    python scripts/merge_worker_shards.py --dry-run      # no write
    python scripts/merge_worker_shards.py --keep-shards  # don't archive
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from apd.config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("merge_shards")

DEFAULT_CANONICAL = settings.images_dir / "main" / "metadata.parquet"
DEFAULT_SHARDS_DIR = settings.images_dir / "main"
DEFAULT_SHARDS_GLOB = "metadata_*.parquet"
DEFAULT_ARCHIVE = settings.images_dir / "main" / "archived_shards"


def discover_shards(shards_dir: Path, pattern: str, canonical: Path) -> list[Path]:
    """Return every parquet matching ``pattern`` except the canonical file."""
    if not shards_dir.exists():
        return []
    shards = sorted(p for p in shards_dir.glob(pattern) if p.resolve() != canonical.resolve())
    return shards


def load_inputs(canonical: Path, shards: list[Path]) -> tuple[pd.DataFrame, int]:
    """Concat canonical (if exists) + every shard. Return (df, total_rows)."""
    parts: list[pd.DataFrame] = []
    if canonical.exists():
        df_canonical = pd.read_parquet(canonical)
        df_canonical["_source"] = "canonical"
        parts.append(df_canonical)
        log.info("  canonical: %d rows", len(df_canonical))
    for shard in shards:
        df_shard = pd.read_parquet(shard)
        df_shard["_source"] = shard.name
        parts.append(df_shard)
        log.info("  shard %s: %d rows", shard.name, len(df_shard))
    if not parts:
        return pd.DataFrame(), 0
    df = pd.concat(parts, ignore_index=True)
    return df, len(df)


def dedup(
    df: pd.DataFrame, key: str = "image_id", order_col: str = "timestamp"
) -> tuple[pd.DataFrame, int]:
    """Keep the highest-``order_col`` row per ``key``. Returns (df_dedup, n_dropped)."""
    if df.empty:
        return df, 0
    if key not in df.columns:
        raise KeyError(f"key column {key!r} missing from shards")
    n_before = len(df)
    # Order descending by order_col so head(1) per group is the latest.
    if order_col not in df.columns:
        log.warning(
            "order column %r missing — falling back to position-based dedup",
            order_col,
        )
        df_dedup = df.drop_duplicates(subset=[key], keep="last").reset_index(drop=True)
    else:
        # Stable sort: equal timestamps fall back to insertion order.
        df_sorted = df.sort_values(by=[order_col], ascending=False, kind="stable")
        df_dedup = df_sorted.drop_duplicates(subset=[key], keep="first").reset_index(drop=True)
    n_after = len(df_dedup)
    return df_dedup, n_before - n_after


def validate(df: pd.DataFrame) -> None:
    """Sanity-check the merged frame; raise if invariants are violated."""
    if df.empty:
        return
    n_unique = df["image_id"].nunique()
    if n_unique != len(df):
        raise ValueError(f"dedup failed: {len(df)} rows but only {n_unique} unique image_ids")
    # image_id ↔ (model, occupation, seed) injectivity.
    if {"model", "occupation", "seed"}.issubset(df.columns):
        triples = df.groupby("image_id")[["model", "occupation", "seed"]].nunique()
        bad = triples[(triples > 1).any(axis=1)]
        if not bad.empty:
            raise ValueError(
                f"image_id ambiguity: {len(bad)} ids map to multiple (model, occupation, seed) tuples"
            )


def atomic_write(df: pd.DataFrame, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(dest)


def archive_shards(shards: list[Path], archive_dir: Path) -> int:
    """Move shards to ``archive_dir`` so the next merge run doesn't see them."""
    if not shards:
        return 0
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    moved = 0
    for shard in shards:
        dest = archive_dir / f"{stamp}__{shard.name}"
        shard.rename(dest)
        moved += 1
    return moved


def run(
    *,
    canonical: Path,
    shards_dir: Path,
    shards_pattern: str,
    archive_dir: Path,
    dry_run: bool,
    keep_shards: bool,
) -> int:
    log.info("inputs:")
    shards = discover_shards(shards_dir, shards_pattern, canonical)
    df, total_rows = load_inputs(canonical, shards)
    if df.empty:
        log.info("nothing to merge — exiting cleanly")
        return 0
    df = df.drop(columns=["_source"], errors="ignore")  # diagnostic-only column
    df_dedup, n_dropped = dedup(df)
    validate(df_dedup)
    n_unique = len(df_dedup)
    log.info(
        "merged %d rows from canonical+%d shards → %d unique image_ids (deduped %d)",
        total_rows,
        len(shards),
        n_unique,
        n_dropped,
    )
    if dry_run:
        log.info("--dry-run set: not writing %s", canonical)
        return 0
    atomic_write(df_dedup, canonical)
    log.info("wrote %s (%d rows)", canonical, n_unique)
    if shards and not keep_shards:
        moved = archive_shards(shards, archive_dir)
        log.info("archived %d shards to %s", moved, archive_dir)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--shards-dir", type=Path, default=DEFAULT_SHARDS_DIR)
    parser.add_argument("--shards-pattern", default=DEFAULT_SHARDS_GLOB)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would change without writing"
    )
    parser.add_argument(
        "--keep-shards",
        action="store_true",
        help="don't move shards to the archive directory after a successful merge",
    )
    args = parser.parse_args(argv)
    return run(
        canonical=args.canonical,
        shards_dir=args.shards_dir,
        shards_pattern=args.shards_pattern,
        archive_dir=args.archive_dir,
        dry_run=args.dry_run,
        keep_shards=args.keep_shards,
    )


if __name__ == "__main__":
    sys.exit(main())
