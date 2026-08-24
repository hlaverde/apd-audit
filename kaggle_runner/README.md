# APD Kaggle runner template

This folder is pushed by `scripts/run_kaggle_batch.ps1` with Kaggle CLI.

Local PowerShell generates:

- `apd_run_config.json` with the batch parameters.
- `kernel-metadata.json` with the target kernel slug and GPU settings.

Kaggle runs `script.py`, which clones the `cloud-generation-20260602` branch,
generates the configured APD shard, creates exactly one ZIP in
`/kaggle/working`, and removes intermediate folders before finishing.

Do not put tokens, raw LAPOP files, local images, or `.venv` content in this
folder.
