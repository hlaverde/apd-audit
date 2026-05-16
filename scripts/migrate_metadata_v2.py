"""Extend ``images/main/metadata.parquet`` with classifier columns.

The metadata schema started as 12 generation-only columns (image_id,
model, occupation, language, country_proxy, seed, prompt, path, sha256,
backend, duration_s, timestamp). To let workers write *self-contained*
shards (generate + classify atomically, no need to centralise PNG bytes
afterwards), we extend the schema with 12 columns produced by
``scripts/04_classify_main.py`` — same column names, same dtypes:

    has_face            bool
    n_faces             int
    ita_value           float
    ita_label           string ("light_I", "tan_IV", ..., "no_face", "not_classified")
    ita_perla           float
    mst_value           float
    mst_perla           float
    casco_perla         float
    perla_consensus     float
    n_classifiers       int
    n_concordant        int
    concordant_2of3     bool

Rows already in ``metadata.parquet`` are filled with sentinel values
meaning "not yet classified":

    has_face=False, n_faces=0,
    ita_value=NaN, ita_label="not_classified", ita_perla=NaN,
    mst_value=NaN, mst_perla=NaN, casco_perla=NaN, perla_consensus=NaN,
    n_classifiers=0, n_concordant=0, concordant_2of3=False

Downstream consumers distinguish "not classified yet" from "classified
but no face detected" by checking ``ita_label`` against the literal
``"not_classified"`` sentinel.

The script is idempotent: running it twice produces byte-identical
output. If all 13 columns are already present, the script is a no-op.

Optional ``--classify`` mode: for any row whose ``path`` exists locally,
run the full face_detect + ITA + MST + CASCo + consensus pipeline and
fill the columns in-place. Skipped rows keep their sentinel values.
The hl#1 shift wrote Colab paths (``/content/drive/...``), so on a
Windows laptop without Drive Desktop sync the classify pass is a no-op
for those rows — by design.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from apd.config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("migrate_metadata_v2")

# The 13 columns produced by 04_classify_main._classify_one. Order is
# stable so dtype assertions are reproducible.
CLASSIFIER_COLUMNS: tuple[tuple[str, object], ...] = (
    ("has_face", False),
    ("n_faces", 0),
    ("ita_value", np.nan),
    ("ita_label", "not_classified"),
    ("ita_perla", np.nan),
    ("mst_value", np.nan),
    ("mst_perla", np.nan),
    ("casco_perla", np.nan),
    ("perla_consensus", np.nan),
    ("n_classifiers", 0),
    ("n_concordant", 0),
    ("concordant_2of3", False),
)

CLASSIFIER_COLUMN_NAMES: tuple[str, ...] = tuple(col for col, _ in CLASSIFIER_COLUMNS)


def extend_schema(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Return ``(df_extended, added_columns)``.

    Columns already present are not overwritten — this preserves any
    classification work already done by a worker shard.
    """
    df = df.copy()
    added: list[str] = []
    for col, sentinel in CLASSIFIER_COLUMNS:
        if col not in df.columns:
            df[col] = sentinel
            added.append(col)
    return df, added


