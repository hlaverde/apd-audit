# Auditing Algorithmic Pigmentocracy — Makefile
#
# Conventions:
#  * Targets that produce files use the file path as the target name; running
#    `make` twice should skip stages whose outputs already exist.
#  * Every Python invocation goes through `uv run` so the project's pinned
#    Python 3.11 venv is used.
#  * `make all-poc` runs the entire proof-of-concept pipeline (~30 imgs).

PY := uv run python
SHELL := cmd.exe

# Make the ``apd`` package importable without relying on the editable .pth
# file, which is fragile when the project path contains non-ASCII characters
# (Windows .pth handling on cp1252 locales). Setting PYTHONPATH gives a
# stable behaviour regardless of locale.
export PYTHONPATH := src
export PYTHONUTF8 := 1

# ---------------- top-level convenience -----------------------------------

.PHONY: help setup all-poc all-prod preflight lint test clean
help:
	@echo Available targets:
	@echo   setup        Create venv and install dependencies (uv sync).
	@echo   preflight    Verify production readiness (LAPOP, ground truth, tests).
	@echo   all-poc      Run the 30-image proof-of-concept pipeline end-to-end.
	@echo   all-prod     Run the production pipeline (assumes images are generated).
	@echo   ground-truth Build f_emp from public microdata.
	@echo   generate     Generate 30 POC images via Pollinations.
	@echo   classify     Run face detect + CASCo + ITA + MST + concordance.
	@echo   panel        Build the (model, occ, country, lang) panel.
	@echo   apd          Compute D, Delta, APD.
	@echo   estimate     Plot gradient (Delta vs status) and run estimators.
	@echo   validate     Sample 300 images for blind PERLA labelling.
	@echo   test         Run pytest (unit + integration).
	@echo   lint         Run ruff + black + isort in check mode.
	@echo   clean        Remove interim artefacts.

setup:
	uv sync --extra dev

preflight:
	$(PY) scripts/00_preflight.py

all-poc: \
	data/processed/ground_truth_poc.parquet \
	images/poc/metadata.parquet \
	data/interim/poc_phenotype.parquet \
	data/processed/panel_poc.parquet \
	results/tables/apd_poc.csv \
	results/figures/gradient_poc.png

# Production pipeline. Assumes:
#   * LAPOP files are in data/raw/.
#   * Image generation has been distributed across coauthor shifts and
#     the resulting images/main/metadata.parquet is committed.
# The make-prod target does not invoke image generation (that happens in
# the notebook).
all-prod: preflight \
	data/processed/ground_truth.parquet \
	data/interim/main_phenotype.parquet \
	data/processed/panel_main.parquet \
	results/tables/apd_main.csv \
	results/validation/labelling.parquet \
	results/tables/h3_language.csv

data/processed/ground_truth.parquet data/processed/status_weights.parquet &: \
		scripts/02_build_ground_truth_main.py \
		src/apd/ingest/lapop.py \
		src/apd/ground_truth/status_weights.py
	$(PY) scripts/02_build_ground_truth_main.py

data/interim/main_phenotype.parquet: \
		images/main/metadata.parquet \
		scripts/04_classify_main.py \
		src/apd/classify/skin_casco.py
	$(PY) scripts/04_classify_main.py

data/processed/panel_main.parquet: \
		images/main/metadata.parquet \
		data/interim/main_phenotype.parquet \
		scripts/05_build_panel_main.py
	$(PY) scripts/05_build_panel_main.py

results/tables/apd_main.csv: \
		data/processed/ground_truth.parquet \
		data/processed/panel_main.parquet \
		scripts/06_compute_apd_main.py \
		src/apd/apd/bootstrap.py
	$(PY) scripts/06_compute_apd_main.py

results/tables/h3_language.csv: \
		results/tables/apd_main.csv \
		scripts/07_estimate_all.py \
		src/apd/estimate/h3.py
	$(PY) scripts/07_estimate_all.py

validate: results/validation/labelling.parquet

results/validation/labelling.parquet: \
		scripts/08_visual_validation.py \
		src/apd/validate/sampling.py
	$(PY) scripts/08_visual_validation.py

# ---------------- pipeline stages -----------------------------------------

data/processed/ground_truth_poc.parquet: \
		scripts/02_build_ground_truth.py \
		src/apd/ground_truth/build.py \
		src/apd/ingest/lapop.py
	$(PY) scripts/02_build_ground_truth.py

images/poc/metadata.parquet: \
		scripts/03_generate_images.py \
		src/apd/generate/hf_backend.py \
		src/apd/generate/orchestrator.py \
		src/apd/prompts/grid.py
	$(PY) scripts/03_generate_images.py

data/interim/poc_phenotype.parquet: \
		images/poc/metadata.parquet \
		scripts/04_classify_images.py \
		src/apd/classify/face_detect.py \
		src/apd/classify/skin_ita.py \
		src/apd/classify/skin_mst.py
	$(PY) scripts/04_classify_images.py

data/processed/panel_poc.parquet: \
		images/poc/metadata.parquet \
		data/interim/poc_phenotype.parquet \
		scripts/05_build_panel.py \
		src/apd/panel/build.py
	$(PY) scripts/05_build_panel.py

results/tables/apd_poc.csv: \
		data/processed/ground_truth_poc.parquet \
		data/processed/panel_poc.parquet \
		scripts/06_compute_apd.py \
		src/apd/apd/distances.py \
		src/apd/apd/indicator.py
	$(PY) scripts/06_compute_apd.py

results/figures/gradient_poc.png: \
		results/tables/apd_poc.csv \
		scripts/07_estimate_hypotheses.py \
		src/apd/viz/plots.py
	$(PY) scripts/07_estimate_hypotheses.py

# named aliases for humans
.PHONY: ground-truth generate classify panel apd estimate
ground-truth: data/processed/ground_truth_poc.parquet
generate:     images/poc/metadata.parquet
classify:     data/interim/poc_phenotype.parquet
panel:        data/processed/panel_poc.parquet
apd:          results/tables/apd_poc.csv
estimate:     results/figures/gradient_poc.png

# ---------------- tooling -------------------------------------------------

test:
	uv run pytest

lint:
	uv run ruff check src scripts tests
	uv run black --check src scripts tests
	uv run isort --check-only src scripts tests

clean:
	@echo Removing interim artefacts (keeping raw and processed).
	-@if exist data\interim rmdir /s /q data\interim
	-@if exist results\figures rmdir /s /q results\figures
	-@if exist images\poc\CEO rmdir /s /q images\poc\CEO
	-@if exist images\poc\nurse rmdir /s /q images\poc\nurse
	-@if exist "images\poc\domestic worker" rmdir /s /q "images\poc\domestic worker"
	@mkdir data\interim 2>nul || ver >nul
	@mkdir results\figures 2>nul || ver >nul
