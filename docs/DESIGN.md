# DESIGN.md — Auditing Algorithmic Pigmentocracy

**Status**: locked candidate. The user reviews and critiques this document
*before* the production-grid generation begins. Sections §1–§7 become the
binding specification at the moment of OSF pre-registration; §8 lists the
decisions the user must resolve.

This document was written after the POC validated the plumbing end-to-end
(4 commits, 36/36 tests, `$0.00` cost, `make all-poc` idempotent). It
operationalises the binding research proposal
(`Propuesta_SciReports_v1.docx`) into an executable empirical study under
three editorial constraints: zero monetary cost, 100% public data, total
reproducibility from a single `make all`.

---

## §1. Research questions and hypotheses

### Central question (Q0)

In what magnitude and direction do text-to-image (T2I) generative AI models
produce phenotypic representations of occupations that differ from the
*empirical* phenotypic distribution of workers in those occupations in
four Latin-American countries (Colombia, Mexico, Brazil, Peru)?

### Hypotheses

The five hypotheses operationalise the proposal's argument that the
**sedimentación pigmentocrática** — the crystallisation of historical
colourist patterns inside the model's embedding geometry — is detectable,
signed, and quantifiable on a welfare-relevant scale.

**H1 — Directional pigmentocratic sedimentation.**
For each country, occupation, language and model, the algorithmic skin-tone
distribution sits at systematically lighter PERLA tones than the empirical
distribution of real workers. Formally: Δ(o, c, ℓ, m) < 0 with high
consistency across the (o, c, ℓ, m) grid.

**H2 — Pigmentocratic gradient over occupational status.**
The magnitude of algorithmic lightening grows monotonically with
occupational status. Formally: β < 0 in the per-(c, ℓ, m) OLS
Δ(o) = α + β · w(o) + γ · X(o) + ε, where w(o) is the percentile rank of
mean monthly labour income and X(o) holds occupational composition
controls (% female, % formal, % tertiary education).

**H3 — Linguistic modulation of representation.**
Comparing prompts in English, Spanish (peninsular), Spanish (Latin
American), Brazilian Portuguese (and exploratorily Quechua and Guaraní),
the language fixed effects in
APD(c, ℓ, m) = α_m + δ_c + λ_ℓ + ε are *jointly significant*. The
*direction* of each language effect (corrective vs amplifying vs
orthogonal) is empirically open and reported, not pre-specified.

**H4 — Scaling does not resolve the bias.**
Controlling for architecture family, model versions with more parameters
do **not** produce a monotone reduction in |APD|. Formally: φ in
APD = θ + φ · log(parameters) + ψ · debias_explicit + ε is *not*
significantly negative. (Replicates Yang 2025 in a multilingual setting.)

**H5 — Quantifiable digital orientalism.**
Prompts that append a Latin-American geographic marker
("Colombian doctor", "Mexican engineer") produce contexts with higher
CLIP zero-shot probability of {rural, folkloric, premodern} backgrounds
than equivalent prompts with US or European markers, holding occupation
and language constant. Reported as a difference-in-differences in CLIP
probabilities, controlling for the unconditioned CLIP baseline.

Hypotheses H1–H3 are **confirmatory** (pre-registered). H4 and H5 are
**exploratory** (declared as such because H4 requires within-family
architectural comparisons whose confounds we cannot fully eliminate, and
H5 leans on the assumption that CLIP itself is neutral toward LatAm
imagery — a strong assumption that the paper discusses honestly).

---

## §2. The APD indicator — derivation and justification

### Pieces

For each (occupation o, country c, language ℓ, model m):

1. **f_alg(t | o, c, ℓ, m)** — distribution over the 11 PERLA tones across
   the N = 30 generated images in the cell, built from the **2-of-3
   concordance rule** between CASCo (Rejón Piña 2023, native PERLA
   classifier), ITA → PERLA, and MST → PERLA. Images that fail face
   detection drop out (and the no-face rate is itself reported as a
   diagnostic).
