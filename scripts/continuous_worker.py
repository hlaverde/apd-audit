"""Layer 2 — local async worker for FLUX-via-Pollinations cells.

Generates pending cells from the FLUX-via-Pollinations slice of the
main + H5 grids using a pool of ``N`` concurrent asyncio streams against
Pollinations.ai. Each image is classified inline (face detection +
ITA + MST + CASCo + 2-of-3 consensus) so the worker writes a *self-
contained* shard parquet — downstream merge does not require PNGs to
be centralised.

Architecture
------------
1. Read ``images/main/metadata.parquet`` plus every ``metadata_*.parquet``
   shard in the same directory. Compute the pending set via
   ``apd.prompts.grid.pending_cells`` filtered to
   ``model == "pollinations/flux"`` and (optionally) restricted to one
   shard of an ``hash(image_id) % n_shards`` partition (so Layer 1
   on GH Actions and Layer 2 locally consume disjoint slices).
2. Spawn ``N`` async tasks sharing a single ``httpx.AsyncClient``.
   Each task: pull the next pending cell, call
   ``AsyncPollinationsBackend.generate``, write the PNG to
   ``images/main/<occ>/seed_<seed>.png``, then run the classifier stack
   in a worker thread (it is sync + CPU-bound).
3. Records accumulate in memory; every ``--checkpoint-every`` rows the
   worker flushes them to ``images/main/metadata_local_<worker_id>_<ts>.parquet``
   and appends a row to ``docs/COST_LOG.md``.
4. Every ``--push-every`` rows the worker tries
   ``git add … && git commit … && git push``; failures are logged but
   not fatal (next push attempt re-tries).
5. CTRL-C or ``--time-budget`` reached → flush in-flight records + exit.

CLI
---
    python scripts/continuous_worker.py \\
        --workers 5 \\
        --shard-id 1 --n-shards 2 \\
        --checkpoint-every 50 \\
        --push-every 200 \\
        --time-budget 18000          # 5 h
"""

