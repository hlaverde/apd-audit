"""Unit tests for the H3, H4, H5 estimators."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from apd.estimate.h3 import H3Result, estimate_h3
from apd.estimate.h4 import H4Result, estimate_h4
from apd.estimate.h5 import H5Result, estimate_h5


# ===================== H3: language fixed effects ========================


def _make_apd_panel(
    countries: list[str],
    languages: list[str],
    models: list[str],
    *,
    language_effect: float = 0.0,
    noise: float = 0.05,
    seed: int = 0,
) -> pd.DataFrame:
    """Build a synthetic APD panel with an optional language effect.

    The synthetic DGP: APD = -0.5 (base) + (lang_idx × language_effect)
    + small noise. Country and model add their own additive shifts.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for c_idx, c in enumerate(countries):
        for l_idx, l in enumerate(languages):
            for m_idx, m in enumerate(models):
                shift = (
                    -0.5
                    + 0.2 * c_idx
                    + 0.3 * m_idx
                    + l_idx * language_effect
                    + float(rng.normal(scale=noise))
                )
                rows.append({"country": c, "language": l, "model": m, "APD": shift})
    return pd.DataFrame(rows)


class TestH3:
    def test_significant_when_language_effect_present(self) -> None:
        panel = _make_apd_panel(
            countries=["CO", "MX", "BR", "PE"],
            languages=["en", "es-ES", "es-LatAm", "pt-BR"],
            models=["m1", "m2", "m3", "m4"],
            language_effect=0.8,
            seed=1,
        )
        out = estimate_h3(panel)
        assert isinstance(out, H3Result)
        assert out.language_p_value < 0.01
        assert out.language_df_num == 3  # 4 languages - 1 reference

    def test_no_language_effect_yields_small_coefficients(self) -> None:
        # Stochastic tests on p-values are flaky; instead assert that the
        # *magnitudes* of the language fixed effects collapse to zero up
        # to bootstrap-sized noise. The DGP has language_effect = 0.
        panel = _make_apd_panel(
            countries=["CO", "MX", "BR", "PE"],
            languages=["en", "es-ES", "es-LatAm", "pt-BR"],
            models=["m1", "m2", "m3", "m4"],
            language_effect=0.0,
            noise=0.05,
            seed=42,
        )
        out = estimate_h3(panel)
        lang_coefs = [
            float(v) for k, v in out.coefficients.items() if k.startswith("C(language)")
        ]
        # Every language fixed effect should be within a noise multiple of zero.
        assert all(abs(c) < 0.1 for c in lang_coefs), (
            f"language coefficients should be near zero under the null, got {lang_coefs}"
        )

    def test_single_language_raises(self) -> None:
        panel = _make_apd_panel(
            countries=["CO", "MX"], languages=["en"], models=["m1", "m2"],
        )
        with pytest.raises(ValueError, match="at least 2 languages"):
            estimate_h3(panel)

    def test_missing_columns_raises(self) -> None:
        panel = pd.DataFrame({"APD": [1.0], "language": ["en"]})
        with pytest.raises(KeyError, match="missing columns"):
            estimate_h3(panel)


# ===================== H5: orientalism contrast =========================


