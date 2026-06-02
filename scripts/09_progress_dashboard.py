"""09 — Progress dashboard for the multi-worker APD generation pipeline.

Reads ``images/main/metadata.parquet`` + every ``metadata_*.parquet``
shard in the same directory, and reports:

* completion per grid (main / H5 / robustness) — counts and % done;
* per-(model × language) matrix for the main grid;
* throughput observed over the last 24h, per backend;
* active shards (mtime < 24h);
* ETA at the observed rate for each grid.

This is a read-only diagnostic. It does not mutate metadata, generate
images, or push to the remote. Safe to run during a worker shift.

Usage
-----
    python scripts/09_progress_dashboard.py
    python scripts/09_progress_dashboard.py --out results/progress.md
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import Counter
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from apd.config import settings  # noqa: E402
from apd.prompts.grid import (  # noqa: E402
    MAIN_LANGUAGES,
    MAIN_MODELS,
    expected_h5_grid_size,
    expected_main_grid_size,
    expected_robustness_grid_size,
    h5_cells,
    image_id_of,
    main_cells,
    robustness_cells,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("dashboard")

DEFAULT_METADATA_DIR = settings.images_dir / "main"
DEFAULT_CANONICAL = DEFAULT_METADATA_DIR / "metadata.parquet"
SHARDS_GLOB = "metadata_*.parquet"
H5_GRID_TOTAL = expected_h5_grid_size()
MAIN_GRID_TOTAL = expected_main_grid_size()
ROBUSTNESS_GRID_TOTAL = expected_robustness_grid_size()
GRAND_TOTAL = MAIN_GRID_TOTAL + H5_GRID_TOTAL + ROBUSTNESS_GRID_TOTAL


# -------------------------------------------------------------------------
# Loading
# -------------------------------------------------------------------------


def load_all_metadata(metadata_dir: Path, canonical: Path) -> tuple[pd.DataFrame, list[Path]]:
    """Concatenate canonical + every shard (no dedup — caller's responsibility).

    Returns the merged frame and the list of shard paths.
    """
    parts: list[pd.DataFrame] = []
    shards: list[Path] = []
    if canonical.exists():
        parts.append(pd.read_parquet(canonical))
    if metadata_dir.exists():
        for shard in sorted(metadata_dir.glob(SHARDS_GLOB)):
            if shard.resolve() == canonical.resolve():
                continue
            shards.append(shard)
            parts.append(pd.read_parquet(shard))
    if not parts:
        return pd.DataFrame(), shards
    return pd.concat(parts, ignore_index=True), shards


def grid_image_ids() -> tuple[set[str], set[str], set[str]]:
    """Expected image_ids per grid (main, h5, robustness)."""
    main_ids = {image_id_of(c) for c in main_cells()}
    h5_ids = {image_id_of(c) for c in h5_cells()}
    robust_ids = {image_id_of(c) for c in robustness_cells()}
    return main_ids, h5_ids, robust_ids


# -------------------------------------------------------------------------
# Metric computation
# -------------------------------------------------------------------------


def compute_throughput_last_24h(
    df: pd.DataFrame, now: int | None = None
) -> dict[str, dict[str, float]]:
    """Per-backend throughput in the last 24h.

    Returns a dict ``backend → {imgs: N, imgs_per_min: X, p50_duration_s: Y}``.
    """
    if df.empty or "timestamp" not in df.columns:
        return {}
    now = now if now is not None else int(time.time())
    cutoff = now - 86_400
    recent = df[df["timestamp"] >= cutoff].copy()
    if recent.empty:
        return {}
    out: dict[str, dict[str, float]] = {}
    for backend, group in recent.groupby("backend", dropna=False):
        n = len(group)
        if n == 0:
            continue
        span_s = max(group["timestamp"].max() - group["timestamp"].min(), 1)
        per_min = (n / span_s) * 60.0
        p50_dur = (
            float(group["duration_s"].median())
            if "duration_s" in group.columns and not group["duration_s"].isna().all()
            else float("nan")
        )
        out[str(backend)] = {"imgs": float(n), "imgs_per_min": per_min, "p50_duration_s": p50_dur}
    return out


def per_grid_done(df: pd.DataFrame) -> dict[str, tuple[int, int]]:
    """Map of grid name → (done, total)."""
    main_ids, h5_ids, robust_ids = grid_image_ids()
    done = set(df["image_id"].astype(str)) if not df.empty and "image_id" in df.columns else set()
    return {
        "main": (len(done & main_ids), MAIN_GRID_TOTAL),
        "h5": (len(done & h5_ids), H5_GRID_TOTAL),
        "robustness": (len(done & robust_ids), ROBUSTNESS_GRID_TOTAL),
    }


def per_model_language_main(df: pd.DataFrame) -> pd.DataFrame:
    """Counts of done main-grid cells per (model × language). Each cell
    has up to 30 imgs (``MAIN_IMAGES_PER_CELL``)."""
    main_ids, _, _ = grid_image_ids()
    if df.empty:
        return pd.DataFrame(
            0,
            index=list(MAIN_MODELS),
            columns=list(MAIN_LANGUAGES),
        )
    in_main = df[df["image_id"].astype(str).isin(main_ids)]
    if in_main.empty:
        return pd.DataFrame(
            0,
            index=list(MAIN_MODELS),
            columns=list(MAIN_LANGUAGES),
        )
    return (
        in_main.groupby(["model", "language"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=list(MAIN_MODELS), columns=list(MAIN_LANGUAGES), fill_value=0)
    )


def active_shards(shards: list[Path], now: int | None = None) -> list[tuple[Path, float]]:
    """Shards with mtime in the last 24h, paired with hours-since-mtime."""
    now = now if now is not None else int(time.time())
    cutoff = now - 86_400
    out: list[tuple[Path, float]] = []
    for shard in shards:
        m = shard.stat().st_mtime
        if m >= cutoff:
            out.append((shard, (now - m) / 3600.0))
    return out


def eta_seconds(done: int, total: int, throughput_per_min: float) -> float | None:
    if throughput_per_min <= 0 or done >= total:
        return None
    pending = total - done
    return (pending / throughput_per_min) * 60.0


def fmt_eta(eta_s: float | None) -> str:
    if eta_s is None:
        return "—"
    days = eta_s / 86_400.0
    if days >= 1:
        return f"{days:.1f} d"
    hours = eta_s / 3600.0
    if hours >= 1:
        return f"{hours:.1f} h"
    minutes = eta_s / 60.0
    return f"{minutes:.0f} min"


# -------------------------------------------------------------------------
# Rendering
# -------------------------------------------------------------------------


def render_report(
    *,
    grid_done: dict[str, tuple[int, int]],
    pml: pd.DataFrame,
    throughput: dict[str, dict[str, float]],
    active: list[tuple[Path, float]],
    n_dup_rows: int,
    n_total_rows: int,
    n_unique_ids: int,
    pending_top: list[tuple[str, str, int]],
) -> str:
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f"APD progress  —  {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    lines.append("=" * 72)
    lines.append("")

    # Overall.
    total_done = sum(d for d, _ in grid_done.values())
    pct = 100.0 * total_done / GRAND_TOTAL if GRAND_TOTAL else 0.0
    lines.append(f"GRAND TOTAL : {total_done:>6} / {GRAND_TOTAL:>6}  ({pct:5.1f}%)")
    lines.append(
        f"unique ids  : {n_unique_ids} (rows {n_total_rows}, dup rows in shards {n_dup_rows})"
    )
    lines.append("")

    # Per grid.
    lines.append("By grid:")
    for name, (d, t) in grid_done.items():
        p = 100.0 * d / t if t else 0.0
        # ETA per grid using aggregate throughput across all backends.
        aggregate_per_min = sum(v["imgs_per_min"] for v in throughput.values())
        eta = eta_seconds(d, t, aggregate_per_min)
        lines.append(f"  {name:<11} {d:>6} / {t:>6}  ({p:5.1f}%)   ETA: {fmt_eta(eta)}")
    lines.append("")

    # Main grid model × language matrix.
    if not pml.empty:
        lines.append(
            "Main grid done by model × language (cell cap = 30 imgs per cell × 25 occ = 750):"
        )
        # Column headers
        header = f"{'model':<48}" + "".join(f"{lang:>11}" for lang in pml.columns)
        lines.append(header)
        lines.append("-" * len(header))
        for model_name, row in pml.iterrows():
            row_str = f"{model_name:<48}" + "".join(f"{int(v):>11}" for v in row.values)
            lines.append(row_str)
        lines.append("")

    # Throughput last 24h.
    if throughput:
        lines.append("Throughput last 24h:")
        for backend, stats in sorted(throughput.items()):
            lines.append(
                f"  {backend:<24}  imgs={int(stats['imgs']):>5}   "
                f"{stats['imgs_per_min']:>5.2f} imgs/min   "
                f"p50_wall={stats['p50_duration_s']:>6.1f} s"
            )
    else:
        lines.append("Throughput last 24h: (no rows with timestamp ≥ now-24h)")
    lines.append("")

    # Active shards.
    if active:
        lines.append("Active shards (mtime < 24h):")
        for shard, hrs_ago in sorted(active, key=lambda t: t[1]):
            lines.append(f"  {shard.name}    {hrs_ago:.1f}h ago")
    else:
        lines.append("Active shards (mtime < 24h): none")
    lines.append("")

    # Pending top (by model × language).
    if pending_top:
        lines.append("Pending top 10 (model, language) — cells still to generate:")
        for model_name, lang, n_pending in pending_top:
            lines.append(f"  {model_name:<48} {lang:<10} {n_pending:>5}")
    lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


def compute_pending_top(df: pd.DataFrame, top_n: int = 10) -> list[tuple[str, str, int]]:
    """For the main grid, count how many cells per (model × language) remain
    to be generated. Returns up to ``top_n`` pairs sorted by remaining desc.
    """
    main_ids, _, _ = grid_image_ids()
    done = set(df["image_id"].astype(str)) if not df.empty and "image_id" in df.columns else set()
    pending_by: Counter[tuple[str, str]] = Counter()
    for cell in main_cells():
        if image_id_of(cell) in done:
            continue
        pending_by[(cell.model, cell.language)] += 1
    return [(model_name, lang, n) for (model_name, lang), n in pending_by.most_common(top_n)]


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------


def run(canonical: Path, metadata_dir: Path, out_md: Path | None) -> int:
    df, shards = load_all_metadata(metadata_dir, canonical)
    n_total = len(df)
    if df.empty:
        report = (
            f"APD progress  —  {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}\n"
            f"No metadata found under {metadata_dir}\n"
        )
        print(report)
        if out_md is not None:
            out_md.parent.mkdir(parents=True, exist_ok=True)
            out_md.write_text(report, encoding="utf-8")
        return 0

    # Dedup-as-counted (don't write back — diagnostic only).
    if "image_id" in df.columns and "timestamp" in df.columns:
        df_unique = (
            df.sort_values("timestamp", ascending=False, kind="stable")
            .drop_duplicates(subset=["image_id"], keep="first")
            .reset_index(drop=True)
        )
    else:
        df_unique = df
    n_unique = len(df_unique)
    n_dup = n_total - n_unique

    grid = per_grid_done(df_unique)
    pml = per_model_language_main(df_unique)
    throughput = compute_throughput_last_24h(df_unique)
    active = active_shards(shards)
    pending_top = compute_pending_top(df_unique)

    report = render_report(
        grid_done=grid,
        pml=pml,
        throughput=throughput,
        active=active,
        n_dup_rows=n_dup,
        n_total_rows=n_total,
        n_unique_ids=n_unique,
        pending_top=pending_top,
    )
    print(report)
    if out_md is not None:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(report, encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--metadata-dir", type=Path, default=DEFAULT_METADATA_DIR)
    parser.add_argument(
        "--out", type=Path, default=None, help="Optional path to write the report as markdown."
    )
    args = parser.parse_args(argv)
    return run(args.canonical, args.metadata_dir, args.out)


if __name__ == "__main__":
    sys.exit(main())
