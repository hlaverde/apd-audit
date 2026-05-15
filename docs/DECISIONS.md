# Decisions log

Append-only journal of analytical and engineering decisions, in chronological
order. Every entry must have a date, a decision, and a short rationale that
references the binding spec when relevant.

---

## 2026-05-14 — Project bootstrap

### D-001: Project root layout

**Decision.** The project root is the `Propuesta No. 2/` folder itself; the
proposal docx is moved to `docs/Propuesta_SciReports_v1.docx`.
**Rationale.** Simpler, fewer nested paths. The folder was otherwise empty.

### D-002: Toolchain

**Decision.** Python 3.11.15 managed by `uv`, GNU make 4.4.1 installed via
`winget` (ezwinports.make), pre-commit with ruff + black + isort + nbstripout.
**Rationale.** Matches the proposal's reproducibility claim. The system Python
3.14 is left untouched. `uv` is faster and gives lockfile-grade reproducibility
for free. Make on Windows lets us stay literal to the user's spec.

### D-003: POC ground-truth source

**Decision.** For the POC we use **LAPOP AmericasBarometer Colombia 2023**
(file: `Colombia 2023 LAPOP AmericasBarometer v1.0_W.dta` or the public CSV
equivalent) because it (i) contains a PERLA-tone item applied by the
interviewer (variable `COLOR`), (ii) contains an occupational code (`OCCUP4A`),
and (iii) is publicly distributed from `lapopsurveys.org/data-access` without
any institutional credential.

If the file requires a free user account: this is documented as a step in
`DATA_SOURCES.md` and is **NOT** considered an institutional credential.

**Fallback A.** If LAPOP becomes unavailable, the POC falls back to a
**documented synthetic prior** for the three test occupations, derived from
published PERLA-coded distributions in Telles (2014, *Pigmentocracies*) and
Campos-Vázquez & Medina-Cortina (2019). This prior is **only** acceptable for
the POC — production runs must use real microdata. The synthetic prior is
labelled `is_synthetic=True` in the parquet schema so it can never be confused
with empirical data downstream.

### D-004: Generation backend

**Decision.** POC generation uses the Hugging Face Inference API (free tier)
with a personal token loaded from `.env`. Local `diffusers` on CPU is the
documented fallback (~5–10 min/image on a typical laptop).
**Rationale.** Fastest path under the zero-cost constraint. Tokens are read
from `.env`, never logged, never committed.

### D-005: Classifier stack — full 2-of-3 concordance now active

**Decision (updated).** The POC runs OpenCV-Haar (face detection; D-010) +
**ITA** + **MST** + **CASCo**. CASCo is reached through the maintained
PyPI library **`skin-tone-classifier`** (`stone.process`), which is the
upstream reference implementation of Rejón Piña & Ma 2023 with PERLA
palette support out of the box. The 2-of-3 concordance rule is
implemented in `apd.classify.consensus.consensus_perla` (median of
available classifier outputs + `concordant_2of3` boolean flag when at
least 2 classifiers fall within ±1 PERLA tone of the median).

**Initial concordance on the POC (n = 30 FLUX-generated faces)**:
* CEO: 9/10 concordant 2-of-3, mean consensus PERLA = 7.2.
* nurse: 10/10 concordant, mean = 7.1.
* domestic worker: 10/10 concordant, mean = 8.0.

29/30 = 97% concordance suggests the three independent measurements
agree on most images. The lone discordant case (CEO seed 9) had
ITA = 1, MST = 5, CASCo = 3 — the median (3) is within ±1 of only
itself, so the row carries `concordant_2of3 = False` and would be
excluded from the "high-confidence subset" robustness specification of
H1.

**Rationale.** With the PyPI library available, vendoring CASCo or
emailing the author is unnecessary. The implementation is published, on
PyPI, actively maintained (v1.2.6 March 2025, used in multiple 2025
peer-reviewed papers), and exposes a clean Python API.

### D-016: CASCo licensing (GPL-3.0 dependency in an MIT project)

**Decision.** Use `skin-tone-classifier` (GPL-3.0) as a runtime
dependency. Our own code remains MIT (`LICENSE`). Anyone redistributing
the combined package must respect GPL-3.0 terms for the CASCo portion;
this is documented in `README.md` and surfaced again here.
**Rationale.** Python's dynamic import is consistently interpreted as
"mere aggregation" rather than statically linked derivative work, so an
MIT-licensed project importing a GPL-3.0 library does not have to relicense
its own code. For peer-review purposes the only obligations are
attribution and unmodified passthrough of the upstream licence — both
satisfied by pinning a published PyPI version.

