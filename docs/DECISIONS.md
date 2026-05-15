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

### D-005: Classifier stack for POC

**Decision.** The POC runs **MediaPipe** (face detection) + **ITA** (CIE-Lab
angle) + **MST** (Monk Skin Tone scale, mapped to PERLA via a published
crosswalk). **CASCo** is deferred to a later commit because its reference
implementation (Rejón Piña 2023) needs to be vendored and validated; it is not
on the critical path for plumbing validation.
**Rationale.** ITA + MST are unambiguous open-source instruments and cover the
"two of three classifier" concordance requirement once CASCo lands.

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
