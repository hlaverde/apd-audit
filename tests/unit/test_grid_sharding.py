"""Unit tests for the multi-worker helpers in ``apd.prompts.grid``.

Covers ``image_id_of``, ``shard_filter``, and ``pending_cells``. These
helpers parameterise *what to generate next* across the 3-layer automation
(GH Actions, local async worker, Kaggle scheduled notebook) without
coordination — disjoint sharding by SHA256 modulo ``n_shards``.
"""

from __future__ import annotations

import pandas as pd
import pytest

from apd.generate.orchestrator import _image_id as orchestrator_image_id
from apd.prompts.grid import (
    PromptCell,
    image_id_of,
    main_cells,
    pending_cells,
    shard_filter,
)


class TestImageIdOf:
    def test_matches_orchestrator_formula(self) -> None:
        """grid.image_id_of must produce byte-identical strings to
        orchestrator._image_id — they share the dedup key contract."""
        cell = PromptCell(
            occupation="domestic worker",
            language="en",
            country="CO",
            model="pollinations/flux",
            seed=20_260_514_000,
        )
        assert image_id_of(cell) == orchestrator_image_id(cell)

    def test_slashes_in_model_replaced(self) -> None:
        cell = PromptCell("CEO", "en", "MULTI", "runwayml/stable-diffusion-v1-5", 1)
        img_id = image_id_of(cell)
        assert "/" not in img_id
        assert "runwayml_stable-diffusion-v1-5" in img_id

    def test_spaces_in_occupation_replaced(self) -> None:
        cell = PromptCell("street vendor", "en", "MULTI", "pollinations/flux", 1)
        img_id = image_id_of(cell)
        assert " " not in img_id
        assert "street_vendor" in img_id


class TestShardFilter:
    def test_nshards_1_is_noop(self) -> None:
        assert shard_filter("anything", shard_id=0, n_shards=1) is True

    def test_partition_is_disjoint(self) -> None:
        """Every image_id falls in exactly one shard."""
        cells = list(main_cells())[:500]  # sample for speed
        assignments_0 = {image_id_of(c) for c in cells if shard_filter(image_id_of(c), 0, 2)}
        assignments_1 = {image_id_of(c) for c in cells if shard_filter(image_id_of(c), 1, 2)}
        assert assignments_0.isdisjoint(assignments_1)
        assert len(assignments_0) + len(assignments_1) == len(cells)

    def test_partition_is_roughly_balanced(self) -> None:
        """Hash-based sharding should give ~50/50 on a large sample.

        Tolerate up to ±5% imbalance over 12 000 cells (well within
        chi-square expectation for a fair binary partition).
        """
        cells = list(main_cells())
        n_in_shard_0 = sum(1 for c in cells if shard_filter(image_id_of(c), 0, 2))
        n_total = len(cells)
        ratio = n_in_shard_0 / n_total
        assert 0.45 <= ratio <= 0.55, f"shard imbalance: {ratio:.3f}"

    def test_invalid_args_raise(self) -> None:
        with pytest.raises(ValueError):
            shard_filter("x", shard_id=2, n_shards=2)
        with pytest.raises(ValueError):
            shard_filter("x", shard_id=-1, n_shards=2)
        with pytest.raises(ValueError):
            shard_filter("x", shard_id=0, n_shards=0)


class TestPendingCells:
    def _write_shard(self, tmp_path, name: str, image_ids: list[str]) -> None:
        df = pd.DataFrame({"image_id": image_ids, "dummy": list(range(len(image_ids)))})
        df.to_parquet(tmp_path / name, index=False)

    def test_empty_metadata_yields_everything(self, tmp_path) -> None:
        cells = [
            PromptCell("CEO", "en", "MULTI", "pollinations/flux", 1),
            PromptCell("nurse", "en", "MULTI", "pollinations/flux", 2),
        ]
        result = list(pending_cells(cells, []))
        assert len(result) == 2

    def test_done_ids_are_skipped(self, tmp_path) -> None:
        cells = [
            PromptCell("CEO", "en", "MULTI", "pollinations/flux", 1),
            PromptCell("nurse", "en", "MULTI", "pollinations/flux", 2),
        ]
        ceo_id = image_id_of(cells[0])
        self._write_shard(tmp_path, "metadata.parquet", [ceo_id])
        result = list(pending_cells(cells, [tmp_path / "metadata.parquet"]))
        assert [c.occupation for c in result] == ["nurse"]

    def test_union_of_multiple_shards(self, tmp_path) -> None:
        cells = [
            PromptCell("CEO", "en", "MULTI", "pollinations/flux", 1),
            PromptCell("nurse", "en", "MULTI", "pollinations/flux", 2),
            PromptCell("lawyer", "en", "MULTI", "pollinations/flux", 3),
        ]
        self._write_shard(tmp_path, "metadata.parquet", [image_id_of(cells[0])])
        self._write_shard(tmp_path, "metadata_local_1.parquet", [image_id_of(cells[1])])
        result = list(
            pending_cells(
                cells,
                [tmp_path / "metadata.parquet", tmp_path / "metadata_local_1.parquet"],
            )
        )
        assert [c.occupation for c in result] == ["lawyer"]

    def test_shard_filter_applied(self, tmp_path) -> None:
        cells = list(main_cells())[:200]
        result_shard_0 = list(pending_cells(cells, [], shard_id=0, n_shards=2))
        result_shard_1 = list(pending_cells(cells, [], shard_id=1, n_shards=2))
        # Disjoint coverage.
        ids_0 = {image_id_of(c) for c in result_shard_0}
        ids_1 = {image_id_of(c) for c in result_shard_1}
        assert ids_0.isdisjoint(ids_1)
        assert len(result_shard_0) + len(result_shard_1) == len(cells)

    def test_missing_metadata_path_is_silently_skipped(self, tmp_path) -> None:
        cells = [PromptCell("CEO", "en", "MULTI", "pollinations/flux", 1)]
        # Doesn't exist:
        non_existent = tmp_path / "never_created.parquet"
        result = list(pending_cells(cells, [non_existent]))
        assert len(result) == 1
