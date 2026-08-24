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

import hashlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from apd.config import settings
from apd.ground_truth.crosswalks import POC_MAPPINGS
from apd.prompts.translations import INDIGENOUS_LANGUAGES, translate

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
    "pollinations/flux",  # FLUX schnell via Pollinations
    "runwayml/stable-diffusion-v1-5",  # SD 1.5 (Colab/Kaggle local)
    "stabilityai/stable-diffusion-xl-base-1.0",  # SD XL (Colab/Kaggle local)
    "stabilityai/stable-diffusion-3.5-medium",  # SD 3.5 Medium (Colab/Kaggle)
)
MAIN_IMAGES_PER_CELL: int = 30

# Per-language sentence template. The article is per-(language × gender)
# in ``ARTICLES``; the occupation noun is per-(occupation × language)
# from the crosswalks. The peninsular Spanish variant uses *fotografía*
# (more formal/peninsular register) vs *foto* (LatAm colloquial).
PROMPT_TEMPLATES: dict[str, str] = {
    "en": "a photo of {article}{occ}",
    "es-ES": "una fotografía de {article} {occ}",
    "es-LatAm": "una foto de {article} {occ}",
    "pt-BR": "uma foto de {article} {occ}",
}

# Indefinite article per language; masculine generic for the main grid.
# See DECISIONS.md D-022 for the gender discussion.
ARTICLES: dict[str, str] = {
    "en": "",  # special-cased: "a" vs "an"
    "es-ES": "un",
    "es-LatAm": "un",
    "pt-BR": "um",
}

# -------------------------------------------------------------------------
# PromptCell + builders
# -------------------------------------------------------------------------


@dataclass(frozen=True)
class PromptCell:
    """One (occupation, language, country, model, seed) cell of the grid.

    The ``occupation`` slot accepts both plain crosswalk keys (e.g.
    ``"doctor"``) and **marker-encoded keys** (e.g.
    ``"marker:LatAm:doctor"``). Marker keys produce H5-flavoured prompts
    that prepend a geographic adjective (e.g. "a photo of a Colombian
    doctor") for the digital-orientalism diff-in-differences.
    """

    occupation: str
    language: str
    country: str
    model: str
    seed: int

    def prompt(self) -> str:
        if is_marker_occupation(self.occupation):
            return _build_marker_prompt(self.occupation, self.language)
        if self.language in INDIGENOUS_LANGUAGES:
            # Sources document occupation phrases, not a full sentence; see
            # docs/INDIGENOUS_PROMPT_SOURCES.md.
            return _occupation_noun(self.occupation, self.language)
        template = PROMPT_TEMPLATES.get(self.language)
        if template is None:
            raise ValueError(f"unknown language {self.language!r}")
        occ_noun = _occupation_noun(self.occupation, self.language)
        article = _english_article(occ_noun) if self.language == "en" else ARTICLES[self.language]
        return template.format(article=article, occ=occ_noun)


# Marker handling is referenced by PromptCell.prompt above but defined
# below so the class definition stays compact. The two helpers are pure
# functions of strings — they do not touch shared state.
def is_marker_occupation(key: str) -> bool:
    return key.startswith("marker:")


def split_marker_key(key: str) -> tuple[str, str]:
    """Return ``(marker, occupation)`` from a synthetic marker key."""
    if not is_marker_occupation(key):
        raise ValueError(f"not a marker key: {key!r}")
    _, marker, occupation = key.split(":", 2)
    return marker, occupation


def _build_marker_prompt(marker_key: str, language: str) -> str:
    if language != "en":
        raise NotImplementedError(
            f"marker prompts are English-only in H5; got {language!r}",
        )
    marker, occupation = split_marker_key(marker_key)
    base = _occupation_noun(occupation, "en")
    adjective = H5_MARKERS[marker]
    full = f"{adjective}{base}"
    return f"a photo of {_english_article(full)}{full}"


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
    if language in INDIGENOUS_LANGUAGES:
        return translate(occupation, language)
    raise ValueError(f"no noun mapping for language {language!r}")


