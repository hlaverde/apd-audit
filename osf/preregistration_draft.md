# OSF Pre-Registration — APD audit

**Status**: candidate draft. This document is the verbatim source HL will
paste into the OSF "AsPredicted-style preregistration" form before the
production-grid image generation begins. Section headings mirror the
OSF template; commentary in *italics* is editor's notes that get
deleted on submission.

---

## 1. Title

**Auditing Algorithmic Pigmentocracy: a multilingual, microdata-calibrated
audit of phenotype–occupation bias in open-weights text-to-image models
for four Latin-American countries.**

## 2. Authors and affiliations

* Carlos Alfonso Laverde Rodríguez (first author, lead implementer).
* Yenny Katherine Parra Acosta (co-author).
* Henry Laverde Rojas (principal investigator, submitter of this form).

Affiliation: Universidad Militar Nueva Granada (UMNG), Colombia.
Author roles follow the CRediT taxonomy and will be made explicit in the
manuscript.

## 3. Pre-registration date

Filed before any image of the **production grid** (12 000 main + 2 400
robustness) is generated. The 30-image **proof-of-concept** that
validated the pipeline is *exempt* from this pre-registration; its
results were not used to choose any specification listed below.

## 4. Description of the project

The project audits the gap between the phenotypic distribution produced
by text-to-image (T2I) generative AI models when prompted for an
occupation and the empirical phenotypic distribution of workers in that
occupation, for four Latin-American countries (Colombia, Mexico, Brazil,
Peru). The core measurement is the **Algorithmic Pigmentocratic
Distance (APD)** indicator (§5.2 of the binding research proposal),
which combines a Wasserstein-1 divergence over the ordinal PERLA tone
scale with status-weighted aggregation across occupations.

## 5. Hypotheses

Confirmatory (locked):

* **H1.** For each country × language × model, the algorithmic
  PERLA distribution is systematically lighter than the empirical PERLA
  distribution. Formally: Δ(o, c, ℓ, m) < 0 with high consistency
  across cells.
* **H2.** For each country × language × model, occupational status
  predicts the magnitude of algorithmic lightening (β < 0 in the OLS
  Δ(o) = α + β·w(o) + γ·X(o) + ε).
* **H3.** Language fixed effects are jointly significant in
  APD(c, ℓ, m) = α_m + δ_c + λ_ℓ + ε.

Exploratory (declared as such):

* **H4.** Within architecture families, scaling does not produce a
  monotone reduction in |APD|.
* **H5.** Latin-American geographic markers in the prompt produce
  higher CLIP zero-shot probability of {rural, folkloric, premodern}
  contexts than US or EU markers.

## 6. Sampling plan

### 6.1 Main confirmatory grid

* **Occupations**: 25 from proposal §6.1, spanning ISCO-08 majors 1–9
  and three status tiers (high, medium, low). Crosswalked to CNO-2015 /
  SINCO-2011 / CBO / COP for the robustness branch.
* **Languages**: English, Spanish (peninsular), Spanish (Latin American
  generic), Brazilian Portuguese.
* **Models** (open weights, locally generable): SD 1.5, SD XL 1.0,
  SD 3.5 Medium, FLUX.1 schnell.
* **Images per cell**: 30, deterministic seeds derived from
  `apd.config.settings.seed = 20260514`.
* **Total**: 25 × 4 × 4 × 30 = **12 000 main images**.

### 6.2 Robustness grid

* 10-occupation subset × 4 main languages × 4 extra open-weights models
  (SD 2.1, Playground v2.5, Kandinsky 3, AltDiffusion-m18) × 10 imgs =
  1 600 cells.
* 10-occupation subset × 2 indigenous languages (Quechua, Guaraní) ×
  4 main models × 10 imgs = 800 cells.
* **Total robustness**: 2 400 images.

### 6.3 H5 marker sub-grid

* 8 occupations × 4 markers (unmarked / LatAm / US / EU) × FLUX schnell
  × 10 imgs = **320 H5 cells**.

### 6.4 Visual validation sample

* 300 images stratified by occupation (12 per stratum × 25 occupations);
  drawn from the main grid; restricted to face-detected images.

## 7. Variables

### 7.1 Manipulated

* **Prompt occupation**: 25-level factor.
* **Prompt language**: 4-level factor (main) + 2-level factor
  (indigenous, exploratory).
* **Model**: 4-level factor (main) + 4-level factor (robustness).
* **Geographic marker** (H5 only): 4-level factor.

### 7.2 Measured (per image)

* **Face detection**: binary (`has_face`) via OpenCV Haar cascade
  (substitute for MediaPipe; DECISIONS.md D-010). Per-image diagnostic.
* **Skin-tone PERLA**: integer 1–11, from 2-of-3 concordance of:
  - CASCo (Rejón Piña & Ma 2023) via the `skin-tone-classifier` PyPI
    library.
  - ITA in CIE-Lab (Chardon 1991) crosswalked to PERLA.
  - Monk Skin Tone Scale nearest-anchor mapped to PERLA.
  Concordance flag (`concordant_2of3`) requires at least 2 classifiers
  within ±1 PERLA tone of the median.
* **CLIP context probabilities** (H5 only): softmax over 6 labels
  (rural / urban / modern office / artisan workshop / folkloric
  landscape / neutral background) via openai/clip-vit-base-patch32.

### 7.3 Auxiliary (per LAPOP respondent)

* `COLOR`: interviewer-applied PERLA tone.
* `OCCUP4A`: ISCO-08 1-digit occupation major.
* `Q10NEW` (or equivalent): monthly labour income (for status weights).
* `pais`: country code.

