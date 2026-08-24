# Kaggle UI and automated batch runner

This document covers the two supported Kaggle paths for APD cloud generation:

```text
Route A, stable:       Kaggle UI T4 x2 -> ZIP -> watch_cloud_inbox/import_cloud_zip
Route B, experimental: PowerShell -> Kaggle CLI -> GPU smoke test -> ZIP -> import_cloud_zip
```

It does not change APD, prompts, occupations, hypotheses, LAPOP ground truth,
or target sample size.

## 1. Route A: stable Kaggle UI T4 x2

Use this path for production batches. The manual Kaggle UI run with **T4 x2**
completed `sd15_en_s1_part1` at `100/100`.

1. Run the Kaggle notebook from the UI and select **T4 x2**.
2. Download the final `apd_cloud_run_*.zip` output.
3. Put the ZIP anywhere under:

```text
cloud_inbox/
```

4. From the local repository root, run:

```powershell
.\scripts\watch_cloud_inbox.ps1 -Once
```

For a non-mutating rehearsal:

```powershell
.\scripts\watch_cloud_inbox.ps1 -Once -DryRun
```

To keep watching for downloaded ZIPs:

```powershell
.\scripts\watch_cloud_inbox.ps1 -PollSeconds 30
```

The watcher:

1. finds new `apd_cloud_run_*.zip` files under `cloud_inbox/`;
2. checks `results/imported_cloud_zips.json` to avoid duplicate imports;
3. runs `scripts/import_cloud_zip.py`;
4. writes `results/logs/import_<zip_stem>.log`;
5. runs dashboard;
6. runs preflight;
7. appends the ZIP hash to `results/imported_cloud_zips.json` only after
   successful import, dashboard, and preflight.

The original ZIP is never deleted and no commit is created automatically.

## 2. Route B: experimental Kaggle CLI

Install and authenticate the Kaggle CLI once:

```powershell
python -m pip install --user kaggle
python -m kaggle auth login
```

If `kaggle.exe` is not in `PATH`, the orchestrator falls back to:

```powershell
python -m kaggle
```

Kaggle CLI may assign P100, so this path is experimental. Use it only when the
generated Kaggle script's GPU smoke test passes.

### Dry-run first

From the repository root:

```powershell
.\scripts\run_kaggle_batch.ps1 `
  -Model "runwayml/stable-diffusion-v1-5" `
  -Language "en" `
  -ShardId 1 `
  -NShards 4 `
  -MaxImages 100 `
  -RunLabel "sd15_en_s1_part1" `
  -DryRun
```

Dry-run writes:

- `kaggle_runner/apd_run_config.json`
- `kaggle_runner/kernel-metadata.json`
- `kaggle_runner/script.py` as an audit snapshot of the self-contained script

It does not launch Kaggle, download outputs, or import ZIPs.

### Run a batch

```powershell
.\scripts\run_kaggle_batch.ps1 `
  -Model "runwayml/stable-diffusion-v1-5" `
  -Language "en" `
  -ShardId 1 `
  -NShards 4 `
  -MaxImages 100 `
  -RunLabel "sd15_en_s1_part1"
```

Optional parameters:

```powershell
-KernelSlug "henrylaverde/apd-kaggle-runner"
-CudaProfile auto
-PollSeconds 60
-TimeoutMinutes 720
```

The script:

1. verifies Kaggle CLI and auth;
2. writes Kaggle config files and a self-contained `script.py`;
3. pushes a short temporary staging folder with GPU enabled;
4. prints GPU diagnostics inside Kaggle (`nvidia-smi`, `python --version`,
   Torch version, Torch CUDA version, `torch.cuda.is_available()`,
   `torch.cuda.get_device_name(0)`, and compute capability when available);
5. runs a CUDA smoke test before Hugging Face model downloads;
6. polls `kaggle kernels status`;
7. downloads `apd_cloud_run_<RUN_LABEL>.zip`;
8. runs `scripts/import_cloud_zip.py`;
9. prints dashboard and preflight output.

## 3. GPU compatibility

The stable production path is Kaggle UI with **T4 x2**. A manual T4 x2 run
completed `sd15_en_s1_part1` at `100/100`.

Kaggle CLI may assign **P100** even when GPU is requested. The current project
ML extra resolves to a very new Torch/CUDA stack, and that stack can fail on
P100 before generation with:

```text
torch.AcceleratorError: CUDA error: no kernel image is available for execution on the device
```

PyTorch's own packaging notes say Pascal support was removed from CUDA 12.8
builds starting with PyTorch 2.8, and the PyTorch 2.12 CUDA support matrix
keeps older architectures such as Maxwell, Pascal, and Volta in the legacy
CUDA 12.6 build while CUDA 13.x targets newer architectures. PyTorch also
documents CUDA 11.8 wheels for older releases such as `torch==2.7.1`.

That gives us a low-cost candidate for P100, but not a production guarantee:

```powershell
.\scripts\run_kaggle_batch.ps1 `
  -Model "runwayml/stable-diffusion-v1-5" `
  -Language "en" `
  -ShardId 1 `
  -NShards 4 `
  -MaxImages 1 `
  -RunLabel "sd15_en_cli_smoke1_p100" `
  -CudaProfile p100
```

