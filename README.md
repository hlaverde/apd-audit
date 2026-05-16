# Auditing Algorithmic Pigmentocracy (APD)

[![OSF Pre-Registration](https://img.shields.io/badge/OSF-10.17605%2FOSF.IO%2FXFQVM-blue)](https://osf.io/xfqvm)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Empirical audit of phenotype-occupation bias in generative text-to-image AI
models against Latin-American labour-market microdata.

This repository operationalises the research proposal
[`docs/Propuesta_SciReports_v1.docx`](docs/Propuesta_SciReports_v1.docx)
and produces the empirical material for a manuscript targeting
**Scientific Reports** (Nature Portfolio).

> **Pre-registered on OSF**: [10.17605/OSF.IO/XFQVM](https://osf.io/xfqvm)
> · filed 2026-05-15. The repository state at the `prereg-v1` git tag
> pins every source file at filing time. Deviations from the
> pre-registered plan are documented in
> [`docs/DECISIONS.md`](docs/DECISIONS.md) with their commit timestamps.

> Authors — Carlos Alfonso Laverde Rodríguez · Yenny Katherine Parra Acosta ·
> Henry Laverde Rojas. Universidad Militar Nueva Granada.

## The three non-negotiable constraints

1. **Zero monetary cost.** No paid APIs, no cloud rentals, no paid datasets.
   Permitted infrastructure: Google Colab free tier, Kaggle Notebooks free
   tier, Hugging Face Inference API free tier, local CPU. Tracked in
   [`docs/COST_LOG.md`](docs/COST_LOG.md).
2. **100% public data, zero institutional agreements.** Every source must be
   downloadable from a public URL. Sources logged in
   [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).
3. **Replicability as the editorial claim.** Every result is regenerable from
   a single clone + `make all`. No notebook-only logic, no manual steps.

## What this repository contains

- **`src/apd/`** — library code, organised by pipeline stage.
- **`scripts/01..07*.py`** — thin CLI entry points, one per `make` target.
- **`tests/`** — unit tests (pure-function logic) and one integration test
  exercising the full POC on tiny fixtures.
- **`docs/`** — binding spec, decision log, data sources, cost ledger.
- **`data/`** (gitignored, schemas only) — raw / interim / processed.
- **`images/`** (gitignored, metadata only) — generated PNGs and metadata.
- **`results/`** — tables and figures produced by the pipeline.
- **`osf/`** — pre-registration draft for OSF.

## The APD indicator

For each occupation `o`, country `c`, prompt language `ℓ`, and model `m`:

```
D(o,c,ℓ,m)  = W₁(f_alg, f_emp)          # Wasserstein-1 over PERLA ordinal
Δ(o,c,ℓ,m)  = E[t|f_alg] - E[t|f_emp]   # signed lightness shift
APD(c,ℓ,m)  = Σ_o w(o,c) · D · sign(Δ)  # status-weighted aggregate
```

`f_alg` is the algorithmic phenotypic distribution over the 11 PERLA tones
(N=30 images per cell); `f_emp` is the empirical distribution derived from
public microdata; `w(o,c)` is the percentile rank of mean monthly wage of the
occupation in the country.

## Reproducing this study

### Prerequisites

- **Python 3.11** (managed by `uv` — installer below).
- **GNU Make ≥ 4** (Windows: `winget install ezwinports.make`).
- A free Hugging Face account + access token (one per coauthor is enough),
  pasted into `.env` based on `.env.example`.

### Bootstrap

```bash
# install uv (one-time, user-level, no admin)
pip install --user uv

# install the Python 3.11 toolchain managed by uv
uv python install 3.11

# create venv + install all dependencies
make setup
```

### Run the proof of concept (3 occupations × Colombia × English × SD 1.5)

```bash
cp .env.example .env   # paste your HF token into HF_TOKEN
make all-poc           # ~30 imgs, end-to-end, < 90 minutes
```

Re-running `make all-poc` skips completed stages (file-based caching).

### Run the full study

The full study (~12 000 main images + ~3 200 robustness) is not part of
this repository's default pipeline; running it requires distributing work
across Colab, Kaggle, and HF free tiers over 4–6 weeks. See
[`docs/DESIGN.md`](docs/DESIGN.md) once that document exists.

## Cost ledger

Every compute action — even free — is logged in
[`docs/COST_LOG.md`](docs/COST_LOG.md). The cumulative cost of this study
is and must remain **$0.00**.

## License

- Code: MIT (see [`LICENSE`](LICENSE)).
- Data products: CC BY 4.0 (see [`LICENSE`](LICENSE)).
- The proposal document remains the intellectual property of its authors.

## Citing

(Pre-print and DOI to be added after submission to Scientific Reports.)
