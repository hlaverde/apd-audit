# CLAUDE.md — guide for AI assistants and human coauthors

This file is read by AI coding assistants (Claude Code, etc.) and by
human coauthors joining the repo. Keep it short: pointers and rules,
not tutorials.

## What this repo is

An empirical audit of phenotype × occupation bias in open-weights
text-to-image generative AI models, calibrated against Latin-American
labour microdata. Targets *Scientific Reports* (Nature Portfolio).
Binding research proposal: `docs/Propuesta_SciReports_v1.docx`.

## Three non-negotiable constraints

1. **Zero monetary cost.** No paid APIs, no cloud rentals, no paid
   datasets. Tracked in `docs/COST_LOG.md`; cumulative must read
   `$0.00`.
2. **100% public data.** Every source must be downloadable from a
   public URL. No institutional credentials.
3. **Total replicability.** Every result regenerable from a clean
   clone via `make all-poc` (proof of concept) or `make all-prod`
   (production).

A change that breaks any of these three is reverted on sight.

## Operating rules

* All design decisions land in `docs/DECISIONS.md` with a date and a
  rationale. New decisions go above the most recent entry; numbering is
  sequential.
* The locked specification is `docs/DESIGN.md`. Updating it after the
  OSF pre-registration is filed requires explicit deviation notes in
  the manuscript supplement.
* Every commit follows conventional commits (`feat:`, `fix:`,
  `chore:`, `docs:`).
* Tests pass on every commit. Run `uv run pytest -q` before pushing.
* PNG outputs are gitignored; metadata parquets are committed.

## How a coauthor runs a generation shift

1. `git pull --rebase` on your local clone.
2. Open `notebooks/generation_shift.ipynb` in **Colab** or **Kaggle**.
3. Edit the *Configuration* cell: `REPO_URL`, optional `HF_TOKEN`,
   `BUDGET` (default 50).
4. Run all cells. The notebook generates the next `BUDGET` pending
   cells, writing PNGs to Drive / Kaggle workspace.
5. Copy the updated `images/main/metadata.parquet` back to your local
   clone.
6. `git add images/main/metadata.parquet`, commit with the format
   `shift: <coauthor-initials>-<YYYYMMDD> +N images` and push.
7. Append a row to `docs/COST_LOG.md`:
   `| YYYY-MM-DD HH:MM UTC | generate shift | Colab T4 free | N imgs / Ts | $0.00 | **$0.00** |`

The orchestrator is idempotent: a session interruption never produces
duplicate images, and another coauthor running in parallel will pick
different pending cells (different seeds).

## Project layout

```
src/apd/             # library code
  apd/               #   APD math: distances, Δ, indicator, bootstrap
  classify/          #   face detection + ITA / MST / CASCo / CLIP
  estimate/          #   H1-H5 econometric specifications
  generate/          #   image-generation backends + orchestrator
  ground_truth/      #   LAPOP loader, status weights, crosswalks
  ingest/            #   national-survey loaders
  panel/             #   per-image panel builder
  prompts/           #   25-occupation × 4-language grid + H5 + robustness
  validate/          #   visual validation sampling + Cohen's κ
  viz/               #   matplotlib helpers (no seaborn)
scripts/             # CLI entrypoints, one per make target
  00_preflight.py    # production-readiness check
  01..07*.py         # ingest → ground truth → generate → classify → panel → APD → estimate
  08_visual_validation.py
tests/unit/          # unit tests (pure functions)
tests/integration/   # end-to-end pipeline test on fixtures
docs/                # DESIGN, DECISIONS, DATA_SOURCES, COST_LOG, Propuesta
osf/                 # pre-registration draft
notebooks/           # Colab/Kaggle shift template
```

## Common commands

```bash
make help               # list make targets
make all-poc            # run the 30-image proof of concept
make all-prod           # run the production pipeline (post-LAPOP)
uv run pytest -q        # run all tests
uv run python scripts/00_preflight.py   # readiness check
```

## What NOT to do

* Do **not** add paid services — even with a "free tier" credit card on
  file.
* Do **not** commit large binary outputs (PNGs, models). They go in
  `images/main/` (gitignored) or downloaded on demand.
* Do **not** edit `osf/preregistration_draft.md` after OSF filing;
  amendments go in the manuscript supplement.
* Do **not** introduce dependencies without updating `pyproject.toml`
  and rerunning `uv sync` + `pytest`.
* Do **not** invent translations for the prompt grid. Updates go
  through `prompts/translations.jsonl` with documented sources.