# ruff: noqa: SIM105

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterable
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from apd.config import settings  # noqa: E402
from apd.generate.pollinations_backend import (  # noqa: E402
    AsyncPollinationsBackend,
    PollinationsQueueFullError,
)
from apd.prompts.grid import (  # noqa: E402
    PromptCell,
    h5_cells,
    image_id_of,
    main_cells,
    pending_cells,
    robustness_cells,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("worker")

# Filter applied to the chained main+H5+robustness grids.
FLUX_MODEL = "pollinations/flux"
_INVALID_PATH_CHARS = '<>:"/\\|?*'
_PATH_TRANSLATION = str.maketrans({char: "_" for char in _INVALID_PATH_CHARS})

# Defaults aligned with the plan; override on the CLI.
DEFAULT_WORKERS = 5
DEFAULT_SHARD_ID = 1
DEFAULT_N_SHARDS = 2
DEFAULT_CHECKPOINT_EVERY = 50
DEFAULT_PUSH_EVERY = 200
DEFAULT_TIME_BUDGET_S = 0  # 0 = unlimited


# -------------------------------------------------------------------------
# Cell enumeration
# -------------------------------------------------------------------------


def candidate_cells() -> Iterable[PromptCell]:
    """Main grid first, then H5, then robustness.

    ``pending_cells`` preserves iteration order, so the production grid
    retains priority while the local Pollinations worker can also consume
    the robustness rows assigned to it.
    """
    yield from main_cells()
    yield from h5_cells()
    yield from robustness_cells()


def pending_flux_cells(
    shard_id: int,
    n_shards: int,
    *,
    metadata_dir: Path | None = None,
) -> list[PromptCell]:
    """Pending FLUX-via-Pollinations cells assigned to this shard.

    ``metadata_dir`` defaults to ``settings.images_dir / "main"`` but can
    be overridden — useful for tests and for running workers against an
    isolated metadata directory.
    """
    if metadata_dir is None:
        metadata_dir = settings.images_dir / "main"
    paths = [metadata_dir / "metadata.parquet"]
    if metadata_dir.exists():
        paths.extend(
            p for p in metadata_dir.glob("metadata_*.parquet") if p.name != "metadata.parquet"
        )

    all_pending = pending_cells(
        candidate_cells(),
        paths,
        shard_id=shard_id,
        n_shards=n_shards,
    )
    ready: list[PromptCell] = []
    for cell in all_pending:
        if cell.model != FLUX_MODEL:
            continue
        try:
            cell.prompt()
        except ValueError:
            # Indigenous-language rows without a documented translation stay
            # pending until the source-backed prompt table is extended.
            continue
        ready.append(cell)
    return ready


# -------------------------------------------------------------------------
# Classification (inline; sync; runs in a thread)
# -------------------------------------------------------------------------


def _classify_png(png_path: Path) -> dict:
    """Run the full face_detect + ITA + MST + CASCo + consensus stack on
    a PNG. Returns a dict matching the 12-column extension from
    ``scripts/migrate_metadata_v2.py``. Imports are lazy so the worker
    can be launched on a host that lacks OpenCV (e.g., in a probe context).
    """
    from apd.classify.consensus import consensus_perla
    from apd.classify.face_detect import detect_face
    from apd.classify.skin_casco import compute_casco_perla
    from apd.classify.skin_casco import is_available as casco_available
    from apd.classify.skin_ita import compute_ita, ita_to_label, ita_to_perla
    from apd.classify.skin_mst import compute_mst, mst_to_perla

    out = {
        "has_face": False,
        "n_faces": 0,
        "ita_value": np.nan,
        "ita_label": "no_face",
        "ita_perla": np.nan,
        "mst_value": np.nan,
        "mst_perla": np.nan,
        "casco_perla": np.nan,
        "perla_consensus": np.nan,
        "n_classifiers": 0,
        "n_concordant": 0,
        "concordant_2of3": False,
    }
    face = detect_face(png_path)
    out["has_face"] = bool(face.has_face)
    out["n_faces"] = int(face.n_faces)
    if not face.has_face or face.cropped_bgr is None:
        return out
    patch = face.cropped_bgr
    ita = compute_ita(patch)
    mst = compute_mst(patch)
    ita_p = ita_to_perla(ita)
    mst_p = mst_to_perla(mst)
    casco_p = compute_casco_perla(png_path) if casco_available() else None
    consensus = consensus_perla([ita_p, mst_p, casco_p])
    out.update(
        {
            "ita_value": float(ita),
            "ita_label": ita_to_label(ita),
            "ita_perla": float(ita_p) if ita_p is not None else np.nan,
            "mst_value": float(mst),
            "mst_perla": float(mst_p) if mst_p is not None else np.nan,
            "casco_perla": float(casco_p) if casco_p is not None else np.nan,
            "perla_consensus": float(consensus.perla) if consensus.perla is not None else np.nan,
            "n_classifiers": int(consensus.n_available),
            "n_concordant": int(consensus.n_concordant),
            "concordant_2of3": bool(consensus.concordant_2of3),
        }
    )
    return out


# -------------------------------------------------------------------------
# Worker state
# -------------------------------------------------------------------------


class WorkerState:
    """Mutable shared state between async tasks and the checkpoint loop."""

    def __init__(
        self,
        worker_id: str,
        png_dir: Path,
        shards_dir: Path,
        cost_log: Path | None = None,
    ):
        self.worker_id = worker_id
        self.png_dir = png_dir
        self.shards_dir = shards_dir
        # ``cost_log = None`` means "don't append" (tests pass None to avoid
        # polluting the real ledger). Production runs pass the canonical path.
        self.cost_log = cost_log
        self.records: list[dict] = []
        self.total_done: int = 0
        self.since_last_push: int = 0
        self.consecutive_failures: int = 0
        self.shutdown = asyncio.Event()
        self.last_checkpoint_at: float = time.monotonic()

    def flush_shard(self) -> Path | None:
        """Write the in-memory records to a new shard parquet. Returns the
        path written, or None if there was nothing to flush.
        """
        if not self.records:
            return None
        ts = int(time.time())
        shard_path = self.shards_dir / f"metadata_local_{self.worker_id}_{ts}.parquet"
        df = pd.DataFrame(self.records)
        shard_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = shard_path.with_suffix(".parquet.tmp")
        df.to_parquet(tmp, index=False)
        tmp.replace(shard_path)
        n = len(self.records)
        self.records = []
        self.last_checkpoint_at = time.monotonic()
        log.info("flushed shard %s (%d rows)", shard_path.name, n)
        if self.cost_log is not None:
            _append_cost_log(self.cost_log, n)
        return shard_path


def _append_cost_log(cost_log: Path, n_imgs: int) -> None:
    line = (
        f"| {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} | shift Layer-2 worker | "
        f"Pollinations free | {n_imgs} imgs / shard checkpoint | $0.00 | **$0.00** |\n"
    )
    try:  # noqa: SIM105 - clearer with the Windows-specific explanatory comment below.
        with cost_log.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        log.warning("cost log append failed: %s", exc)


# -------------------------------------------------------------------------
# Generation pipeline (per cell)
# -------------------------------------------------------------------------


def _safe_occupation_dirname(occupation: str) -> str:
    """Return a deterministic, Windows-safe directory component."""
    safe = occupation.translate(_PATH_TRANSLATION).replace(" ", "_").rstrip(". ")
    return safe or "_"


async def process_cell(
    cell: PromptCell,
    backend: AsyncPollinationsBackend,
    client: httpx.AsyncClient,
    state: WorkerState,
) -> dict | None:
    """Generate + classify a single cell. Returns the record dict, or
    ``None`` on failure (logged)."""
    try:
        result = await backend.generate(cell.prompt(), cell.seed, client=client)
    except PollinationsQueueFullError as exc:
        log.warning("Pollinations free queue is full; pausing worker: %s", exc)
        raise
    except Exception as exc:
        log.error("generate failed for %s seed=%s: %s", cell.occupation, cell.seed, exc)
        return None
    # Write PNG locally (Windows safe path; D-017 OpenCV Unicode workaround
    # handled inside classifiers).
    occ_dir = state.png_dir / _safe_occupation_dirname(cell.occupation)
    png_path = occ_dir / f"seed_{cell.seed}.png"
    try:
        occ_dir.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(result.image_bytes)
    except OSError as exc:
        log.error("write failed for %s seed=%s: %s", cell.occupation, cell.seed, exc)
        return None
    # Classify in a worker thread (sync + IO-bound + CPU-bound).
    try:
        classification = await asyncio.to_thread(_classify_png, png_path)
    except Exception as exc:
        log.error("classify failed for %s: %s — recording as no_face", png_path.name, exc)
        classification = {
            "has_face": False,
            "n_faces": 0,
            "ita_value": np.nan,
            "ita_label": "classify_error",
            "ita_perla": np.nan,
            "mst_value": np.nan,
            "mst_perla": np.nan,
            "casco_perla": np.nan,
            "perla_consensus": np.nan,
            "n_classifiers": 0,
            "n_concordant": 0,
            "concordant_2of3": False,
        }
    return {
        "image_id": image_id_of(cell),
        "model": cell.model,
        "occupation": cell.occupation,
        "language": cell.language,
        "country_proxy": cell.country,
        "seed": cell.seed,
        "prompt": cell.prompt(),
        "path": str(png_path),
        "sha256": result.sha256,
        "backend": result.backend,
        "duration_s": result.duration_s,
        "timestamp": int(time.time()),
        **classification,
    }


async def worker_loop(
    worker_idx: int,
    queue: asyncio.Queue,
    backend: AsyncPollinationsBackend,
    client: httpx.AsyncClient,
    state: WorkerState,
    max_consecutive_failures: int,
    queue_full_wait_s: int,
) -> None:
    while not state.shutdown.is_set():
        try:
            cell = await asyncio.wait_for(queue.get(), timeout=1.0)
        except TimeoutError:
            continue
        if cell is None:
            queue.task_done()
            break
        try:
            try:
                record = await process_cell(cell, backend, client, state)
            except PollinationsQueueFullError:
                await queue.put(cell)
                wait_s = max(1, queue_full_wait_s)
                log.warning(
                    "Pollinations queue full; requeued current cell and sleeping %ds",
                    wait_s,
                )
                await asyncio.sleep(wait_s)
                continue
            if record is not None:
                state.records.append(record)
                state.total_done += 1
                state.since_last_push += 1
                state.consecutive_failures = 0
                if state.total_done % 5 == 0:
                    log.info(
                        "[w%d] %d done — pending in queue: %d",
                        worker_idx,
                        state.total_done,
                        queue.qsize(),
                    )
            if record is None:
                state.consecutive_failures += 1
                if state.consecutive_failures >= max_consecutive_failures:
                    log.warning(
                        "%d consecutive generation failures; initiating shutdown",
                        state.consecutive_failures,
                    )
                    state.shutdown.set()
                    break
        finally:
            queue.task_done()


# -------------------------------------------------------------------------
# Checkpoint + push background tasks
# -------------------------------------------------------------------------


async def checkpoint_loop(state: WorkerState, every_n: int, time_budget_s: int) -> None:
    """Flush a new shard every ``every_n`` records OR every 5 minutes,
    whichever comes first. Also enforces the time budget."""
    started = time.monotonic()
    while not state.shutdown.is_set():
        await asyncio.sleep(2.0)
        # Time budget?
        if time_budget_s > 0 and time.monotonic() - started >= time_budget_s:
            log.info("time budget %ds reached — initiating shutdown", time_budget_s)
            state.shutdown.set()
            break
        # Count-based checkpoint.
        if len(state.records) >= every_n:
            state.flush_shard()
            continue
        # Time-based checkpoint (avoid losing work if records < every_n
        # but the worker has been running for >5 min since last flush).
        if state.records and (time.monotonic() - state.last_checkpoint_at) >= 300:
            state.flush_shard()


async def push_loop(state: WorkerState, every_n: int, do_push: bool) -> None:
    while not state.shutdown.is_set():
        await asyncio.sleep(5.0)
        if state.since_last_push >= every_n:
            state.since_last_push = 0
            if do_push:
                await asyncio.to_thread(_git_push)


def _git_push() -> None:
    try:
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        subprocess.run(
            [
                "git",
                "-C",
                str(PROJECT_ROOT),
                "add",
                "images/main/metadata_local_*.parquet",
                "docs/COST_LOG.md",
            ],
            check=False,
            env=env,
            timeout=60,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(PROJECT_ROOT),
                "commit",
                "-m",
                f"shift: Layer-2 worker checkpoint {socket.gethostname()}",
            ],
            check=False,
            env=env,
            timeout=60,
        )
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "push"],
            check=False,
            env=env,
            timeout=180,
        )
        if result.returncode != 0:
            log.warning("git push exit code %d; next checkpoint will retry", result.returncode)
        else:
            log.info("git push OK")
    except Exception as exc:
        log.warning("git push failed: %s", exc)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------