## 8. Analysis plan

### 8.1 Construction of the dependent variables

* `f_alg(t | o, c, ℓ, m)`: histogram over PERLA 1–11 across the N = 30
  images in the cell, after dropping no-face images and restricting to
  `concordant_2of3 = True` (the "high-confidence subset"; reported also
  without this restriction as a robustness check).
* `f_emp(t | o, c)`: empirical distribution from LAPOP 2023, restricted
  to country `c` and ISCO-08 major group of occupation `o`. When the
  cell has fewer than 30 LAPOP observations we collapse to a broader
  ISCO grouping, documented in the supplement.
* `w(o, c)`: percentile rank of mean monthly labour income in country
  `c`, normalised so `Σ_o w(o, c) = 1`. Computed by
  `apd.ground_truth.status_weights.status_weights_from_lapop`.
* `D(o, c, ℓ, m) = W_1(f_alg, f_emp)` — 1-Wasserstein on ordinal PERLA.
* `Δ(o, c, ℓ, m) = E[t | f_alg] − E[t | f_emp]` — signed lightness shift.
* `APD(c, ℓ, m) = Σ_o w(o, c) · D · sign(Δ)`.

### 8.2 Confirmatory hypothesis tests

* **H1.** For each (c, ℓ, m) one-sided cluster-robust t-test on Δ < 0;
  occupation-level clustering. Rejection criterion: BH-FDR-adjusted
  p < 0.05 across the (c × ℓ × m) grid AND point estimate Δ < −0.5
  PERLA tones.
* **H2.** OLS Δ(o) = α + β·w(o) + γ·X(o) + ε per (c, ℓ, m). β reported
  with bootstrap-1000 percentile CI. Pooled β with two-way clustered
  SEs by occupation and model. Rejection criterion: pooled β < 0 and
  FDR-adjusted p < 0.05.
* **H3.** OLS APD(c, ℓ, m) = α_m + δ_c + λ_ℓ + ε. Joint F-test on
  language fixed effects. Rejection criterion: F p < 0.05.

### 8.3 Exploratory analyses

* **H4.** OLS APD = θ + φ·log(parameters) + ψ·debias_explicit +
  family_FE + ε. One-sided test on φ ≥ 0. Reported as exploratory.
* **H5.** OLS P_orientalist = α + β_LatAm·marker_LatAm + β_US·marker_US +
  β_EU·marker_EU + occ_FE + model_FE + ε with HC1 SEs. Linear contrast
  β_LatAm − β_US reported with bootstrap CI. Reported as exploratory.
* Indigenous-language results (Quechua, Guaraní) reported separately.
* Per-occupation cross-tabs of PERLA × FairFace gender / age / race
  (when FairFace integration lands — currently deferred per D-023).

### 8.4 Bootstrap

* 1 000 percentile bootstrap replicates of D, Δ and APD per cell,
  pre-registered seed = 20260514, percentile CIs at 95%.
* Implemented in `apd.apd.bootstrap.bootstrap_apd`.

### 8.5 Multiple testing

* Benjamini-Hochberg FDR at 5% across all H1 cells (the c × ℓ × m grid).
* H2 pooled p-value reported alongside per-cell stratified estimates.

### 8.6 Visual validation

* Cohen's κ (linearly-weighted, PERLA is ordinal) between CL and YP on
  the 300-image stratified sample. Threshold for "acceptable
  agreement": κ ≥ 0.6. Below that we trigger a second labelling round
  with a revised rubric.
* HL adjudicates rows with |CL − YP| > 2 PERLA tones (the "disagreed"
  subset). The adjudicated value becomes the consensus ground truth
  against which the algorithmic 2-of-3 is compared via a second κ.

## 9. Software and reproducibility

* Code: github.com/.../apd-audit (public repository, MIT licence for
  our code; `skin-tone-classifier` GPL-3.0 dependency acknowledged in
  README + DECISIONS.md D-016).
* Pinned commit (`prereg-v1` tag) captures the locked state at
  pre-registration time.
* Lockfile: `uv.lock` committed.
* Computational environment: Python 3.11.15 via `uv`; runs on Colab T4,
  Kaggle GPU, or local CPU.
* All outputs regenerable from the committed prompts + ground-truth
  parquet via `make all-prod` (production target equivalent of the POC
  `make all-poc`).

## 10. Materials archived at pre-registration

The following artefacts are tagged `prereg-v1` and frozen on submission
of this form:

* `prompts/grid.py` — the 12 000-cell main grid generator.
* `prompts/translations.jsonl` — validated translations for the 4 main
  languages.
* `data/processed/status_weights.parquet` — per-country, per-occupation
  weights derived from LAPOP income data.
* `data/processed/ground_truth.parquet` — f_emp distributions for all
  four countries.
* `osf/preregistration_draft.md` — this document.

## 11. Ethical considerations

* Generated images are synthetic and do not represent identifiable
  individuals; analysis is aggregate.
* The study does not generate or distribute individual images of public
  figures or under-age individuals.
* CEI/IRB review at UMNG: filed in parallel with this pre-registration.
* No human subjects beyond the coauthor-labellers, who consent
  explicitly to participating in the visual-validation round and to
  having their labels reported in aggregate (Cohen's κ).
* Data governance: only public microdata sources are used (LAPOP open
  data plus national statistical-office files). No private data, no
  paid datasets, no individuals re-identified.

## 12. Funding / conflicts

Funding source: none. The project is executed within ordinary academic
duties at UMNG. The authors declare no competing financial or
non-financial interests.

---

*End of pre-registration draft. Edit history kept in git
(`git log -- osf/preregistration_draft.md`).*
