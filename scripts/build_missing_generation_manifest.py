"""Build the master manifest of pending APD image generation.

The manifest is image-level: one row per image_id that is still missing from
the canonical production metadata and any active shard under images/main/.
Cell-level counts (target_n/current_n/missing_n) are repeated on each pending
image row so Kaggle/Colab notebooks can filter by model/language/shard without
needing to reconstruct the scientific grid.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from apd.config import settings  # noqa: E402
from apd.prompts.grid import (  # noqa: E402
    H5_IMAGES_PER_CELL,
    MAIN_IMAGES_PER_CELL,
    MAIN_MODELS,
    ROBUSTNESS_IMAGES_PER_CELL,
    PromptCell,
    h5_cells,
    image_id_of,
    main_cells,
    robustness_cells,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("missing_manifest")

DEFAULT_OUT = PROJECT_ROOT / "results" / "missing_generation_manifest_2026-06-02.csv"
DEFAULT_METADATA_DIR = settings.images_dir / "main"
DEFAULT_N_SHARDS = 4

LOCAL_FLUX_MODEL = "pollinations/flux"
KAGGLE_PRIORITY_MODELS = {
    "runwayml/stable-diffusion-v1-5",
    "stabilityai/stable-diffusion-xl-base-1.0",
    "stabilityai/stable-diffusion-2-1",
    "playgroundai/playground-v2.5-1024px-aesthetic",
    "kandinsky-community/kandinsky-3",
    "BAAI/AltDiffusion-m18",
}
COLAB_PRIORITY_MODELS = {"stabilityai/stable-diffusion-3.5-medium"}


def metadata_paths(metadata_dir: Path) -> list[Path]:
    paths = [metadata_dir / "metadata.parquet"]
    if metadata_dir.exists():
        paths.extend(
            sorted(p for p in metadata_dir.glob("metadata_*.parquet") if p.name != "metadata.parquet")
        )
    return paths


def load_done(metadata_dir: Path) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for path in metadata_paths(metadata_dir):
        if path.exists():
            parts.append(pd.read_parquet(path))
    if not parts:
        return pd.DataFrame(columns=["image_id"])
    df = pd.concat(parts, ignore_index=True)
    if "timestamp" in df.columns:
        return (
            df.sort_values("timestamp", ascending=False, kind="stable")
            .drop_duplicates("image_id", keep="first")
            .reset_index(drop=True)
        )
    return df.drop_duplicates("image_id", keep="last").reset_index(drop=True)


def all_grid_cells() -> list[tuple[str, PromptCell, int]]:
    return (
        [("main", c, MAIN_IMAGES_PER_CELL) for c in main_cells()]
        + [("h5", c, H5_IMAGES_PER_CELL) for c in h5_cells()]
        + [("robustness", c, ROBUSTNESS_IMAGES_PER_CELL) for c in robustness_cells()]
    )


def cell_id(cell: PromptCell) -> str:
    return f"{cell.model}|{cell.language}|{cell.country}|{cell.occupation}"


def prompt_for(cell: PromptCell) -> tuple[str, str]:
    try:
        return cell.prompt(), "ok"
    except Exception as exc:  # noqa: BLE001 - manifest should diagnose unready prompt slices.
        return "", f"unavailable:{type(exc).__name__}:{exc}"


def backend_for(model: str) -> str:
    if model == LOCAL_FLUX_MODEL:
        return "pollinations"
    return "local_diffusers"


def recommended_runner(model: str) -> str:
    if model == LOCAL_FLUX_MODEL:
        return "local"
    if model in KAGGLE_PRIORITY_MODELS:
        return "kaggle"
    if model in COLAB_PRIORITY_MODELS:
        return "colab"
    if model in MAIN_MODELS:
        return "kaggle"
    return "manual"


def stable_group_shard(value: str, n_shards: int) -> int:
    if n_shards <= 1:
        return 0
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return int(digest, 16) % n_shards


def build_manifest(done: pd.DataFrame, *, n_shards: int) -> pd.DataFrame:
    done_ids = set(done["image_id"].astype(str)) if "image_id" in done.columns else set()
    grid_cells = all_grid_cells()
    counts_by_cell: Counter[str] = Counter()
    for _grid, cell, _target_n in grid_cells:
        if image_id_of(cell) in done_ids:
            counts_by_cell[cell_id(cell)] += 1

    rows: list[dict] = []
    for grid, cell, target_n in grid_cells:
        img_id = image_id_of(cell)
        if img_id in done_ids:
            continue
        cid = cell_id(cell)
        current_n = counts_by_cell[cid]
        missing_n = max(target_n - current_n, 0)
        prompt, prompt_status = prompt_for(cell)
        shard_group = f"{grid}|{cell.model}|{cell.language}"
        shard_id = stable_group_shard(img_id, n_shards)
        rows.append(
            {
                "grid": grid,
                "model": cell.model,
                "backend": backend_for(cell.model),
                "language": cell.language,
                "country": cell.country,
                "occupation": cell.occupation,
                "prompt_id": cid,
                "cell_id": cid,
                "image_id": img_id,
                "seed": cell.seed,
                "prompt": prompt,
                "prompt_status": prompt_status,
                "target_n": target_n,
                "current_n": current_n,
                "missing_n": missing_n,
                "shard_group": shard_group,
                "shard_id": shard_id,
                "n_shards": n_shards,
                "recommended_runner": recommended_runner(cell.model),
                "output_metadata_path": f"images/main/metadata_{recommended_runner(cell.model)}_<run_id>.parquet",
                "output_image_dir": "images/main",
            }
        )
    return pd.DataFrame(rows)


def validate_manifest(df: pd.DataFrame) -> None:
    if df.empty:
        return
    duplicated = df["image_id"].duplicated().sum()
    if duplicated:
        raise ValueError(f"manifest has {duplicated} duplicate image_id rows")
    bad_counts = df[(df["missing_n"] <= 0) | (df["current_n"] >= df["target_n"])]
    if not bad_counts.empty:
        raise ValueError(f"manifest contains {len(bad_counts)} rows from completed cells")


def write_summary(df: pd.DataFrame) -> None:
    log.info("pending image rows: %d", len(df))
    if df.empty:
        return
    summary = df.groupby(["grid", "recommended_runner", "model"], dropna=False).size()
    for key, n in summary.items():
        log.info("  %s: %d", key, n)
    unavailable = df[df["prompt_status"] != "ok"]
    if not unavailable.empty:
        log.warning("prompt-unavailable rows: %d", len(unavailable))


def run(*, out: Path, metadata_dir: Path, n_shards: int) -> int:
    done = load_done(metadata_dir)
    manifest = build_manifest(done, n_shards=n_shards)
    validate_manifest(manifest)
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(out, index=False)
    log.info("wrote %s", out)
    write_summary(manifest)
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--metadata-dir", type=Path, default=DEFAULT_METADATA_DIR)
    parser.add_argument("--n-shards", type=int, default=DEFAULT_N_SHARDS)
    args = parser.parse_args(argv)
    return run(out=args.out, metadata_dir=args.metadata_dir, n_shards=args.n_shards)


if __name__ == "__main__":
    sys.exit(main())
