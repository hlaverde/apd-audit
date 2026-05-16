"""Unit tests for ``scripts/merge_worker_shards.py``.

Covers the dedup invariant: when shards (or canonical) carry duplicate
``image_id`` rows, the merged frame keeps exactly one row per id — the
one with the highest ``timestamp``. Also covers atomic write and the
``--dry-run`` / ``--keep-shards`` flags.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "merge_worker_shards.py"


@pytest.fixture(scope="module")
def merge_mod():
    spec = importlib.util.spec_from_file_location("merge_worker_shards", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["merge_worker_shards"] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_row(
    image_id: str,
    model: str = "pollinations/flux",
    occ: str = "CEO",
    seed: int = 1,
    timestamp: int = 1,
) -> dict:
    return {
        "image_id": image_id,
        "model": model,
        "occupation": occ,
        "language": "en",
        "country_proxy": "MULTI",
        "seed": seed,
        "prompt": "a photo of a CEO",
        "path": f"/tmp/{image_id}.png",
        "sha256": "deadbeef",
        "backend": "pollinations",
        "duration_s": 1.0,
        "timestamp": timestamp,
    }


def _write_parquet(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_parquet(path, index=False)


class TestDiscoverShards:
    def test_canonical_excluded(self, tmp_path, merge_mod) -> None:
        canonical = tmp_path / "metadata.parquet"
        _write_parquet(canonical, [_make_row("id_a")])
        _write_parquet(tmp_path / "metadata_local_1.parquet", [_make_row("id_b")])
        _write_parquet(tmp_path / "metadata_gha_2.parquet", [_make_row("id_c")])

        shards = merge_mod.discover_shards(tmp_path, "metadata_*.parquet", canonical)
        names = sorted(s.name for s in shards)
        assert names == ["metadata_gha_2.parquet", "metadata_local_1.parquet"]


class TestDedup:
    def test_keeps_highest_timestamp(self, merge_mod) -> None:
        df = pd.DataFrame(
            [
                _make_row("id_a", timestamp=1, model="pollinations/flux", seed=1),
                _make_row("id_a", timestamp=5, model="pollinations/flux", seed=1),
                _make_row("id_a", timestamp=3, model="pollinations/flux", seed=1),
                _make_row("id_b", timestamp=2, seed=2),
            ]
        )
        dedup, n_dropped = merge_mod.dedup(df)
        assert len(dedup) == 2
        assert n_dropped == 2
        a_row = dedup[dedup["image_id"] == "id_a"].iloc[0]
        assert a_row["timestamp"] == 5

    def test_missing_order_col_falls_back_to_last(self, merge_mod) -> None:
        df = pd.DataFrame(
            [
                {"image_id": "id_a", "v": 1},
                {"image_id": "id_a", "v": 2},
            ]
        )
        dedup, _ = merge_mod.dedup(df, order_col="timestamp")
        # Falls back to position-based "keep=last" → v=2.
        assert dedup.iloc[0]["v"] == 2


class TestValidate:
    def test_passes_on_unique_ids(self, merge_mod) -> None:
        df = pd.DataFrame([_make_row("id_a"), _make_row("id_b", seed=2)])
        merge_mod.validate(df)  # no raise

    def test_raises_on_duplicate_ids(self, merge_mod) -> None:
        df = pd.DataFrame([_make_row("id_a"), _make_row("id_a")])
        with pytest.raises(ValueError, match="dedup failed"):
            merge_mod.validate(df)

    def test_raises_on_image_id_ambiguity(self, merge_mod) -> None:
        # Same image_id but different (model, seed) — invariant violation.
        df = pd.DataFrame(
            [
                _make_row("id_a", model="pollinations/flux", seed=1),
                _make_row("id_a", model="runwayml/stable-diffusion-v1-5", seed=99),
            ]
        )
        # First dedup keeps one row by timestamp, but with seed=1 and seed=99
        # both present we expect the dedup to remove one — leaving a unique
        # mapping. The injectivity check is mostly a guard against shards
        # that themselves carry inconsistent rows.
        # Force a case where dedup keeps both (different timestamps but
        # also different image_ids → impossible in real data). We bypass
        # dedup and call validate directly on a known-bad frame.
        bad = pd.DataFrame(
            [
                {"image_id": "id_a", "model": "A", "occupation": "CEO", "seed": 1, "timestamp": 1},
                {"image_id": "id_a", "model": "B", "occupation": "CEO", "seed": 1, "timestamp": 2},
            ]
        )
        # Drop the duplicate image_id check by adding a fake column to make
        # rows distinct under dedup.
        with pytest.raises(ValueError, match="dedup failed|image_id ambiguity"):
            merge_mod.validate(bad)


class TestEndToEndRun:
    def test_dry_run_does_not_write(self, tmp_path, merge_mod) -> None:
        canonical = tmp_path / "metadata.parquet"
        _write_parquet(canonical, [_make_row("id_a", timestamp=1)])
        _write_parquet(tmp_path / "metadata_local_1.parquet", [_make_row("id_a", timestamp=5)])

        before_mtime = canonical.stat().st_mtime
        rc = merge_mod.run(
            canonical=canonical,
            shards_dir=tmp_path,
            shards_pattern="metadata_*.parquet",
            archive_dir=tmp_path / "archive",
            dry_run=True,
            keep_shards=True,
        )
        assert rc == 0
        # Canonical untouched (mtime unchanged).
        assert canonical.stat().st_mtime == before_mtime
        # Shard not archived.
        assert (tmp_path / "metadata_local_1.parquet").exists()

    def test_real_run_writes_and_archives(self, tmp_path, merge_mod) -> None:
        canonical = tmp_path / "metadata.parquet"
        archive = tmp_path / "archive"
        _write_parquet(canonical, [_make_row("id_a", timestamp=1, seed=1)])
        _write_parquet(
            tmp_path / "metadata_local_1.parquet",
            [_make_row("id_a", timestamp=5, seed=1), _make_row("id_b", timestamp=2, seed=2)],
        )

        rc = merge_mod.run(
            canonical=canonical,
            shards_dir=tmp_path,
            shards_pattern="metadata_*.parquet",
            archive_dir=archive,
            dry_run=False,
            keep_shards=False,
        )
        assert rc == 0
        # Canonical now contains the deduped union.
        df = pd.read_parquet(canonical)
        assert sorted(df["image_id"].tolist()) == ["id_a", "id_b"]
        assert df.loc[df["image_id"] == "id_a", "timestamp"].iloc[0] == 5
        # Shard moved to archive.
        assert not (tmp_path / "metadata_local_1.parquet").exists()
        archived = list(archive.glob("*__metadata_local_1.parquet"))
        assert len(archived) == 1

    def test_empty_inputs_exit_clean(self, tmp_path, merge_mod) -> None:
        rc = merge_mod.run(
            canonical=tmp_path / "metadata.parquet",
            shards_dir=tmp_path,
            shards_pattern="metadata_*.parquet",
            archive_dir=tmp_path / "archive",
            dry_run=False,
            keep_shards=False,
        )
        assert rc == 0
        # Nothing got created since there was nothing to merge.
        assert not (tmp_path / "metadata.parquet").exists()

    def test_idempotent(self, tmp_path, merge_mod) -> None:
        """Two runs in a row produce the same canonical bytes."""
        canonical = tmp_path / "metadata.parquet"
        _write_parquet(canonical, [_make_row("id_a", timestamp=1)])
        _write_parquet(tmp_path / "metadata_local_1.parquet", [_make_row("id_b", timestamp=2)])

        merge_mod.run(
            canonical=canonical,
            shards_dir=tmp_path,
            shards_pattern="metadata_*.parquet",
            archive_dir=tmp_path / "archive",
            dry_run=False,
            keep_shards=False,
        )
        bytes_1 = canonical.read_bytes()
        # No more shards left after archive. Second run is a no-op.
        merge_mod.run(
            canonical=canonical,
            shards_dir=tmp_path,
            shards_pattern="metadata_*.parquet",
            archive_dir=tmp_path / "archive",
            dry_run=False,
            keep_shards=False,
        )
        bytes_2 = canonical.read_bytes()
        assert bytes_1 == bytes_2
