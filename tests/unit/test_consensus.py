"""Unit tests for the 2-of-3 PERLA concordance rule."""

from __future__ import annotations

from apd.classify.consensus import consensus_perla


class TestConsensus:
    def test_three_identical_values(self) -> None:
        r = consensus_perla([5, 5, 5])
        assert r.perla == 5
        assert r.n_available == 3
        assert r.n_concordant == 3
        assert r.concordant_2of3 is True

    def test_two_concordant_one_outlier(self) -> None:
        r = consensus_perla([4, 5, 11])  # 4 and 5 within tol, 11 far
        assert r.perla == 5  # median of {4, 5, 11}
        assert r.n_available == 3
        assert r.n_concordant == 2  # 4 and 5 within ±1 of median 5
        assert r.concordant_2of3 is True

    def test_all_three_disagree(self) -> None:
        r = consensus_perla([2, 6, 10])  # spread > tolerance
        assert r.perla == 6  # median
        # Only one value (the median itself) is within ±1 of median.
        assert r.concordant_2of3 is False

    def test_two_only(self) -> None:
        r = consensus_perla([4, 5, None])
        assert r.perla == 4  # median of {4, 5}
        assert r.n_available == 2
        assert r.concordant_2of3 is True

    def test_one_only_cannot_be_concordant(self) -> None:
        r = consensus_perla([7, None, None])
        assert r.perla == 7
        assert r.n_available == 1
        assert r.concordant_2of3 is False

    def test_all_none_returns_none(self) -> None:
        r = consensus_perla([None, None, None])
        assert r.perla is None
        assert r.n_available == 0
        assert r.concordant_2of3 is False

    def test_tolerance_is_configurable(self) -> None:
        # With tolerance=2 a spread of 4 collapses to concordant.
        r_strict = consensus_perla([3, 5, 9], tolerance=1)
        assert r_strict.concordant_2of3 is False
        r_loose = consensus_perla([3, 5, 9], tolerance=2)
        # Median 5; with tol=2, both 3 and 5 are within ±2 of 5.
        assert r_loose.concordant_2of3 is True