# Vowel-letter words that English pronounces with an initial /j/ or /w/
# consonant sound and therefore take "a", not "an".
_CONSONANT_SOUND_VOWEL_PREFIXES: tuple[str, ...] = (
    "eu",  # European, Europe
    "uni",  # university, unique, unicorn
    "use",  # useful, user
    "ute",  # uterus, utensil
    "one",  # one-year-old
)


def _english_article(noun: str) -> str:
    """'a' vs 'an' based on the leading vowel sound (heuristic).

    Letters {a, e, i, o, u} default to "an", except for the small list of
    consonant-sound-vowel prefixes (European, university, useful, etc.).
    """
    if not noun:
        return "a "
    lower = noun.lower()
    if lower[0] not in "aeiou":
        return "a "
    for prefix in _CONSONANT_SOUND_VOWEL_PREFIXES:
        if lower.startswith(prefix):
            return "a "
    return "an "


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
        "es-ES": "MX",  # peninsular Spanish prompt × Mexico microdata
        "es-LatAm": "CO",  # LatAm-generic Spanish × Colombia microdata
        "pt-BR": "BR",  # Brazilian Portuguese × Brazil microdata
    }.get(language, "CO")


def expected_main_grid_size() -> int:
    """Total cells the main grid will produce — 25 × 4 × 4 × 30 = 12 000."""
    return len(MAIN_OCCUPATIONS) * len(MAIN_LANGUAGES) * len(MAIN_MODELS) * MAIN_IMAGES_PER_CELL


# -------------------------------------------------------------------------
# H5 marker-variant grid — geographic markers for the digital-orientalism
# diff-in-differences. Proposal §3 H5: "médico colombiano" vs "American
# doctor" vs unmarked. Restricted to a subset of occupations and a single
# model to keep the budget modest (H5 is exploratory).
# -------------------------------------------------------------------------

# Subset of occupations that exercise the high-status / low-status range
# without inflating the H5 budget. Picked to balance ISCO majors 1, 2, 5, 7,
# 9 with both high-prestige and low-prestige roles.
H5_OCCUPATIONS: tuple[str, ...] = (
    "CEO",
    "doctor",
    "lawyer",
    "architect",
    "nurse",
    "construction worker",
    "domestic worker",
    "street vendor",
)
H5_MODELS: tuple[str, ...] = ("pollinations/flux",)
H5_LANGUAGE: str = "en"  # H5 holds language fixed (en) to isolate marker effect
H5_IMAGES_PER_CELL: int = 10

# Markers map to a sentence-level adjective applied to the occupation
# noun. The "unmarked" baseline is the no-adjective form used in the main
# grid; we include it explicitly here so the H5 panel ships its own
# control rows (the analysis does NOT borrow control rows from the main
# grid because seeds differ).
H5_MARKERS: dict[str, str] = {
    "unmarked": "",
    "LatAm": "Colombian ",
    "US": "American ",
    "EU": "European ",
}


def h5_cells() -> Iterator[PromptCell]:
    """H5 grid: 8 occ × 4 markers × 1 model × 10 imgs = 320 cells."""
    base = settings.seed
    for occ_idx, occ in enumerate(H5_OCCUPATIONS):
        for mk_idx, marker in enumerate(H5_MARKERS):
            for img_idx in range(H5_IMAGES_PER_CELL):
                yield PromptCell(
                    occupation=_marker_occupation_key(occ, marker),
                    language=H5_LANGUAGE,
                    country="MULTI",
                    model=H5_MODELS[0],
                    # Distinct seed namespace from the main grid: + 5_000_000_000
                    seed=cell_seed(base, occ_idx, mk_idx, 0, img_idx) + 5_000_000_000,
                )


def _marker_occupation_key(occupation: str, marker: str) -> str:
    """Encode marker into the occupation slot so PromptCell.prompt() works."""
    return f"marker:{marker}:{occupation}"


