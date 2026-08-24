"""Import a Kaggle/Colab APD generation ZIP into the local repository.

The importer copies cloud-generated PNGs and metadata shards into
``images/main/``, archives run logs under ``results/cloud_runs/<zip_stem>/``,
invokes the same merge logic used by ``merge_worker_shards.py``, then runs the
dashboard and preflight checks.

It never deletes the original ZIP and never commits changes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MERGE_SCRIPT = PROJECT_ROOT / "scripts" / "merge_worker_shards.py"


@dataclass
class ImportSummary:
    zip_path: str
    extract_dir: str
    rows_before: int
    shard_rows: int
    rows_after: int
    duplicates_after: int
    images_copied: int
    images_skipped_existing: int
    metadata_copied: int
    runs_copied: int
    merge_returncode: int
    dashboard_returncode: int | None
    preflight_returncode: int | None


def load_merge_module():
    spec = importlib.util.spec_from_file_location("merge_worker_shards", MERGE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {MERGE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["merge_worker_shards"] = module
    spec.loader.exec_module(module)
    return module


def safe_extract(zip_path: Path, extract_dir: Path) -> None:
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = PurePosixPath(info.filename)
            if info.filename.startswith("/") or ".." in name.parts:
                raise ValueError(f"unsafe ZIP member path: {info.filename!r}")
        zf.extractall(extract_dir)


def find_payload_root(extract_dir: Path) -> Path:
    candidates: list[Path] = []
    for path in [extract_dir, *extract_dir.rglob("*")]:
        if not path.is_dir():
            continue
        images_main = path / "images" / "main"
        if images_main.exists() and list(images_main.glob("metadata_*.parquet")):
            candidates.append(path)
    if not candidates:
        raise FileNotFoundError(
            f"no payload root with images/main/metadata_*.parquet under {extract_dir}"
        )
    return min(candidates, key=lambda p: len(p.parts))


def count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return len(pd.read_parquet(path))


def unique_dest(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    for i in range(1, 10_000):
        candidate = dest.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find unique destination for {dest}")


def copy_metadata(metadata_files: list[Path], images_dest: Path, zip_stem: str) -> tuple[int, int]:
    copied = 0
    rows = 0
    images_dest.mkdir(parents=True, exist_ok=True)
    for src in metadata_files:
        rows += count_rows(src)
        dest_name = src.name
        if not dest_name.startswith("metadata_"):
            dest_name = f"metadata_{dest_name}"
        dest = images_dest / dest_name
        if dest.exists() and dest.read_bytes() != src.read_bytes():
            dest = unique_dest(images_dest / f"metadata_{zip_stem}_{src.name}")
        if dest.exists() and dest.read_bytes() == src.read_bytes():
            continue
        shutil.copy2(src, dest)
        copied += 1
    return copied, rows


def copy_images(images_src: Path, images_dest: Path) -> tuple[int, int]:
    copied = 0
    skipped = 0
    for src in images_src.rglob("*"):
        if not src.is_file() or src.name.startswith("metadata_"):
            continue
        if src.suffix.lower() == ".parquet":
            continue
        rel = src.relative_to(images_src)
        dest = images_dest / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            skipped += 1
            continue
        shutil.copy2(src, dest)
        copied += 1
    return copied, skipped


def copy_runs(payload_root: Path, runs_dest: Path) -> int:
    runs_src = payload_root / "runs"
    if not runs_src.exists():
        return 0
    if runs_dest.exists():
        shutil.rmtree(runs_dest)
    shutil.copytree(runs_src, runs_dest)
    return sum(1 for p in runs_dest.rglob("*") if p.is_file())


def run_subprocess(args: list[str], cwd: Path) -> int:
    completed = subprocess.run(args, cwd=cwd, text=True)
    return int(completed.returncode)


def import_zip(
    zip_path: Path,
    *,
    project_root: Path = PROJECT_ROOT,
    inbox_dir: Path | None = None,
    run_dashboard: bool = True,
    run_preflight: bool = True,
) -> ImportSummary:
    zip_path = zip_path.resolve()
    project_root = project_root.resolve()
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)
    if zip_path.suffix.lower() != ".zip":
        raise ValueError(f"expected a .zip file, got {zip_path}")

    inbox_dir = (inbox_dir or (project_root / "cloud_inbox")).resolve()
    extract_dir = inbox_dir / zip_path.stem
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    safe_extract(zip_path, extract_dir)

    payload_root = find_payload_root(extract_dir)
    images_src = payload_root / "images" / "main"
    metadata_files = sorted(images_src.glob("metadata_*.parquet"))
    if not metadata_files:
        raise FileNotFoundError(f"no metadata_*.parquet under {images_src}")

    images_dest = project_root / "images" / "main"
    canonical = images_dest / "metadata.parquet"
    rows_before = count_rows(canonical)
    metadata_copied, shard_rows = copy_metadata(metadata_files, images_dest, zip_path.stem)
    images_copied, images_skipped = copy_images(images_src, images_dest)
    runs_copied = copy_runs(payload_root, project_root / "results" / "cloud_runs" / zip_path.stem)

    merge_mod = load_merge_module()
    merge_rc = merge_mod.run(
        canonical=canonical,
        shards_dir=images_dest,
        shards_pattern="metadata_*.parquet",
        archive_dir=images_dest / "archived_shards",
        dry_run=False,
        keep_shards=False,
    )

    rows_after = count_rows(canonical)
    after = pd.read_parquet(canonical) if canonical.exists() else pd.DataFrame()
    duplicates_after = (
        int(len(after) - after["image_id"].nunique()) if "image_id" in after.columns else 0
    )
    if duplicates_after:
        raise ValueError(f"metadata has {duplicates_after} duplicate image_id rows after merge")

    dashboard_rc = None
    if run_dashboard:
        dashboard_rc = run_subprocess(
            [sys.executable, str(project_root / "scripts" / "09_progress_dashboard.py")],
            project_root,
        )
    preflight_rc = None
    if run_preflight:
        preflight_rc = run_subprocess(
            [sys.executable, str(project_root / "scripts" / "00_preflight.py")],
            project_root,
        )

    return ImportSummary(
        zip_path=str(zip_path),
        extract_dir=str(extract_dir),
        rows_before=rows_before,
        shard_rows=shard_rows,
        rows_after=rows_after,
        duplicates_after=duplicates_after,
        images_copied=images_copied,
        images_skipped_existing=images_skipped,
        metadata_copied=metadata_copied,
        runs_copied=runs_copied,
        merge_returncode=int(merge_rc),
        dashboard_returncode=dashboard_rc,
        preflight_returncode=preflight_rc,
    )


def print_summary(summary: ImportSummary) -> None:
    print("\n============== CLOUD ZIP IMPORT SUMMARY ==============")
    for key, value in asdict(summary).items():
        print(f"{key}: {value}")
    print("======================================================")
    print(json.dumps(asdict(summary), indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--inbox-dir", type=Path, default=None)
    parser.add_argument("--skip-dashboard", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    args = parser.parse_args(argv)

    summary = import_zip(
        args.zip_path,
        project_root=args.project_root,
        inbox_dir=args.inbox_dir,
        run_dashboard=not args.skip_dashboard,
        run_preflight=not args.skip_preflight,
    )
    print_summary(summary)
    if summary.merge_returncode != 0:
        return summary.merge_returncode
    if summary.dashboard_returncode not in (None, 0):
        return int(summary.dashboard_returncode)
    if summary.preflight_returncode not in (None, 0):
        return int(summary.preflight_returncode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