2. **f_emp(t | o, c)** — empirical distribution over the 11 PERLA tones
   for real workers in occupation o, country c, derived from public
   microdata (§4).
3. **w(o, c)** — percentile rank of the mean monthly labour income of
   occupation o in country c, normalised so that Σ_o w(o, c) = 1.

### Three quantities

```
D(o, c, ℓ, m)   = W₁( f_alg , f_emp )                     # magnitude
Δ(o, c, ℓ, m)   = E[t | f_alg] − E[t | f_emp]             # sign
APD(c, ℓ, m)    = Σ_o  w(o, c) · D(o, c, ℓ, m) · sign(Δ(o, c, ℓ, m))
```

### Why Wasserstein-1 over the ordinal lattice

PERLA is **ordinal with meaningful unit spacing**: shifting probability
mass from tone 2 to tone 4 is "less wrong" than shifting the same mass
from tone 2 to tone 9.

* **KL** and **Jensen-Shannon** divergences ignore this — they only see
  whether categories match. KL exploding when a single tone has zero
  empirical mass is a well-known practical headache that does not arise
  with W₁.
* **Statistical parity** metrics (Bianchi 2023, AlDahoul 2025) treat
  phenotype as *categorical* and therefore cannot rank the severity of
  mistakes by the *distance* they sit from the empirical distribution.

W₁ over the integer support {1, …, 11} with unit spacing is the canonical
*ordinal* divergence. It equals the integrated absolute difference of the
CDFs, has units of "PERLA tones", and reduces to a closed form that
`scipy.stats.wasserstein_distance` computes exactly. Already unit-tested
in `tests/unit/test_distances.py` against known cases (identity, unit
shift, ten-tone shift, uniform vs concentrated).

### Why the signed Δ separately from D

D is a *magnitude* (always ≥ 0). The proposal's H1 is a *directional*
claim ("models lighten"). Reporting D alone would conflate two phenomena:
a model that systematically darkens and one that systematically lightens
by the same amount would receive the same D. The signed Δ tags the
direction; the product `D · sign(Δ)` preserves both magnitude and
direction in a single scalar before aggregation.

### Why the status weights

H1 averages across all occupations; H2 says the *gradient* matters —
high-status occupations should be more affected. Aggregating
D · sign(Δ) with weights proportional to occupational income converts
APD into a **welfare-relevant scalar**: it tells a regulator how much
algorithmic lightening occurs, weighted by where in the labour hierarchy
it sits. APD ≈ 0 means no directional bias on average; APD significantly
negative means the model lightens high-status occupations more than it
darkens (or matches) low-status ones; APD significantly positive would
falsify H1.

### Why this is a publishable methodological contribution

| Property | APD | Bianchi 2023 | AlDahoul 2025 | KL / JSD |
|---|:---:|:---:|:---:|:---:|
| Respects PERLA ordinality | ✓ | ✗ | ✗ | ✗ |
| Calibrated against empirical reality | ✓ | partial | ✓ | depends |
| Sign-tagged (direction testable) | ✓ | ✗ | ✗ | ✗ |
| Welfare-weighted | ✓ | ✗ | ✗ | ✗ |
| Decomposes cleanly (D, Δ, APD) | ✓ | ✗ | ✗ | ✗ |
| Transportable to any country/model/lang | ✓ | ✓ | ✓ | ✓ |

None of the prior literature reviewed in the proposal §2 combines these
six properties. AlDahoul 2025 in *Scientific Reports* used statistical
parity over discrete race categories against US BLS; APD replaces each
ingredient.

---

## §3. Identification strategy per hypothesis

For each H I list (i) the treatment or comparison, (ii) the control,
(iii) the threats to validity, (iv) the robustness specifications.

### H1 — Directional sedimentation (descriptive, confirmatory)

* **Comparison.** The algorithmic distribution f_alg from each model m
  versus the empirical distribution f_emp of real workers.
* **Control.** None needed — H1 is a *descriptive directional claim*.
  We are not claiming a causal arrow between model architecture and
  pigmentocracy; we are measuring whether the deviation has a consistent
  sign.
