"""Tests for ``scripts/import_cloud_zip.py``."""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "import_cloud_zip.py"


@pytest.fixture(scope="module")
def importer_mod():
    spec = importlib.util.spec_from_file_location("import_cloud_zip", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["import_cloud_zip"] = mod
    spec.loader.exec_module(mod)
    return mod


def _row(image_id: str, seed: int, path: str = "images/main/CEO/seed_1.png") -> dict:
    return {
        "image_id": image_id,
        "model": "runwayml/stable-diffusion-v1-5",
        "occupation": "CEO",
        "language": "en",
        "country_proxy": "MULTI",
        "seed": seed,
        "prompt": "a photo of a CEO",
        "path": path,
        "sha256": f"sha-{image_id}",
        "backend": "local",
        "duration_s": 1.0,
        "timestamp": seed,
    }


def _write_zip(zip_path: Path, payload_root: Path) -> None:
    with zipfile.ZipFile(zip_path, "w") as zf:
        for file in payload_root.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(payload_root.parent).as_posix())


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "images" / "main").mkdir(parents=True)
    (project / "scripts").mkdir()
    (project / "results").mkdir()
    # import_cloud_zip loads merge_worker_shards.py from the real repo path,
    # but writes to explicit project-root paths, so only the target tree is needed.
    pd.DataFrame([_row("id_existing", 1)]).to_parquet(
        project / "images" / "main" / "metadata.parquet",
        index=False,
    )
    return project


def test_imports_zip_merges_metadata_and_copies_runs(tmp_path, importer_mod) -> None:
    project = _make_project(tmp_path)
    payload = tmp_path / "payload" / "apd_cloud_run_sd15_en_s1"
    images = payload / "images" / "main" / "CEO"
    images.mkdir(parents=True)
    (payload / "runs" / "sd15_en_s1").mkdir(parents=True)
    (payload / "runs" / "sd15_en_s1" / "run.log").write_text("ok", encoding="utf-8")
    (images / "seed_2.png").write_bytes(b"png-2")
    pd.DataFrame([_row("id_new", 2)]).to_parquet(
        payload / "images" / "main" / "metadata_kaggle_sd15_en_s1.parquet",
        index=False,
    )
    zip_path = tmp_path / "apd_cloud_run_sd15_en_s1.zip"
    _write_zip(zip_path, payload)

    summary = importer_mod.import_zip(
        zip_path,
        project_root=project,
        inbox_dir=tmp_path / "inbox",
        run_dashboard=False,
        run_preflight=False,
    )

    assert summary.rows_before == 1
    assert summary.shard_rows == 1
    assert summary.rows_after == 2
    assert summary.duplicates_after == 0
    assert summary.images_copied == 1
    assert summary.metadata_copied == 1
    assert summary.runs_copied == 1
    merged = pd.read_parquet(project / "images" / "main" / "metadata.parquet")
    assert sorted(merged["image_id"].tolist()) == ["id_existing", "id_new"]
    assert (project / "images" / "main" / "CEO" / "seed_2.png").exists()
    assert (project / "results" / "cloud_runs" / zip_path.stem / "sd15_en_s1" / "run.log").exists()
    assert zip_path.exists(), "original ZIP must not be deleted"


def test_duplicate_image_id_is_deduplicated_by_merge(tmp_path, importer_mod) -> None:
    project = _make_project(tmp_path)
    payload = tmp_path / "payload" / "root"
    (payload / "images" / "main" / "CEO").mkdir(parents=True)
    (payload / "images" / "main" / "CEO" / "seed_1.png").write_bytes(b"newer")
    pd.DataFrame([_row("id_existing", 99)]).to_parquet(
        payload / "images" / "main" / "metadata_kaggle_dup.parquet",
        index=False,
    )
    zip_path = tmp_path / "dup.zip"
    _write_zip(zip_path, payload)

    summary = importer_mod.import_zip(
        zip_path,
        project_root=project,
        inbox_dir=tmp_path / "inbox",
        run_dashboard=False,
        run_preflight=False,
    )

    assert summary.rows_after == 1
    assert summary.duplicates_after == 0
    merged = pd.read_parquet(project / "images" / "main" / "metadata.parquet")
    assert merged.loc[0, "timestamp"] == 99


def test_rejects_zip_slip_member(tmp_path, importer_mod) -> None:
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../evil.txt", "nope")

    with pytest.raises(ValueError, match="unsafe ZIP member"):
        importer_mod.import_zip(
            zip_path,
            project_root=_make_project(tmp_path),
            inbox_dir=tmp_path / "inbox",
            run_dashboard=False,
            run_preflight=False,
        )
