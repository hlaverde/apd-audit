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

## 4. Known issue — most PNG files aren't reachable from this machine

**This does not block APD computation** (which only reads
`perla_consensus` etc. from the parquet), but it blocks anything that
needs the actual pixels (visual validation, manuscript figure examples).

```
11 290 / 14 720 rows (77%) have a `path` column pointing to a file that
does not exist on this Windows machine.
```

Breakdown: all `backend="local"` rows (11 200 — everything generated via
`diffusers` on Kaggle/Colab GPU) plus 90 `backend="pollinations"` rows
(Layer-1 GitHub Actions images, which — per §3 — never had a
locally-reachable PNG to begin with; expected and permanent).

For the 11 200 Kaggle/Colab rows: the PNGs likely **do exist somewhere**
(either still in an un-imported ZIP, or imported but under a different
local path than what's recorded in the `path` column — the cloud
runtime's absolute path may not have been rewritten on import). This
needs investigation before trusting it's unrecoverable:
1. Check whether `images/main/<occupation>/seed_<seed>.png` exists at
   the *canonical* layout path for a sample of these rows (the
   generators all write there — `scripts/continuous_worker.py`'s
   `_safe_occupation_dirname` convention) even though the `path` column
   says something else.
2. If yes: this is a metadata bug (stale `path` strings), fixable by
   rewriting the column from `image_id` — cheap, no regeneration needed.
3. If the PNGs are genuinely gone: decide whether visual validation can
   proceed on the ~23% subset with reachable PNGs (still likely >300
   images, i.e. probably still enough for the pre-registered sample),
   or whether specific cells need re-generating.

**Nobody has actually diagnosed which of these is true yet.** This is
the first thing a new session should check before doing anything else
with images.

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
(this Windows machine's working tree, uncommitted). That's now fixed:
a commit was made on `cloud-generation-20260602` capturing the full
14 720-row metadata, every supporting script, every cost-log entry, the
indigenous-language source register, and the Kaggle run provenance.
**That commit exists locally but has NOT been pushed yet** — pushing
is a network/GitHub action, so it's waiting on an explicit go-ahead
rather than being done automatically. It would be a plain fast-forward
push to `origin/cloud-generation-20260602` (no conflict, since nothing
else has touched that remote branch since 2026-06-02).

**What still needs a deliberate decision (not done automatically):**

1. **Push `cloud-generation-20260602`** to its own remote — safe,
   fast-forward, zero risk of overwriting anyone else's work. This is
   the single highest-value pending action; ask Henry before doing it
   (pushing is a "confirm first" action per house rules even when it's
   this safe).
2. **Decide what to do about `main`.** Two independent branches with
   real, non-overlapping content (Layer 1's FLUX-only commits on
   `main`; everything else on `cloud-generation-20260602`) is not a
   stable end state for a repo whose README/OSF registration describe
   a single canonical pipeline. Options: merge `cloud-generation-20260602`
   into `main` (making `cloud-generation-20260602`'s 14 720-row
   metadata the base, then re-applying/discarding Layer 1's FLUX-only
   commits — check whether Layer 1's cells are already a subset of the
   14 720, which is likely), or open a PR, or repoint the GH Actions
   workflow at `cloud-generation-20260602` instead of `main` going
   forward. Not diagnosed in detail yet — do that before touching it.
3. Once (1) and (2) are settled, `docs/PROJECT_STATUS.md` should be
   updated again to say so (and this section shortened — it's long
   because it's a live incident writeup, not a permanent description).

Tests are healthy on the current (still working-tree-dirty in other
respects, e.g. `.Rhistory`, `kaggle_runner/__pycache__/`, which are
deliberately not tracked) tree: **248 passed, 1 skipped**
(`uv run pytest -q`, last run 2026-08-24). Skip is
`test_context_clip.py` (needs `ml` extras, expected).

## 6. What's actually left (in priority order)

Generation was the expensive, slow part. It's done. Everything below is
analysis and writing — much faster.

1. **Push the safety-net commit** (§5) — currently sitting local-only
   on `cloud-generation-20260602`. Fast-forward, zero risk, just needs
   Henry's go-ahead since pushing is a confirm-first action.
2. **Decide how to unify `cloud-generation-20260602` and `main`** (§5)
   — not yet diagnosed in detail (does Layer 1's FLUX-only work on
   `main` overlap with what's already in the 14 720-row grid, or add
   anything new?). Do that diagnosis before merging either direction.
3. **Diagnose the PNG-path issue** (§4) — blocks visual validation and
   figure generation; does not block APD.
4. **Run the production analysis pipeline** — has never been run on the
   full grid. Only `results/tables/apd_poc.csv` exists, and it's the
   30-image POC from 2026-05-15. Need: build the production panel
   (`scripts/05_build_panel_main.py` or equivalent — check it still
   matches the current 24-column metadata schema from D-028), compute
   APD with real bootstrap CIs per (country, language, model) cell,
   run H1–H5 estimation (`src/apd/estimate/`) against real data.
5. **Visual validation** — 300-image stratified sample, two labellers
   blind to algorithmic output, Cohen's κ ≥ 0.6 threshold
   (`src/apd/validate/`, `scripts/08_visual_validation.py`). Blocked on
   #3 (need reachable PNGs for whichever images the stratified sample
   selects).
6. **Manuscript** — Results section can only be written after #4.

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
  sitting fully uncommitted. That work is now committed locally to
  `cloud-generation-20260602` (not yet pushed — needs Henry's
  go-ahead). §5 has the corrected diagnosis; treat the version in this
  section as the summary and §5 as the detail.

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