* **Threats.** (a) Classifier noise on synthetic faces. (b) f_emp
  imputation noise where occupation × PERLA is sparse in microdata.
  (c) Selection by face-detection rate (no-detection rates may differ
  systematically across occupations).
* **Robustness.** Report APD with each of the three classifiers
  separately; restrict to the "concordant 3-of-3" subset; replace mean Δ
  with median Δ (robust to outliers); report face-detection rates as a
  primary table.

### H2 — Pigmentocratic gradient (associational, confirmatory)

* **Comparison.** Across occupations, varying w(o), for each (c, ℓ, m).
* **Control.** Occupational composition variables X(o) — % female,
  % formal, % tertiary education, all from the same microdata cell.
  These absorb confounds where occupation race composition correlates
  with status.
* **Threats.** (a) Status weights may *themselves* correlate with the
  empirical race composition of the occupation (a real-world feature).
  (b) The functional form (linear in w) is a choice.
* **Robustness.** Report β with and without race-composition controls;
  show the gap as the inference of interest. Replace OLS with quantile
  regression at median. Report β stratified by language and model. Pool
  with two-way clustered SEs by occupation and model.

### H3 — Linguistic modulation (quasi-experimental, confirmatory)

* **Treatment.** Prompt language ℓ.
* **Control.** Model fixed effects × country fixed effects: comparing
  the same model audited with English vs Spanish (peninsular) vs Spanish
  (LatAm) vs Brazilian Portuguese on the same country's microdata.
* **Threats.** (a) Translation quality varies; (b) the model's training
  exposure to each language varies — but this exposure variation *is part
  of what we measure*, not a confound.
* **Robustness.** Drop indigenous languages from confirmatory testing
  (declared exploratory in the proposal §4.5). Restrict to images where
  face detection succeeded with concordant 2-of-3 phenotype.

### H4 — Scaling (observational, exploratory)

* **Comparison.** log(parameters) within a single architecture family
  (SD 1.5 → SD 2.1 → SD XL → SD 3.5 Medium; FLUX schnell → FLUX dev).
* **Control.** Indicator for explicit-debias variants where shipped by
  the model authors.
* **Threats.** Confound between scale and unrelated architectural
  changes (attention block sizes, training-data scale, prompt encoder
  upgrades). This is the reason H4 is exploratory.
* **Robustness.** Restrict to within-family comparisons. Report φ both
  pooled and stratified. Bootstrap CI on φ. Visualise the APD-vs-log-scale
  curve directly so the reader sees non-monotonicity if it exists.

### H5 — Digital orientalism (quasi-experimental, exploratory)

* **Treatment.** Geographic marker in the prompt
  ("Colombian engineer" vs "American engineer").
* **Control.** Same occupation, same language, identical seed.
* **Threats.** CLIP itself has cultural biases — it may inflate
  "folkloric" probabilities for LatAm imagery regardless of the model
  under test.
* **Robustness.** Test as a **difference-in-differences** of CLIP
  probabilities between marker variants, controlling for the
  unconditioned CLIP baseline (i.e., comparing the *change* in CLIP
  probability, not the level). Repeat with CLIP variants (ViT-B/32 vs
  ViT-L/14) and report between-classifier sensitivity.

---

## §4. Data plan

Every source below has been verified accessible without institutional
credentials. License + retrieval-date go into
[`docs/DATA_SOURCES.md`](DATA_SOURCES.md); raw downloads land in
`data/raw/` and are gitignored; a `data/raw/.manifest.json` carrying
filename + SHA256 + retrieval timestamp is committed.

### 4.1 Public microdata (ground truth)

