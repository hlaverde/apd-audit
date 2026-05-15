"""Unit tests for bootstrap CIs around D, Δ, and APD."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from apd.apd.bootstrap import BootstrapEstimate, bootstrap_apd


def _make_ground_truth(occs: list[str], dist: dict[str, np.ndarray], weights: dict[str, float]) -> pd.DataFrame:
    rows = []
    for o in occs:
        for tone, p in zip(range(1, 12), dist[o], strict=True):
            rows.append({"country": "CO", "occupation": o, "perla_tone": int(tone),
                         "prob": float(p), "weight": float(weights[o])})
    return pd.DataFrame(rows)


def _make_panel(occs: list[str], values: dict[str, list[int]]) -> pd.DataFrame:
    rows = []
    for o in occs:
        for i, v in enumerate(values[o]):
            rows.append({"image_id": f"img_{o}_{i}", "occupation": o,
                         "has_face": True, "perla_consensus": int(v)})
    return pd.DataFrame(rows)


def _onehot(idx: int) -> np.ndarray:
    v = np.zeros(11)
    v[idx] = 1.0
    return v


@pytest.fixture
def ground_truth() -> pd.DataFrame:
    return _make_ground_truth(
        ["CEO", "worker"],
        # _onehot(k) puts unit mass at PERLA tone k+1 (the array is
        # length 11 indexed 0..10 mapped to tones 1..11). Pick tones
        # 8 for CEO (empirically dark) and 2 for worker (empirically
        # light) to give clean integer Δs in the asserts below.
        {"CEO": _onehot(7), "worker": _onehot(1)},
        {"CEO": 0.7, "worker": 0.3},
    )


@pytest.fixture
def panel_with_signal() -> pd.DataFrame:
    # CEO algorithmically light (PERLA 2 across all images) → strong Δ<0
    # worker algorithmically dark (PERLA 8) → strong Δ>0
    return _make_panel(
        ["CEO", "worker"],
        {"CEO": [2] * 30, "worker": [8] * 30},
    )


class TestBootstrapShape:
    def test_returns_apd_plus_per_occupation(self, ground_truth, panel_with_signal) -> None:
        out = bootstrap_apd(panel_with_signal, ground_truth, n_replicates=100)
        assert "APD" in out
        assert "D[CEO]" in out
        assert "D[worker]" in out
        assert "delta[CEO]" in out
        assert "delta[worker]" in out
        assert len(out) == 1 + 2 * 2  # APD + 2 occs × {D, delta}

    def test_estimates_have_well_formed_cis(self, ground_truth, panel_with_signal) -> None:
        out = bootstrap_apd(panel_with_signal, ground_truth, n_replicates=200)
        for est in out.values():
            assert isinstance(est, BootstrapEstimate)
            assert est.ci_lower <= est.point or est.ci_upper >= est.point
            assert est.ci_lower <= est.ci_upper
            assert est.n_replicates == 200
            assert est.ci_level == pytest.approx(0.95)


class TestBootstrapSignal:
    def test_ceo_delta_is_negative_when_alg_lighter(
        self, ground_truth, panel_with_signal,
    ) -> None:
        # f_alg concentrated at PERLA 2, f_emp at PERLA 8 → Δ = 2 - 8 = -6
        out = bootstrap_apd(panel_with_signal, ground_truth, n_replicates=200)
        d = out["delta[CEO]"]
        assert d.point == pytest.approx(-6.0)
        # With f_alg constant the bootstrap CI is tight around -6.
        assert d.ci_lower == pytest.approx(-6.0, abs=0.1)
        assert d.ci_upper == pytest.approx(-6.0, abs=0.1)

    def test_worker_delta_is_positive_when_alg_darker(
        self, ground_truth, panel_with_signal,
    ) -> None:
        out = bootstrap_apd(panel_with_signal, ground_truth, n_replicates=200)
        d = out["delta[worker]"]
        assert d.point == pytest.approx(6.0)


class TestBootstrapWiderCIWithNoise:
    def test_ci_widens_when_within_cell_variance_grows(self, ground_truth) -> None:
        rng = np.random.default_rng(0)
        # Constant cell → narrow CI
        constant_panel = _make_panel(
            ["CEO", "worker"],
            {"CEO": [3] * 30, "worker": [9] * 30},
        )
        # Noisy cell with same mean → wider CI
        noisy_ceo = [int(np.clip(round(3 + rng.normal(scale=2.0)), 1, 11)) for _ in range(30)]
        noisy_worker = [int(np.clip(round(9 + rng.normal(scale=2.0)), 1, 11)) for _ in range(30)]
        noisy_panel = _make_panel(["CEO", "worker"], {"CEO": noisy_ceo, "worker": noisy_worker})

        constant = bootstrap_apd(constant_panel, ground_truth, n_replicates=300, seed=1)
        noisy = bootstrap_apd(noisy_panel, ground_truth, n_replicates=300, seed=1)

        constant_width = constant["delta[CEO]"].ci_upper - constant["delta[CEO]"].ci_lower
        noisy_width = noisy["delta[CEO]"].ci_upper - noisy["delta[CEO]"].ci_lower
        assert noisy_width > constant_width


class TestBootstrapDeterminism:
    def test_same_seed_reproduces_cis(self, ground_truth, panel_with_signal) -> None:
        out_a = bootstrap_apd(panel_with_signal, ground_truth, n_replicates=200, seed=42)
        out_b = bootstrap_apd(panel_with_signal, ground_truth, n_replicates=200, seed=42)
        for key in out_a:
            assert out_a[key].ci_lower == out_b[key].ci_lower
            assert out_a[key].ci_upper == out_b[key].ci_upper

    def test_different_seeds_produce_different_cis(self, ground_truth) -> None:
        # Need variation across replicates → introduce within-cell variance.
        rng = np.random.default_rng(0)
        panel = _make_panel(
            ["CEO", "worker"],
            {
                "CEO": [int(rng.integers(1, 12)) for _ in range(30)],
                "worker": [int(rng.integers(1, 12)) for _ in range(30)],
            },
        )
        out_a = bootstrap_apd(panel, ground_truth, n_replicates=200, seed=1)
        out_b = bootstrap_apd(panel, ground_truth, n_replicates=200, seed=2)
        assert (out_a["APD"].ci_lower, out_a["APD"].ci_upper) != (
            out_b["APD"].ci_lower, out_b["APD"].ci_upper,
        )
