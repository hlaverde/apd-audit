"""Unit tests for the pooled H2 gradient with cluster-robust SEs."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from apd.estimate.h1_h2 import PooledGradientFit, pooled_gradient


def _make_panel(
    *,
    beta: float,
    n_occupations: int = 25,
    n_models: int = 4,
    noise: float = 0.4,
    seed: int = 0,
) -> pd.DataFrame:
    """Build a cell-level panel where Δ = α + β·w + ε with clustering.

    Each occupation appears n_models times (once per model), so clustering
    by occupation has non-trivial intra-cluster correlation.
    """
    rng = np.random.default_rng(seed)
    rows = []
    # Generate weights monotone in occupation index
    for occ_idx in range(n_occupations):
        weight = (occ_idx + 1) / (n_occupations + 1)
        occ_shock = float(rng.normal(scale=0.3))  # cluster-level shock
        for m in range(n_models):
            delta = -0.5 + beta * weight + occ_shock + float(rng.normal(scale=noise))
            rows.append(
                {
                    "occupation": f"occ_{occ_idx}",
                    "model": f"m_{m}",
                    "weight": weight,
                    "delta": delta,
                },
            )
    return pd.DataFrame(rows)


class TestPooledGradient:
    def test_recovers_negative_beta_when_present(self) -> None:
        panel = _make_panel(beta=-2.0, seed=1)
        out = pooled_gradient(panel)
        assert isinstance(out, PooledGradientFit)
        assert -3.0 < out.beta < -1.0
        # One-sided p (β < 0) should be small.
        assert out.p_value_one_sided < 0.01

    def test_no_effect_when_beta_zero(self) -> None:
        panel = _make_panel(beta=0.0, seed=2)
        out = pooled_gradient(panel)
        # Point estimate close to zero; not asserting on p-value (stochastic).
        assert abs(out.beta) < 0.5

    def test_reports_cluster_count(self) -> None:
        panel = _make_panel(beta=-1.0, n_occupations=10, n_models=3)
        out = pooled_gradient(panel, cluster_by="occupation")
        assert out.n_clusters == 10
        assert out.n_obs == 30  # 10 occs × 3 models
        assert out.cluster_variable == "occupation"

    def test_one_sided_p_is_half_two_sided_when_t_negative(self) -> None:
        panel = _make_panel(beta=-2.0, seed=10)
        out = pooled_gradient(panel)
        assert out.t_statistic < 0
        assert out.p_value_one_sided == pytest.approx(out.p_value_two_sided / 2)

    def test_missing_columns_raises(self) -> None:
        bad = pd.DataFrame({"weight": [0.1, 0.2], "delta": [-0.5, -0.6]})
        with pytest.raises(KeyError, match="missing"):
            pooled_gradient(bad)

    def test_single_cluster_raises(self) -> None:
        panel = pd.DataFrame(
            {
                "occupation": ["only_occ"] * 5,
                "weight": [0.1, 0.2, 0.3, 0.4, 0.5],
                "delta": [-1.0, -1.5, -2.0, -2.5, -3.0],
            },
        )
        with pytest.raises(ValueError, match="need at least 2 distinct"):
            pooled_gradient(panel)
