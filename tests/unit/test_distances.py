"""Unit tests for W_1 over the PERLA ordinal lattice."""

from __future__ import annotations

import numpy as np
import pytest

from apd.apd.distances import wasserstein1_perla


def _onehot(idx: int, n: int = 11) -> np.ndarray:
    v = np.zeros(n)
    v[idx] = 1.0
    return v


class TestWasserstein1Perla:
    def test_identical_distributions_have_zero_distance(self) -> None:
        p = np.array([0.1, 0.2, 0.2, 0.2, 0.1, 0.05, 0.05, 0.05, 0.025, 0.025, 0.0])
        assert wasserstein1_perla(p, p) == pytest.approx(0.0)

    def test_unit_shift_costs_one(self) -> None:
        # All mass at PERLA 1 vs all mass at PERLA 2 → W_1 = 1
        assert wasserstein1_perla(_onehot(0), _onehot(1)) == pytest.approx(1.0)

    def test_ten_step_shift_costs_ten(self) -> None:
        # PERLA 1 vs PERLA 11 → W_1 = 10
        assert wasserstein1_perla(_onehot(0), _onehot(10)) == pytest.approx(10.0)

    def test_symmetric(self) -> None:
        p = _onehot(2)
        q = _onehot(7)
        assert wasserstein1_perla(p, q) == pytest.approx(wasserstein1_perla(q, p))

    def test_rejects_nonnormalised(self) -> None:
        with pytest.raises(ValueError, match="sum to 1"):
            wasserstein1_perla([0.5, 0.5, 0, 0, 0, 0, 0, 0, 0, 0, 0.5], _onehot(0))

    def test_rejects_negative_probabilities(self) -> None:
        bad = np.zeros(11)
        bad[0] = 1.2
        bad[1] = -0.2
        with pytest.raises(ValueError, match="non-negative"):
            wasserstein1_perla(bad, _onehot(0))

    def test_rejects_shape_mismatch(self) -> None:
        with pytest.raises(ValueError, match="shape mismatch"):
            wasserstein1_perla([0.5, 0.5], [0.2, 0.3, 0.5])

    def test_uniform_vs_uniform_is_zero(self) -> None:
        u = np.full(11, 1 / 11)
        assert wasserstein1_perla(u, u) == pytest.approx(0.0)

    def test_uniform_vs_concentrated_is_finite(self) -> None:
        u = np.full(11, 1 / 11)
        c = _onehot(5)
        d = wasserstein1_perla(u, c)
        # All mass moves from positions 1..11 to position 6 (PERLA index 5+1).
        # Mean of |k - 6| for k in 1..11 = (5+4+3+2+1+0+1+2+3+4+5)/11 = 30/11.
        assert d == pytest.approx(30 / 11)
