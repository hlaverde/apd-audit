"""Unit tests for ``scripts/migrate_metadata_v2.py``.

Pins the contract of the schema extension:

* Adds 12 classifier columns to existing rows with sentinel "not yet
  classified" values.
* Preserves any columns already present (idempotent — running twice is
  a no-op).
* Skips ``--classify`` in-place classification gracefully when PNGs are
  not locally accessible (the hl#1 shift wrote Colab paths).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "migrate_metadata_v2.py"


@pytest.fixture(scope="module")
def mig():
    spec = importlib.util.spec_from_file_location("migrate_metadata_v2", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["migrate_metadata_v2"] = mod
    spec.loader.exec_module(mod)
    return mod


def _base_row(image_id: str = "id_a", path: str = "/nope/seed_1.png") -> dict:
    return {
        "image_id": image_id,
        "model": "pollinations/flux",
        "occupation": "CEO",
        "language": "en",
        "country_proxy": "MULTI",
        "seed": 1,
        "prompt": "a photo of a CEO",
        "path": path,
        "sha256": "deadbeef",
        "backend": "pollinations",
        "duration_s": 1.0,
        "timestamp": 1,
    }


class TestExtendSchema:
    def test_adds_all_twelve_columns(self, mig) -> None:
        df = pd.DataFrame([_base_row()])
        extended, added = mig.extend_schema(df)
        assert len(added) == 12
        for col, _ in mig.CLASSIFIER_COLUMNS:
            assert col in extended.columns

    def test_sentinel_values_set(self, mig) -> None:
        df = pd.DataFrame([_base_row()])
        extended, _ = mig.extend_schema(df)
        row = extended.iloc[0]
        assert row["has_face"] == False  # noqa: E712 — explicit value check
        assert row["n_faces"] == 0
        assert pd.isna(row["ita_value"])
        assert row["ita_label"] == "not_classified"
        assert pd.isna(row["ita_perla"])
        assert pd.isna(row["mst_value"])
        assert pd.isna(row["mst_perla"])
        assert pd.isna(row["casco_perla"])
        assert pd.isna(row["perla_consensus"])
        assert row["n_classifiers"] == 0
        assert row["n_concordant"] == 0
        assert row["concordant_2of3"] == False  # noqa: E712

    def test_preserves_existing_columns(self, mig) -> None:
        """If `has_face` is already True in the input (worker shard with
        classifications), extend_schema must NOT overwrite it."""
        row = _base_row()
        row["has_face"] = True
        row["n_faces"] = 1
        row["ita_value"] = 30.5
        row["ita_label"] = "tan_IV"
        df = pd.DataFrame([row])
        extended, added = mig.extend_schema(df)
        # Already-present columns should not appear in `added`.
        assert "has_face" not in added
        assert "ita_value" not in added
        # The values must be preserved.
        out = extended.iloc[0]
        assert out["has_face"] is True or out["has_face"] == True  # noqa
        assert out["n_faces"] == 1
        assert out["ita_value"] == 30.5
        assert out["ita_label"] == "tan_IV"
        # Missing columns should still be added.
        assert "mst_value" in added

    def test_idempotent_twice(self, mig) -> None:
        df = pd.DataFrame([_base_row()])
        e1, added1 = mig.extend_schema(df)
        e2, added2 = mig.extend_schema(e1)
        assert added1 == list(mig.CLASSIFIER_COLUMN_NAMES)
        assert added2 == []  # nothing more to add.


class TestRun:
    def test_dry_run_does_not_write(self, tmp_path, mig) -> None:
        metadata = tmp_path / "metadata.parquet"
        pd.DataFrame([_base_row()]).to_parquet(metadata, index=False)
        before = metadata.stat().st_mtime
        rc = mig.run(metadata=metadata, classify=False, png_base=None, dry_run=True)
        assert rc == 0
        # No write happened.
        assert metadata.stat().st_mtime == before
        # Cols stay at 12 (original).
        df_after = pd.read_parquet(metadata)
        assert len(df_after.columns) == 12

    def test_real_run_writes_extended_schema(self, tmp_path, mig) -> None:
        metadata = tmp_path / "metadata.parquet"
        pd.DataFrame([_base_row(), _base_row(image_id="id_b")]).to_parquet(metadata, index=False)
        rc = mig.run(metadata=metadata, classify=False, png_base=None, dry_run=False)
        assert rc == 0
        df_after = pd.read_parquet(metadata)
        assert len(df_after) == 2  # rows preserved.
        # 12 original + 12 classifier = 24 cols.
        assert len(df_after.columns) == 24
        # Sentinel value present.
        assert (df_after["ita_label"] == "not_classified").all()

    def test_classify_skips_missing_pngs(self, tmp_path, mig) -> None:
        """When PNG paths point to non-existent files, classify pass leaves
        sentinel values intact and reports the count of skipped rows."""
        metadata = tmp_path / "metadata.parquet"
        # 2 rows with paths that don't exist on disk.
        rows = [
            _base_row(image_id="id_a", path=str(tmp_path / "nope_a.png")),
            _base_row(image_id="id_b", path=str(tmp_path / "nope_b.png")),
        ]
        pd.DataFrame(rows).to_parquet(metadata, index=False)
        rc = mig.run(metadata=metadata, classify=True, png_base=None, dry_run=False)
        assert rc == 0
        df_after = pd.read_parquet(metadata)
        # Sentinel values preserved (no classification happened).
        assert (df_after["ita_label"] == "not_classified").all()
        assert (df_after["has_face"] == False).all()  # noqa: E712

    def test_missing_metadata_file_returns_2(self, tmp_path, mig) -> None:
        rc = mig.run(
            metadata=tmp_path / "does_not_exist.parquet",
            classify=False,
            png_base=None,
            dry_run=False,
        )
        assert rc == 2

    def test_idempotent_two_runs(self, tmp_path, mig) -> None:
        metadata = tmp_path / "metadata.parquet"
        pd.DataFrame([_base_row()]).to_parquet(metadata, index=False)
        rc1 = mig.run(metadata=metadata, classify=False, png_base=None, dry_run=False)
        bytes_after_first = metadata.read_bytes()
        rc2 = mig.run(metadata=metadata, classify=False, png_base=None, dry_run=False)
        bytes_after_second = metadata.read_bytes()
        assert rc1 == 0 and rc2 == 0
        # Second run should be a no-op (schema already extended).
        assert bytes_after_first == bytes_after_second
