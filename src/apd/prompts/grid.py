"""Prompt grid construction.

POC scope (this module is the only thing the POC needs):
    3 occupations × Colombia × English × SD 1.5 × 10 images = 30 cells.

Each cell carries its own deterministic seed derived from
``apd.config.settings.seed`` so re-runs reproduce byte-identical images
when the generation backend honours the seed parameter (HF Inference API
does; local diffusers does).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from apd.config import settings

POC_OCCUPATIONS: tuple[str, ...] = ("CEO", "nurse", "domestic worker")
POC_LANGUAGE: str = "en"
POC_COUNTRY: str = "CO"
POC_MODEL: str = "runwayml/stable-diffusion-v1-5"
POC_IMAGES_PER_CELL: int = 10


@dataclass(frozen=True)
class PromptCell:
    occupation: str
    language: str
    country: str
    model: str
    seed: int

    def prompt(self) -> str:
        if self.language != "en":
            raise NotImplementedError(
                f"POC uses English only; got language={self.language!r}",
            )
        # Indefinite article is intentional — keeps the prompt minimal so that
        # phenotype differences are attributable to the occupation alone.
        article = "an" if self.occupation[0].lower() in "aeiou" else "a"
        return f"a photo of {article} {self.occupation}"


def cell_seed(base: int, occupation_index: int, image_index: int) -> int:
    return base * 1000 + occupation_index * 100 + image_index


def poc_cells() -> Iterator[PromptCell]:
    """30 deterministic PromptCells for the POC."""
    base = settings.seed
    for occ_idx, occ in enumerate(POC_OCCUPATIONS):
        for img_idx in range(POC_IMAGES_PER_CELL):
            yield PromptCell(
                occupation=occ,
                language=POC_LANGUAGE,
                country=POC_COUNTRY,
                model=POC_MODEL,
                seed=cell_seed(base, occ_idx, img_idx),
            )
