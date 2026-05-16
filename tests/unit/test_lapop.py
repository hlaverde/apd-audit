"""Unit tests for the LAPOP real loader against a synthetic fixture."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apd.ingest.lapop import (
    LAPOP_COUNTRY_CODES,
    _load_real,
    _read_lapop_file,
    synthetic_prior,
)


@pytest.fixture
def lapop_fixture_csv(tmp_path: Path) -> Path:
    """Synthetic CSV mimicking the **real LAPOP 2023** schema.

    Variables: ``pais`` (country code), ``colorr`` (PERLA 1-11),
    ``edre`` (education level 0-6, used as status proxy per
    DECISIONS.md D-024). Two countries (Colombia=8, Mexico=1) and a
    pigmentocratic education-PERLA gradient so the loader can recover
    a sign-positive structure.
    """
    rng = np.random.default_rng(20260514)
    rows: list[dict] = []
    for country_code in (LAPOP_COUNTRY_CODES["CO"], LAPOP_COUNTRY_CODES["MX"]):
        for _ in range(500):
            edre = int(rng.integers(0, 7))  # 0..6
            # Higher education → lighter PERLA (modal pattern).
            centre = 8.0 - edre * 0.9
            tone = int(np.clip(round(rng.normal(centre, 1.5)), 1, 11))
            if rng.random() < 0.05:
                tone = 88  # LAPOP missing sentinel
            rows.append({"pais": country_code, "colorr": tone, "edre": edre})
    csv = tmp_path / "lapop_synthetic.csv"
    pd.DataFrame(rows).to_csv(csv, index=False)
    return csv


class TestReadFile:
    def test_reads_csv(self, lapop_fixture_csv: Path) -> None:
        df = _read_lapop_file(lapop_fixture_csv)
        assert {"pais", "colorr", "edre"} <= set(df.columns)
        assert len(df) == 1000

    def test_rejects_unknown_format(self, tmp_path: Path) -> None:
        bad = tmp_path / "foo.xml"
        bad.write_text("<root/>")
        with pytest.raises(ValueError, match="unknown LAPOP file format"):
            _read_lapop_file(bad)


class TestLoadRealColombia:
    def test_returns_expected_schema(self, lapop_fixture_csv: Path) -> None:
        df = _load_real(
            lapop_fixture_csv,
            ["CEO", "nurse", "domestic worker"],
            country="CO",
        )
        expected_cols = {"occupation", "perla_tone", "prob", "is_synthetic",
                         "n_respondents", "education_tier"}
        assert expected_cols <= set(df.columns)

    def test_is_synthetic_false(self, lapop_fixture_csv: Path) -> None:
        df = _load_real(lapop_fixture_csv, ["CEO", "nurse"], country="CO")
        assert (df["is_synthetic"] == False).all()  # noqa: E712

    def test_each_occupation_has_eleven_tones(self, lapop_fixture_csv: Path) -> None:
        df = _load_real(lapop_fixture_csv, ["CEO", "nurse", "domestic worker"], country="CO")
        for occ in ("CEO", "nurse", "domestic worker"):
            sub = df[df["occupation"] == occ]
            assert len(sub) == 11
            assert set(sub["perla_tone"]) == set(range(1, 12))

    def test_probabilities_sum_to_one(self, lapop_fixture_csv: Path) -> None:
        df = _load_real(lapop_fixture_csv, ["CEO", "nurse", "domestic worker"], country="CO")
        for occ, sub in df.groupby("occupation"):
            assert sub["prob"].sum() == pytest.approx(1.0, abs=1e-6)

    def test_missing_perla_codes_are_dropped(self, lapop_fixture_csv: Path) -> None:
        df = _load_real(lapop_fixture_csv, ["nurse"], country="CO")
        assert 88 not in df["perla_tone"].unique()

    def test_pigmentocratic_signal_recovered(self, lapop_fixture_csv: Path) -> None:
        """The fixture has a lighter→darker gradient by education tier.

        CEO (status_tier='high' → edre 5,6) should land at lighter mean
        PERLA than domestic worker ('low' → edre 0,1,2) given the
        fixture's negative slope of PERLA on edre.
        """
        df = _load_real(
            lapop_fixture_csv,
            ["CEO", "domestic worker"],
            country="CO",
        )
        tones = np.arange(1, 12)
        e_ceo = (df[df["occupation"] == "CEO"]["prob"].to_numpy() * tones).sum()
        e_dom = (df[df["occupation"] == "domestic worker"]["prob"].to_numpy() * tones).sum()
        assert e_ceo < e_dom, (
            f"CEO mean PERLA ({e_ceo:.2f}) should be < "
            f"domestic worker ({e_dom:.2f}) given the fixture's gradient."
        )

    def test_records_education_tier(self, lapop_fixture_csv: Path) -> None:
        df = _load_real(lapop_fixture_csv, ["CEO"], country="CO")
        assert (df["education_tier"] == "high").all()


class TestLoadRealErrors:
    def test_missing_columns_raises(self, tmp_path: Path) -> None:
        bad_csv = tmp_path / "broken.csv"
        pd.DataFrame({"foo": [1, 2], "bar": [3, 4]}).to_csv(bad_csv, index=False)
        with pytest.raises(KeyError, match="missing expected columns"):
            _load_real(bad_csv, ["CEO"], country="CO")

    def test_unknown_country_raises(self, lapop_fixture_csv: Path) -> None:
        with pytest.raises(KeyError, match="no LAPOP country code"):
            _load_real(lapop_fixture_csv, ["CEO"], country="ZZ")

    def test_unknown_occupation_raises(self, lapop_fixture_csv: Path) -> None:
        with pytest.raises(KeyError, match="not registered in crosswalks"):
            _load_real(lapop_fixture_csv, ["astronaut"], country="CO")


class TestSyntheticPriorCoverage:
    def test_all_25_occupations_have_priors(self) -> None:
        from apd.ground_truth.crosswalks import POC_MAPPINGS

        prior = synthetic_prior(list(POC_MAPPINGS.keys()))
        assert set(prior["occupation"].unique()) == set(POC_MAPPINGS.keys())
        for occ, sub in prior.groupby("occupation"):
            assert sub["prob"].sum() == pytest.approx(1.0, abs=1e-6)