### D-017: Unicode-path workaround for OpenCV / CASCo / Haar

**Decision.** `src/apd/classify/skin_casco.py` redirects
`cv2.data.haarcascades` to an ASCII tmp cache at module import. Input
images are copied to a temp ASCII path before being passed to
`stone.process`. The same `_read_image_unicode_safe` pattern from D-017
is reused in `face_detect`.
**Rationale.** On Windows with a cp1252 system codepage, OpenCV's
`cv2.imread`, `cv2.FileStorage`, and any function backed by `fopen`
silently fail to open files whose path contains non-ASCII characters.
The project root contains *Investigación* with the *ó*, so every cv2
call dies unless we sidestep the path. The patch is idempotent and
process-local (no environment changes).


### D-006: Wasserstein implementation

**Decision.** `scipy.stats.wasserstein_distance` over integer PERLA tones 1..11
treated as positions on the real line. This is **W₁ on an ordinal lattice with
unit spacing**, which is exactly what the proposal §5.2 step 2 prescribes.
**Rationale.** Standard library, well tested, no extra dependencies. POT
(Python Optimal Transport) would offer flexibility for higher-dimensional cases
but is unnecessary for 1-D ordinal distances.

### D-007: Status weights `w(o, c)` for the POC

**Decision.** Use percentile rank of mean monthly *labour income* of full-time
workers in the LAPOP sample, restricted to the three POC occupations and
country = Colombia. Normalised so that Σ_o w(o) = 1 across the three.
**Rationale.** LAPOP carries an income variable (`Q10NEW` / `Q14`). For
production the user explicitly wants country-specific status — we mirror that
choice in the POC even though three occupations is statistically trivial.

### D-008: Random seed

**Decision.** `apd.config.SEED = 20260514` (today, YYYYMMDD). All RNGs derive
from this seed or from per-image seeds = `SEED * 1000 + occupation_index *
100 + image_index`.
**Rationale.** Deterministic, traceable, single source of truth.

### D-009: Idempotency strategy

**Decision.** Each pipeline stage writes a single canonical output file. The
Makefile uses file-target dependencies so re-running `make all-poc` skips
stages whose output already exists *and* is newer than its inputs.
**Rationale.** Required by the editorial replicability claim and by the POC
acceptance criterion that `make all-poc` re-runs cleanly.

### D-015: Q-G resolved — Scientific Reports is the primary target

**Decision.** The primary submission journal is **Scientific Reports** (Nature
Portfolio, Q1 multidisciplinary, FI ≈ 4.6). Cascade if rejected with
constructive feedback: *Nature Human Behaviour* → *PLOS ONE* → *Big Data &
Society* → *EPJ Data Science* → *AI & Society* → FAccT proceedings.
**Rationale.**
* The proposal itself selected SR as target (§9). The realistic acceptance
  probability is 35–55% conditional on competent execution, per the proposal's
  own estimate.
* AlDahoul, Rahwan & Zaki (2025) published a structurally identical audit
  (T2I bias × occupations × phenotype) in SR. The editorial precedent is
  direct.
* SR's reproducibility expectations align with our zero-cost + open-data
  commitment.
* Aiming higher (NHB or PNAS) is feasible but requires a heavier theory
  and policy framing that we should NOT decide before seeing the empirical
  results. The same paper can be re-targeted at NHB after the panel is
  built, without losing work.

### D-014: Q-A resolved — LAPOP 2023 primary ground truth across all four countries

**Decision.** Production ground truth is built from **LAPOP AmericasBarometer
2023** for Colombia, Mexico, Brazil and Peru. The four national surveys
(GEIH/ENADIS/PNADC/ENAHO) enter as a **robustness check** that uses each
country's own classification system and confirms the LAPOP-based estimate.
**Rationale.**
* LAPOP carries PERLA `COLOR` applied by the interviewer — directly the
  instrument the proposal §4.2 prescribes. No ethnic-category → PERLA
  imputation chain to defend at peer review.
* One registration (email, free) covers all four countries with a uniform
  schema.
* Setup cost: ~1 day. National surveys: 1–2 weeks (four different portals,
  four schemas, ethnic imputation).
* Risk: small per-(country × occupation) cell sizes for high-status
  occupations. Mitigation: collapse to ISCO-08 sub-major group when n < 30
  in a cell, document the procedure, report n per cell in the supplement.
* The proposal §4.2 explicitly anticipates this path.

### D-013: Pollinations.ai as the POC image-generation relay

