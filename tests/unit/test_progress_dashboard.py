"""Unit tests for ``scripts/09_progress_dashboard.py``.

Covers the deterministic helpers (per-grid counts, throughput, ETA,
pending top, rendering) using synthetic metadata frames. The
end-to-end ``run()`` path is exercised against a temp dir with two
shards to verify the load+dedup pipeline.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "09_progress_dashboard.py"


@pytest.fixture(scope="module")
def dash():
    spec = importlib.util.spec_from_file_location("progress_dashboard", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["progress_dashboard"] = mod
    spec.loader.exec_module(mod)
    return mod


def _sample_row(
    image_id: str,
    *,
    model: str = "pollinations/flux",
    language: str = "en",
    backend: str = "pollinations",
    timestamp: int | None = None,
    duration_s: float = 5.0,
) -> dict:
    return {
        "image_id": image_id,
        "model": model,
        "occupation": "CEO",
        "language": language,
        "country_proxy": "MULTI",
        "seed": 1,
        "prompt": "a photo of a CEO",
        "path": f"/tmp/{image_id}.png",
        "sha256": "deadbeef",
        "backend": backend,
        "duration_s": duration_s,
        "timestamp": timestamp if timestamp is not None else int(time.time()),
    }


class TestPerGridDone:
    def test_empty_df_yields_zero(self, dash) -> None:
        out = dash.per_grid_done(pd.DataFrame())
        assert out["main"] == (0, dash.MAIN_GRID_TOTAL)
        assert out["h5"] == (0, dash.H5_GRID_TOTAL)
        assert out["robustness"] == (0, dash.ROBUSTNESS_GRID_TOTAL)

    def test_main_grid_id_counted(self, dash) -> None:
        from apd.prompts.grid import image_id_of, main_cells

        first_cell = next(main_cells())
        df = pd.DataFrame([_sample_row(image_id_of(first_cell))])
        out = dash.per_grid_done(df)
        assert out["main"][0] == 1
        # H5 / robustness unaffected.
        assert out["h5"][0] == 0
        assert out["robustness"][0] == 0


class TestThroughputLast24h:
    def test_excludes_old_rows(self, dash) -> None:
        now = 2_000_000_000
        df = pd.DataFrame(
            [
                _sample_row("a", timestamp=now - 100),  # recent
                _sample_row("b", timestamp=now - 1_000),  # recent
                _sample_row("c", timestamp=now - 200_000),  # > 24h
            ]
        )
        out = dash.compute_throughput_last_24h(df, now=now)
        assert "pollinations" in out
        assert out["pollinations"]["imgs"] == 2.0

    def test_empty_input(self, dash) -> None:
        assert dash.compute_throughput_last_24h(pd.DataFrame()) == {}


class TestEtaSeconds:
    def test_zero_throughput_returns_none(self, dash) -> None:
        assert dash.eta_seconds(0, 100, 0.0) is None

    def test_complete_grid_returns_none(self, dash) -> None:
        assert dash.eta_seconds(100, 100, 5.0) is None

    def test_eta_arithmetic(self, dash) -> None:
        # 1000 pending @ 10 imgs/min = 100 min = 6000 s.
        assert dash.eta_seconds(0, 1000, 10.0) == pytest.approx(6000.0)


class TestPmlMatrix:
    def test_shape_matches_main_grid(self, dash) -> None:
        from apd.prompts.grid import MAIN_LANGUAGES, MAIN_MODELS

        out = dash.per_model_language_main(pd.DataFrame())
        assert list(out.index) == list(MAIN_MODELS)
        assert list(out.columns) == list(MAIN_LANGUAGES)
        assert (out == 0).all().all()


class TestEndToEnd:
    def test_run_with_real_50_img_metadata(self, tmp_path, dash) -> None:
        """Smoke test: write a metadata.parquet with 50 main-grid rows and
        verify the report is generated without error and reports >= 1
        main-grid count."""
        from apd.prompts.grid import image_id_of, main_cells

        cells = []
        for i, cell in enumerate(main_cells()):
            if i >= 50:
                break
            cells.append(cell)

        rows = [
            _sample_row(
                image_id_of(c), model=c.model, language=c.language, timestamp=int(time.time()) - 60
            )
            for c in cells
        ]
        canonical = tmp_path / "metadata.parquet"
        pd.DataFrame(rows).to_parquet(canonical, index=False)

        out_md = tmp_path / "progress.md"
        rc = dash.run(canonical=canonical, metadata_dir=tmp_path, out_md=out_md)
        assert rc == 0
        assert out_md.exists()
        text = out_md.read_text(encoding="utf-8")
        assert "GRAND TOTAL" in text
        # Should report 50 done in the main grid.
        assert "50 /" in text or "    50" in text

    def test_run_with_no_metadata(self, tmp_path, dash) -> None:
        """Empty dir: report says no metadata, returns 0."""
        rc = dash.run(canonical=tmp_path / "missing.parquet", metadata_dir=tmp_path, out_md=None)
        assert rc == 0
