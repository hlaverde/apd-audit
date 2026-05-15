"""CLIP zero-shot context classifier for the H5 (digital orientalism) test.

Per proposal §6.2 step 5, every generated image is scored against a
short list of contextual labels — rural, urban, modern office, artisan
workshop, folkloric landscape, neutral background — using CLIP zero-shot
classification. The probability distribution over these labels is the
per-image observable that feeds the H5 difference-in-differences design
(geographic-marker prompts vs unmarked equivalents).

We use the open OpenAI release ``openai/clip-vit-base-patch32`` (MIT
licence, ~600 MB weight download on first use). The weights load lazily
so that importing this module does not pull torch into the process
unless the scorer is actually instantiated.

Required runtime: the optional ``ml`` extras of this project
(``uv sync --extra ml``), which installs torch + transformers. Module
import succeeds without these; calling ``score`` raises a clear error
explaining how to install them.

H5 analysis recipe (downstream, in ``apd/estimate/h5.py``):
    Δp_label = P(label | marker prompt) − P(label | unmarked prompt)
implementation here keeps the scorer label-agnostic so the H5 module
can swap labels in for robustness.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default zero-shot label set from proposal §6.2 step 5.
DEFAULT_CONTEXT_LABELS: tuple[str, ...] = (
    "a rural scene",
    "an urban scene",
    "a modern office",
    "an artisan workshop",
    "a folkloric landscape",
    "a neutral background",
)

DEFAULT_MODEL_NAME: str = "openai/clip-vit-base-patch32"


@dataclass(frozen=True)
class ContextScore:
    image_id: str
    probs: dict[str, float]

    @property
    def dominant_label(self) -> str:
        return max(self.probs, key=self.probs.get)

    @property
    def dominant_prob(self) -> float:
        return self.probs[self.dominant_label]


class CLIPContextScorer:
    """Lazy wrapper around HF ``transformers`` CLIPModel + CLIPProcessor.

    Instantiation is free (no imports, no downloads). The first call to
    ``score`` materialises the model.
    """

    def __init__(
        self,
        labels: Sequence[str] = DEFAULT_CONTEXT_LABELS,
        model_name: str = DEFAULT_MODEL_NAME,
        device: str | None = None,
    ) -> None:
        self.labels: tuple[str, ...] = tuple(labels)
        self.model_name: str = model_name
        self._device_pref: str | None = device
        self._model = None
        self._processor = None
        self._torch = None  # cached after first import

    # --- public ------------------------------------------------------

    def score(self, image_path: Path, image_id: str | None = None) -> ContextScore:
        """Return a ContextScore for ``image_path``.

        Raises RuntimeError with installation instructions if the ML
        extras are not present.
        """
        self._ensure_loaded()
        # Pillow handles unicode paths on Windows via Win32 wide-char APIs,
        # so PIL.Image.open is safe where cv2.imread is not (cf. D-017).
        from PIL import Image  # noqa: WPS433

        with Image.open(image_path) as img:
            rgb = img.convert("RGB")
            inputs = self._processor(
                text=list(self.labels),
                images=rgb,
                return_tensors="pt",
                padding=True,
            )
        torch = self._torch
        with torch.no_grad():
            outputs = self._model(**inputs)
        logits_per_image = outputs.logits_per_image  # shape: (1, n_labels)
        probs = logits_per_image.softmax(dim=-1)[0].tolist()
        return ContextScore(
            image_id=image_id or image_path.stem,
            probs={label: float(p) for label, p in zip(self.labels, probs, strict=True)},
        )

    def score_many(
        self,
        image_paths: Iterable[Path],
        image_ids: Iterable[str] | None = None,
    ) -> list[ContextScore]:
        """Score a batch of images. Sequential — CLIP-B/32 on CPU runs at
        ~1–2 images/second, which is sufficient for the 12 000-image grid
        run from a single Colab shift."""
        if image_ids is None:
            image_ids = (None for _ in image_paths)
        return [self.score(p, image_id=i) for p, i in zip(image_paths, image_ids)]

    # --- internals ---------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            import torch  # noqa: WPS433
            from transformers import CLIPModel, CLIPProcessor  # noqa: WPS433
        except ImportError as exc:
            raise RuntimeError(
                "CLIP context scoring requires the 'ml' extras. "
                "Run `uv sync --extra ml` (installs torch + transformers).",
            ) from exc

        device = self._device_pref or ("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("Loading %s on %s", self.model_name, device)
        model = CLIPModel.from_pretrained(self.model_name).to(device)
        model.eval()
        processor = CLIPProcessor.from_pretrained(self.model_name)
        self._torch = torch
        self._model = model
        self._processor = processor


def is_available() -> bool:
    """Whether the optional ``ml`` extras (torch + transformers) are importable."""
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        return False
    return True
