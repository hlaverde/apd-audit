# Kaggle/Colab generation plan — 2026-06-02

Purpose: accelerate APD image generation without changing the scientific
design, prompts, target sample size, APD indicator, LAPOP ground truth, or
zero-cost constraint.

## Current routing

| Route | Scope | Why |
|---|---|---|
| Local Windows | `pollinations/flux` main + H5 + FLUX robustness, `--workers 1` | Pollinations allows sequential free use but rejects parallel access. |
| Kaggle free GPU | SD 1.5, SDXL, SD 2.1, Playground 2.5, Kandinsky 3, AltDiffusion | Best fit for non-gated local `diffusers` models and longer free GPU runs. |
| Colab free GPU | SD 3.5 Medium and short spillover slices | SD 3.5 may require interactive HF auth and smaller manual shifts. |

Do not upload raw LAPOP files to Kaggle/Colab. Cloud notebooks need only the
manifest and image metadata, not ground-truth microdata.

## Standard parameters

| Parameter | Default | Notes |
|---|---:|---|
| `N_SHARDS` | 4 | Deterministic SHA256 sharding by `image_id`. |
| `MAX_IMAGES_PER_RUN` | 50 | Increase only if the free runtime is stable. |
| `CHECKPOINT_EVERY` | 5 | Writes partial metadata frequently. |
| `CLASSIFY` | `True` | Keeps cloud shards self-contained when CV deps install cleanly. |
| `DRY_RUN` | `False` | Use `True` only for smoke tests outside canonical metadata. |

## Suggested first 12 turns

| Turn | Runner | Grid | Model | Language | Shard | Notebook | Expected slice size |
|---:|---|---|---|---|---:|---|---:|
| 1 | Kaggle | main | `runwayml/stable-diffusion-v1-5` | `en` | 0/4 | `notebooks/kaggle_apd_generation_runner.ipynb` | ~188 |
| 2 | Kaggle | main | `runwayml/stable-diffusion-v1-5` | `en` | 1/4 | `notebooks/kaggle_apd_generation_runner.ipynb` | ~188 |
| 3 | Kaggle | main | `runwayml/stable-diffusion-v1-5` | `es-ES` | 0/4 | `notebooks/kaggle_apd_generation_runner.ipynb` | ~188 |
| 4 | Kaggle | main | `runwayml/stable-diffusion-v1-5` | `es-LatAm` | 0/4 | `notebooks/kaggle_apd_generation_runner.ipynb` | ~188 |
| 5 | Kaggle | main | `stabilityai/stable-diffusion-xl-base-1.0` | `en` | 0/4 | `notebooks/kaggle_apd_generation_runner.ipynb` | ~188 |
| 6 | Kaggle | main | `stabilityai/stable-diffusion-xl-base-1.0` | `es-ES` | 0/4 | `notebooks/kaggle_apd_generation_runner.ipynb` | ~188 |
| 7 | Kaggle | main | `stabilityai/stable-diffusion-xl-base-1.0` | `es-LatAm` | 0/4 | `notebooks/kaggle_apd_generation_runner.ipynb` | ~188 |
| 8 | Kaggle | main | `stabilityai/stable-diffusion-xl-base-1.0` | `pt-BR` | 0/4 | `notebooks/kaggle_apd_generation_runner.ipynb` | ~188 |
| 9 | Colab | main | `stabilityai/stable-diffusion-3.5-medium` | `en` | 0/4 | `notebooks/colab_apd_generation_runner.ipynb` | ~188 |
| 10 | Colab | main | `stabilityai/stable-diffusion-3.5-medium` | `es-ES` | 0/4 | `notebooks/colab_apd_generation_runner.ipynb` | ~188 |
| 11 | Colab | main | `stabilityai/stable-diffusion-3.5-medium` | `es-LatAm` | 0/4 | `notebooks/colab_apd_generation_runner.ipynb` | ~188 |
| 12 | Colab | main | `stabilityai/stable-diffusion-3.5-medium` | `pt-BR` | 0/4 | `notebooks/colab_apd_generation_runner.ipynb` | ~188 |

Set `MAX_IMAGES_PER_RUN=50` for the first execution of each turn. If a model
is stable and the free session has time remaining, repeat the same turn with
the same parameters; it will resume from checkpoint and skip existing
`image_id`s.

## Follow-up turns

After the first 12 turns, fill the remaining shards for the same
model/language pairs (`1/4`, `2/4`, `3/4`) before moving to robustness
models. Keep `pollinations/flux` on Local Windows only.

The robustness rows for `qu` and `gn` are present in the manifest but marked
`prompt_status=unavailable` until documented translations are supplied. Do
not generate those rows from invented translations.
