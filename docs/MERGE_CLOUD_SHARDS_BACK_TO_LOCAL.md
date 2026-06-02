# Merge cloud shards back to local

This guide imports APD generation ZIPs produced by Kaggle/Colab notebooks
back into the local Windows clone.

Local repository:

```powershell
D:\DocumentosHL\Documentos\Documents\2021\Henry Laverde\2026\Investigación\Paper de IA\Propuesta No. 2
```

## 1. Download ZIPs

Kaggle:

- Open the finished notebook run.
- Download the ZIP from the notebook Output panel.
- The ZIP name starts with `apd_kaggle_`.

Colab:

- If `USE_DRIVE=True`, download from Google Drive under `apd_cloud_output`.
- Otherwise download the ZIP from `/content/apd_cloud_output/runs/<RUN_ID>/`.
- The ZIP name starts with `apd_colab_`.

## 2. Copy ZIPs into the repo

Create an inbox that is ignored by analysis code:

```powershell
mkdir cloud_inbox
```

Copy every downloaded ZIP into:

```powershell
cloud_inbox
```

## 3. Unzip

Each ZIP contains an `images/main` tree and a `runs/<RUN_ID>` folder. Expand
into a temporary folder first:

```powershell
mkdir cloud_inbox\expanded
Expand-Archive cloud_inbox\apd_kaggle_<RUN_ID>.zip -DestinationPath cloud_inbox\expanded\<RUN_ID>
```

Then copy the generated metadata shards and image folders into the repo:

```powershell
Copy-Item cloud_inbox\expanded\<RUN_ID>\images\main\metadata_*.parquet images\main\ -Force
Copy-Item cloud_inbox\expanded\<RUN_ID>\images\main\* images\main\ -Recurse -Force
```

If PowerShell asks about overwriting PNG files, choose overwrite only when the
path corresponds to the same `image_id`/seed. The merge step deduplicates
metadata by `image_id`, but image files should also be deterministic.

## 4. Merge and verify

Run:

```powershell
python -m uv run python scripts\merge_worker_shards.py
python -m uv run python scripts\09_progress_dashboard.py
python -m uv run python scripts\00_preflight.py
```

Expected:

- `merge_worker_shards.py` reports zero or more deduplicated rows and writes
  `images/main/metadata.parquet`.
- `09_progress_dashboard.py` increases unique image IDs and reports no active
  shards after merge.
- `00_preflight.py` has zero blocking failures.

## 5. Check uniqueness and missing files

```powershell
@'
import pandas as pd
from pathlib import Path

meta = pd.read_parquet("images/main/metadata.parquet")
print("rows", len(meta))
print("unique image_id", meta["image_id"].nunique())
print("duplicate rows", len(meta) - meta["image_id"].nunique())

missing_paths = [p for p in meta["path"].astype(str) if p and not Path(p).exists()]
print("missing image files", len(missing_paths))
print(meta.groupby(["model", "language"]).size().to_string())
'@ | python -m uv run python -
```

If `missing image files` is positive, inspect whether the cloud ZIP preserved
absolute paths from the cloud runtime. Metadata can still be analytically
useful for generation accounting, but classification from local PNG files
requires copied images.

## 6. Rebuild the pending manifest

After each merge, rebuild the manifest so future notebooks skip completed
images:

```powershell
python -m uv run python scripts\build_missing_generation_manifest.py --n-shards 4
```

Commit only after reviewing:

- `docs/COST_LOG.md`
- `images/main/metadata.parquet`
- cloud shard parquets if you keep archived provenance
- updated `results/missing_generation_manifest_2026-06-02.csv`
