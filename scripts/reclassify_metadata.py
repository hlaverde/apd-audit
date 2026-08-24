"""Re-run the phenotype classifiers over images/main/ and rewrite the
classifier columns of images/main/metadata.parquet in place.

Needed because the classifier output stored in the metadata was produced
at generation time (D-028) by an ITA implementation that used
``arctan2``. That form wraps patches with b* < 0 into quadrants II/III
and returns angles beyond ±90, which are not ITA at all; ``ita_to_perla``
then clamped them to PERLA 1 or 11 — the extremes of the scale. 610 of
10 663 detected faces (5.7%) carry such a value. See D-042.

The run is idempotent: it recomputes from the PNGs, so re-running after
another classifier change simply refreshes the columns again. Rows whose
PNG is no longer on disk (D-036) are left untouched and reported.

The metadata is backed up next to itself before anything is written, and
the new file is written to a temporary path and then moved into place, so
an interrupted run cannot leave a half-written parquet.

Usage:
    uv run python scripts/reclassify_metadata.py [--workers N] [--limit N]
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from apd.classify.consensus import consensus_perla  # noqa: E402
from apd.classify.face_detect import detect_face  # noqa: E402
from apd.classify.skin_casco import compute_casco_perla  # noqa: E402
from apd.classify.skin_casco import is_available as casco_available  # noqa: E402
from apd.classify.skin_ita import compute_ita, ita_to_label, ita_to_perla  # noqa: E402
from apd.classify.skin_mst import compute_mst, mst_to_perla  # noqa: E402
from apd.config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("reclassify")

META = settings.images_dir / "main" / "metadata.parquet"

CLASSIFIER_COLUMNS = (
    "has_face", "n_faces", "ita_value", "ita_label", "ita_perla",
    "mst_value", "mst_perla", "casco_perla", "perla_consensus",
    "n_classifiers", "n_concordant", "concordant_2of3",
)

_NO_FACE = {
    "has_face": False, "n_faces": 0,
    "ita_value": np.nan, "ita_label": "no_face", "ita_perla": np.nan,
    "mst_value": np.nan, "mst_perla": np.nan, "casco_perla": np.nan,
    "perla_consensus": np.nan,
    "n_classifiers": 0, "n_concordant": 0, "concordant_2of3": False,
}


def classify_one(args: tuple[str, str]) -> dict:
    """Classify one image. Runs in a worker process, so it takes and
    returns only picklable values."""
    image_id, path_str = args
    path = Path(path_str)
    face = detect_face(path)
    if not face.has_face or face.cropped_bgr is None:
        return {"image_id": image_id, **_NO_FACE, "n_faces": face.n_faces}

    patch = face.cropped_bgr
    ita = compute_ita(patch)
    mst = compute_mst(patch)
    ita_p = ita_to_perla(ita)
    mst_p = mst_to_perla(mst)
    casco_p = compute_casco_perla(path) if casco_available() else None
    consensus = consensus_perla([ita_p, mst_p, casco_p])
    return {
        "image_id": image_id,
        "has_face": True,
        "n_faces": int(face.n_faces),
        "ita_value": float(ita),
        "ita_label": ita_to_label(ita),
        "ita_perla": float(ita_p) if ita_p is not None else np.nan,
        "mst_value": float(mst),
        "mst_perla": float(mst_p) if mst_p is not None else np.nan,
        "casco_perla": float(casco_p) if casco_p is not None else np.nan,
        "perla_consensus": (
            float(consensus.perla) if consensus.perla is not None else np.nan
        ),
        "n_classifiers": int(consensus.n_available),
        "n_concordant": int(consensus.n_concordant),
        "concordant_2of3": bool(consensus.concordant_2of3),
    }


def _repair_unrecomputable_ita(meta: pd.DataFrame, recomputed: set[str]) -> pd.DataFrame:
    """Invalidate out-of-range ITA on rows that could not be re-derived.

    Rows whose PNG is gone (D-036) keep whatever the old implementation
    stored, which for a handful of them is an angle outside Chardon's
    (-90, 90) — the arctan2 signature. The pixels are unavailable, but
    MST and CASCo were never affected by that bug, so the row is
    recoverable: drop the ITA vote and re-take the consensus from the
    classifiers that remain.
    """
    stale = (
        ~meta["image_id"].isin(recomputed)
        & meta["ita_value"].notna()
        & (meta["ita_value"].abs() > 90.0)
    )
    if not stale.any():
        return meta
    log.info("Repairing %d row(s) with an unrecomputable out-of-range ITA.", int(stale.sum()))
    for i in meta.index[stale]:
        mst_p = meta.at[i, "mst_perla"]
        casco_p = meta.at[i, "casco_perla"]
        votes = [
            int(v) for v in (mst_p, casco_p)
            if v is not None and not pd.isna(v)
        ]
        consensus = consensus_perla(votes)
        meta.at[i, "ita_value"] = np.nan
        meta.at[i, "ita_label"] = "unknown"
        meta.at[i, "ita_perla"] = np.nan
        meta.at[i, "perla_consensus"] = (
            float(consensus.perla) if consensus.perla is not None else np.nan
        )
        meta.at[i, "n_classifiers"] = int(consensus.n_available)
        meta.at[i, "n_concordant"] = int(consensus.n_concordant)
        meta.at[i, "concordant_2of3"] = bool(consensus.concordant_2of3)
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=None,
                    help="classify only the first N rows (for a dry run)")
    args = ap.parse_args()

    if not META.exists():
        log.error("Missing %s", META)
        return 1

    meta = pd.read_parquet(META)
    log.info("Loaded %d rows from %s", len(meta), META)

    work: list[tuple[str, str]] = []
    missing: list[str] = []
    for image_id, rel in zip(meta["image_id"], meta["path"], strict=True):
        p = Path(rel)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if p.exists():
            work.append((image_id, str(p)))
        else:
            missing.append(image_id)
    if args.limit:
        work = work[: args.limit]
    log.info("%d images to classify, %d with no PNG on disk (left untouched)",
             len(work), len(missing))

    before = meta.set_index("image_id")
    results: list[dict] = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, rec in enumerate(pool.map(classify_one, work, chunksize=32), start=1):
            results.append(rec)
            if i % 1000 == 0:
                log.info("  %d / %d", i, len(work))

    new = pd.DataFrame(results).set_index("image_id")
    log.info("Classified %d images.", len(new))

    if not args.limit:
        backup = META.with_suffix(".parquet.pre_d042_backup")
        if not backup.exists():
            shutil.copy2(META, backup)
            log.info("Backed up the previous metadata to %s", backup.name)

    # --- what changed -------------------------------------------------
    common = before.index.intersection(new.index)
    old_c = before.loc[common, "perla_consensus"]
    new_c = new.loc[common, "perla_consensus"]
    changed = int((old_c.fillna(-1) != new_c.fillna(-1)).sum())
    old_face = before.loc[common, "has_face"].astype(bool)
    new_face = new.loc[common, "has_face"].astype(bool)
    log.info(
        "perla_consensus changed for %d/%d (%.1f%%); mean %.3f -> %.3f",
        changed, len(common), 100.0 * changed / max(len(common), 1),
        float(old_c.mean()), float(new_c.mean()),
    )
    log.info(
        "faces: %d -> %d; ITA unavailable (non-skin patch): %d",
        int(old_face.sum()), int(new_face.sum()),
        int(new.loc[common, "ita_perla"].isna().sum() - (~new_face).sum()),
    )
    out_of_range = int((new.loc[common, "ita_value"].abs() > 90).sum())
    log.info("ITA values outside Chardon's (-90, 90): %d (must be 0)", out_of_range)

    if args.limit:
        log.info("--limit set: metadata NOT written.")
        return 0

    for col in CLASSIFIER_COLUMNS:
        meta.loc[meta["image_id"].isin(common), col] = (
            meta.loc[meta["image_id"].isin(common), "image_id"].map(new[col]).to_numpy()
        )
    meta = _repair_unrecomputable_ita(meta, recomputed=set(common))
    meta["has_face"] = meta["has_face"].astype(bool)
    meta["concordant_2of3"] = meta["concordant_2of3"].astype(bool)

    tmp = META.with_suffix(".parquet.tmp")
    meta.to_parquet(tmp, index=False)
    tmp.replace(META)
    log.info("Rewrote %s (%d rows).", META, len(meta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
