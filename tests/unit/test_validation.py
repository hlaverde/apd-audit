"""Unit tests for validate.sampling and validate.agreement."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from apd.validate.agreement import cohens_kappa, compare_to_consensus
from apd.validate.sampling import (
    LABELLING_SCHEMA,
    StratificationPlan,
    sample_for_validation,
)


def _make_panel(n_per_occ: int, occs: list[str]) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rows = []
    for occ in occs:
        for i in range(n_per_occ):
            rows.append(
                {
                    "image_id": f"{occ}_{i}",
                    "occupation": occ,
                    "language": rng.choice(["en", "es-ES", "es-LatAm", "pt-BR"]),
                    "model": rng.choice(["m1", "m2", "m3", "m4"]),
                    "country": rng.choice(["CO", "MX", "BR", "PE"]),
                    "path": f"/fake/{occ}/{i}.png",
                    "has_face": True,
                    "perla_consensus": int(rng.integers(1, 12)),
                },
            )
    return pd.DataFrame(rows)


class TestSampling:
    def test_n_per_occupation_respected(self) -> None:
        panel = _make_panel(n_per_occ=20, occs=["CEO", "nurse", "domestic worker"])
        plan = StratificationPlan(n_per_occupation=5, seed=1)
        sample = sample_for_validation(panel, plan)
        assert len(sample) == 5 * 3
        counts = sample.groupby("occupation").size()
        for occ in ("CEO", "nurse", "domestic worker"):
            assert counts[occ] == 5

    def test_takes_all_when_panel_smaller_than_target(self) -> None:
        panel = _make_panel(n_per_occ=3, occs=["CEO", "nurse"])
        plan = StratificationPlan(n_per_occupation=12, seed=1)
        sample = sample_for_validation(panel, plan)
        assert len(sample) == 6  # 3 per occ × 2 occs

    def test_schema_matches_canonical(self) -> None:
        panel = _make_panel(n_per_occ=10, occs=["CEO"])
        sample = sample_for_validation(panel, StratificationPlan(n_per_occupation=5))
        assert list(sample.columns) == list(LABELLING_SCHEMA)

    def test_label_columns_start_empty(self) -> None:
        panel = _make_panel(n_per_occ=10, occs=["CEO"])
        sample = sample_for_validation(panel, StratificationPlan(n_per_occupation=5))
        assert sample["cl_perla"].isna().all()
        assert sample["yp_perla"].isna().all()
        assert sample["hl_adjudication"].isna().all()

    def test_same_seed_same_sample(self) -> None:
        panel = _make_panel(n_per_occ=30, occs=["CEO", "nurse"])
        plan = StratificationPlan(n_per_occupation=5, seed=99)
        a = sample_for_validation(panel, plan)
        b = sample_for_validation(panel, plan)
        assert a["image_id"].tolist() == b["image_id"].tolist()

    def test_face_filter_drops_no_face_rows(self) -> None:
        panel = _make_panel(n_per_occ=10, occs=["CEO"])
        # Mark half the rows as no-face.
        panel.loc[panel.index[:5], "has_face"] = False
        plan = StratificationPlan(n_per_occupation=10, seed=1, require_face=True)
        sample = sample_for_validation(panel, plan)
        assert len(sample) == 5

    def test_missing_columns_raises(self) -> None:
        bad = pd.DataFrame({"image_id": ["x"]})
        with pytest.raises(KeyError, match="missing columns"):
            sample_for_validation(bad)


class TestAgreement:
    def test_perfect_agreement_gives_kappa_one(self) -> None:
        a = pd.Series([1, 5, 8, 3, 11])
        b = pd.Series([1, 5, 8, 3, 11])
        out = cohens_kappa(a, b)
        assert out.value == pytest.approx(1.0)
        assert out.n == 5

    def test_systematic_disagreement_gives_kappa_below_zero(self) -> None:
        # When raters swap labels in a structured way (each uses BOTH
        # categories but disagrees on which case is which), expected
        # agreement under chance is high while observed agreement is
        # zero, so κ becomes strongly negative.
        a = pd.Series([1, 1, 1, 5, 5, 5])
        b = pd.Series([5, 5, 5, 1, 1, 1])
        out = cohens_kappa(a, b)
        assert out.value < 0

    def test_drops_unlabelled_rows(self) -> None:
        a = pd.Series([1, 2, None, 4, 5])
        b = pd.Series([1, 2, 3, None, 5])
        out = cohens_kappa(a, b)
        # Only rows where BOTH raters labelled (indices 0, 1, 4) count.
        assert out.n == 3

    def test_too_few_returns_nan(self) -> None:
        a = pd.Series([1])
        b = pd.Series([1])
        out = cohens_kappa(a, b)
        assert np.isnan(out.value)
        assert "too few" in out.note

    def test_compare_to_consensus_is_a_kappa(self) -> None:
        a = pd.Series([1, 2, 3, 4, 5, 6, 7])
        consensus = pd.Series([1, 2, 3, 4, 5, 6, 6])
        out = compare_to_consensus(a, consensus)
        assert 0.0 <= out.value <= 1.0
        assert out.n == 7
