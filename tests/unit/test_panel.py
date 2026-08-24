"""Unit tests for the panel seam: grid classification, column normalisation,
and the multi-country ground-truth pooling used by MULTI cells."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from apd.apd.bootstrap import _ground_truth_for_cell, per_occupation_panel, pool_ground_truth
from apd.panel.build import build_panel
from apd.prompts.grid import classify_grid


class TestClassifyGrid:
    def test_main_grid(self) -> None:
        assert classify_grid("doctor", "es-LatAm", "pollinations/flux") == "main"

    def test_extra_model_is_robustness(self) -> None:
        assert classify_grid("doctor", "es-LatAm", "stabilityai/stable-diffusion-2-1") == "robustness"

    def test_indigenous_language_is_robustness(self) -> None:
        assert classify_grid("doctor", "qu", "pollinations/flux") == "robustness"

    def test_marker_occupation_is_h5(self) -> None:
        assert classify_grid("marker:LatAm:doctor", "en", "pollinations/flux") == "h5"

    def test_marker_wins_over_robustness(self) -> None:
        # An H5 row must never be counted as robustness, whatever the model.
        assert classify_grid(
            "marker:US:CEO", "qu", "stabilityai/stable-diffusion-2-1",
        ) == "h5"


class TestBuildPanel:
    @staticmethod
    def _write(tmp_path, meta: pd.DataFrame, pheno: pd.DataFrame):
        m, p = tmp_path / "meta.parquet", tmp_path / "pheno.parquet"
        meta.to_parquet(m, index=False)
        pheno.to_parquet(p, index=False)
        return m, p

    def test_renames_country_proxy_to_country(self, tmp_path) -> None:
        meta = pd.DataFrame({"image_id": ["a"], "country_proxy": ["CO"]})
        pheno = pd.DataFrame({"image_id": ["a"], "perla_consensus": [5.0]})
        panel = build_panel(*self._write(tmp_path, meta, pheno))
        assert "country" in panel.columns
        assert "country_proxy" not in panel.columns
        assert panel["country"].iloc[0] == "CO"

    def test_inline_classifier_columns_do_not_fork(self, tmp_path) -> None:
        # Post-D-028 metadata carries the classifier columns too; the merge
        # must not produce perla_consensus_x / _y.
        meta = pd.DataFrame(
            {"image_id": ["a"], "country_proxy": ["CO"],
             "has_face": [True], "perla_consensus": [9.0]},
        )
        pheno = pd.DataFrame(
            {"image_id": ["a"], "has_face": [True], "perla_consensus": [5.0]},
        )
        panel = build_panel(*self._write(tmp_path, meta, pheno))
        assert [c for c in panel.columns if c.endswith(("_x", "_y"))] == []
        # The phenotype file is the authoritative source for those columns.
        assert panel["perla_consensus"].iloc[0] == 5.0


def _ground_truth(countries=("CO", "MX"), n_respondents=(100, 300)) -> pd.DataFrame:
    rows = []
    for country, n in zip(countries, n_respondents, strict=True):
        # CO mass on the light end, MX on the dark end, so pooling is visible.
        probs = np.zeros(11)
        probs[0 if country == "CO" else 10] = 1.0
        for tone, prob in zip(range(1, 12), probs, strict=True):
            rows.append(
                {"country": country, "occupation": "doctor", "perla_tone": tone,
                 "prob": float(prob), "weight": 0.5, "n_respondents": n},
            )
    return pd.DataFrame(rows)


class TestPoolGroundTruth:
    def test_pools_to_one_row_per_tone(self) -> None:
        pooled = pool_ground_truth(_ground_truth())
        assert len(pooled) == 11
        assert pooled["prob"].sum() == pytest.approx(1.0)

    def test_weights_by_respondent_count(self) -> None:
        # CO n=100 (all mass on tone 1), MX n=300 (all mass on tone 11).
        pooled = pool_ground_truth(_ground_truth()).set_index("perla_tone")
        assert pooled.loc[1, "prob"] == pytest.approx(0.25)
        assert pooled.loc[11, "prob"] == pytest.approx(0.75)

    def test_status_weight_survives_pooling(self) -> None:
        pooled = pool_ground_truth(_ground_truth())
        assert pooled["weight"].unique().tolist() == [0.5]


class TestGroundTruthForCell:
    def test_named_country_is_filtered(self) -> None:
        out = _ground_truth_for_cell({"country": "CO"}, _ground_truth())
        assert set(out["country"]) == {"CO"}
        assert len(out) == 11

    def test_multi_is_pooled_not_stacked(self) -> None:
        # The bug this guards: returning the un-pooled frame gives 22 rows
        # for one occupation, and every MULTI cell then fails the
        # f_alg/f_emp shape check inside the APD computation.
        out = _ground_truth_for_cell({"country": "MULTI"}, _ground_truth())
        assert len(out[out["occupation"] == "doctor"]) == 11


class TestPerOccupationPanel:
    def test_emits_one_row_per_cell_and_occupation(self) -> None:
        panel = pd.DataFrame(
            {
                "image_id": [f"i{i}" for i in range(6)],
                "country": ["CO"] * 3 + ["MX"] * 3,
                "language": ["es-LatAm"] * 6,
                "model": ["m"] * 6,
                "occupation": ["doctor"] * 6,
                "has_face": [True] * 6,
                "perla_consensus": [3.0, 4.0, 5.0, 8.0, 9.0, 10.0],
            },
        )
        out = per_occupation_panel(panel, _ground_truth())
        assert len(out) == 2
        assert set(out.columns) >= {"country", "language", "model", "occupation",
                                    "D", "delta", "weight", "n_images", "n_faces"}
        assert out["n_images"].tolist() == [3, 3]

    def test_missing_cell_key_is_a_loud_error(self) -> None:
        panel = pd.DataFrame({"image_id": ["a"], "occupation": ["doctor"]})
        with pytest.raises(KeyError, match="cell keys"):
            per_occupation_panel(panel, _ground_truth())