async def amain(args: argparse.Namespace) -> int:
    cells_to_do = pending_flux_cells(shard_id=args.shard_id, n_shards=args.n_shards)
    log.info(
        "shard %d of %d: %d FLUX-via-Pollinations cells pending",
        args.shard_id,
        args.n_shards,
        len(cells_to_do),
    )
    if not cells_to_do:
        log.info("nothing to do — exiting cleanly")
        return 0
    png_dir = settings.images_dir / "main"
    shards_dir = png_dir
    state = WorkerState(
        worker_id=args.worker_id,
        png_dir=png_dir,
        shards_dir=shards_dir,
        cost_log=PROJECT_ROOT / "docs" / "COST_LOG.md",
    )

    queue: asyncio.Queue[PromptCell | None] = asyncio.Queue()
    for cell in cells_to_do:
        await queue.put(cell)

    backend = AsyncPollinationsBackend(model="flux", width=512, height=512)

    # Wire SIGINT to graceful shutdown.
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, state.shutdown.set)
    except NotImplementedError:
        # Windows asyncio doesn't support signal handlers in ProactorEventLoop
        # for SIGINT — KeyboardInterrupt propagates as a Python exception,
        # which we handle in main() via try/except.
        pass

    timeout_total = httpx.Timeout(300.0, connect=20.0)
    limits = httpx.Limits(max_connections=args.workers + 2, max_keepalive_connections=args.workers)
    async with httpx.AsyncClient(
        timeout=timeout_total, limits=limits, follow_redirects=True
    ) as client:
        ckpt_task = asyncio.create_task(
            checkpoint_loop(state, args.checkpoint_every, args.time_budget),
        )
        push_task = asyncio.create_task(
            push_loop(state, args.push_every, do_push=not args.no_push),
        )
        worker_tasks = [
            asyncio.create_task(
                worker_loop(
                    i,
                    queue,
                    backend,
                    client,
                    state,
                    args.max_consecutive_failures,
                    args.queue_full_wait,
                )
            )
            for i in range(args.workers)
        ]
        try:
            # Wait until the queue drains OR shutdown fires.
            await _race_queue_and_shutdown(queue, state.shutdown)
        finally:
            state.shutdown.set()
            for _ in worker_tasks:
                await queue.put(None)
            await asyncio.gather(*worker_tasks, return_exceptions=True)
            ckpt_task.cancel()
            push_task.cancel()
            await asyncio.gather(ckpt_task, push_task, return_exceptions=True)
            # Final flush + push.
            state.flush_shard()
            if not args.no_push:
                await asyncio.to_thread(_git_push)
    log.info("done: %d cells processed by worker %s", state.total_done, args.worker_id)
    return 0