def expected_h5_grid_size() -> int:
    return len(H5_OCCUPATIONS) * len(H5_MARKERS) * len(H5_MODELS) * H5_IMAGES_PER_CELL


# -------------------------------------------------------------------------
# Robustness grid — 4 extra models + 2 indigenous languages, subset of
# occupations, lower image count (proposal §6.1 "análisis exploratorio").
# -------------------------------------------------------------------------

ROBUSTNESS_OCCUPATIONS: tuple[str, ...] = (
    "CEO",
    "doctor",
    "lawyer",
    "nurse",
    "police officer",
    "salesperson",
    "cook",
    "construction worker",
    "domestic worker",
    "street vendor",
)
ROBUSTNESS_MODELS_EXTRA: tuple[str, ...] = (
    "stabilityai/stable-diffusion-2-1",
    "playgroundai/playground-v2.5-1024px-aesthetic",
    "kandinsky-community/kandinsky-3",
    "BAAI/AltDiffusion-m18",
)
ROBUSTNESS_LANGUAGES_INDIGENOUS: tuple[str, ...] = ("qu", "gn")  # quechua, guaraní
ROBUSTNESS_IMAGES_PER_CELL: int = 10


def robustness_cells() -> Iterator[PromptCell]:
    """Robustness grid: extra-models × main-langs + main-models × indigenous-langs.

    Two complementary subsets:
    1. The 4 robustness models × 10 occupations × 4 main languages × 10
       imgs = 1 600 cells.
    2. The 4 main models × 10 occupations × 2 indigenous languages × 10
       imgs = 800 cells.

    Total: 2 400 robustness cells. The proposal §6.1 budget allows up to
    ~3 200; the rest is reserved for additional checks discovered during
    main-grid analysis.
    """
    base = settings.seed
    # Subset 1: extra models × main languages
    for occ_idx, occ in enumerate(ROBUSTNESS_OCCUPATIONS):
        for lang_idx, lang in enumerate(MAIN_LANGUAGES):
            country = "MULTI" if lang == "en" else _country_for_lang(lang)
            for model_idx, model in enumerate(ROBUSTNESS_MODELS_EXTRA):
                for img_idx in range(ROBUSTNESS_IMAGES_PER_CELL):
                    yield PromptCell(
                        occupation=occ,
                        language=lang,
                        country=country,
                        model=model,
                        # Seed offset 1e10 keeps this grid distinct.
                        seed=cell_seed(base, occ_idx, lang_idx, model_idx, img_idx)
                        + 10_000_000_000,
                    )
    # Subset 2: main models × indigenous languages
    for occ_idx, occ in enumerate(ROBUSTNESS_OCCUPATIONS):
        for lang_idx, lang in enumerate(ROBUSTNESS_LANGUAGES_INDIGENOUS):
            for model_idx, model in enumerate(MAIN_MODELS):
                for img_idx in range(ROBUSTNESS_IMAGES_PER_CELL):
                    yield PromptCell(
                        occupation=occ,
                        language=lang,
                        country="MULTI",
                        model=model,
                        seed=cell_seed(base, occ_idx, lang_idx, model_idx, img_idx)
                        + 20_000_000_000,
                    )


def expected_robustness_grid_size() -> int:
    n_occ = len(ROBUSTNESS_OCCUPATIONS)
    n_img = ROBUSTNESS_IMAGES_PER_CELL
    s1 = n_occ * len(MAIN_LANGUAGES) * len(ROBUSTNESS_MODELS_EXTRA) * n_img
    s2 = n_occ * len(ROBUSTNESS_LANGUAGES_INDIGENOUS) * len(MAIN_MODELS) * n_img
    return s1 + s2


