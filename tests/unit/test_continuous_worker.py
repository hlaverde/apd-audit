"""Unit tests for ``scripts/continuous_worker.py``.

The async I/O path is exercised with httpx.MockTransport. The classifier
stack is replaced with a no-op stub via monkeypatching so the tests stay
fast and don't require OpenCV at import time.

Covered:
* ``pending_flux_cells`` filters to ``pollinations/flux`` cells only.
* ``candidate_cells`` yields main grid first then H5.
* ``WorkerState.flush_shard`` writes parquet with all 19 columns.
* ``process_cell`` calls backend + classifier and assembles a record.
* ``_race_queue_and_shutdown`` exits early when shutdown is set.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "continuous_worker.py"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture(scope="module")
def worker_mod():
    spec = importlib.util.spec_from_file_location("continuous_worker", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["continuous_worker"] = mod
    spec.loader.exec_module(mod)
    return mod


def _no_face_classification() -> dict:
    return {
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


# -------------------------------------------------------------------------
# Cell enumeration
# -------------------------------------------------------------------------


class TestCandidateCells:
    def test_main_before_h5(self, worker_mod) -> None:
        cells = list(worker_mod.candidate_cells())
        # Main grid (12 000) precedes H5 (320).
        assert len(cells) == 12_000 + 320
        # First batch is all from main grid.
        first_models = {c.model for c in cells[:100]}
        assert "pollinations/flux" in first_models

    def test_pending_flux_cells_filters_model(self, worker_mod, tmp_path) -> None:
        # Empty metadata dir → every candidate is pending → filter to FLUX.
        cells = worker_mod.pending_flux_cells(
            shard_id=0,
            n_shards=1,
            metadata_dir=tmp_path,
        )
        # All FLUX cells in main+H5 = 3 000 main + 320 H5 = 3 320.
        # (Main grid: 25 occ × 4 lang × 4 models × 30 imgs, FLUX is 1 of 4 models.)
        assert all(c.model == worker_mod.FLUX_MODEL for c in cells)
        # H5 cells have model="pollinations/flux" too, all 320 of them.
        assert len(cells) == 3_000 + 320


# -------------------------------------------------------------------------
# WorkerState
# -------------------------------------------------------------------------


class TestWorkerStateFlush:
    def test_flush_writes_parquet(self, worker_mod, tmp_path) -> None:
        state = worker_mod.WorkerState(worker_id="testhost", png_dir=tmp_path, shards_dir=tmp_path)
        state.records.append(
            {
                "image_id": "id_a",
                "model": "pollinations/flux",
                "occupation": "CEO",
                "language": "en",
                "country_proxy": "MULTI",
                "seed": 1,
                "prompt": "a photo of a CEO",
                "path": "/tmp/foo.png",
                "sha256": "deadbeef",
                "backend": "pollinations",
                "duration_s": 1.0,
                "timestamp": 1000,
                **_no_face_classification(),
            }
        )
        shard = state.flush_shard()
        assert shard is not None and shard.exists()
        df = pd.read_parquet(shard)
        assert len(df) == 1
        # 12 gen cols + 12 classifier cols = 24.
        assert len(df.columns) == 24
        # After flush, in-memory records emptied.
        assert state.records == []

    def test_flush_empty_returns_none(self, worker_mod, tmp_path) -> None:
        state = worker_mod.WorkerState(worker_id="testhost", png_dir=tmp_path, shards_dir=tmp_path)
        assert state.flush_shard() is None


# -------------------------------------------------------------------------
# process_cell (async, with mocked backend + classifier)
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_cell_writes_png_and_record(tmp_path, monkeypatch, worker_mod) -> None:
    from apd.generate.pollinations_backend import AsyncPollinationsBackend
    from apd.prompts.grid import PromptCell

    # Stub classifier so we don't load OpenCV.
    monkeypatch.setattr(worker_mod, "_classify_png", lambda p: _no_face_classification())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=PNG_BYTES, headers={"content-type": "image/png"})

    transport = httpx.MockTransport(handler)
    state = worker_mod.WorkerState(worker_id="t", png_dir=tmp_path, shards_dir=tmp_path)
    backend = AsyncPollinationsBackend(model="flux")
    cell = PromptCell("CEO", "en", "MULTI", "pollinations/flux", 1)

    async with httpx.AsyncClient(transport=transport) as client:
        record = await worker_mod.process_cell(cell, backend, client, state)

    assert record is not None
    assert record["image_id"].endswith("__CEO__1")
    assert record["backend"] == "pollinations"
    assert record["has_face"] is False  # stubbed classifier
    # PNG written.
    png_path = Path(record["path"])
    assert png_path.exists()
    assert png_path.read_bytes() == PNG_BYTES


@pytest.mark.asyncio
async def test_process_cell_returns_none_on_backend_failure(
    tmp_path, monkeypatch, worker_mod
) -> None:
    from apd.generate import pollinations_backend as poll_mod
    from apd.generate.pollinations_backend import AsyncPollinationsBackend
    from apd.prompts.grid import PromptCell

    # Stub classifier (won't be reached).
    monkeypatch.setattr(worker_mod, "_classify_png", lambda p: _no_face_classification())
    # Disable sleeps during backoff so the test is fast.
    monkeypatch.setattr(poll_mod.asyncio, "sleep", lambda _: asyncio.sleep(0))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"down", headers={"content-type": "text/plain"})

    transport = httpx.MockTransport(handler)
    state = worker_mod.WorkerState(worker_id="t", png_dir=tmp_path, shards_dir=tmp_path)
    backend = AsyncPollinationsBackend(model="flux")
    cell = PromptCell("nurse", "en", "MULTI", "pollinations/flux", 2)

    async with httpx.AsyncClient(transport=transport) as client:
        record = await worker_mod.process_cell(cell, backend, client, state)

    assert record is None


# -------------------------------------------------------------------------
# Shutdown race
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_race_queue_and_shutdown_exits_on_shutdown(worker_mod) -> None:
    """If shutdown is set, _race_queue_and_shutdown returns even with a
    non-empty queue."""
    queue: asyncio.Queue = asyncio.Queue()
    await queue.put("never-consumed")
    shutdown = asyncio.Event()
    shutdown.set()
    await asyncio.wait_for(
        worker_mod._race_queue_and_shutdown(queue, shutdown),
        timeout=2.0,
    )


@pytest.mark.asyncio
async def test_race_queue_and_shutdown_exits_on_queue_empty(worker_mod) -> None:
    """If the queue is empty (drained), the race returns even though
    shutdown was never set."""
    queue: asyncio.Queue = asyncio.Queue()
    # task_done() count must equal put() count for queue.join() to return.
    # Empty queue → join() returns immediately.
    shutdown = asyncio.Event()
    await asyncio.wait_for(
        worker_mod._race_queue_and_shutdown(queue, shutdown),
        timeout=2.0,
    )
