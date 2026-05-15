"""Unit tests for the occupation crosswalks."""

from __future__ import annotations

import pytest

from apd.ground_truth.crosswalks import (
    POC_MAPPINGS,
    all_isco08_minor_codes,
    get_mapping,
    occupations_by_tier,
)

# The proposal §6.1 grid is 25 occupations spanning ISCO-08 majors 1..9.
EXPECTED_COUNT = 25
EXPECTED_TIERS = {"high", "medium", "low"}


class TestCrosswalkCoverage:
    def test_25_occupations_registered(self) -> None:
        assert len(POC_MAPPINGS) == EXPECTED_COUNT

    def test_all_have_three_digit_isco_minor(self) -> None:
        for name, m in POC_MAPPINGS.items():
            assert m.isco08_minor.isdigit() and len(m.isco08_minor) == 3, (
                f"{name}: isco08_minor must be 3-digit numeric, got {m.isco08_minor!r}"
            )

    def test_all_have_one_digit_isco_major(self) -> None:
        for name, m in POC_MAPPINGS.items():
            major = m.derived_major
            assert major.isdigit() and len(major) == 1, f"{name}: bad major {major!r}"
            assert m.isco08_minor.startswith(major), (
                f"{name}: minor {m.isco08_minor} must start with major {major}"
            )

    def test_status_tiers_use_canonical_labels(self) -> None:
        for name, m in POC_MAPPINGS.items():
            assert m.status_tier in EXPECTED_TIERS, (
                f"{name}: status_tier {m.status_tier!r} not in {EXPECTED_TIERS}"
            )

    def test_all_have_translations(self) -> None:
        for name, m in POC_MAPPINGS.items():
            assert m.spanish, f"{name} missing Spanish translation"
            assert m.portuguese, f"{name} missing Portuguese translation"

    def test_distribution_across_status_tiers(self) -> None:
        # The grid mixes high/medium/low to exercise the H2 gradient.
        for tier in EXPECTED_TIERS:
            occs = occupations_by_tier(tier)
            assert len(occs) >= 3, f"only {len(occs)} occupations in tier {tier!r}"


class TestKeyAnchors:
    """Spot-checks on a handful of well-known ISCO assignments."""

    def test_ceo_is_managing_directors(self) -> None:
        assert get_mapping("CEO").isco08_minor == "112"
        assert get_mapping("CEO").derived_major == "1"

    def test_doctor_is_medical_professional(self) -> None:
        assert get_mapping("doctor").isco08_minor == "221"

    def test_nurse_is_nursing_professional(self) -> None:
        assert get_mapping("nurse").isco08_minor == "222"

    def test_domestic_worker_is_elementary_cleaner(self) -> None:
        m = get_mapping("domestic worker")
        assert m.isco08_minor == "911"
        assert m.derived_major == "9"


class TestErrors:
    def test_unknown_occupation_raises(self) -> None:
        with pytest.raises(KeyError, match="no crosswalk"):
            get_mapping("astronaut")


def test_all_isco_minor_codes_sorted() -> None:
    codes = all_isco08_minor_codes()
    assert codes == sorted(codes)
    # 25 occupations may collapse to fewer minor codes (some share an ISCO
    # group like janitor + domestic worker = 911), but should still cover
    # at least 20 distinct minor groups.
    assert len(codes) >= 20