def classify_grid(occupation: str, language: str, model: str) -> str:
    """Return which grid a generated row belongs to: main, robustness or h5.

    All three grids write into the same ``images/main/metadata.parquet``,
    but they are separate analyses: the main grid carries the full 25
    occupations (status weights sum to 1), robustness covers 10, and H5
    holds marker-encoded occupation keys that no ground truth or weight
    table contains. Mixing them in one APD table would put cells with
    incomparable weight mass side by side.
    """
    if is_marker_occupation(occupation):
        return "h5"
    if model in ROBUSTNESS_MODELS_EXTRA or language in ROBUSTNESS_LANGUAGES_INDIGENOUS:
        return "robustness"
    return "main"


# -------------------------------------------------------------------------
# Helpers for multi-worker generation (Layer 1 GH Actions / Layer 2 local
# async / Layer 3 Kaggle). These are branch-independent: they parameterise
# *what to generate next*, not *where to generate*.
# -------------------------------------------------------------------------


def image_id_of(cell: PromptCell) -> str:
    """Deterministic ``image_id`` for a cell.

    Mirrors ``apd.generate.orchestrator._image_id`` (kept in sync — same
    formula, two locations because ``orchestrator`` imports from this
    module and we want no reverse import). The format is the dedup key
    used in every shard parquet:

        ``{model_slash_to_underscore}__{occ_space_to_underscore}__{seed}``
    """
    return f"{cell.model.replace('/', '_')}__{cell.occupation.replace(' ', '_')}__{cell.seed}"


def shard_filter(image_id: str, shard_id: int, n_shards: int) -> bool:
    """Deterministic shard assignment via ``SHA256(image_id) % n_shards``.

    Used by Layer 1 (GH Actions) and Layer 2 (local async worker) to
    consume disjoint slices of the FLUX-via-Pollinations pool without
    coordination. The ``merge_worker_shards.py`` helper deduplicates any
    accidental overlap as a safety net.

    Parameters
    ----------
    image_id:
        The deterministic ``image_id`` returned by :func:`image_id_of`.
    shard_id:
        Index of this worker (``0 <= shard_id < n_shards``).
    n_shards:
        Total number of workers sharing the pool. ``n_shards = 1`` makes
        the filter a no-op (every cell belongs to this worker).
    """
    if n_shards < 1:
        raise ValueError(f"n_shards must be >= 1, got {n_shards}")
    if not (0 <= shard_id < n_shards):
        raise ValueError(f"shard_id {shard_id} out of range for n_shards {n_shards}")
    if n_shards == 1:
        return True
    h = int(hashlib.sha256(image_id.encode("utf-8")).hexdigest()[:16], 16)
    return h % n_shards == shard_id


def _read_done_image_ids(metadata_paths: Iterable[Path]) -> set[str]:
    """Union of ``image_id`` columns across every existing parquet path.

    Missing paths are silently ignored so callers can pass a glob result
    that may not exist yet. ``pandas`` is imported lazily so callers that
    don't use this helper avoid the import cost.
    """
    import pandas as pd  # local: keep grid.py importable for prompt-only callers

    done: set[str] = set()
    for p in metadata_paths:
        path = Path(p)
        if not path.exists():
            continue
        df = pd.read_parquet(path, columns=["image_id"])
        done.update(df["image_id"].astype(str).tolist())
    return done


def pending_cells(
    cells: Iterable[PromptCell],
    metadata_paths: Iterable[Path],
    *,
    shard_id: int = 0,
    n_shards: int = 1,
) -> Iterator[PromptCell]:
    """Yield cells that are not yet present in any metadata shard AND
    belong to this worker's shard.

    ``cells`` is typically the chained iterator of one or more grids,
    e.g. ``itertools.chain(main_cells(), h5_cells())``. ``metadata_paths``
    is the union of canonical ``images/main/metadata.parquet`` plus every
    ``images/main/metadata_*.parquet`` shard.

    The order of yielded cells follows ``cells``'s iteration order so
    callers can prioritise (e.g. main grid before robustness).
    """
    done = _read_done_image_ids(metadata_paths)
    for cell in cells:
        img_id = image_id_of(cell)
        if img_id in done:
            continue
        if not shard_filter(img_id, shard_id, n_shards):
            continue
        yield cell