| Country | Primary | Auxiliary | Free? | Variable mapping |
|---|---|---|---|---|
| Colombia | LAPOP 2023 CO | PERLA core 2010 CO | yes, free account | `COLOR` (PERLA 1–11), `OCCUP4A` (ISCO-08 1-digit) |
| Mexico | LAPOP 2023 MX, ENADIS 2022 | PERLA core 2010 MX | yes; ENADIS public CSV | LAPOP `COLOR`; ENADIS skin tone scale 1–11 |
| Brazil | LAPOP 2023 BR, PNADC 2023 | PERLA core 2010 BR | yes; PNADC public ZIP | LAPOP `COLOR`; PNADC `cor` mapped via Telles 2014 imputation |
| Peru | LAPOP 2023 PE, ENAHO 2023 | PERLA core 2010 PE | yes; ENAHO public ZIP | LAPOP `COLOR`; ENAHO ethnic self-id mapped via PERLA core |

**Primary strategy**: LAPOP 2023 in all four countries (one registration,
four files, uniform schema). The national surveys (ENADIS, PNADC, ENAHO,
GEIH) enter as a **robustness check** that uses each country's own
classification system and confirms the LAPOP-based estimate.

**Imputation when needed**: where the primary survey lacks PERLA tone
(PNADC, ENAHO), we use the ethnic-category → PERLA-tone imputation
documented in proposal §4.2: cross self-declared ethnic category with the
empirical PERLA distribution observed *for that ethnic category* in PERLA
core 2010 and LAPOP merged. This is the Telles 2014 / Campos-Vázquez &
Medina-Cortina 2019 standard procedure.

**Hard rule**: if any source requires institutional credentials or paid
access, it is **dropped** and the alternative is documented in
`DECISIONS.md`. The synthetic prior (D-003) is the absolute fallback for
the POC only; production findings require real microdata.

### 4.2 Generative models — operational plan revised after the bootstrap

The proposal §4.1 listed 8 open-weights models served via Hugging Face
free Inference API. The bootstrap revealed (DECISIONS D-011, D-013):

* The legacy HF Inference API was retired in 2025.
* The new HF Inference Providers router charges credits per image;
  the free tier on a non-Pro account is ≈ $0.10/month and **does not
  cover** a 12 000-image grid.

Operational revision (compatible with the proposal's intent and explicit
about the substitution):

| Model | Where we run it | License |
|---|---|---|
| **SD 1.5** (main) | Colab T4 or Kaggle GPU, local `diffusers` | CreativeML Open RAIL-M |
| **SD XL 1.0** (main) | Colab T4 or Kaggle GPU, local `diffusers` | CreativeML Open RAIL++-M |
| **SD 3.5 Medium** (main) | Colab T4 or Kaggle GPU, local `diffusers` | Stability Community |
| **FLUX.1 schnell** (main) | Pollinations.ai relay + Colab cross-validation subset | Apache 2.0 |
| **SD 2.1** (robust) | Colab T4 | CreativeML Open RAIL++-M |
| **Playground v2.5** (robust) | Colab T4 | Playground v2.5 Community |
| **Kandinsky 3** (robust) | Colab T4 | Apache 2.0 |
| **AltDiffusion-m18** (robust) | Colab T4 | CreativeML Open RAIL-M |

Pollinations is documented as a *relay* over public FLUX weights; for a
random ~5% subset of the FLUX-schnell cells we additionally regenerate
locally with `diffusers` and confirm byte-equivalent outputs given the
same seed. The reproducibility audit trail (proposal §6.4) is intact.

### 4.3 Classifiers (open-source, vendored)

| Tool | Source | Vendoring path | License |
|---|---|---|---|
| **CASCo** (Rejón Piña 2023) | Author's GitHub mirror of the *Skin Research and Technology* supplement | `third_party/casco/` + NOTICE | TBD — see §8 Q-E |
| **ITA** | Implemented in `apd.classify.skin_ita` | n/a | MIT (this repo) |
| **MST** | Implemented in `apd.classify.skin_mst` | n/a | MIT (this repo) |
| **FairFace** (Karkkainen & Joo 2021) | https://github.com/joojs/fairface release | `third_party/fairface/` | MIT |
| **CLIP** ViT-B/32 (OpenAI) | HF Hub `openai/clip-vit-base-patch32` | downloaded at first use | MIT |
| **MediaPipe Tasks** Face Detector | Optional re-evaluation post-POC | n/a | Apache 2.0 |