async def _race_queue_and_shutdown(queue: asyncio.Queue, shutdown: asyncio.Event) -> None:
    """Return as soon as either the queue is empty or shutdown is set."""
    join_task = asyncio.create_task(queue.join())
    shutdown_task = asyncio.create_task(shutdown.wait())
    done, pending = await asyncio.wait(
        {join_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED
    )
    for t in pending:
        t.cancel()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--shard-id", type=int, default=DEFAULT_SHARD_ID)
    parser.add_argument("--n-shards", type=int, default=DEFAULT_N_SHARDS)
    parser.add_argument("--checkpoint-every", type=int, default=DEFAULT_CHECKPOINT_EVERY)
    parser.add_argument("--push-every", type=int, default=DEFAULT_PUSH_EVERY)
    parser.add_argument(
        "--time-budget", type=int, default=DEFAULT_TIME_BUDGET_S, help="seconds; 0 = unlimited"
    )
    parser.add_argument(
        "--worker-id", default=socket.gethostname().lower(), help="suffix for shard file naming"
    )
    parser.add_argument(
        "--no-push", action="store_true", help="skip git commit + push (write shard locally only)"
    )
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=5,
        help="stop after this many consecutive failed generations",
    )
    parser.add_argument(
        "--queue-full-wait",
        type=int,
        default=300,
        help="seconds to wait before retrying when the free Pollinations queue is full",
    )
    args = parser.parse_args(argv)
    try:
        return asyncio.run(amain(args))
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt — shutting down")
        return 130


if __name__ == "__main__":
    sys.exit(main())
