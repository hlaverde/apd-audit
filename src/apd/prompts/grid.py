"""Prompt grid construction.

Two grids live in this module:

* **POC grid** (`poc_cells`): 3 occupations × English × FLUX via Pollinations
  × 10 images = 30 cells. Validated end-to-end and committed in the POC
  artefacts.
* **Main confirmatory grid** (`main_cells`): 25 occupations × 4 languages
  × 4 models × 30 images = **12 000 cells**. The production target.

Each cell carries a deterministic seed derived from
``apd.config.settings.seed`` so re-runs reproduce byte-identical images
when the backend honours the seed parameter.

Cell-seed formula
-----------------
``seed = base * 10_000_000
        + occupation_index *  100_000
        + language_index   *   10_000
        + model_index      *    1_000
        + image_index``

The choice of multipliers keeps every (o, ℓ, m, i) tuple distinct as long
as occupation_index < 100, language_index < 10, model_index < 10 and
image_index < 1_000 — comfortably above the grid dimensions.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from apd.config import settings
from apd.ground_truth.crosswalks import POC_MAPPINGS

# -------------------------------------------------------------------------
# POC grid (back-compat — keep stable; the POC artefacts depend on it).
# -------------------------------------------------------------------------

POC_OCCUPATIONS: tuple[str, ...] = ("CEO", "nurse", "domestic worker")
POC_LANGUAGE: str = "en"
POC_COUNTRY: str = "CO"
POC_MODEL: str = "pollinations/flux"
POC_IMAGES_PER_CELL: int = 10

# -------------------------------------------------------------------------
# Main confirmatory grid (production).
# -------------------------------------------------------------------------

MAIN_OCCUPATIONS: tuple[str, ...] = tuple(POC_MAPPINGS.keys())  # 25 occupations
MAIN_LANGUAGES: tuple[str, ...] = ("en", "es-ES", "es-LatAm", "pt-BR")
MAIN_COUNTRIES: tuple[str, ...] = ("CO", "MX", "BR", "PE")
MAIN_MODELS: tuple[str, ...] = (
    "pollinations/flux",                    # FLUX schnell via Pollinations
    "runwayml/stable-diffusion-v1-5",       # SD 1.5 (Colab/Kaggle local)
    "stabilityai/stable-diffusion-xl-base-1.0",  # SD XL (Colab/Kaggle local)
    "stabilityai/stable-diffusion-3.5-medium",   # SD 3.5 Medium (Colab/Kaggle)
)
MAIN_IMAGES_PER_CELL: int = 30

# Per-language sentence template. The article is per-(language × gender)
# in ``ARTICLES``; the occupation noun is per-(occupation × language)
# from the crosswalks. The peninsular Spanish variant uses *fotografía*
# (more formal/peninsular register) vs *foto* (LatAm colloquial).
PROMPT_TEMPLATES: dict[str, str] = {
    "en":       "a photo of {article}{occ}",
    "es-ES":    "una fotografía de {article} {occ}",
    "es-LatAm": "una foto de {article} {occ}",
    "pt-BR":    "uma foto de {article} {occ}",
}

# Indefinite article per language; masculine generic for the main grid.
# See DECISIONS.md D-022 for the gender discussion.
ARTICLES: dict[str, str] = {
    "en":       "",  # special-cased: "a" vs "an"
    "es-ES":    "un",
    "es-LatAm": "un",
    "pt-BR":    "um",
}

# -------------------------------------------------------------------------
# PromptCell + builders
# -------------------------------------------------------------------------


@dataclass(frozen=True)
class PromptCell:
    """One (occupation, language, country, model, seed) cell of the grid."""

    occupation: str
    language: str
    country: str
    model: str
    seed: int

    def prompt(self) -> str:
        template = PROMPT_TEMPLATES.get(self.language)
        if template is None:
            raise ValueError(f"unknown language {self.language!r}")
        occ_noun = _occupation_noun(self.occupation, self.language)
        article = _english_article(occ_noun) if self.language == "en" else ARTICLES[self.language]
        if self.language == "en":
            return template.format(article=article, occ=occ_noun)
        return template.format(article=article, occ=occ_noun)


def _occupation_noun(occupation: str, language: str) -> str:
    """Look up the language-specific noun for an occupation."""
    if occupation not in POC_MAPPINGS:
        raise KeyError(f"unknown occupation {occupation!r}")
    m = POC_MAPPINGS[occupation]
    if language == "en":
        return m.occupation
    if language.startswith("es"):
        return m.spanish
    if language == "pt-BR":
        return m.portuguese
    raise ValueError(f"no noun mapping for language {language!r}")


def _english_article(noun: str) -> str:
    """'a' vs 'an' based on the leading vowel sound (heuristic)."""
    if not noun:
        return "a "
    first = noun[0].lower()
    # Crude rule: vowel-initial → 'an'. "university" and other y-initial
    # cases are rare in our grid and accepted as 'a university professor'
    # is in fact correct (consonant /j/ sound).
    return "an " if first in "aeiou" else "a "


def cell_seed(
    base: int,
    occupation_index: int,
    language_index: int,
    model_index: int,
    image_index: int,
) -> int:
    return (
        base * 10_000_000
        + occupation_index * 100_000
        + language_index * 10_000
        + model_index * 1_000
        + image_index
    )


# ---- POC grid (backwards compatible) ----
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
                # Keep POC seeds in the legacy short format so existing
                # cached PNGs stay valid: SEED*1000 + occ*100 + img.
                seed=base * 1000 + occ_idx * 100 + img_idx,
            )


# ---- Main confirmatory grid ----
def main_cells(
    occupations: tuple[str, ...] = MAIN_OCCUPATIONS,
    languages: tuple[str, ...] = MAIN_LANGUAGES,
    models: tuple[str, ...] = MAIN_MODELS,
    images_per_cell: int = MAIN_IMAGES_PER_CELL,
) -> Iterator[PromptCell]:
    """12 000 deterministic PromptCells for the main confirmatory grid.

    25 occupations × 4 languages × 4 models × 30 images = 12 000 cells,
    matching the proposal §6.1 operational reduction. The ``country``
    tag of each cell records which microdata baseline is used at APD
    computation time:

    * Non-English prompts anchor to their primary LatAm country (es-ES
      → Mexico, es-LatAm → Colombia, pt-BR → Brazil).
    * English prompts carry ``country = "MULTI"`` and downstream are
      compared against *every* country's f_emp, producing 4 APDs per
      (occupation, en, model) triple.
    """
    base = settings.seed
    for occ_idx, occ in enumerate(occupations):
        for lang_idx, lang in enumerate(languages):
            country = "MULTI" if lang == "en" else _country_for_lang(lang)
            for model_idx, model in enumerate(models):
                for img_idx in range(images_per_cell):
                    yield PromptCell(
                        occupation=occ,
                        language=lang,
                        country=country,
                        model=model,
                        seed=cell_seed(base, occ_idx, lang_idx, model_idx, img_idx),
                    )


def _country_for_lang(language: str) -> str:
    """Anchor a non-English prompt language to its primary LatAm country."""
    return {
        "es-ES": "MX",      # peninsular Spanish prompt × Mexico microdata
        "es-LatAm": "CO",   # LatAm-generic Spanish × Colombia microdata
        "pt-BR": "BR",      # Brazilian Portuguese × Brazil microdata
    }.get(language, "CO")


def expected_main_grid_size() -> int:
    """Total cells the main grid will produce — 25 × 4 × 4 × 30 = 12 000."""
    return (
        len(MAIN_OCCUPATIONS)
        * len(MAIN_LANGUAGES)
        * len(MAIN_MODELS)
        * MAIN_IMAGES_PER_CELL
    )
