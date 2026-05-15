"""Unit tests for the POC occupation crosswalks."""

from __future__ import annotations

import pytest

from apd.ground_truth.crosswalks import POC_MAPPINGS, get_mapping


def test_all_poc_occupations_have_isco_codes() -> None:
    expected = {"CEO", "nurse", "domestic worker"}
    assert set(POC_MAPPINGS) == expected
    for occ in expected:
        mapping = get_mapping(occ)
        assert mapping.isco08_minor != ""
        # ISCO-08 sub-major codes are 3-digit numerals
        assert mapping.isco08_minor.isdigit()
        assert len(mapping.isco08_minor) == 3


def test_isco_codes_are_in_the_expected_groups() -> None:
    # CEO ∈ ISCO-08 group 11 (chief executives, senior officials and legislators)
    assert get_mapping("CEO").isco08_minor.startswith("11")
    # Nurses ∈ ISCO-08 group 22 (health professionals)
    assert get_mapping("nurse").isco08_minor.startswith("22")
    # Domestic workers ∈ ISCO-08 group 91 (cleaners and helpers)
    assert get_mapping("domestic worker").isco08_minor.startswith("91")


def test_unknown_occupation_raises() -> None:
    with pytest.raises(KeyError, match="no crosswalk"):
        get_mapping("astronaut")