def classify_existing(
    df: pd.DataFrame, *, path_override: Path | None = None
) -> tuple[pd.DataFrame, int, int]:
    """For every row whose ``path`` exists, run the classifier stack.

    Returns ``(df_updated, n_classified, n_skipped_no_png)``.

    Skipped rows keep their sentinel values. This function lazy-imports
    the classifier stack so the migration script can run on hosts
    without OpenCV (e.g., when only the schema extension is needed).
    """
    from apd.classify.consensus import consensus_perla
    from apd.classify.face_detect import detect_face
    from apd.classify.skin_casco import compute_casco_perla
    from apd.classify.skin_casco import is_available as casco_available
    from apd.classify.skin_ita import compute_ita, ita_to_label, ita_to_perla
    from apd.classify.skin_mst import compute_mst, mst_to_perla

    casco_on = casco_available()
    if not casco_on:
        log.warning("CASCo unavailable (skin-tone-classifier not installed?) — using ITA+MST only")

    df = df.copy()
    n_classified = 0
    n_skipped = 0
    for i, row in df.iterrows():
        raw_path = row["path"]
        path = Path(raw_path)
        if path_override is not None and not path.exists():
            # Try the override directory + basename layout.
            path = path_override / Path(raw_path).parent.name / Path(raw_path).name
        if not path.exists():
            n_skipped += 1
            continue

        face = detect_face(path)
        df.at[i, "has_face"] = bool(face.has_face)
        df.at[i, "n_faces"] = int(face.n_faces)
        if not face.has_face or face.cropped_bgr is None:
            df.at[i, "ita_label"] = "no_face"
            df.at[i, "n_classifiers"] = 0
            df.at[i, "n_concordant"] = 0
            df.at[i, "concordant_2of3"] = False
            n_classified += 1
            continue
        patch = face.cropped_bgr
        ita = compute_ita(patch)
        mst = compute_mst(patch)
        ita_p = ita_to_perla(ita)
        mst_p = mst_to_perla(mst)
        casco_p = compute_casco_perla(path) if casco_on else None
        consensus = consensus_perla([ita_p, mst_p, casco_p])

        df.at[i, "ita_value"] = float(ita)
        df.at[i, "ita_label"] = ita_to_label(ita)
        df.at[i, "ita_perla"] = float(ita_p) if ita_p is not None else np.nan
        df.at[i, "mst_value"] = float(mst)
        df.at[i, "mst_perla"] = float(mst_p) if mst_p is not None else np.nan
        df.at[i, "casco_perla"] = float(casco_p) if casco_p is not None else np.nan
        df.at[i, "perla_consensus"] = (
            float(consensus.perla) if consensus.perla is not None else np.nan
        )
        df.at[i, "n_classifiers"] = int(consensus.n_available)
        df.at[i, "n_concordant"] = int(consensus.n_concordant)
        df.at[i, "concordant_2of3"] = bool(consensus.concordant_2of3)
        n_classified += 1
    return df, n_classified, n_skipped


def atomic_write(df: pd.DataFrame, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(dest)


def run(*, metadata: Path, classify: bool, png_base: Path | None, dry_run: bool) -> int:
    if not metadata.exists():
        log.error("metadata not found: %s", metadata)
        return 2

    df_before = pd.read_parquet(metadata)
    n_rows = len(df_before)
    cols_before = set(df_before.columns)
    log.info("read %s (%d rows, %d cols)", metadata, n_rows, len(cols_before))

    df, added = extend_schema(df_before)
    if added:
        log.info("added %d classifier columns: %s", len(added), ", ".join(added))
    else:
        log.info("schema already extended — no columns added")

    n_classified = n_skipped = 0
    if classify:
        log.info(
            "classify pass: looking for PNGs in metadata paths%s",
            f" with override {png_base}" if png_base else "",
        )
        df, n_classified, n_skipped = classify_existing(df, path_override=png_base)
        log.info(
            "classify pass: %d rows classified, %d skipped (PNG not found)",
            n_classified,
            n_skipped,
        )

    if dry_run:
        log.info("--dry-run: not writing %s", metadata)
        return 0

    # Skip the write if nothing changed (schema already extended AND classify=off).
    if not added and not classify:
        log.info("no-op (schema already extended and no --classify): skipping write")
        return 0

    atomic_write(df, metadata)
    log.info("wrote %s (%d rows, %d cols)", metadata, len(df), len(df.columns))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--metadata",
        type=Path,
        default=settings.images_dir / "main" / "metadata.parquet",
        help="Path to metadata.parquet (default: images/main/metadata.parquet).",
    )
    parser.add_argument(
        "--classify",
        action="store_true",
        help="In-place classify any row whose PNG file is accessible (no-op for rows whose path is on Colab Drive when run on Windows).",
    )
    parser.add_argument(
        "--png-base",
        type=Path,
        default=None,
        help="Override base directory to look up PNGs when the recorded `path` points elsewhere (e.g., Colab Drive paths from a remote shift).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return run(
        metadata=args.metadata,
        classify=args.classify,
        png_base=args.png_base,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
