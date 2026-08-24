# Decisions log

## 2026-08-24 - Classifier validity: fix ITA, and validate before interpreting APD levels

### D-043: The classifier reads ~3 PERLA points darker than LAPOP, so visual validation precedes the APD headline

**Finding.** Over the main grid's 10 663 detected faces the algorithmic
`perla_consensus` averages **7.08**; the respondent-weighted LAPOP
baseline averages **4.10**. A ~3-point gap on an 11-point scale, with
the two distributions barely overlapping (algorithmic mass sits on
PERLA 7–8, empirical on 3–4).

**This is a measurement-scale problem, not a result.** Checked by eye:
`images/main/CEO/seed_202605140023000.png`, which the classifier scores
PERLA 7, is a visibly light-skinned man — PERLA 2–3 on the palette. The
gap is also flat across face sizes (mean PERLA 6.58 to 7.31 from the
smallest to the largest face-size band, Spearman ρ = −0.06, p = 0.28),
so it is not an artefact of bad crops or distant faces; and restricting
the patch to YCrCb skin pixels moves the mean only from 6.37 to 6.04.
It is the ITA/MST/CASCo → PERLA calibration itself, applied to
uncalibrated rendered sRGB images, versus a palette held in the hand by
an interviewer.

**Consequence.** `D` is a Wasserstein distance between f_alg and f_emp,
so this offset dominates it, and therefore dominates APD. An APD near 3
would mostly be measuring instrument incomparability rather than
pigmentocratic bias.

**Decision (Henry, 2026-08-24).** Run the visual validation *before*
publishing any APD level. 300 human PERLA ratings against the physical
palette card give the offset directly, and with it either a
recalibration or a quantified limitation. `scripts/07_estimate_all.py`
stays unwired for H4/H5 until then.

**What is unaffected.** The pigmentocratic *ordering* inside the model
output is rank-based and survives any monotone recalibration:
Spearman(status weight, mean algorithmic tone) = **−0.573, p = 0.0028**
— CEO 6.66 and doctor 6.79 at the light end, farmer 7.86 and street
vendor 7.68 at the dark end. The empirical ordering is steeper
(ρ = −0.933), which is why the *difference* carries no status gradient:
pooled H2 on the main grid gives β = +1.19 (SE 2.03, one-sided
p = 0.72, R² = 0.001).

### D-042: ITA is `arctan((L*-50)/b*)`, and an unmeasurable patch votes for nothing

**Decision.** `compute_ita` uses `arctan`, not `arctan2`, and returns
NaN when the retained pixels have median b* ≤ 0. `ita_to_perla` returns
`None` for NaN instead of the mid-scale tone 6.
`scripts/reclassify_metadata.py` re-runs the classifiers over
`images/main/` and rewrites the stored columns.

**Rationale.** Chardon's ITA is bounded to (−90°, +90°). `arctan2`
wraps patches with b* < 0 into quadrants II/III and returns angles out
to ±180°, which are not ITA. The stored data ranged **−178.5° to
+179.5°**, and 610 of 10 663 faces (5.7%) carried an out-of-range
value; `ita_to_perla` then clamped those to PERLA **1 or 11** — the
extremes of the scale — and 947 rows had `ita_label = "unknown"`.
Confirmed on the images: every out-of-range row has b* < 0, and where
b* > 0 the two formulas agree exactly.

Human skin is yellow-positive on b*, so b* ≤ 0 means the patch is not
skin (shadow, cool-cast background, clothing). Switching to `arctan`
alone would turn an obviously-invalid number into a plausible-looking
one, so those patches are reported as unmeasurable instead. Mapping an
unmeasurable patch to tone 6 likewise fed the 2-of-3 consensus a vote
no classifier cast; `None` is the contract CASCo already uses.

**Effect.** On a 200-image dry run, `perla_consensus` changed for 2.5%
of rows, face detection was unchanged, and no ITA value fell outside
Chardon's range. The fix does **not** explain the offset in D-043 —
that is driven by MST (7.29) and CASCo (7.12), which agree with each
other and outvote ITA (5.65).

### D-044: The labelling sheet shows the image and a sequence number, nothing else

**Decision.** `scripts/make_labelling_sheet.py` builds a self-contained
HTML sheet with each sampled image embedded as a downscaled JPEG, a
1–11 radio row, and a CSV export. The caption is `Image 001`, not the
`image_id`. `scripts/08_visual_validation.py` samples only the main
grid and only rows whose PNG is on disk.

**Rationale.** `image_id` is
`{model}__{occupation}__{seed}` — printing it would have shown the
labeller the model and the occupation next to every image, which is
exactly what the blind protocol withholds (caught by a leak check on
the generated HTML: "pollinations", "CEO" and the SD model names were
all rendered on the page). Presentation order is shuffled under a fixed
seed so rating drift cannot line up with occupation. The sheet draws no
on-screen PERLA swatches on purpose: LAPOP's `colorr` was recorded
against the physical palette card, and an approximated on-screen
palette would be a second, differently-calibrated instrument — the very
problem D-043 is about. Without the grid filter the sampler would have
built 57 strata instead of 25, because the H5 rows carry
`marker:<MARKER>:<occupation>` keys.

## 2026-08-24 - Wire the production analysis pipeline to the real 14 720-image grid

### D-038: Tabulate the main, robustness and H5 grids separately

**Decision.** `scripts/05_build_panel_main.py` labels every panel row
`main` / `robustness` / `h5` via `apd.prompts.grid.classify_grid`, and
`scripts/06_compute_apd_main.py` writes `results/tables/apd_main.csv`
from the main grid only, `apd_robustness.csv` from the robustness grid,
and excludes H5 from both.