**Decision.** The POC generates images through **Pollinations.ai**
(`https://image.pollinations.ai/prompt/...`), with the model parameter
`flux` (which on Pollinations is FLUX.1 schnell open weights). The
orchestrator's `select_backend` defaults to `PollinationsBackend` for
the POC model identifier `pollinations/flux`.
**Rationale.** During the bootstrap we discovered that:

* The legacy HF Inference API (`api-inference.huggingface.co`) was
  retired in 2025 — every probe returns 404.
* The new HF Inference Providers router
  (`router.huggingface.co/hf-inference`) **does** serve open-weights
  image models, but the free tier is essentially $0 of credit for a
  non-Pro, ``canPay=False`` account: a single test image went through;
  the second request returned **402 Payment Required**.
* Pollinations.ai is a public, free, no-token relay over the same
  FLUX open weights named in the proposal §4.1. No registration,
  no quota observed in testing, ~1–2 s per 512×512 image.

This keeps the **zero-cost constraint** intact and uses a model that is
already in the proposal's auditable list (FLUX.1 schnell, Apache 2.0).
The relay is explicitly documented as a third-party service; the
production run will choose between (a) staying on Pollinations,
(b) downloading the FLUX-schnell weights to a Colab/Kaggle notebook,
or (c) configuring a local `diffusers` install. That choice belongs in
DESIGN.md.

**Audit trail.** The Pollinations request signature
(model, seed, width, height) is recorded in `images/poc/metadata.parquet`
for every cell, so any reader can reproduce the exact prompt-to-image
mapping.

### D-012: Local diffusers + sd-turbo (deferred fallback, not active)

**Decision.** The `LocalBackend` is kept implemented and wired through
the orchestrator (`prefer_local=True`), but is **not** the default for
the POC. It remains the documented hard fallback if Pollinations
becomes unavailable.
**Rationale.** Pollinations works today and is dramatically faster than
CPU-only diffusers. We don't pay the install/download cost of the `ml`
extras (~500 MB of torch + diffusers) until we genuinely need them.

### D-011: Generative model for the POC (FLUX.1-schnell instead of SD 1.5)

**Decision.** The POC uses **FLUX.1-schnell** (`black-forest-labs/FLUX.1-schnell`)
on the Hugging Face free Inference Providers router
(`https://router.huggingface.co/hf-inference/models/...`), not Stable
Diffusion 1.5.
**Rationale.** During 2025 Hugging Face migrated the free Inference API
to the new Inference Providers router and de-listed many older models
from the free `hf-inference` provider. Probing the live API today returns:

| Model | Free `hf-inference`? |
|---|---|
| `runwayml/stable-diffusion-v1-5` | **400 — Model not supported by provider hf-inference** |
| `stabilityai/stable-diffusion-2-1` | **400 — Model not supported** |
| `stabilityai/stable-diffusion-xl-base-1.0` | **410 — deprecated** |
| `black-forest-labs/FLUX.1-schnell` | **200 — works, ~15 s / 1024×1024 image** |

FLUX.1-schnell is in the proposal's open-weights list (§4.1, row 5),
Apache-2.0 licensed, and produces 1024×1024 images in ~4 denoising steps.
Operationally it is the obvious POC choice. The main study can keep SD 1.5
in scope by routing it through a local `diffusers` install (the `ml`
extras), once the user authorises the ~3 GB weight download.

**Update to plan.** The proposal's plan to audit *eight* open-weights
models requires re-confirming which ones the free Inference Providers
router still accepts; this is a Step-3 (`DESIGN.md`) concern, not a POC
blocker.

### D-010: Face detector for the POC (OpenCV Haar instead of MediaPipe)

**Decision.** `src/apd/classify/face_detect.py` runs OpenCV's bundled Haar
cascade (`haarcascade_frontalface_default.xml`) rather than MediaPipe.
**Rationale.** MediaPipe 0.10.35 (the current PyPI release as of the
bootstrap date) removed the `mp.solutions` top-level namespace. The
replacement `mediapipe.tasks` API requires downloading a `.tflite` model
bundle; while feasible, it adds a binary asset to the install path and a
network step on the critical path. OpenCV Haar ships inside the
`opencv-python` wheel — zero extra downloads, zero state. The proposal
mentions MediaPipe by name, not by API; the substitution preserves the
methodological intent (free, open-source, deterministic face detection)
and is reversed once the MediaPipe Tasks pipeline is hardened or we
migrate to RetinaFace.

---

(Append future decisions below.)