POC currently uses **OpenCV Haar cascade** for face detection
(DECISIONS D-010) because MediaPipe 0.10.35 removed the `mp.solutions`
namespace; the MediaPipe Tasks pipeline can be re-introduced later
without affecting the rest of the panel.

### 4.4 Occupational crosswalks

ISCO-08 (3-digit sub-major group) is the canonical anchor. Each national
crosswalk is a public XLSX from the corresponding statistical office:

| Country | Source | Local code |
|---|---|---|
| Colombia | DANE classifications portal | CNO-2015 |
| Mexico | INEGI classifications portal | SINCO-2011 |
| Brazil | IBGE concorda portal | CBO |
| Peru | INEI classifications portal | COP |

Files are downloaded once, committed under `data/crosswalks/` (each is
50–200 KB), and unit-tested for round-trip mapping over all 25 study
occupations.

### 4.5 Zero-cost confirmation

Every line above either (a) requires only a public URL fetch, or
(b) requires a free email-only account whose registration falls inside
the "no institutional credentials" rule. None requires paid access or
institutional sponsorship. `docs/COST_LOG.md` records every download
batch with `$0.00` and cumulative `$0.00`.

---

## §5. Translation strategy

Goal: an audit-ready prompt grid in four confirmatory languages plus two
exploratory indigenous languages, produced and validated **without any
paid translation service**.

### 5.1 Procedure per language

| Language | Procedure | Validation | Status |
|---|---|---|---|
| **English** | Native authoring | Self-validated by trilingual authors | locked |
| **Spanish (peninsular)** | Native authoring by Spanish-speaking authors | RAE *Diccionario de la lengua española* normative check | locked |
| **Spanish (Latin American generic)** | Dialectal lookup via RAE *Diccionario de americanismos* | Per-country native-author cross-check (CL/HL Colombian, plus invited Mexican + Brazilian colleagues for completeness) | drafted |
| **Brazilian Portuguese** | Native authoring by invited Brazilian colleague | Acordo Ortográfico de 1990 norms | drafted |
| **Quechua** (exploratory) | Apertium + QuechuaCorpus (Helsinki) + Llamacha open MT | FLACSO Andes academic network review | exploratory |
| **Guaraní** (exploratory) | Guaraní Renda (UFP) + Wiktionary + Yvy MT open project | UFP academic contacts | exploratory |

### 5.2 Validation workflow (zero cost, open science)

1. The full translated prompt grid is published as a GitHub gist and an
   OSF supplementary file 4 weeks before generation begins.
2. Native-speaker linguists in CLACSO / FLACSO networks are invited to
   review and submit corrections via GitHub PR or OSF comment.
3. Each prompt's status (`validated`, `unreviewed`, `declined`,
   `disputed`) is recorded in `prompts/translations.jsonl`, committed,
   and locked at pre-registration time.
4. Indigenous-language prompts whose validation status remains
   `unreviewed` at lock time are kept in the **exploratory** analysis
   only; the manuscript distinguishes them from confirmatory results.

### 5.3 Methodological honesty

* The Spanish (LatAm generic) variant is acknowledged as a *constructed
  composite* of Mexican, Colombian and Argentine occupational nouns; the
  paper discusses this construction transparently and runs the analysis
  also separately per dialect when sample size allows.
* The proposal explicitly anticipates that some languages may produce
  uninterpretable prompts in the model; **the non-comprehension itself
  is a finding** (a strong form of digital orientalism). This is reported
  as such, not as a failure.

---

## §6. Computational budget — the arithmetic

The proposal's footprint: **25 occupations × 4 main models × 4 main
languages × 30 images = 12 000 main images**, plus 10 occupations × 4
robustness models × 2 indigenous languages × 10 images ≈ 3 200 robustness
images. Total **~15 200 generations**.

### 6.1 Per-platform throughput (conservative)

