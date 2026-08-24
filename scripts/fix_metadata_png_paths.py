"""One-off repair: rewrite stale ``path`` strings in images/main/metadata.parquet.

Context (docs/PROJECT_STATUS.md section 4, docs/DECISIONS.md D-036):
rows generated on Kaggle/Colab record ``path`` as the cloud runtime's
absolute path (e.g. ``/kaggle/working/<run>/images/main/<occ>/seed_<seed>.png``).
After importing the run's ZIP locally, the PNG lives at the project's
canonical layout (``images/main/<occ>/seed_<seed>.png``) but the
``path`` column was never rewritten to match. This left 11 290/14 720
rows (77%) pointing at a file that doesn't exist on this machine, even
though 11 180 of those PNGs are sitting right there under the
canonical path.

This script is idempotent and non-destructive:
* For every row whose registered ``path`` doesn't exist, check the
  canonical ``images/main/<occ>/seed_<seed>.png`` path.
* If the canonical file exists: rewrite ``path`` to it (relative,
  forward-slash, matching how every *other* row in the table already
  stores its path).
* If neither the registered nor the canonical path exists: leave the
  row untouched and report it as a genuine gap (currently 110 rows,
  all ``runwayml/stable-diffusion-v1-5`` / ``backend=local`` / seeds
  from the 2026-05-14 bootstrap run).

Run: ``uv run python scripts/fix_metadata_png_paths.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd

from apd.config import settings

INVALID_PATH_CHARS = '<>:"/\\|?*'
_TRANSLATION = str.maketrans({c: "_" for c in INVALID_PATH_CHARS})


def safe_occupation_dirname(occupation: str) -> str:
    safe = str(occupation).translate(_TRANSLATION).replace(" ", "_").rstrip(". ")
    return safe or "_"


def canonical_path(row: pd.Series) -> Path:
    occ_dir = safe_occupation_dirname(row["occupation"])
    return settings.images_dir / "main" / occ_dir / f"seed_{row['seed']}.png"


def main() -> int:
    meta_path = settings.images_dir / "main" / "metadata.parquet"
    df = pd.read_parquet(meta_path)

    registered_exists = df["path"].apply(lambda p: Path(str(p)).exists())
    missing = df[~registered_exists].copy()
    print(f"total rows: {len(df)}")
    print(f"rows with a broken registered path: {len(missing)}")

    if missing.empty:
        print("nothing to fix")
        return 0

    missing["canonical"] = missing.apply(canonical_path, axis=1)
    canonical_exists = missing["canonical"].apply(lambda p: p.exists())
    fixable = missing[canonical_exists]
    orphaned = missing[~canonical_exists]

    print(f"fixable (canonical PNG found on disk): {len(fixable)}")
    print(f"genuinely orphaned (no PNG anywhere found): {len(orphaned)}")

    if not fixable.empty:
        # Store relative, forward-slash paths -- matches the convention
        # every already-correct row in this table already uses.
        project_root = settings.project_root
        rel_paths = fixable["canonical"].apply(
            lambda p: p.relative_to(project_root).as_posix(),
        )
        df.loc[fixable.index, "path"] = rel_paths
        df.to_parquet(meta_path, index=False)
        print(f"rewrote {len(fixable)} path values in {meta_path}")

    if not orphaned.empty:
        report_path = settings.project_root / "results" / "orphaned_png_rows.csv"
        orphaned.drop(columns=["canonical"]).to_csv(report_path, index=False)
        print(f"wrote {len(orphaned)} genuinely-missing rows to {report_path}")
        print("breakdown:")
        print(
            orphaned.groupby(["model", "backend"]).size().to_string(),
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
