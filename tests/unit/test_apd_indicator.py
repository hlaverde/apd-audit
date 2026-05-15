"""Unit tests for the APD indicator and signed Δ."""

from __future__ import annotations

import numpy as np
import pytest

from apd.apd.delta import expected_perla, signed_delta
from apd.apd.indicator import apd, compute_occupation_metrics


def _onehot(idx: int, n: int = 11) -> np.ndarray:
    v = np.zeros(n)
    v[idx] = 1.0
    return v


class TestExpectedPerla:
    def test_concentrated_distribution_returns_the_position(self) -> None:
        for k in (1, 5, 11):
            assert expected_perla(_onehot(k - 1)) == pytest.approx(float(k))

    def test_uniform_distribution_returns_midpoint(self) -> None:
        u = np.full(11, 1 / 11)
        assert expected_perla(u) == pytest.approx(6.0)


class TestSignedDelta:
    def test_zero_when_equal(self) -> None:
        u = np.full(11, 1 / 11)
        assert signed_delta(u, u) == pytest.approx(0.0)

    def test_negative_when_alg_is_lighter(self) -> None:
        # f_alg concentrated at PERLA 2, f_emp at PERLA 8 → Δ = 2-8 = -6
        assert signed_delta(_onehot(1), _onehot(7)) == pytest.approx(-6.0)

    def test_positive_when_alg_is_darker(self) -> None:
        assert signed_delta(_onehot(9), _onehot(3)) == pytest.approx(6.0)


class TestAPD:
    def test_zero_when_distributions_match(self) -> None:
        f = np.array([0.1, 0.2, 0.2, 0.2, 0.1, 0.05, 0.05, 0.05, 0.025, 0.025, 0.0])
        results = [
            compute_occupation_metrics("CEO", f, f, 0.6),
            compute_occupation_metrics("nurse", f, f, 0.3),
            compute_occupation_metrics("worker", f, f, 0.1),
        ]
        assert apd(results) == pytest.approx(0.0)

    def test_negative_when_alg_lightens_high_status(self) -> None:
        # High-status occupation: f_alg way lighter than f_emp → Δ<0, D>0,
        # signed_D = -D. APD ≤ 0.
        f_emp = _onehot(7)  # darker
        f_alg = _onehot(1)  # lighter
        results = [
            compute_occupation_metrics("CEO", f_alg, f_emp, weight=1.0),
        ]
        out = apd(results)
        assert out < 0
        assert out == pytest.approx(-6.0)  # D = 6, sign(Δ) = -1, w = 1

    def test_positive_when_alg_darkens_low_status(self) -> None:
        # The opposite asymmetry.
        f_emp = _onehot(1)
        f_alg = _onehot(7)
        results = [compute_occupation_metrics("worker", f_alg, f_emp, weight=1.0)]
        assert apd(results) == pytest.approx(6.0)

    def test_weights_compose_linearly(self) -> None:
        f_emp = _onehot(7)
        f_alg = _onehot(1)
        r = compute_occupation_metrics("CEO", f_alg, f_emp, weight=0.4)
        assert apd([r]) == pytest.approx(-2.4)  # 0.4 * 6 * -1


def test_occupation_result_signed_D_handles_zero_delta() -> None:
    """Zero Δ should produce zero signed_D, not propagate NaN."""
    f = np.array([0.0, 0.4, 0.2, 0.2, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    # symmetric around its mean, so Δ = 0 against itself
    r = compute_occupation_metrics("x", f, f, weight=0.5)
    assert r.signed_D == 0.0
    assert apd([r]) == 0.0