* **Google Colab T4 free**: 90 minutes of GPU per day per Google account.
  SD XL takes ~12 s/image at 25 inference steps; FLUX schnell ~5 s; SD
  1.5 ~5 s. **Conservative average 8 s/image.** Per session:
  90 × 60 / 8 ≈ **675 images/day** per account.
* **Kaggle Notebooks free**: 30 GPU-hours per week (T4 or P100). At
  8 s/image: 30 × 3600 / 8 ≈ **13 500 images/week** per account.
* **Pollinations.ai**: empirically observed ~10 s/image without rate
  limit. ~6 images/min sustained ≈ **7 200 images/day** per machine,
  unconditional on accounts.
* **HF Inference free**: deprecated for image models. Not in the plan.

### 6.2 Per-author capacity (3 coauthors → 3 accounts each)

Each platform is used legitimately under its own terms of service; each
coauthor uses their personal account.

| Resource | Daily capacity |
|---|---|
| Colab × 3 accounts | 3 × 675 = **2 025 imgs/day** |
| Kaggle × 3 accounts (sustained) | 3 × 13 500 / 7 ≈ **5 800 imgs/day** |
| Pollinations | **5 000 imgs/day** (polite throttle) |
| **Sustained total** | **~12 800 imgs/day under conservative assumptions** |

### 6.3 Wall-clock estimate

15 200 images / 12 800 imgs/day ≈ **1.2 days of pure generation time**.

Add 10× overhead for setup, classification, debugging, rate-limit slack,
and per-coauthor manual session handoffs: **~12 days of wall-clock**, well
inside the proposal's "4–6 weeks of generation" window.

### 6.4 Checkpointing and resilience

* The orchestrator already checkpoints every image to disk and is
  idempotent: a killed session loses at most the in-flight image.
* Each Colab/Kaggle notebook commits its `metadata.parquet` shard to the
  repo at session end; the panel builder merges and deduplicates.
* Generation is parallel across coauthors: a partial-failure in one
  account doesn't block the others.
* `docs/COST_LOG.md` records one row per notebook shift with the free
  tier consumed; cumulative must always read `$0.00`.

### 6.5 If a platform changes its free-tier rules mid-study

The orchestrator's `select_backend` decouples the model identifier from
the runtime path. If Pollinations becomes paid mid-run, the workflow
re-routes to local `diffusers` on Colab/Kaggle. If Colab tightens its
free quota, we shift weight to Kaggle. Documented in DECISIONS.md the
moment it happens.

---

## §7. OSF pre-registration checklist

Pre-registration is filed **once §1–§5 are locked and §8 is resolved**,
and **before** any of the 15 200 production images is generated.

### 7.1 Confirmatory specifications (locked at pre-registration)

* **H1.** For each (c, ℓ, m), test that the mean of Δ(o) across
  occupations is < 0 via a one-sided t-test with cluster-robust SEs by
  occupation. Reject H1 in that cell if p > 0.05 *and* the point estimate
  is non-negative.
* **H2.** For each (c, ℓ, m), fit Δ(o) = α + β · w(o) + γ · X(o) + ε via
  OLS. Report β with bootstrap-1000 percentile CI. Report a pooled β
  across (c, ℓ, m) with two-way clustered SEs by occupation and model.
* **H3.** For each c, joint F-test on language fixed effects in
  APD(c, ℓ, m) = α_m + λ_ℓ + ε.

### 7.2 Exploratory analyses (reported as such)

* H4 (scaling), H5 (digital orientalism), indigenous-language results,
  per-occupation cross-tabs with FairFace gender/age/race.
* Sensitivity to classifier choice: APD recomputed under CASCo-only,
  ITA-only, MST-only.

### 7.3 Decision rules

* Multiple testing: Benjamini-Hochberg FDR at 5% across all H1 cells.
* Bootstrap: 1 000 percentile replicates, seed pre-registered.
* Minimum effect threshold to claim "directional sedimentation":
  Δ < −0.5 PERLA tones with FDR-adjusted p < 0.05.

