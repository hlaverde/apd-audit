"""Local ``diffusers`` fallback backend.

Network-free generation on CPU (or GPU if available). Used by Layer 3
(Kaggle scheduled notebook) for SD 1.x / SD XL / SD 3.5 Medium / FLUX
schnell and the 4 robustness models (Playground v2.5, Kandinsky 3,
AltDiffusion-m18, SD 2.1). Requires the optional ``ml`` extras:

    uv sync --extra ml

GPU (T4) generation is fast (~3-5 s/img for SD 1.5, ~12 s/img for SDXL).
CPU is slow (~5-10 min/img for SD 1.5) and acceptable only for the POC.

The pipeline class is auto-detected via ``AutoPipelineForText2Image``
because the locked main+robustness grid (D-018) spans four architecture
families that each ship a different ``StableDiffusion*Pipeline``
subclass. Loading SDXL weights through the plain ``StableDiffusionPipeline``
silently misuses the two-text-encoder architecture and the first call
to ``pipe(prompt=...)`` raises ``argument of type 'NoneType' is not
iterable`` — the exact failure observed on the 2026-05-20 Kaggle Layer 3
run (40 SDXL cells failed in a row before SD 3.5 Medium hit a 401).
"""

from __future__ import annotations

import hashlib
import io
import logging
import time

from apd.config import settings

from .hf_backend import GenerationResult

logger = logging.getLogger(__name__)

MODEL_SOURCE_OVERRIDES = {
    # The official SD 2.1 Hub repository was retired after the grid was
    # locked. This public mirror exposes the historical 768 EMA checkpoint
    # under the independently documented SHA-256 recorded in D-032.
    "stabilityai/stable-diffusion-2-1": "sd2-community/stable-diffusion-2-1",
}


class LocalBackend:
    name = "local"

    def __init__(self, model: str, device: str | None = None) -> None:
        self.model = model
        self.model_source = MODEL_SOURCE_OVERRIDES.get(model, model)
        # Lazy-import torch only when this backend is actually used so that
        # importing the package does not pull torch into the dependency tree
        # of users running the HF-only path.
        import torch  # noqa: WPS433
        from diffusers import AutoPipelineForText2Image  # noqa: WPS433

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        logger.info(
            "Loading requested model %s from %s on %s (dtype=%s)",
            model,
            self.model_source,
            self.device,
            dtype,
        )
        # AutoPipelineForText2Image reads ``model_index.json`` from the
        # checkpoint and instantiates the correct subclass: SD 1.x / 2.x →
        # StableDiffusionPipeline; SDXL → StableDiffusionXLPipeline; SD 3.x →
        # StableDiffusion3Pipeline; FLUX → FluxPipeline; Kandinsky →
        # KandinskyV22Pipeline; etc.
        pipeline_cls = AutoPipelineForText2Image
        if model == "BAAI/AltDiffusion-m18":
            from diffusers import AltDiffusionPipeline  # noqa: WPS433
            from diffusers.pipelines.deprecated.alt_diffusion.modeling_roberta_series import (  # noqa: WPS433
                RobertaSeriesModelWithTransformation,
            )
            from transformers import XLMRobertaTokenizer  # noqa: WPS433

            pipeline_cls = AltDiffusionPipeline
        load_kwargs = {"torch_dtype": dtype}
        if model == "BAAI/AltDiffusion-m18":
            # The checkpoint's 2023 model_index references the retired
            # ``alt_diffusion`` dynamic module. Supplying these two public
            # components explicitly keeps modern diffusers from resolving it.
            load_kwargs["text_encoder"] = RobertaSeriesModelWithTransformation.from_pretrained(
                model, subfolder="text_encoder", torch_dtype=dtype
            )
            load_kwargs["tokenizer"] = XLMRobertaTokenizer.from_pretrained(
                model, subfolder="tokenizer"
            )
        if model == "kandinsky-community/kandinsky-3":
            load_kwargs["variant"] = "fp16"
            load_kwargs["use_safetensors"] = True
        self.pipe = pipeline_cls.from_pretrained(
            self.model_source,
            **load_kwargs,
        )
        if model == "kandinsky-community/kandinsky-3" and self.device == "cuda":
            self.pipe.enable_sequential_cpu_offload()
        elif model == "stabilityai/stable-diffusion-3.5-medium" and self.device == "cuda":
            self.pipe.enable_model_cpu_offload()
        else:
            self.pipe = self.pipe.to(self.device)
        # SD 1.x and SD 2.x ship a safety_checker we disable for the audit
        # (DESIGN.md §6.4: we report no_face rates as a diagnostic, we don't
        # want the safety filter dropping images silently). Other pipeline
        # classes (SDXL, SD3, FLUX, Kandinsky) don't have safety_checker.
        if hasattr(self.pipe, "safety_checker"):
            self.pipe.safety_checker = None
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