def _make_image_panel(
    markers: list[str],
    occupations: list[str],
    models: list[str],
    *,
    n_per_cell: int = 10,
    latam_lift: float = 0.0,
    us_lift: float = 0.0,
    noise: float = 0.05,
    seed: int = 0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for marker in markers:
        for occ in occupations:
            for m in models:
                for i in range(n_per_cell):
                    base = 0.15  # baseline P_rural under "unmarked"
                    lift = (
                        latam_lift if marker == "LatAm"
                        else us_lift if marker == "US"
                        else 0.0
                    )
                    p_rural = float(np.clip(base + lift + rng.normal(scale=noise), 0, 1))
                    rows.append(
                        {
                            "image_id": f"{marker}_{occ}_{m}_{i}",
                            "marker": marker,
                            "occupation": occ,
                            "model": m,
                            "a rural scene": p_rural / 3,
                            "a folkloric landscape": p_rural / 3,
                            "an artisan workshop": p_rural / 3,
                            "an urban scene": 0.2,
                            "a modern office": 0.2,
                            "a neutral background": max(0.0, 1.0 - p_rural - 0.4),
                        },
                    )
    return pd.DataFrame(rows)


class TestH5:
    def test_positive_diff_when_latam_lifts_orientalist_prob(self) -> None:
        panel = _make_image_panel(
            markers=["LatAm", "US", "unmarked"],
            occupations=["doctor", "engineer"],
            models=["m1", "m2"],
            latam_lift=0.30,
            us_lift=0.05,
            seed=11,
        )
        out = estimate_h5(panel)
        assert isinstance(out, H5Result)
        assert out.diff_in_diff > 0
        assert out.diff_in_diff_p_value < 0.01

    def test_zero_diff_when_no_marker_effect(self) -> None:
        panel = _make_image_panel(
            markers=["LatAm", "US", "unmarked"],
            occupations=["doctor", "engineer"],
            models=["m1", "m2"],
            latam_lift=0.0,
            us_lift=0.0,
            noise=0.05,
            seed=22,
        )
        out = estimate_h5(panel)
        # Under the null, the point estimate is close to zero. p-value can
        # land anywhere in [0, 1] depending on the side that noise pushed
        # the estimate; we therefore avoid asserting on it.
        assert abs(out.diff_in_diff) < 0.05

    def test_single_marker_raises(self) -> None:
        panel = _make_image_panel(
            markers=["unmarked"], occupations=["x"], models=["m"], n_per_cell=5,
        )
        with pytest.raises(ValueError, match="at least 2 marker levels"):
            estimate_h5(panel)

    def test_missing_probability_columns_raises(self) -> None:
        bad = pd.DataFrame(
            {"image_id": ["x"], "marker": ["LatAm"], "occupation": ["d"], "model": ["m"]},
        )
        with pytest.raises(KeyError, match="missing columns"):
            estimate_h5(bad)

    def test_rejects_out_of_range_probabilities(self) -> None:
        # Two rows so the marker-level count check doesn't fire first.
        rows = []
        for marker in ("LatAm", "US"):
            rows.append(
                {
                    "image_id": f"x_{marker}",
                    "marker": marker,
                    "occupation": "d",
                    "model": "m",
                    "a rural scene": 0.9,
                    "a folkloric landscape": 0.9,    # sum > 1 with workshop
                    "an artisan workshop": 0.9,
                },
            )
        with pytest.raises(ValueError, match="outside \\[0, 1\\]"):
            estimate_h5(pd.DataFrame(rows))


# ===================== H4: scaling specification ========================


def _make_model_panel(
    phi: float,
    *,
    n: int = 8,
    noise: float = 0.1,
    seed: int = 0,
) -> pd.DataFrame:
    """Build a synthetic panel where APD = α + φ·log(params) + noise."""
    rng = np.random.default_rng(seed)
    # params spaced log-evenly between 100M and 12B
    log_params = np.linspace(np.log(1e8), np.log(1.2e10), n)
    apd = 1.0 + phi * log_params + rng.normal(scale=noise, size=n)
    return pd.DataFrame(
        {
            "model_id": [f"m{i}" for i in range(n)],
            "APD": apd,
            "log_parameters": log_params,
            "architecture_family": ["SD"] * n,
            "debias_explicit": [0] * n,
        },
    )


class TestH4:
    def test_phi_negative_significant_when_scaling_reduces_bias(self) -> None:
        panel = _make_model_panel(phi=-0.2, n=10, seed=1)
        out = estimate_h4(panel)
        assert isinstance(out, H4Result)
        assert out.phi_estimate < 0
        # One-sided p (alternative φ < 0) should reject H4 here.
        assert out.phi_p_value_one_sided < 0.05

    def test_phi_zero_when_scaling_neutral(self) -> None:
        panel = _make_model_panel(phi=0.0, n=10, noise=0.2, seed=2)
        out = estimate_h4(panel)
        # Sign of estimate is uncertain at zero effect; p should be near 0.5.
        assert 0.2 < out.phi_p_value_one_sided < 0.8

    def test_phi_positive_when_scaling_worsens_bias(self) -> None:
        panel = _make_model_panel(phi=+0.2, n=10, seed=3)
        out = estimate_h4(panel)
        # H4 *supports* a non-reduction; a positive φ trivially supports it.
        assert out.phi_estimate > 0
        assert out.phi_p_value_one_sided > 0.5

    def test_too_few_observations_raises(self) -> None:
        panel = _make_model_panel(phi=-0.1, n=3)
        with pytest.raises(ValueError, match="at least 4 observations"):
            estimate_h4(panel)
