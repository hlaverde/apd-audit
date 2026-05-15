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

.PHONY: help setup all-poc lint test clean
help:
	@echo Available targets:
	@echo   setup        Create venv and install dependencies (uv sync).
	@echo   all-poc      Run the full POC pipeline end-to-end.
	@echo   ground-truth Build f_emp from public microdata.
	@echo   generate     Generate 30 SD1.5 images via HF free tier.
	@echo   classify     Run MediaPipe + ITA + MST + (optional) CASCo.
	@echo   panel        Build the (model, occ, country, lang) panel.
	@echo   apd          Compute D, Delta, APD.
	@echo   estimate     Plot gradient (Delta vs status) and run H1-H5 stubs.
	@echo   test         Run pytest (unit + integration on fixtures).
	@echo   lint         Run ruff + black + isort in check mode.
	@echo   clean        Remove interim artefacts (NOT raw or final results).

setup:
	uv sync --extra dev

all-poc: \
	data/processed/ground_truth_poc.parquet \
	images/poc/metadata.parquet \
	data/interim/poc_phenotype.parquet \
	data/processed/panel_poc.parquet \
	results/tables/apd_poc.csv \
	results/figures/gradient_poc.png

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