**Rationale.** All three grids write into the same
`images/main/metadata.parquet`, so the panel mixed them: 12 000 main +
2 400 robustness + 320 H5 = 14 720. They are not comparable in one
table. Main-grid cells audit all 25 occupations and their status
weights sum to 1.0; robustness cells audit 10 occupations and sum to
**0.4246–0.4292**, so `APD = Σ w·D·sign(Δ)` is mechanically shrunk to
~42% of a main-grid value — a robustness model would look less biased
purely because it was run on fewer occupations. The H5 rows carry
synthetic `marker:<MARKER>:<occupation>` keys that appear in neither
the ground truth nor the weight table; they were silently dropped from
every calculation while still inflating each cell's reported
`n_images`.

**Open for the author.** Whether to renormalise weights within each
cell's audited occupation set (`w' = w / Σw`), which would make
robustness and main APD directly comparable at the cost of departing
from the pre-registered formula. Not done here — the pre-registered
definition is kept and the incomparability is made visible instead.

### D-039: `country`, not `country_proxy`, is the panel's cell key

**Decision.** `build_panel` renames `country_proxy` to `country`, and
drops metadata's copies of the classifier columns before merging the
phenotype table.

**Rationale.** Two seams between the generation and analysis halves of
the codebase were unconnected, so the production pipeline could not run
at all. (1) Generation writes `country_proxy`; every analysis consumer —
`bootstrap_apd_by_cell`'s cell keys, `estimate/h3.py`,
`validate/sampling.py`, ground truth, status weights — keys on
`country`, so the APD step raised `KeyError: panel missing cell keys:
['country']`. (2) Since D-028 the metadata already carries the 12
classifier columns, so merging it with the phenotype table forked every
one of them into `_x`/`_y`; `algorithmic_distribution` would then find
no `perla_consensus` column and fall back to a **uniform** f_alg,
silently manufacturing a null result. Both are fixed at the panel seam.

### D-040: MULTI cells are audited against a respondent-weighted pool of the four countries

**Decision.** `pool_ground_truth` collapses the four countries' f_emp
into one distribution per occupation, weighted by `n_respondents`.
`_ground_truth_for_cell` returns it for `country="MULTI"`.

**Rationale.** English and indigenous-language cells carry
`country="MULTI"` because no single national labour market backs them.
The previous code returned the *un-pooled* frame for those cells, which
stacked four 11-tone distributions into a 44-row block per occupation.
`wasserstein1_perla` then raised `shape mismatch: p=(11,), q=(44,)`,
which `bootstrap_apd_by_cell` caught and logged as "bootstrap failed
for cell … — skipping". Every English and indigenous-language cell
would have been dropped from the results table without an error. That
is 4 of 16 main cells and 12 of 24 robustness cells.

### D-041: `04_classify_main.py` extracts the inline classifier columns instead of re-classifying

**Decision.** When the metadata already carries the classifier columns
(the D-028 self-contained-shard architecture), the script selects them
out. It falls back to classifying from the PNG only for rows that lack
them.

**Rationale.** Re-deriving them would recompute identical values —
verified on a 40-image sample, where the recomputed consensus matched
the stored value in 40/40 cases — at ~0.35 s/image, i.e. ~85 minutes,
and would fail for the 110 rows whose PNG is gone (D-036).

## 2026-08-24 - Unify the two divergent git branches

### D-037: Merge `main` into `cloud-generation-20260602` with the `ours` strategy, then fast-forward `main`

**Decision.** On `cloud-generation-20260602`, run
`git merge main -s ours` — a merge commit that records `main`'s 88
GitHub-Actions-authored commits as ancestors (preserving their audit
trail: timestamps, run IDs, individual generation batches) while
leaving this branch's file tree completely untouched. Then fast-forward
local `main` to that merge commit and push it, so the two branches stop
diverging.

**Rationale.** The repository had accumulated two branches doing
unrelated work: `cloud-generation-20260602` (nearly all real
generation/analysis work, 14 720-row `metadata.parquet`) and `main`
(only Layer-1's GitHub Actions cron auto-commits, 1 743-row
`metadata.parquet`, pushed directly by the CI bot — no PR ever
existed between them). Before merging, both branches' `metadata.parquet`
were extracted directly from GitHub (`git show origin/<branch>:path`)
and compared by `image_id`: **0 rows were exclusive to `main`** — every
one of its 1 743 rows already exists in `cloud-generation-20260602`'s
14 720. The two branches'
`.github/workflows/generate-flux-pollinations.yml` files were also
byte-identical. With no data or code to reconcile, a content-level
merge would only add merge-conflict risk for zero benefit; `-s ours`
gets the equivalent outcome (one shared history going forward) without
touching a single file.

**Verification.** Post-merge, `images/main/metadata.parquet` on
`cloud-generation-20260602` still has exactly 14 720 rows / 14 720
unique `image_id` (no change from pre-merge), `git merge-base
--is-ancestor main HEAD` confirms `main` is now an ancestor (so the
`main` fast-forward is a true fast-forward, not a rewrite), and the
full test suite still passes (248 passed, 1 skipped — unchanged from
pre-merge).

**Guardrail.** Because `main` is the GitHub Actions cron's trigger
branch and the shared/public default branch, pushing the fast-forwarded
`main` to `origin` requires the user's explicit go-ahead even though
the merge itself carried no data risk — see `docs/PROJECT_STATUS.md`
section 5 for the standing house rule.

## 2026-08-24 - Repair stale PNG paths left by the cloud-import workflow

### D-036: Rewrite metadata `path` column to the canonical local layout

**Decision.** `scripts/fix_metadata_png_paths.py` rewrites the `path`
column of any `images/main/metadata.parquet` row whose registered path
doesn't resolve locally, to the project's canonical
`images/main/<occupation>/seed_<seed>.png` layout, whenever a PNG
actually exists there. Rows where neither the registered nor the
canonical path resolves are left untouched and logged to
`results/orphaned_png_rows.csv` instead of being silently dropped or
guessed at.

**Rationale.** 11 290/14 720 rows (77%) had a `path` pointing at the
Kaggle/Colab runtime's absolute path (e.g.
`/kaggle/working/<run>/images/main/<occ>/seed_<seed>.png`) because the
cloud-import workflow (`scripts/import_cloud_zip.py`,
`docs/MERGE_CLOUD_SHARDS_BACK_TO_LOCAL.md`) copies the PNG files into
the canonical local layout but never rewrote the `path` string
recorded at generation time on the remote runtime. Of those 11 290,
11 180 (99%) had their PNG sitting right there under the canonical
path — a metadata bug, not a data-loss problem. Fixed by rewriting the
string; no image was regenerated or altered.

**Result.** Only **110 rows genuinely have no locally-reachable PNG**:
* 90 rows, `model=pollinations/flux`, `backend=pollinations` — these
  were generated by Layer 1 (GitHub Actions cron), whose ephemeral
  runner is torn down after classifying the image and never uploads
  the PNG as an artifact (see `docs/PROJECT_STATUS.md` section 3).
  This is expected and permanent; the row's classifier output
  (`perla_consensus` etc.) was already computed on the runner before
  teardown and is intact — only the pixels are gone.
* 20 rows, `model=runwayml/stable-diffusion-v1-5`, `backend=local`,
  occupation=CEO, language=en, seeds `202605140001000`-`202605140001019`
  — these are exactly the 20 rows identified in D-029/D-030 (the
  2026-05-15 hl#1 shift's mislabelling bug). Their classifier output
  was recomputed correctly at some point after the bug fix (15/20 have
  `has_face=True` with a `perla_consensus` value; 5/20 legitimately
  have no detected face), but the regenerated PNG was produced on a
  Kaggle runtime (`path` still reads
  `/kaggle/working/apd-audit/images/main/CEO/seed_...png`) and that
  specific file never made it into a locally-imported ZIP.

**Guardrail.** Neither category blocks APD computation (which reads
`perla_consensus` from the parquet, not the PNG). They do matter for
visual validation and manuscript figure examples — the stratified
sampler (`apd.validate.sampling`) should exclude rows without a
locally-reachable PNG, or these 110 cells should be regenerated first
if they end up selected. 110/14 720 = 0.75% of the grid; not worth
blocking on unless the stratified sample happens to need them.

## 2026-08-18 - Complete source-backed Quechua robustness prompts

### D-035: Enable the two remaining Quechua occupation phrases

**Decision.** Enable Quechua `domestic worker` as `Wasimanta llank’aq chayri
wasi ruwanata ruwaq` and `street vendor` as `ñanniqpi ranqhaq` for the
exploratory robustness grid. Both phrases are taken from the official Chile
Census 2024 Quechua questionnaire and are paired with their exact Spanish
categories/examples in the official Spanish questionnaire.

**Rationale.** This public bilingual government instrument supplies the
specific occupational meanings that were missing under D-034. Enabling them
releases the final 80 pre-specified robustness cells without changing the
grid, models, seeds, hypotheses, or confirmatory prompts.

**Guardrail.** These phrases remain exploratory and `unreviewed`; they must
not be described as native-speaker validated. The source URL and file hash are
recorded in `docs/INDIGENOUS_PROMPT_SOURCES.md`.

## 2026-08-13 - Source-backed expansion of exploratory indigenous prompts

### D-034: Enable six newly documented occupation phrases, retain two unavailable Quechua cells

**Decision.** Following explicit authorization to research and register public
sources, add documented exploratory terms for Quechua `nurse` and
`salesperson`, and Guarani `construction worker`, `domestic worker`, `nurse`,
and `street vendor`. The public source register, translation registry, and
tests identify the exact terms. Quechua `domestic worker` and `street vendor`
remain unavailable.

**Rationale.** This turns 240 of 320 missing robustness cells into
source-traceable candidates without changing the locked confirmatory grid or
inventing translations. The remaining 80 cells have no sufficiently specific
public lexical source located during this review.

**Guardrail.** The two remaining Quechua cells may be enabled only after a
public, citable lexical source is added with another decision-log entry. No
generic-worker, gendered, or inferred substitute is permitted.

## 2026-07-23 - Source-traceable exploratory Quechua and Guarani prompts

### D-033: Enable only publicly documented indigenous-language occupation phrases

**Decision.** With explicit user authorization, the robustness grid may render
the documented `qu` and `gn` occupation phrases listed in
`docs/INDIGENOUS_PROMPT_SOURCES.md`. These prompts are occupation phrases only,
are recorded as exploratory/unreviewed, and leave every occupation without a
sufficiently specific public lexical source unavailable.

**Rationale.** This implements the exploratory pathway in `docs/DESIGN.md`
section 5 without inventing translations, changing the locked confirmatory
prompt grid, or treating a source glossary as native-speaker validation. The
source register provides public URLs, a source revision/hash, and the exact
lexical mapping used for every enabled cell.

**Guardrail.** The legacy `qu` grid code is explicitly tied to the Quechua
Sureno (`quz`) source variety in the register. No generic-worker, gendered,
or inferred substitute may be added for the remaining cells without a public
source and a new decision.

## 2026-07-17 — Retired SD 2.1 source resolution

### D-032: Preserve the locked SD 2.1 model identity while recording a verified mirror source

**Decision.** The locked manifest continues to identify the robustness model as
``stabilityai/stable-diffusion-2-1``. Its retired Hub repository is resolved at
execution time to the public ``sd2-community/stable-diffusion-2-1`` mirror, with
``model_source`` persisted in each generated metadata row.

**Rationale.** The official repository now returns HTTP 401/404 and cannot be
requested or authenticated. The mirror's ``v2-1_768-ema-pruned.ckpt`` has
SHA-256 ``ad2a33c361c1f593c4a1fb32ea81afce2b5bb7d1983c6b94793a26a3b54b08a0``,
matching the independently published historical checksum for that SD 2.1
checkpoint. This restores public, zero-cost reproducibility without changing
prompts, seeds, cells, APD calculations, or the requested model identity.

**Guardrail.** The source override is limited to this retired identifier. Any
future source change requires a new decision and checksum evidence.

## 2026-06-02 — Distributed free-tier generation hardening

### D-031: Manifest-driven Kaggle/Colab runners for SD-family generation

**Decision.** Production image generation now uses a manifest-driven
distributed runner for free Kaggle/Colab GPU sessions. The runner reads
``results/missing_generation_manifest_2026-06-02.csv``, selects a
deterministic ``image_id`` shard, writes merge-compatible metadata shards,
and exports a ZIP for local consolidation. Local Windows remains the
sequential ``pollinations/flux`` route with ``--workers 1`` and no automatic
push.

**Rationale.** The local Pollinations route is stable but too slow for the
full 14 720-image grid if used alone. Kaggle/Colab can generate SD-family
models with local ``diffusers`` under free GPU quotas while preserving the
locked scientific design: same prompt grid, same seeds, same ``target_n``,
same APD estimator, same LAPOP ground truth, and zero monetary cost.

**Guardrails.**

* No paid APIs, paid notebooks, cloud rentals, or multi-account limit
  evasion.
* No raw LAPOP redistribution to cloud notebooks; notebooks need only the
  manifest and generation metadata.
* No invented translations for ``qu`` / ``gn`` robustness rows. Those rows
  remain in the manifest with ``prompt_status=unavailable`` until documented
  translations exist.
* ``merge_worker_shards.py`` remains the only local consolidation path and
  deduplicates by ``image_id``.

Append-only journal of analytical and engineering decisions, in chronological
order. Every entry must have a date, a decision, and a short rationale that
references the binding spec when relevant.

---

## 2026-05-16 — Automation & schema for production scale-up

### D-026: TAREA 1 — Pollinations parallel throughput probe results

**Decision.** Pollinations.ai **does not** tolerate parallel access from
a single IP. We accept the operational reality and route the FLUX-via-
Pollinations slice through **N=1 sequential trickle** on Layer 1 (GH
Actions cron c/6h) + Layer 2 (local async worker with ``--workers 1``)
while SD-family + robustness + indigenous-langs move to Kaggle
(Layer 3, local ``diffusers``). This is "Branch B with sequential
trickle" in the May 16 plan file.

**Measurement (probe ran 2026-05-16, ~33 min wall, 80 imgs total).**
``scripts/_probe_pollinations_parallel.py`` ran 4 phases with
N ∈ {1, 3, 5, 10} concurrent streams × 20 imgs each. The probe seeds
sit in a disjoint range (``+ 90_000_000_000``) so the 80 imgs do not
collide with main/H5/robustness grids. Full data:
``results/pollinations_probe.json``.

| N concurrent | attempted | imgs_ok | 402 (Payment Required) | wall_s | p50_s/img | agg imgs/min |
|---:|---:|---:|---:|---:|---:|---:|
| **1** | 20 | **20** | 0  | 1712.4 | 89.9 | **0.70** |
| 3  | 20 |  1 | 19 |   90.0 | 90.0 | 0.67 |
| 5  | 20 |  1 | 19 |   90.3 | 90.2 | 0.66 |
| 10 | 20 |  1 | 19 |   89.6 | 89.6 | 0.67 |

**Reading.**

* **N=1** sustained at ~90 s/img — identical to shift hl#1's
  observation (88 s/img). Functional.
* **N≥2**: Pollinations returns ``HTTP/1.1 402 Payment Required`` on
  the second concurrent request onwards. Exactly **one** request per
  parallel phase made it through (presumably the first to land on the
  origin), at the *same* ~90 s latency as N=1. Every other request
  came back 402 in well under 1 s. Aggregate throughput on every
  parallel phase is *worse* or equal to N=1 because the lucky 200 OK
  is the only contribution.
* The 402 mechanism matches what killed HF Inference's free tier in
  2025 (D-013). Pollinations now operates a "free for N=1 only"
  policy at the application layer.

**Routing implication for the 14 720-img grid.**

| Slice | Cells | Backend | Layer | Estimated wall |
|---|---:|---|---|---|
| FLUX × main grid (4 langs × 25 occ × 30 imgs) | 3 000 | Pollinations N=1 sequential | L1 GHA + L2 local | ~75 h sustained → ~10 d at 8 h/day per IP, OR ~4 d split across L1 GHA (different IP) + L2 local |
| FLUX × H5 marker grid (8 occ × 4 markers × 10 imgs) | 320 | Pollinations N=1 sequential | L1 GHA + L2 local | ~8 h |
| SD-family × main grid (3 models × 4 langs × 25 occ × 30 imgs) | 9 000 | local ``diffusers`` on T4 | L3 Kaggle scheduled | ~13 h GPU per Kaggle 30h/week quota (1 acct) → ~1 wk |
| Robustness × 4 extra models × 4 main langs × 10 occ × 10 imgs | 1 600 | local ``diffusers`` on T4 | L3 Kaggle | ~2 h GPU |
| Robustness × 4 main models × 2 indigenous langs × 10 occ × 10 imgs | 800 | mixed (FLUX via Poll. + SD via diffusers) | L1/L2 + L3 | ~3 h |
| FLUX cross-validation 5% subset (DESIGN.md §4.2) | ~150 | local ``diffusers`` on T4 | L3 Kaggle | < 1 h |

**Rate-limiting hypothesis testable in the next 24h.** Pollinations
*may* now also throttle sustained N=1 if the IP exceeds a daily quota.
The first 24h of Layer 1+2 operation will reveal this. If sustained N=1
also starts returning 402, we fall back to Kaggle-for-everything
(remove ``pollinations/flux`` cells from L1/L2 and reassign to L3 +
local ``diffusers`` FLUX schnell).

**Rationale.**

* No scope reduction. The 4 main models (D-018), 4 main languages,
  25 occupations, 30 imgs/cell, BH-FDR 5%, bootstrap 1000, κ ≥ 0.6,
  master seed 20260514 — all unchanged.
* The locked ``DESIGN.md §6.5`` ("if Pollinations becomes paid mid-run,
  the workflow re-routes to local ``diffusers`` on Colab/Kaggle")
  explicitly anticipates this contingency. No OSF amendment required.
* ``select_backend`` (post D-029 fix) routes ``pollinations/flux``
  identifiers to ``PollinationsBackend`` and HF-repo-path identifiers
  to ``HFBackend`` or ``LocalBackend``. No silent fallback.

**Probe artefact hardening.** The probe crashed at the very last step
(``print(reason)``) because Windows console default cp1252 cannot
encode the ``≥`` glyph used in the recommendation text. Two
follow-up patches:
1. ``write_json`` moved BEFORE the stdout prints so a print() crash
   never throws away the 80-image measurement run.
2. ``≥`` / ``≤`` replaced with ASCII ``>=`` / ``<=``; a
   ``UnicodeEncodeError`` fallback wraps the final print.
The reconstructed ``results/pollinations_probe.json`` carries the
exact metrics from the table above (annotated with ``_note``).

### D-027: Three-layer automation architecture for the 14 720-img pipeline

**Decision.** The full production grid (12 000 main + 320 H5 + 2 400
robustness ≈ 14 720 imgs minus the 50 from shift hl#1) is generated by
three layers running in parallel, each idempotent and restartable:

1. **Layer 1 — GitHub Actions cron** (``.github/workflows/generate-flux-pollinations.yml``).
   ``ubuntu-latest`` runner, free unlimited minutes for the public repo,
   cron every 6 h plus ``workflow_dispatch``. Consumes the *even-hash*
   shard of FLUX-via-Pollinations pending cells. Time-boxed below the
   GH Actions 6 h hard cap.
2. **Layer 2 — Local async worker** (``scripts/continuous_worker.py``).
   ``asyncio`` + ``httpx`` pool against Pollinations.ai. Consumes the
   *odd-hash* shard of FLUX-via-Pollinations pending cells. Runs on
   Henry's laptop continuously between Colab/Kaggle shifts.
3. **Layer 3 — Kaggle scheduled notebook** (``notebooks/kaggle_scheduled.ipynb``).
   Runs ``diffusers`` locally on T4 for every non-Pollinations cell:
   SD 1.5, SDXL, SD 3.5 Medium (main); SD 2.1, Playground 2.5,
   Kandinsky 3, AltDiffusion-m18 (robustness); the 2-indigenous-langs
   sub-grid; and the ~5 % FLUX cross-validation sample from
   ``DESIGN.md §4.2``.

**Sharding rule.** ``apd.prompts.grid.shard_filter(image_id, shard_id,
n_shards)`` uses ``SHA256(image_id) % n_shards`` to deterministically
assign each cell to one of two FLUX shards (Layer 1 = even, Layer 2 =
odd). Workers do not coordinate; ``scripts/merge_worker_shards.py``
deduplicates as a safety net (expected overlap < 5 %).

**Self-contained shards.** Each layer writes a single parquet shard per
checkpoint containing both the generation columns and the 12 classifier
columns (face detection + ITA + MST + CASCo + 2-of-3 consensus, per
D-005). PNGs do not need to be centralised for the panel to be built —
only the metadata shards.

**Rationale.**
* No scope reduction: every cell in the locked ``prereg-v1`` grid still
  gets generated under exactly the model identifier the proposal names.
* Decouples model identifier from runtime path, per ``DESIGN.md §6.5``.
* Triple redundancy: a failure in any one layer doesn't block the others.
* Free under all three platforms: GH Actions free unlimited (public
  repo), Pollinations free relay, Kaggle 30 GPU-hours/week free tier.
* Henry runs solo — no per-coauthor account coordination needed for the
  critical path.

**Operational consequence for ``COST_LOG.md``.** Each layer appends a
row per checkpoint with ``$0.00`` marginal cost. Cumulative stays
``$0.00``.

### D-028: Extend ``images/main/metadata.parquet`` schema with 12 classifier columns

**Decision.** The canonical ``images/main/metadata.parquet`` schema
grows from 12 generation columns (image_id, model, occupation,
language, country_proxy, seed, prompt, path, sha256, backend,
duration_s, timestamp) to 24 columns. The 12 additional columns are
the classifier outputs already produced by
``scripts/04_classify_main.py``:

    has_face            bool
    n_faces             int
    ita_value           float
    ita_label           string
    ita_perla           float
    mst_value           float
    mst_perla           float
    casco_perla         float
    perla_consensus     float
    n_classifiers       int
    n_concordant        int
    concordant_2of3     bool

**Migration.** ``scripts/migrate_metadata_v2.py`` adds the 12 columns
in-place to the 50 existing rows from shift hl#1 with sentinel values
indicating "not yet classified" (``ita_label="not_classified"``,
``has_face=False``, classifier scalars = ``NaN``). The script is
idempotent and supports an optional ``--classify`` flag that runs the
classifier stack in-place for any row whose PNG is locally accessible.

**Why one table instead of joining ``data/interim/main_phenotype.parquet``.**
Self-contained shards (D-027) let workers commit a single parquet per
checkpoint containing everything needed downstream. Two-table joining
adds an extra merge step per layer per run, multiplies failure modes,
and requires the merge helper to track two parallel sets of canonical +
shard files. One table is the smaller blast radius.

**Backwards compatibility.** ``scripts/04_classify_main.py`` is
re-targeted to write directly into ``images/main/metadata.parquet``'s
new columns rather than to ``data/interim/main_phenotype.parquet``
(planned follow-up; not yet implemented at the time of this entry).
The existing 50-row hl#1 shift's gen columns are unchanged; only the
12 classifier columns are added (sentinel-filled).

**Implication for prereg-v1.** The schema extension is operational
metadata — it does not alter the locked statistical specifications
(hypotheses, BH-FDR, bootstrap, κ ≥ 0.6 threshold, master seed). No
OSF amendment needed.

### D-030: Delete 20 SD-1.5 mislabelled rows from hl#1 shift

**Decision.** Drop the 20 rows in ``images/main/metadata.parquet`` whose
``model == "runwayml/stable-diffusion-v1-5"`` AND
``backend == "pollinations"`` (the bug imprint described in D-029). After
deletion, ``images/main/metadata.parquet`` contains exactly the 30
legitimate FLUX rows from hl#1 (CEO × en × pollinations/flux × imgs
0–29). ``scripts/_fix_hl1_mislabeled.py`` performs the deletion
idempotently.

**Why deletion (and not "re-label" or "flag").** The pending-cell
machinery (``apd.prompts.grid.pending_cells``) skips any cell whose
``image_id`` is already present in the canonical or shard parquet. If
the 20 mislabelled rows stayed in metadata with a re-label or flag,
Layer 3 (Kaggle, local ``diffusers``) would never regenerate those
``runwayml/stable-diffusion-v1-5 × CEO × en × seeds[0..19]`` cells —
leaving 20 permanent holes in the SD-1.5 main-grid. The pre-registered
``prereg-v1`` grid requires every cell to be generated under the model
identifier the proposal names; "flag and forget" violates that.

**Effect on the panel.** Layer 3 will regenerate those 20 cells as
*real* SD 1.5 images via local ``diffusers`` on Kaggle T4. The
``image_id`` is deterministic (``image_id_of`` formula), so the
regenerated rows will be byte-identical in identity to the deleted
ones; only the image bytes and classifier outputs will be those of
genuine SD 1.5.

**Effect on prereg-v1.** ``DESIGN.md §6.5`` already authorises
re-routing a cell to a different backend platform when an upstream free
tier changes. This is the same provision: we move 20 cells from
"Pollinations relay" to "local diffusers on Kaggle T4" without touching
the model identifier. No OSF amendment required.

**Operational consequence for COST_LOG.md.** The 20 deleted images
cost $0.00 to generate (Pollinations free) and cost $0.00 to delete
(local). The 20 replacements on Kaggle T4 cost $0.00 (free tier, GPU
hours from the 30 h/week allowance). Cumulative stays $0.00.

### D-029: ``select_backend`` fails loud (post-mortem on hl#1 shift)

**Decision.** ``apd.generate.orchestrator.select_backend`` no longer
silently falls back to ``PollinationsBackend(model="flux")`` for HF-
repo-path identifiers when no token is configured. It now raises
``BackendUnavailableError`` with an explicit message naming the three
remediation paths: (a) use a ``pollinations/<id>`` identifier, (b) set
``HF_TOKEN`` in ``.env``, (c) install the ``ml`` extras for local
``diffusers``.

If the ``ml`` extras *are* installed, the function routes HF-repo-path
identifiers to ``LocalBackend`` with the *exact same* model — no
architecture substitution under any circumstance.

**Post-mortem on the hl#1 shift (2026-05-15).** The 50-img production
shift labelled as "FLUX via Pollinations (88 s/img)" actually contains
**30 cells with ``model="pollinations/flux"`` + ``backend="pollinations"``**
(legitimate FLUX images) and **20 cells with
``model="runwayml/stable-diffusion-v1-5"`` + ``backend="pollinations"``**
(FLUX images mislabelled as SD 1.5). Root cause: the shift notebook
iterated ``main_cells()`` which yields cells across all four main
models in order; on the SD-1.5 cells, the old ``select_backend``
detected no ``HF_TOKEN`` and silently constructed
``PollinationsBackend(model="flux")``, generating FLUX images while
the metadata recorded SD 1.5 as the architecture.

The corruption is bounded — 20 mislabelled rows out of 50, all in
``model="runwayml/stable-diffusion-v1-5" × occupation="CEO" ×
language="en" × seed in {first 20 SD-1.5 main-grid seeds}``. Cleanup
is tracked separately (see future ``D-030``); the orchestrator fix
prevents recurrence regardless of which layer (1, 2, or 3) calls it.

**Rationale.** Silent architectural substitution corrupts the panel
data downstream — H1 would have read ``f_alg(CEO, en, SD-1.5)`` from
images that were actually FLUX, producing a meaningless cell estimate.
Fail-loud is the only acceptable contract for a backend selector in a
pre-registered audit.

**Tests.** ``tests/unit/test_orchestrator_select_backend.py`` pins:
* ``"pollinations/<id>"`` → ``PollinationsBackend`` (exact identifier).
* HF repo path + no token + no ml extras → ``BackendUnavailableError``
  with all three remediation paths in the message.
* HF repo path + ml extras available → ``LocalBackend`` with the
  identical model identifier (no substitution).

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

### D-018: Q-B resolved — 4 main + 4 robustness models

**Decision.** Main confirmatory grid uses **SD 1.5, SD XL 1.0, SD 3.5
Medium, FLUX.1-schnell**. Robustness grid uses **SD 2.1, Playground v2.5,
Kandinsky 3, AltDiffusion-m18**. Total 8 models, exactly as the proposal
§4.1 specifies (§6.1's "operational reduction").
**Rationale.**
* Reducing the main grid below 4 weakens H4 (the test of whether scaling
  resolves the bias requires within-family comparisons across at least
  3–4 versions).
* Expanding past 4 main multiplies confounds (training-corpus mix, prompt
  encoder differences) without proportionate explanatory gain.
* The 4 robustness models defend the manuscript against the "you only
  tested commercial-leaning Stability AI lineage" critique by adding
  Apache-2.0 (Kandinsky 3, FLUX), multilingual (AltDiffusion) and
  aesthetic-tuned (Playground v2.5) coverage.

**Operational consequence.** Total of ~12 000 main images + 3 200
robustness ≈ 15 200 generations distributed across Colab T4, Kaggle GPU,
and Pollinations.ai per §6 of `DESIGN.md`. Weights cached per coauthor
account on Google Drive (~50 GB combined for the 8 models, one-time).

### D-019: Q-C resolved — parallel daily generation shifts

**Decision.** Each coauthor runs **one Colab T4 shift (≤90 min) + one
Kaggle GPU shift (up to 12 h) per working day** during the production
window. A shared work-queue is read from the committed prompt-grid
parquet; the orchestrator picks the next *N* pending cells, generates
them, and commits the resulting metadata shard back to the repo at
session end. The panel builder merges shards and deduplicates on
`image_id`.
**Rationale.**
* Maximises sustained throughput (≈12 800 imgs/day, per `DESIGN.md` §6.2).
* The pipeline is already idempotent (POC validated); two coauthors
  generating the same cell does no harm and saves coordination overhead.
* `images/main/metadata.parquet` becomes the single source of truth for
  "what's done", visible to all coauthors via git.
* Concretised in `notebooks/generation_shift.ipynb` (template committed).

### D-020: Q-D resolved — visual validation labellers

**Decision.** **CL (first author)** and **YP (co-author)** independently
PERLA-label the stratified 300-image sample, **blind** to all algorithmic
classifier outputs. **HL (PI)** adjudicates the cases of κ disagreement.
The labelling round happens 4 weeks before manuscript submission.
**Rationale.**
* Two-rater blind labelling produces a reportable inter-rater Cohen's κ —
  the standard reviewer-defensible metric for classifier validity.
* A PI adjudicator resolves edge cases without inflating the
  inter-rater agreement statistic itself (the κ is the *raw* CL/YP
  agreement; adjudication produces a separate "consensus ground truth"
  used as the validation reference).
* Timing 4 weeks pre-submission leaves room for re-labelling if κ < 0.6.

### D-025: OSF Pre-Registration filed (2026-05-15, 20:03 UTC-5)

**Decision.** The OSF Pre-Registration was filed under
**DOI 10.17605/OSF.IO/XFQVM** at https://osf.io/xfqvm. The
associated project (currently private) lives at https://osf.io/zkpnx.
The state of the repository at the moment of filing is permanently
pinned at the git tag `prereg-v1`.

**Coverage.** The pre-registration covers §1–§7 of `DESIGN.md`: the
five hypotheses (H1–H3 confirmatory; H4–H5 exploratory), the locked
prompt grid (25 occupations × 4 languages × 4 models × 30 imgs +
H5 marker sub-grid + robustness grid), the LAPOP 2023 + education-tier
empirical baseline (D-024), the 2-of-3 phenotype concordance rule
(D-005), the bootstrap-1 000 CI procedure, the BH-FDR-at-5%
multiple-testing correction, the κ ≥ 0.6 visual-validation threshold,
and the master seed 20260514. Three documented methodological
deviations from the binding proposal are listed verbatim in the
"Context and additional information" section of the registration
(HF Inference dropping image models; LAPOP 2023 dropping occupation
coding; MediaPipe API churn).

**Implication for the manuscript.** Any deviation from the pre-registered
specifications discovered during the production run is reported as an
explicit deviation note in the manuscript supplement, with the commit
timestamp at which the deviation was applied. Confirmatory hypotheses
cannot be re-specified after this date.

### D-024: LAPOP 2023 dropped occupation coding — use education tier as status proxy

**Decision.** Production f_emp(PERLA | study_occupation, country) is built
by (a) mapping each of the 25 study occupations to one of three
**education tiers** (primary / secondary / tertiary) and (b) computing
the empirical PERLA distribution from LAPOP 2023 conditional on the
respondent's `edre` (Nivel de educación) falling in that tier.

**Rationale.** Inspection of the four LAPOP 2023 country files revealed:
* LAPOP 2023's `ocup4a` is the *employment-status* indicator (working /
  unemployed / student / homemaker / retired / disabled / not looking)
  with 7 levels — **not** an occupation classifier. There is no ISCO,
  CIUO or industry-coded occupation variable in the wave's free files.
* `colorr` (interviewer-applied PERLA 1–11) is present and clean: clear
  modal distribution at light tones (CO mode = 3) with a long dark tail
  matching published Colombian phenotype distributions.
* `edre` (education level 0–6, from "Ninguna" through "Universitaria
  superior") shows a strong education × PERLA crosstab gradient, exactly
  the status-graded structure we need.
* `etid` (5 ethnic self-categories — Blanca/Mestiza/Indígena/Negra/Mulata)
  is present and crosses well with colorr, enabling a future
  ethnic-category-to-PERLA imputation when national surveys are wired up.

**Mapping (from crosswalks.status_tier):**
* **tertiary** (`edre ∈ {5, 6}`): CEO, doctor, software engineer, lawyer,
  university professor, architect, accountant, journalist.
* **secondary** (`edre ∈ {3, 4}`): nurse, police officer, mechanic,
  salesperson, secretary, cook, hairdresser, driver, security guard.
* **primary** (`edre ∈ {0, 1, 2}`): farmer, nanny, construction worker,
  seamstress, janitor, domestic worker, street vendor, waste collector.

**Limitations explicitly carried into the manuscript.**
* Education is a noisier proxy for occupation than ISCO codes (R ~ 0.5–0.7
  in LatAm GEIH / PNADC / ENAHO data).
* Within a tier, all study occupations share the same f_emp baseline — H2
  cannot fully separate occupations within the same tier.
* The proposal §4.2 imputation strategy (ethnic-category bridge using
  national surveys) remains the **production-grade** ground truth and is
  filed as **future work**: download GEIH 2023 / ENADIS 2022 / PNADC
  2023 / ENAHO 2023, observe (occupation × ethnic_category), combine with
  LAPOP's (ethnic_category × PERLA) for a per-occupation f_emp.

**This decision unlocks a real Colombia ground truth today** without
waiting on national-survey downloads. The manuscript reports the
education-tier baseline as the primary specification and the ethnic-
imputation baseline as a robustness check once national surveys land.

### D-023: FairFace integration deferred to second milestone

**Decision.** FairFace (gender + age + race controls, proposal §4.3) is
**deferred** to a second integration milestone *after* the LAPOP data is
in hand and a real APD panel exists. For now ``apd.classify.fairface``
stays a documented stub.
**Rationale.**
* The official FairFace weights (Karkkainen & Joo 2021) are distributed
  via Google Drive links from the project's GitHub repo, which is *not*
  a directly-scriptable download — Google Drive's free-tier downloads
  require either an authenticated user session or a third-party scraper.
  Neither fits the "zero monetary cost + no institutional credentials"
  rule cleanly.
* A Hugging Face mirror of the FairFace weights would solve this. The
  next milestone will (a) search HF Hub for an existing mirror with a
  compatible licence and (b) if absent, upload our own mirror with the
  authors' permission.
* FairFace is an *exogenous control* in the H1 / H2 regressions, not a
  primary outcome. The APD point estimates and bootstrap CIs are
  computable without it; FairFace tightens the H2 specification and
  enables the gender × pigmentocracy interaction tables but is not on
  the critical path for the first manuscript draft.

**Operational consequence.** Production H1 / H2 will be reported without
gender × race controls in the manuscript's main tables; FairFace-based
robustness specifications will appear in the supplement once the
weights are wired up.

### D-022: Masculine generic gender for Spanish and Portuguese prompts

**Decision.** The main confirmatory grid uses **masculine generic forms**
in Spanish and Portuguese (``médico``, ``ingeniero``, ``niñero``,
``costurero``, etc.) for every one of the 25 occupations. Feminine
variants enter as an **exploratory robustness specification**, not the
confirmatory grid.
**Rationale.**
* English's neutral occupational nouns ("doctor", "nurse", "nanny") map
  most cleanly onto the masculine generic in Romance languages.
* Spanish and Portuguese training corpora are dominated by masculine
  generic forms; this is the most likely prompt a real user would write
  and therefore the most ecologically valid baseline.
* Holding gender form fixed in the main grid leaves gender as a *clean
  treatment variable* for a future robustness specification (compare
  ``médico``/``médica`` outputs explicitly).
* The proposal's notation "médico/a" is honored in the supplementary
  robustness analysis. The main result is reported under masculine
  generic and the supplement reports the gender-variant gap.

**Operational consequence.** The Spanish nouns in
`src/apd/ground_truth/crosswalks.py` are stored in their masculine
singular form. ``niñera`` → ``niñero``, ``costurera`` → ``costurero``,
``empleada doméstica`` → ``empleado doméstico``.

### D-021: Q-F resolved — HL files the OSF pre-registration

**Decision.** Henry Laverde (PI) submits the OSF pre-registration form
once §1–§7 of `DESIGN.md` are locked and *before* any production-grid
image is generated.
**Rationale.**
* The PI's submission carries institutional weight for the CEI / IRB
  trail that any peer-reviewed venue may consult.
* The PI sees the entire research plan; the first author and co-author
  retain comment access on the OSF preprint for revisions.
* A single submitter avoids fork-of-truth registration ambiguity.

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
