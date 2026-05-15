"""04 — Classify generated images: MediaPipe + ITA + MST → data/interim/poc_phenotype.parquet."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from apd.classify.face_detect import detect_face
from apd.classify.skin_ita import compute_ita, ita_to_label, ita_to_perla
from apd.classify.skin_mst import compute_mst, mst_to_perla
from apd.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("04_classify")

META_IN = settings.images_dir / "poc" / "metadata.parquet"
OUT = settings.data_interim / "poc_phenotype.parquet"


def main() -> int:
    settings.data_interim.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        log.info("Cached: %s", OUT)
        return 0
    if not META_IN.exists():
        log.error("Missing %s. Run scripts/03_generate_images.py first.", META_IN)
        return 1

    meta = pd.read_parquet(META_IN)
    log.info("Classifying %d images", len(meta))

    records: list[dict] = []
    for _, row in meta.iterrows():
        records.append(_classify_one(row))
    pd.DataFrame(records).to_parquet(OUT, index=False)
    log.info("Wrote %s (%d rows)", OUT, len(records))
    return 0


def _classify_one(row: pd.Series) -> dict:
    path = Path(row["path"])
    face = detect_face(path)
    rec: dict = {
        "image_id": row["image_id"],
        "has_face": face.has_face,
        "n_faces": face.n_faces,
        "ita_value": float("nan"),
        "ita_label": "no_face",
        "ita_perla": np.nan,
        "mst_value": np.nan,
        "mst_perla": np.nan,
        "perla_consensus": np.nan,
    }
    if not face.has_face or face.cropped_bgr is None:
        return rec
    patch = face.cropped_bgr
    ita = compute_ita(patch)
    mst = compute_mst(patch)
    ita_p = ita_to_perla(ita)
    mst_p = mst_to_perla(mst)
    rec.update(
        {
            "ita_value": ita,
            "ita_label": ita_to_label(ita),
            "ita_perla": ita_p,
            "mst_value": mst,
            "mst_perla": mst_p,
            # 2-of-3 concordance reduces to 2-of-2 while CASCo is deferred:
            # we average ITA-PERLA and MST-PERLA. This is documented in
            # DECISIONS.md D-005 and replaced by a true mode-of-three once
            # CASCo lands.
            "perla_consensus": int(round((ita_p + mst_p) / 2.0)),
        },
    )
    return rec


if __name__ == "__main__":
    sys.exit(main())