### 7.4 Visual validation

* 300 images stratified by (occupation × model × language), manually
  PERLA-labelled by two coauthors **blind** to the algorithmic classifier
  output. Cohen's κ reported between coauthors and between manual labels
  and the 2-of-3 algorithmic consensus.

### 7.5 Files locked at pre-registration time

* **Code**: a git tag `prereg-v1` pinning every source file.
* **Prompt grid**: `prompts/grid.json` committed.
* **Translations**: `prompts/translations.jsonl` committed in current
  validated state.
* **Status weights**: `data/processed/status_weights.parquet` committed,
  sourced from real microdata.
* **Ground truth**: `data/processed/ground_truth.parquet` (real, not
  synthetic), committed.

---

## §8. Open questions for the user

These need an answer before scale-up. Each has a recommendation; the
final call is yours.

### Q-A. Microdata source

**Context.** LAPOP 2023 covers all four countries with a uniform schema
(`COLOR` + `OCCUP4A`). Free registration with email — not institutional —
so satisfies the binding spec.

**Recommendation.** Register at LAPOP. Single decision, four files,
uniform schema. National surveys (ENADIS / PNADC / ENAHO / GEIH) enter
as robustness.

**Open.** Want me to walk you through the LAPOP registration step-by-step
in the next session?

### Q-B. Model audit scope

**Context.** Running 4 main + 4 robustness models on the full 12 000
grid requires ~50 GB of weight downloads cached to Drive/Kaggle. Doable
but bandwidth-heavy.

**Recommendation.** Keep 4 main + 4 robustness exactly as the proposal
§6.1 specifies. Cache weights once per coauthor account.

### Q-C. Colab/Kaggle multi-day shifts

**Context.** The orchestrator is idempotent; each session is a 90-min
Colab block or a 12-h Kaggle block. End-to-end automation across many
sessions still requires a human at session boundaries.

**Recommendation.** Each coauthor commits to one Colab + one Kaggle
shift per day for ~12 working days. I will build a
`notebooks/generation_shift.ipynb` template that reads the next pending
cell from `images/metadata.parquet` and writes new images back.

### Q-D. Visual validation labellers

**Context.** Pre-registration commits to two coauthors manually
PERLA-labelling 300 stratified images blind to the classifier outputs.
~3 hours each.

**Open.** Confirm CL + YP (or other pair) as labellers, and pick a date
~2 weeks before manuscript submission for the labelling round.

### Q-E. CASCo licensing

**Context.** Rejón Piña 2023 published CASCo as supplementary code with
*Skin Research and Technology* (Wiley). Public mirrors carry no explicit
license. We either (a) email the author asking for explicit
academic-redistribution clearance, or (b) re-implement CASCo from the
paper's specification (the algorithm is fully described).

**Recommendation.** Email the author. The 2-of-3 concordance rule rests
on three independent classifiers; reimplementing CASCo from scratch
duplicates effort but is the safer fallback if no reply arrives within
2 weeks.

**Open.** Want me to draft the email?

### Q-F. Pre-registration filing

**Context.** Pre-registration on OSF is a 1-day task (the OSF form takes
the spec from §1–§5 of this document verbatim). Requires a single human
submitter.

**Open.** Are you willing to file the pre-registration once §1–§7 are
locked? Or do we delegate to one of the coauthors?

### Q-G. Target journal commitment

**Context.** Scientific Reports is the realistic target (35–55%
acceptance probability per the proposal's own estimate). Nature Human
Behaviour and PNAS are stretch targets that require a heavier theory and
policy framing — same empirical execution, different manuscript shape.

**Recommendation.** Commit to **Scientific Reports** as the primary
submission. Keep NHB → *Big Data & Society* → *EPJ Data Science* as a
cascade if SR rejects with constructive feedback.

**Open.** Agree, or escalate to NHB primary?

---

End of design document. Sign-off on Q-A through Q-G means scale-up
proceeds: LAPOP downloads first, then the full crosswalks and
translations, then the production grid.
