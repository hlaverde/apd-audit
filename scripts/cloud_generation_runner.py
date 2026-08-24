"""Cloud shard runner for Kaggle/Colab APD image generation.

Reads the missing-generation manifest, selects a deterministic slice, generates
images with local diffusers, writes checkpoint shards compatible with
``scripts/merge_worker_shards.py``, and exports a ZIP containing images,
metadata, logs, and a small zero-cost ledger.

This script is intentionally cloud-provider neutral. The notebooks set paths
and parameters; the scientific grid remains defined in ``apd.prompts.grid``.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import shutil
import sys
import time
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from continuous_worker import _classify_png  # noqa: E402

from apd.generate.local_backend import LocalBackend  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cloud_runner")

CLASSIFIER_COLUMNS = {
    "has_face": False,
    "n_faces": 0,
    "ita_value": float("nan"),
    "ita_label": "not_run",
    "ita_perla": float("nan"),
    "mst_value": float("nan"),
    "mst_perla": float("nan"),
    "casco_perla": float("nan"),
    "perla_consensus": float("nan"),
    "n_classifiers": 0,
    "n_concordant": 0,
    "concordant_2of3": False,
}


def stable_shard(image_id: str, n_shards: int) -> int:
    if n_shards <= 1:
        return 0
    digest = hashlib.sha256(image_id.encode("utf-8")).hexdigest()[:16]
    return int(digest, 16) % n_shards


def read_done_ids(paths: Iterable[Path]) -> set[str]:
    done: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path, columns=["image_id"])
        except Exception:
            df = pd.read_csv(path, usecols=["image_id"])
        done.update(df["image_id"].astype(str).tolist())
    return done


def local_metadata_paths(output_dir: Path) -> list[Path]:
    paths = []
    canonical = output_dir / "metadata.parquet"
    if canonical.exists():
        paths.append(canonical)
    paths.extend(sorted(output_dir.glob("metadata_*.parquet")))
    return paths


def normalize_manifest(manifest: pd.DataFrame, *, default_grid: str | None) -> pd.DataFrame:
    df = manifest.copy()
    df.columns = [str(col).strip() for col in df.columns]
    if "grid" not in df.columns:
        if "shard_group" in df.columns:
            df["grid"] = df["shard_group"].astype(str).str.split("|", n=1).str[0]
        elif default_grid:
            df["grid"] = default_grid
    required = {
        "model",
        "language",
        "grid",
        "recommended_runner",
        "prompt_status",
        "image_id",
        "occupation",
        "seed",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise RuntimeError(
            "Manifest is missing required columns "
            f"{missing}; available columns are {list(df.columns)}"
        )
    return df


def select_rows(
    manifest: pd.DataFrame,
    *,
    model: str,
    language: str,
    shard_id: int,
    n_shards: int,
    max_images: int,
    grid: str | None,
    recommended_runner_filter: str | None,
    done_ids: set[str],
) -> pd.DataFrame:
    df = normalize_manifest(manifest, default_grid=grid)
    df = df[(df["model"] == model) & (df["language"] == language)]
    if grid:
        df = df[df["grid"] == grid]
    if recommended_runner_filter:
        df = df[df["recommended_runner"] == recommended_runner_filter]
    df = df[df["prompt_status"] == "ok"]
    df = df[~df["image_id"].astype(str).isin(done_ids)]
    df = df[df["image_id"].astype(str).map(lambda x: stable_shard(x, n_shards) == shard_id)]
    df = df.sort_values(["grid", "occupation", "seed"], kind="stable")
    if max_images > 0:
        df = df.head(max_images)
    return df.reset_index(drop=True)


def image_path_for(row: pd.Series, output_dir: Path) -> Path:
    occ = str(row["occupation"]).replace(" ", "_")
    return output_dir / occ / f"seed_{int(row['seed'])}.png"


def metadata_row(
    row: pd.Series,
    png_path: Path,
    sha256: str,
    backend: str,
    duration_s: float,
    model_source: str | None = None,
) -> dict:
    return {
        "image_id": row["image_id"],
        "model": row["model"],
        "model_source": model_source or row["model"],
        "occupation": row["occupation"],
        "language": row["language"],
        "country_proxy": row["country"],
        "seed": int(row["seed"]),
        "prompt": row["prompt"],
        "path": str(png_path),
        "sha256": sha256,
        "backend": backend,
        "duration_s": float(duration_s),
        "timestamp": int(time.time()),
    }


def flush(records: list[dict], shard_path: Path) -> None:
    if not records:
        return
    shard_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = shard_path.with_suffix(".parquet.tmp")
    pd.DataFrame(records).to_parquet(tmp, index=False)
    tmp.replace(shard_path)
    log.info("checkpoint wrote %s (%d rows)", shard_path, len(records))


def write_cost_log(path: Path, *, runner: str, n_images: int, elapsed_s: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    line = (
        f"| {stamp} | shift {runner} cloud shard | {runner} free | "
        f"{n_images} imgs / {elapsed_s:.0f}s | $0.00 | **$0.00** |\n"
    )
    path.write_text(line, encoding="utf-8")


def make_zip(output_root: Path, zip_base: Path) -> Path:
    zip_base.parent.mkdir(parents=True, exist_ok=True)
    archive = shutil.make_archive(str(zip_base), "zip", root_dir=output_root)
    return Path(archive)


def run(args: argparse.Namespace) -> int:
    started = time.time()
    manifest = pd.read_csv(args.manifest)
    output_root = args.output_root.resolve()
    images_dir = output_root / "images" / "main"
    run_dir = output_root / "runs" / args.run_id
    shard_path = images_dir / f"metadata_{args.runner}_{args.run_id}.parquet"
    cost_path = run_dir / "COST_LOG_SHARD.md"
    log_path = run_dir / "run.log"
    run_dir.mkdir(parents=True, exist_ok=True)

    done_ids = read_done_ids([Path(args.existing_metadata), *local_metadata_paths(images_dir)])
    selected = select_rows(
        manifest,
        model=args.model,
        language=args.language,
        shard_id=args.shard_id,
        n_shards=args.n_shards,
        max_images=args.max_images_per_run,
        grid=args.grid,
        recommended_runner_filter=args.recommended_runner_filter,
        done_ids=done_ids,
    )
    log.info("selected %d rows for %s %s shard %d/%d", len(selected), args.model, args.language, args.shard_id, args.n_shards)
    if selected.empty:
        write_cost_log(cost_path, runner=args.runner, n_images=0, elapsed_s=time.time() - started)
        if not args.skip_zip:
            make_zip(output_root, run_dir / f"apd_{args.runner}_{args.run_id}")
        return 0

    records: list[dict] = []
    existing_records: list[dict] = []
    if shard_path.exists():
        existing_records = pd.read_parquet(shard_path).to_dict("records")
        records.extend(existing_records)

    backend = None
    if not args.dry_run:
        backend = LocalBackend(args.model)

    for i, row in selected.iterrows():
        png_path = image_path_for(row, images_dir)
        png_path.parent.mkdir(parents=True, exist_ok=True)
        if png_path.exists() and str(row["image_id"]) in {str(r["image_id"]) for r in records}:
            log.info("[%d/%d] cached metadata+png: %s", i + 1, len(selected), row["image_id"])
            continue
        log.info("[%d/%d] generating %s", i + 1, len(selected), row["image_id"])
        if args.dry_run:
            png_path.write_bytes(b"dry-run-placeholder")
            sha = hashlib.sha256(png_path.read_bytes()).hexdigest()
            rec = metadata_row(row, png_path, sha, "dry_run", 0.0)
        else:
            assert backend is not None
            result = backend.generate(str(row["prompt"]), int(row["seed"]))
            png_path.write_bytes(result.image_bytes)
            rec = metadata_row(
                row,
                png_path,
                result.sha256,
                result.backend,
                result.duration_s,
                backend.model_source,
            )

        if args.classify and not args.dry_run:
            try:
                rec.update(_classify_png(png_path))
            except Exception as exc:  # noqa: BLE001 - keep image metadata even if classifier stack fails.
                log.warning("classification failed for %s: %s", row["image_id"], exc)
                rec.update(CLASSIFIER_COLUMNS)
                rec["ita_label"] = "classification_error"
        else:
            rec.update(CLASSIFIER_COLUMNS)
        records.append(rec)
        if len(records) % args.checkpoint_every == 0:
            flush(records, shard_path)

    flush(records, shard_path)
    elapsed = time.time() - started
    write_cost_log(cost_path, runner=args.runner, n_images=len(records) - len(existing_records), elapsed_s=elapsed)
    log_path.write_text(
        "\n".join(
            [
                f"run_id={args.run_id}",
                f"runner={args.runner}",
                f"recommended_runner_filter={args.recommended_runner_filter}",
                f"model={args.model}",
                f"language={args.language}",
                f"shard={args.shard_id}/{args.n_shards}",
                f"rows_selected={len(selected)}",
                f"rows_written={len(records)}",
                f"elapsed_s={elapsed:.1f}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if args.skip_zip:
        log.info("skip internal zip requested; output_root remains unpacked for caller packaging")
    else:
        zip_path = make_zip(output_root, run_dir / f"apd_{args.runner}_{args.run_id}")
        log.info("zip ready: %s", zip_path)
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--existing-metadata", type=Path, default=Path("images/main/metadata.parquet"))
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--runner", choices=["kaggle", "colab"], required=True)
    parser.add_argument("--recommended-runner-filter", choices=["kaggle", "colab"], default=None)
    parser.add_argument("--run-id", default=time.strftime("%Y%m%d_%H%M%S", time.gmtime()))
    parser.add_argument("--model", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--grid", default="main")
    parser.add_argument("--shard-id", type=int, required=True)
    parser.add_argument("--n-shards", type=int, required=True)
    parser.add_argument("--max-images-per-run", type=int, default=50)
    parser.add_argument("--checkpoint-every", type=int, default=5)
    parser.add_argument("--classify", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skip-zip", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not (0 <= args.shard_id < args.n_shards):
        raise SystemExit(f"invalid shard {args.shard_id}/{args.n_shards}")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
