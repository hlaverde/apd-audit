"""Unit tests for the status_weights module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from apd.ground_truth.status_weights import (
    status_weights_from_lapop,
    status_weights_prior,
)


class TestPrior:
    def test_returns_one_row_per_occupation(self) -> None:
        out = status_weights_prior(["CEO", "nurse", "domestic worker"])
        assert len(out) == 3
        assert set(out["occupation"]) == {"CEO", "nurse", "domestic worker"}

    def test_weights_sum_to_one(self) -> None:
        out = status_weights_prior(["CEO", "nurse", "domestic worker"])
        assert out["weight"].sum() == pytest.approx(1.0)

    def test_ceo_has_largest_weight(self) -> None:
        out = status_weights_prior(["CEO", "nurse", "domestic worker"])
        weights = out.set_index("occupation")["weight"]
        assert weights["CEO"] > weights["nurse"] > weights["domestic worker"]

    def test_unknown_occupation_raises(self) -> None:
        with pytest.raises(KeyError, match="no income prior for occupations"):
            status_weights_prior(["astronaut"])

    def test_unknown_country_raises(self) -> None:
        with pytest.raises(KeyError, match="no income prior for country"):
            status_weights_prior(["CEO"], country="ZZ")

    def test_supports_all_four_target_countries(self) -> None:
        # Every target country in the proposal must have a prior.
        for country in ("CO", "MX", "BR", "PE"):
            out = status_weights_prior(["CEO", "nurse", "domestic worker"], country=country)
            assert out["country"].iloc[0] == country
            assert out["weight"].sum() == pytest.approx(1.0)


@pytest.fixture
def lapop_with_income() -> pd.DataFrame:
    rng = np.random.default_rng(20260514)
    rows = []
    # ISCO majors 1..9, income decreasing with status as a real-world expectation
    base_income_by_major = {1: 10_000, 2: 8_000, 3: 6_000, 4: 4_500,
                            5: 3_500, 6: 2_500, 7: 2_800, 8: 3_000, 9: 1_500}
    for major, mean_inc in base_income_by_major.items():
        for _ in range(60):
            rows.append(
                {
                    "pais": 8,
                    "OCCUP4A": major,
                    "Q10NEW": float(rng.normal(mean_inc, mean_inc * 0.15)),
                },
            )
    # 30 missing-sentinel rows
    for _ in range(30):
        rows.append({"pais": 8, "OCCUP4A": int(rng.integers(1, 10)), "Q10NEW": 88})
    return pd.DataFrame(rows)


class TestLapopPath:
    def test_uses_real_income_when_present(self, lapop_with_income: pd.DataFrame) -> None:
        out = status_weights_from_lapop(
            lapop_with_income,
            ["CEO", "nurse", "domestic worker"],
            country="CO", country_code=8,
        )
        assert (out["weight_source"] == "lapop").all()
        # CEO (ISCO 1, highest base income) should outrank domestic worker (ISCO 9).
        weights = out.set_index("occupation")["weight"]
        assert weights["CEO"] > weights["domestic worker"]

    def test_falls_back_to_prior_when_income_column_missing(self) -> None:
        df = pd.DataFrame(
            {"pais": [8] * 5, "OCCUP4A": [1, 2, 9, 5, 6]},
        )
        out = status_weights_from_lapop(
            df,
            ["CEO", "nurse", "domestic worker"],
            country="CO", country_code=8,
        )
        assert (out["weight_source"] == "prior").all()

    def test_falls_back_when_no_rows_for_country(self, lapop_with_income: pd.DataFrame) -> None:
        # Use a country code absent in the fixture.
        out = status_weights_from_lapop(
            lapop_with_income,
            ["CEO", "nurse"],
            country="MX", country_code=1,
        )
        assert (out["weight_source"] == "prior").all()

    def test_weights_sum_to_one_with_real_data(self, lapop_with_income: pd.DataFrame) -> None:
        out = status_weights_from_lapop(
            lapop_with_income,
            ["CEO", "doctor", "nurse", "domestic worker"],
            country="CO", country_code=8,
        )
        assert out["weight"].sum() == pytest.approx(1.0)

    def test_sentinel_incomes_dropped(self, lapop_with_income: pd.DataFrame) -> None:
        # 88 is a sentinel; remove all real income rows so only sentinels remain.
        only_sentinels = lapop_with_income[lapop_with_income["Q10NEW"] == 88]
        out = status_weights_from_lapop(
            only_sentinels,
            ["CEO", "nurse"],
            country="CO", country_code=8,
        )
        # All-sentinel input falls back to the prior.
        assert (out["weight_source"] == "prior").all()
