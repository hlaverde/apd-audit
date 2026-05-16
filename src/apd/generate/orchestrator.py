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

from .hf_backend import GenerationResult, HFBackend
from .pollinations_backend import PollinationsBackend

logger = logging.getLogger(__name__)


class Backend(Protocol):
    name: str

    def generate(self, prompt: str, seed: int) -> GenerationResult: ...


def image_path(cell: PromptCell, base_dir: Path) -> Path:
    safe_occ = cell.occupation.replace(" ", "_")
    return base_dir / safe_occ / f"seed_{cell.seed}.png"


class BackendUnavailableError(RuntimeError):
    """Raised when no backend can faithfully serve the requested model.

    Replaces the previous silent fallback to ``PollinationsBackend(model="flux")``
    which caused the hl#1 shift (2026-05-15) to label 20 SD-1.5 cells with
    FLUX images. See ``DECISIONS.md`` for the post-mortem entry.
    """


def select_backend(model: str, *, prefer_local: bool = False) -> Backend:
    """Pick a backend for ``model`` *or fail loudly*.

    Resolution order:

    1. ``prefer_local=True`` → always ``LocalBackend`` (requires ``ml``
       extras; raises ``BackendUnavailableError`` if not installed).
    2. ``model`` starts with ``"pollinations/"`` → ``PollinationsBackend``
       with the suffix as the relay model identifier (``flux``,
       ``flux-realism``, ``turbo``, …).
    3. ``model`` looks like a Hugging Face repo path AND ``HF_TOKEN`` is
       set → ``HFBackend``.
    4. ``model`` looks like a Hugging Face repo path AND the ``ml`` extras
       are installed → ``LocalBackend`` (diffusers on CPU/GPU).
    5. Otherwise → ``BackendUnavailableError`` with an explicit message.

    Critically, the function NEVER silently substitutes one open-weights
    model for another. The previous behaviour ("default to Pollinations
    FLUX") routed SD 1.5 / SDXL / SD 3.5 cells through FLUX in the hl#1
    shift, mislabelling 20 rows. The new contract:

    * Callers passing ``"pollinations/<id>"`` get exactly that relay.
    * Callers passing an HF repo path get HF or local diffusers — same
      open weights, no architecture substitution.
    * If neither path is feasible (no token, no ml extras), the call
      fails so the caller (worker, notebook, shift) can fix the
      environment instead of silently corrupting metadata.
    """
    if prefer_local:
        from .local_backend import LocalBackend, is_available  # noqa: WPS433

        if not is_available():
            raise BackendUnavailableError(
                f"Cannot serve {model!r} via LocalBackend: 'ml' extras not "
                "installed. Run `uv sync --extra ml` first.",
            )
        return LocalBackend(model=model)

    # 1. Pollinations relay (explicit identifier).
    if model.startswith("pollinations/"):
        return PollinationsBackend(model=model.split("/", 1)[1])

    # 2. HF Inference Providers (when token present).
    if "/" in model and settings.hf_token:
        return HFBackend(model=model)

    # 3. Local diffusers fallback (when ml extras installed).
    if "/" in model:
        try:
            from .local_backend import LocalBackend, is_available  # noqa: WPS433

            if is_available():
                return LocalBackend(model=model)
        except ImportError:  # pragma: no cover — defensive; is_available also catches this
            pass

    # 4. Fail-loud: do NOT substitute a different open-weights model.
    raise BackendUnavailableError(
        f"No backend available for model {model!r}. The previous fallback "
        f"(silent route to Pollinations FLUX) corrupted the hl#1 shift. "
        f"Pick one: (a) use 'pollinations/<id>' identifier for FLUX/Turbo "
        f"via the public relay; (b) set HF_TOKEN in .env for HF Inference; "
        f"(c) `uv sync --extra ml` + run on a GPU host for local diffusers.",
    )


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
    cell: PromptCell,
    out_path: Path,
    sha: str,
    backend_name: str,
    duration_s: float,
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