`-CudaProfile p100` keeps APD/prompts/grid/ground truth unchanged and only
reinstalls `torch==2.7.1`, `torchvision==0.22.1`, and `torchaudio==2.7.1`
from the official CUDA 11.8 PyTorch wheel index inside Kaggle's temporary uv
environment when `nvidia-smi` reports P100. It uses `uv pip install --python
/tmp/apd-venv/bin/python`, not `python -m pip`, because Kaggle's temporary uv
environment may not include pip. The runner still aborts before model
downloads if the CUDA smoke test fails.

Observed on 2026-06-03: `sd15_en_cli_smoke1_p100` ran through Kaggle CLI on
`Tesla P100-PCIE-16GB` with `torch==2.7.1+cu118`, `torch.version.cuda == 11.8`,
compute capability `(6, 0)`, and a passing CUDA smoke test. It generated and
imported 1 SD 1.5 image successfully. P100 is therefore viable for SD 1.5 at
smoke-test scale with `-CudaProfile p100`, but production should still scale
incrementally.

Later on 2026-06-03, the same P100 profile completed `MaxImages 10`, `25`,
`50`, and `100`. The runner now embeds the current local `metadata.parquet`
snapshot in `script.py` so Kaggle CLI does not regenerate already imported
images while the cloud branch is behind local metadata.

Default `-CudaProfile auto` uses the project lockfile stack. If Kaggle CLI
assigns P100 and the smoke test fails, the runner aborts early and production
must not be launched from Kaggle CLI until either `-CudaProfile p100` is proven
by smoke tests or Kaggle assigns a non-P100 GPU.

## 4. CLI smoke-test escalation

Do not jump straight back to 100 images. Use this sequence:

1. `sd15_en_cli_smoke1`, `MaxImages 1`.
2. If import/dashboard/preflight pass: `MaxImages 10`.
3. If that passes: `MaxImages 25`.
4. If that passes: `MaxImages 50`.
5. Only after those pass: `MaxImages 100`.

If any step fails, do not launch production. Keep the logs under
`results/logs/`, inspect the Kaggle GPU diagnostics, and document the cause in
this file.

## 5. Verify progress

```powershell
python -m uv run python scripts\09_progress_dashboard.py
python -m uv run python scripts\00_preflight.py
```

Expected:

- no active metadata shards after import;
- unique `image_id` count increases;
- preflight has zero blocking failures.

## 6. If Kaggle fails

The orchestrator tries to download logs with:

```powershell
python -m kaggle kernels logs henrylaverde/apd-kaggle-runner
```

It saves failure logs under:

```text
results/cloud_runs/<RUN_LABEL>/kaggle_failure.log
results/logs/kaggle_<RUN_LABEL>_failure.log
```

Common fixes:

- if diagnostics show P100, rerun through the Kaggle UI and select T4 x2;
- lower `-MaxImages` to 50-100 for SD 1.5;
- use 50-100 for SDXL first;
- use 25-50 for SD 3.5;
- confirm internet and GPU are enabled in `kernel-metadata.json`;
- rerun the same `RunLabel` only if the previous Kaggle output was not imported.

## 7. Do not commit

Do not commit:

- `.env`, tokens, or Kaggle credentials;
- `.venv`, caches, `cloud_inbox/`, or downloaded ZIPs;
- raw LAPOP files;
- generated PNGs;
- heavyweight cloud outputs unless explicitly reviewed.

Commit only reviewed code, notebooks, docs, and small metadata artefacts that
the project policy allows.
