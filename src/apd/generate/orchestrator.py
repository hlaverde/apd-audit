"""Generation orchestrator: pick a backend, cache to disk, return metadata.

The orchestrator is responsible for:
    1. Picking a backend (HF by default; local diffusers as documented fallback).
    2. Skipping cells whose output PNG already exists on disk (idempotency).
    3. Returning a tidy DataFrame with one row per cell, used to build
       ``images/poc/metadata.parquet``.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

import pandas as pd

from apd.config import settings
from apd.prompts.grid import PromptCell

from .hf_backend import GenerationResult, HFBackend, HFGenerationError

logger = logging.getLogger(__name__)


class Backend(Protocol):
    name: str

    def generate(self, prompt: str, seed: int) -> GenerationResult: ...


def image_path(cell: PromptCell, base_dir: Path) -> Path:
    safe_occ = cell.occupation.replace(" ", "_")
    return base_dir / safe_occ / f"seed_{cell.seed}.png"


def select_backend(model: str, *, prefer_local: bool = False) -> Backend:
    """Pick a backend.

    If ``HF_TOKEN`` is set and ``prefer_local`` is False, returns ``HFBackend``.
    Otherwise tries to construct a ``LocalBackend`` from the ``ml`` extras.
    """
    if not prefer_local and settings.hf_token:
        return HFBackend(model=model)
    # Lazy import — local backend pulls torch / diffusers from the ``ml``
    # extras which we don't install by default.
    from .local_backend import LocalBackend, is_available  # noqa: WPS433

    if not is_available():
        raise HFGenerationError(
            "Neither HF_TOKEN nor the local 'ml' extras are available. "
            "Either set HF_TOKEN in .env or run `uv sync --extra ml`.",
        )
    return LocalBackend(model=model)


def generate_poc(
    cells: Iterable[PromptCell],
    *,
    out_dir: Path | None = None,
    backend: Backend | None = None,
) -> pd.DataFrame:
    """Generate (or read from cache) every cell, return metadata DataFrame."""
    cells_list = list(cells)
    if not cells_list:
        raise ValueError("no cells to generate")
    out_dir = (out_dir or (settings.images_dir / "poc")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    backend = backend or select_backend(cells_list[0].model)
    logger.info("Backend: %s on model %s", backend.name, cells_list[0].model)

    records: list[dict] = []
    for i, cell in enumerate(cells_list, start=1):
        out_path = image_path(cell, out_dir)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if out_path.exists():
            logger.info("[%d/%d] cached: %s", i, len(cells_list), out_path.name)
            records.append(_record(cell, out_path, _sha256_of(out_path), "cache", 0.0))
            continue

        prompt = cell.prompt()
        logger.info("[%d/%d] generating %s — %r", i, len(cells_list), cell.occupation, prompt)
        result = backend.generate(prompt, cell.seed)
        out_path.write_bytes(result.image_bytes)
        records.append(_record(cell, out_path, result.sha256, result.backend, result.duration_s))

    return pd.DataFrame(records)


def _record(
    cell: PromptCell, out_path: Path, sha: str, backend_name: str, duration_s: float,
) -> dict:
    return {
        "image_id": _image_id(cell),
        "model": cell.model,
        "occupation": cell.occupation,
        "language": cell.language,
        "country_proxy": cell.country,
        "seed": cell.seed,
        "prompt": cell.prompt(),
        "path": str(out_path),
        "sha256": sha,
        "backend": backend_name,
        "duration_s": duration_s,
        "timestamp": int(time.time()),
    }


def _image_id(cell: PromptCell) -> str:
    return f"{cell.model.replace('/', '_')}__{cell.occupation.replace(' ', '_')}__{cell.seed}"


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
