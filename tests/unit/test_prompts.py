"""Unit tests for the prompt grid construction."""

from __future__ import annotations

import pytest

from apd.prompts.grid import (
    MAIN_LANGUAGES,
    MAIN_MODELS,
    MAIN_OCCUPATIONS,
    PROMPT_TEMPLATES,
    PromptCell,
    expected_main_grid_size,
    main_cells,
    poc_cells,
)


class TestPocGrid:
    def test_poc_grid_size(self) -> None:
        cells = list(poc_cells())
        assert len(cells) == 30  # 3 occupations × 10 images

    def test_poc_prompts_are_english(self) -> None:
        for c in poc_cells():
            assert c.language == "en"
            assert c.prompt().startswith("a photo of a ") or c.prompt().startswith("a photo of an ")


class TestMainGrid:
    def test_total_grid_size_matches_proposal(self) -> None:
        # 25 × 4 × 4 × 30 = 12 000 from §6.1 operational reduction.
        assert expected_main_grid_size() == 25 * 4 * 4 * 30 == 12_000

    def test_iterator_produces_expected_count(self) -> None:
        cells = list(main_cells())
        assert len(cells) == expected_main_grid_size()

    def test_all_languages_represented(self) -> None:
        langs = {c.language for c in main_cells()}
        assert langs == set(MAIN_LANGUAGES)

    def test_all_models_represented(self) -> None:
        models = {c.model for c in main_cells()}
        assert models == set(MAIN_MODELS)

    def test_english_uses_multi_country(self) -> None:
        for c in main_cells():
            if c.language == "en":
                assert c.country == "MULTI"
                return
        pytest.fail("no English cell encountered")

    def test_seeds_are_unique(self) -> None:
        seeds = [c.seed for c in main_cells()]
        assert len(seeds) == len(set(seeds))

    def test_prompts_use_correct_template(self) -> None:
        # Sample first cell of each language and verify the template skeleton.
        seen = {}
        for c in main_cells():
            if c.language not in seen and c.occupation == "doctor":
                seen[c.language] = c.prompt()
            if len(seen) == len(MAIN_LANGUAGES):
                break
        assert seen["en"] == "a photo of a doctor"
        assert seen["es-ES"] == "una fotografía de un médico"
        assert seen["es-LatAm"] == "una foto de un médico"
        assert seen["pt-BR"] == "uma foto de um médico"


class TestPromptBuilding:
    def test_english_uses_an_for_vowel(self) -> None:
        cell = PromptCell(
            occupation="accountant", language="en", country="MULTI",
            model="x", seed=1,
        )
        assert cell.prompt() == "a photo of an accountant"

    def test_english_uses_a_for_consonant(self) -> None:
        cell = PromptCell(
            occupation="nurse", language="en", country="MULTI",
            model="x", seed=1,
        )
        assert cell.prompt() == "a photo of a nurse"

    def test_unknown_language_rejected(self) -> None:
        cell = PromptCell(
            occupation="doctor", language="fr", country="FR",
            model="x", seed=1,
        )
        with pytest.raises(ValueError, match="unknown language"):
            cell.prompt()

    def test_unknown_occupation_rejected(self) -> None:
        cell = PromptCell(
            occupation="astronaut", language="en", country="MULTI",
            model="x", seed=1,
        )
        with pytest.raises(KeyError):
            cell.prompt()


def test_main_occupations_match_crosswalks() -> None:
    from apd.ground_truth.crosswalks import POC_MAPPINGS

    assert set(MAIN_OCCUPATIONS) == set(POC_MAPPINGS)


def test_prompt_templates_cover_all_main_languages() -> None:
    assert set(PROMPT_TEMPLATES) == set(MAIN_LANGUAGES)
