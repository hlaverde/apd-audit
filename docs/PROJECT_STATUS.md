# PROJECT STATUS — read this first in any new session

**Last verified:** 2026-08-24, by direct inspection of this working tree
(row counts, git log, pytest run — not from memory). If you are an AI
assistant picking up this project in a new chat, read this whole file
before doing anything else. It supersedes any summary a human pastes
from an older conversation — verify against the repo, not against what
someone remembers being true.

Binding context you also need: `docs/DESIGN.md` (the locked research
design), `docs/DECISIONS.md` (every engineering/methodology decision,
numbered D-001 onward, newest at the top), `CLAUDE.md` / `AGENTS.md`
(house rules — read those too, they're short).

---

## 1. What this project is

Empirical audit of phenotype × occupation bias in open-weights
text-to-image generative AI models, calibrated against Latin-American
labour microdata (LAPOP 2023, four countries: Colombia, Mexico, Brazil,
Peru). Target journal: **Scientific Reports** (Nature Portfolio).

Three non-negotiable constraints (see `CLAUDE.md`): zero monetary cost,
100% public data, total replicability. Nothing below violates any of
these — cumulative cost is still $0.00 (`docs/COST_LOG.md`).

- **Repo:** https://github.com/hlaverde/apd-audit (public)
- **OSF pre-registration:** DOI [10.17605/OSF.IO/XFQVM](https://osf.io/xfqvm),
  filed 2026-05-15. Git tag `prereg-v1` pins the locked specification at
  that moment (confirmatory hypotheses, grid size, seeds, thresholds).
  Any deviation from what's pinned there needs a DECISIONS.md entry and,
  if it touches a confirmatory spec, a documented note for the
  manuscript supplement — not a silent change.

## 2. The headline fact: image generation is DONE

```
14 720 / 14 720 rows in images/main/metadata.parquet   (verified 2026-08-24)
unique image_id: 14 720 / 14 720 — no duplicates
```

| Grid slice | Target | Status |
|---|---:|---|
| Main confirmatory (25 occ × 4 lang × 4 models × 30) | 12 000 | ✅ complete |
| H5 marker (8 occ × 4 markers × FLUX × 10) | 320 | ✅ complete |
| Robustness — 4 extra models (10 occ × 4 lang × 10) | 1 600 | ✅ complete |
| Robustness — indigenous languages (qu/gn, 10 occ × 4 models × 10) | 800 | ✅ complete (see §3) |

By model: FLUX (Pollinations) 3 520 · SD 3.5 Medium 3 200 · SDXL 3 200 ·
SD 1.5 3 200 · SD 2.1 400 · AltDiffusion-m18 400 · Kandinsky 3 400 ·
Playground v2.5 400.

Every row already carries classifier output (`has_face`, `ita_perla`,
`mst_perla`, `casco_perla`, `perla_consensus`, `concordant_2of3`) —
computed inline at generation time (D-028's "self-contained shards"),
not a separate pending step. `has_face` fill rate is 100% (i.e. every
row was actually run through the classifier; ~72% of rows have
`has_face=True`).

**Do not re-run generation.** If a future session sees "missing images"
somewhere, check `results/missing_generation_manifest_*.csv` and this
file's row count first — it is very likely already done and the
apparent gap is something else (stale manifest, wrong grid-size
assumption, or the PNG-path issue in §4).

## 3. How it got done — three-layer automation (built May–Aug 2026)

Planned and built across several sessions (this Claude Code session,
plus — per `AGENTS.md`'s presence — apparently also a Codex session, and
manual runs by Henry). All three layers are idempotent and
sharded/deduplicated by `scripts/merge_worker_shards.py`.

1. **Layer 1 — GitHub Actions cron** (`.github/workflows/generate-flux-pollinations.yml`).
   Runs every 6h, generates FLUX-via-Pollinations cells, commits+pushes
   directly to `origin/main`. Does **not** upload artifacts — PNGs from
   this layer are not recoverable once the runner exits; only the
   metadata row (with classifier output already computed) survives.
2. **Layer 2 — local async worker** (`scripts/continuous_worker.py`).
   `asyncio` + `httpx`, `--workers 1` (Pollinations rejects concurrency
   >1, see D-026), checkpoints every N images to a local shard parquet.
   This is what generated the final indigenous-language FLUX cells.
3. **Layer 3 — Kaggle** (`docs/KAGGLE_AUTOMATED_BATCH_RUNNER.md`,
   `scripts/cloud_generation_runner.py`, `scripts/run_kaggle_batch.ps1`).
   Manifest-driven (`results/missing_generation_manifest_*.csv`), local
   `diffusers` on Kaggle T4/P100 GPU for all SD-family models. Output
   ZIPs downloaded by hand and imported via
   `scripts/import_cloud_zip.py` (workflow documented in
   `docs/MERGE_CLOUD_SHARDS_BACK_TO_LOCAL.md`). `cloud_inbox/` holds ~80
   already-imported run folders from this layer — that pipeline is
   caught up, there is no backlog of un-imported cloud ZIPs.

Key engineering findings along the way (full detail in
`docs/DECISIONS.md`):

- **D-026:** Pollinations only tolerates N=1 sequential access (~90 s/img);
  concurrent requests get HTTP 402. This is why Layer 1+2 are
  sequential, and Layer 3 (GPU, no such limit) carries the SD-family
  bulk of the grid.
- **D-029/D-030:** a silent-fallback bug in `select_backend` generated
  FLUX images but labelled 20 rows as SD-1.5 in the very first shift
  (2026-05-15). Found, fixed (now fails loud), and the 20 corrupted
  rows deleted + regenerated correctly.
- **D-032:** SD 2.1's official HF repo was retired mid-project (401/404).
  Resolved to a verified public mirror with a checksum match to the
  historical checkpoint; model identity in the locked grid unchanged.
- **D-033/D-034/D-035:** the indigenous-language (Quechua, Guaraní)
  robustness slice started with only 6/10 occupations having a
  documented public lexical source (240/800 cells). Two follow-up
  rounds of source research (Aug 13, Aug 18) found citable public
  sources (government census questionnaires, academic theses, Apertium,
  Glosbe, etc.) for the remaining occupations — **zero invented
  translations** at any point. All sources are logged with URL (and
  hash, where the source is a static file) in
  `docs/INDIGENOUS_PROMPT_SOURCES.md`. The slice is now 800/800.

## 4. PNG-path issue — RESOLVED 2026-08-24 (was 77%, now 0.75%)

**Fixed, see D-036.** The 77% figure was almost entirely a stale-string
bug, not missing data: `scripts/import_cloud_zip.py` copies PNGs into
the canonical `images/main/<occupation>/seed_<seed>.png` layout but
never rewrote the `path` column away from the Kaggle/Colab runtime's
absolute path. `scripts/fix_metadata_png_paths.py` rewrote 11 180 of
11 290 broken paths to the canonical location (verified present on
disk first, nothing guessed).

**What's actually, permanently missing: 110 / 14 720 rows (0.75%)**,
logged in `results/orphaned_png_rows.csv`:
* 90 rows — Layer-1 GitHub Actions FLUX cells. Expected, permanent
  (ephemeral runner, no artifact upload; classifier output is intact,
  only pixels are gone).
* 20 rows — the D-029/D-030 mislabelling bug's cells (CEO × en × SD1.5,
  seeds 202605140001000-019). Classifier output was recomputed
  correctly; the regenerated PNG just never got imported from Kaggle.

Neither category blocks APD (reads `perla_consensus`, not pixels). They
only matter if the visual-validation stratified sample happens to pick
one of these 110 rows — check for that when building the sample
(`apd.validate.sampling`), and either exclude them or regenerate first.

## 5. Git state — corrected diagnosis (2026-08-24, second look same day)

**Earlier today this section said "diverged 88 vs 2 commits, needs
careful reconciliation." That first diagnosis was comparing the wrong
things.** Corrected version below — read this one.

The key fact: **this repo has two branches that never merged into each
other, doing unrelated work.**

```
Active branch here:  cloud-generation-20260602
  local HEAD before today's commits: bf6c9e3 (2026-06-02)
  its own upstream:    origin/cloud-generation-20260602
  divergence from THAT upstream: essentially none (was "ahead 1",
    i.e. only this session's own new commits — not a real conflict)
  BUT the last commit actually pushed to that upstream has
    images/main/metadata.parquet at only 91 ROWS (the very first
    Kaggle smoke test, 2026-06-02). Everything generated since then —
    effectively the entire 14 720-row grid — was sitting UNCOMMITTED
    in the working tree until today (see the commit made in this
    session, "feat: consolidate ~3 months of production generation
    work (91 -> 14720 rows)").

Separate, local-only branch: main
  86-88 commits BEHIND origin/main (stale — nobody has run `git pull`
    on this local `main` branch since 2026-06-02; this is harmless,
    just means the local main ref is old)
  origin/main has ~88 "shift: GH Actions Layer-1 worker" commits —
    the GitHub Actions cron workflow, which pushes directly to
    origin/main, not to cloud-generation-20260602. It has been
    generating FLUX-via-Pollinations cells independently the whole
    time, on a branch that has NOTHING ELSE merged into it (no SD-
    family images, no indigenous-language expansion, none of the
    Kaggle work — just whatever FLUX cells Layer 1 found pending on
    each 6-hourly run).

No open or merged PR exists between these two branches
(`gh pr list --state all` returns empty). They have simply never been
reconciled.
```

**What was actually at risk, and what's been done about it (today):**

The real risk was not "conflicting data between two branches" — it was
that **three months of generation work existed in exactly one place**
(this Windows machine's working tree, uncommitted). Fixed: committed
locally to `cloud-generation-20260602` (14 720-row metadata + every
supporting script, cost-log entry, indigenous-language source
register, Kaggle run provenance), then **pushed** — Henry confirmed
explicitly. Verified after push by extracting
`origin/cloud-generation-20260602:images/main/metadata.parquet`
directly and re-counting: **14 720 rows, 14 720 unique `image_id`, on
GitHub, independent of this machine.** Push was `bf6c9e3..05a64d9`
(fast-forward, as expected — nothing else had touched that remote
branch since 2026-06-02).

**The single-machine-failure risk is closed.** What's left is not
urgent in the same way — it's normal project-hygiene and analysis work.

**What still needs a deliberate decision:**

1. ~~Push `cloud-generation-20260602`~~ — **done**, see above.
2. ~~Decide what to do about `main`~~ — **diagnosed and merged,
   2026-08-24 (D-037).** `origin/main`'s 1 743 rows were confirmed a
   *strict subset* of `cloud-generation-20260602`'s 14 720 (0 exclusive
   `image_id`s), and the two branches' GH Actions workflow files were
   byte-identical, so there was nothing to reconcile — only history to
   preserve. Executed: `git merge main -s ours` on
   `cloud-generation-20260602` (records `main`'s 88 commits as
   ancestors, tree untouched), verified post-merge (still 14 720 rows /
   14 720 unique `image_id`, tests still 248 passed / 1 skipped, `main`
   confirmed a true ancestor via `git merge-base --is-ancestor`). **Not
   yet done: fast-forwarding local `main` to this merge commit and
   pushing it to `origin/main`** — that push needs Henry's explicit
   go-ahead first (shared/public default branch; same rule as the
   earlier safety-net push). See D-037 for the full writeup.
3. Once `main` is fast-forwarded and pushed, this section should be
   shortened to a permanent one-branch description — it's long right
   now because it's a live incident writeup.

Tests are healthy on the current (still working-tree-dirty in other
respects, e.g. `.Rhistory`, `kaggle_runner/__pycache__/`, which are
deliberately not tracked) tree: **248 passed, 1 skipped**
(`uv run pytest -q`, last run 2026-08-24, re-confirmed after the D-037
merge). Skip is `test_context_clip.py` (needs `ml` extras, expected).

## 6. What's actually left (in priority order)

Generation was the expensive, slow part. It's done, and it's safely on
GitHub (§5). Everything below is analysis and writing — much faster,
and none of it is a data-loss risk anymore.

1. ~~Unify `cloud-generation-20260602` and `main`~~ — **merged locally**,
   see §5 and D-037. Only remaining step: fast-forward local `main` and
   push it to `origin/main` — **needs Henry's explicit go-ahead**
   before that push happens (shared/public default branch).
2. ~~Diagnose the PNG-path issue~~ — **done**, see §4. 110/14 720 rows
   (0.75%) are genuinely unrecoverable; noted for visual validation.
3. **Run the production analysis pipeline** — has never been run on the
   full grid. Only `results/tables/apd_poc.csv` exists, and it's the
   30-image POC from 2026-05-15. Need: build the production panel
   (`scripts/05_build_panel_main.py` or equivalent — check it still
   matches the current 24-column metadata schema from D-028), compute
   APD with real bootstrap CIs per (country, language, model) cell,
   run H1–H5 estimation (`src/apd/estimate/`) against real data.
4. **Visual validation** — 300-image stratified sample, two labellers
   blind to algorithmic output, Cohen's κ ≥ 0.6 threshold
   (`src/apd/validate/`, `scripts/08_visual_validation.py`). Exclude
   the 110 rows in `results/orphaned_png_rows.csv` from the sampling
   pool (see D-036).
5. **Manuscript** — Results section can only be written after #3.

## 7. Session log (chronological, so you know what already happened)

- **2026-05-14/15:** Project bootstrap. Skeleton, APD math, POC
  pipeline validated on 30 synthetic-then-real images. LAPOP 2023
  downloaded for all 4 countries. First production shift (50 images,
  contained the D-029/D-030 mislabeling bug, fixed).
- **2026-05-15:** GitHub repo created and pushed (`hlaverde/apd-audit`).
  OSF pre-registration filed (DOI 10.17605/OSF.IO/XFQVM), `prereg-v1`
  tag created.
- **2026-05-16 to ~06-02:** Three-layer automation architecture
  designed and built (D-026/D-027/D-028), Pollinations throughput
  probed empirically, Kaggle/Colab manifest-driven runners added.
- **~06-02 to 07-23:** Bulk of SD-family generation via Kaggle across
  dozens of tagged runs (see `cloud_inbox/` folder names for the
  granular history — batch sizes, retries, GPU profile issues like the
  P100-vs-T4 SDXL crash that's now handled in `local_backend.py`).
- **07-17:** SD 2.1 HF repo retirement discovered and worked around
  (D-032).
- **07-23:** Indigenous-language sourcing started (D-033) — 240/800
  cells enabled with documented sources; this session's continuous
  worker run (`hl-indigenous-fill`, ~120 FLUX cells) plus manual Kaggle
  runs (SD 1.5 + SDXL, "b60" batches) closed the FLUX/SD1.5/SDXL side
  of the eligible slice.
- **08-13, 08-18:** Further indigenous-language source research
  (D-034, D-035) closed the remaining occupations. Grid reaches
  14 720/14 720.
- **08-24 (today):** This file written, verified by direct inspection
  (not memory). First pass mis-diagnosed the git situation as a risky
  88-vs-2-commit divergence on `main`; on closer inspection it's a
  separate branch (`cloud-generation-20260602`) whose own upstream was
  fine, but which had 3 months of generation work (91 → 14 720 rows)
  sitting fully uncommitted. That work was committed locally to
  `cloud-generation-20260602`, then **pushed to
  `origin/cloud-generation-20260602`** after Henry's explicit
  confirmation — verified on GitHub afterward (14 720 rows, 14 720
  unique `image_id`). §5 has the corrected diagnosis. Same session,
  later: diagnosed and fixed the PNG-path issue (D-036, §4) — 11 180
  rows repaired by string rewrite, 110 genuinely orphaned and logged.
  Then diagnosed and merged the `main`/`cloud-generation-20260602`
  branch split (D-037, §5) — `git merge main -s ours`, verified clean
  (row count and tests unchanged). Still open: push the fast-forwarded
  `main` to `origin/main` (needs Henry's go-ahead, not yet asked).

## 8. If you're an AI assistant starting fresh here

Do, in order:
1. `git status` and `git log --oneline -20` — confirm §5 is still
   accurate (it may not be, if Henry reconciled git since this was
   written).
2. Read `images/main/metadata.parquet` row count — confirm §2 is still
   14 720 (or more, if new grid work was authorized — check
   `docs/DECISIONS.md` for anything past D-035 first).
3. Re-run `uv run pytest -q` — confirm code health before touching
   anything.
4. Pick up at whichever step in §6 is still open, starting from the
   top — they're ordered by dependency, not just priority.

Don't:
- Re-derive the three non-negotiable constraints from scratch — they're
  in `CLAUDE.md`/`AGENTS.md`, already enforced throughout the codebase.
- Assume anything about image counts, git state, or "what's missing"
  from a prior chat's summary (including this one, past its "last
  verified" date) without checking the live repo first.
- Touch `osf/preregistration_draft.md` or the confirmatory grid
  parameters (25 occupations, 4 main languages, 4 main models, 30
  imgs/cell, seed 20260514) without a new DECISIONS.md entry — they're
  pinned at `prereg-v1`.
