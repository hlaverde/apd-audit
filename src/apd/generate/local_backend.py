"""Local ``diffusers`` fallback backend.

Network-free generation on CPU (or GPU if available). Used only when HF
Inference is unreachable; documented in DECISIONS.md D-004 as the
zero-cost fallback. Requires the optional ``ml`` extras:

    uv sync --extra ml

CPU generation is slow (~5–10 min/image for SD 1.5 on a laptop); this is
acceptable for the 30-image POC but not for the full study.
"""

from __future__ import annotations

import hashlib
import io
import logging
import time

from apd.config import settings

from .hf_backend import GenerationResult

logger = logging.getLogger(__name__)


class LocalBackend:
    name = "local"

    def __init__(self, model: str, device: str | None = None) -> None:
        self.model = model
        # Lazy-import torch only when this backend is actually used so that
        # importing the package does not pull torch into the dependency tree
        # of users running the HF-only path.
        import torch  # noqa: WPS433
        from diffusers import StableDiffusionPipeline  # noqa: WPS433

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        logger.info("Loading %s on %s (dtype=%s)", model, self.device, dtype)
        self.pipe = StableDiffusionPipeline.from_pretrained(
            model,
            torch_dtype=dtype,
            safety_checker=None,
        ).to(self.device)
        self._torch = torch

    def generate(self, prompt: str, seed: int) -> GenerationResult:
        started = time.time()
        generator = self._torch.Generator(device=self.device).manual_seed(int(seed))
        out = self.pipe(prompt=prompt, generator=generator, num_inference_steps=25)
        image = out.images[0]
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        content = buf.getvalue()
        return GenerationResult(
            image_bytes=content,
            sha256=hashlib.sha256(content).hexdigest(),
            backend=self.name,
            duration_s=time.time() - started,
        )


# Lightweight check used by the orchestrator before instantiating the heavy
# pipeline class. Returns True iff the optional ``ml`` extras are available.
def is_available() -> bool:
    try:
        import diffusers  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


_ = settings  # silence unused-import warnings in environments where settings isn't read here
