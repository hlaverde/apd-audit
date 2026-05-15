"""04b — Production classification: read images/main/metadata.parquet,
classify every image with face-detect + CASCo + ITA + MST + consensus,
write data/interim/main_phenotype.parquet.

Same logic as 04_classify_images.py but for the main grid (after the
coauthor shifts have populated images/main/).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from apd.classify.consensus import consensus_perla
from apd.classify.face_detect import detect_face
from apd.classify.skin_casco import compute_casco_perla, is_available as casco_available
from apd.classify.skin_ita import compute_ita, ita_to_label, ita_to_perla
from apd.classify.skin_mst import compute_mst, mst_to_perla
from apd.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("04b_classify_main")

META_IN = settings.images_dir / "main" / "metadata.parquet"
OUT = settings.data_interim / "main_phenotype.parquet"


def _classify_one(row: pd.Series, casco_on: bool) -> dict:
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
        "casco_perla": np.nan,
        "perla_consensus": np.nan,
        "n_classifiers": 0,
        "n_concordant": 0,
        "concordant_2of3": False,
    }
    if not face.has_face or face.cropped_bgr is None:
        return rec
    patch = face.cropped_bgr
    ita = compute_ita(patch)
    mst = compute_mst(patch)
    ita_p = ita_to_perla(ita)
    mst_p = mst_to_perla(mst)
    casco_p = compute_casco_perla(path) if casco_on else None
    consensus = consensus_perla([ita_p, mst_p, casco_p])
    rec.update(
        {
            "ita_value": float(ita),
            "ita_label": ita_to_label(ita),
            "ita_perla": int(ita_p),
            "mst_value": int(mst),
            "mst_perla": int(mst_p),
            "casco_perla": int(casco_p) if casco_p is not None else np.nan,
            "perla_consensus": consensus.perla,
            "n_classifiers": consensus.n_available,
            "n_concordant": consensus.n_concordant,
            "concordant_2of3": consensus.concordant_2of3,
        },
    )
    return rec


def main() -> int:
    settings.data_interim.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        log.info("Cached: %s", OUT)
        return 0
    if not META_IN.exists():
        log.error("Missing %s. Generate main images via the notebook first.", META_IN)
        return 1

    meta = pd.read_parquet(META_IN)
    casco_on = casco_available()
    log.info("Classifying %d images (CASCo=%s)", len(meta), "on" if casco_on else "OFF")

    records = [_classify_one(row, casco_on=casco_on) for _, row in meta.iterrows()]
    pd.DataFrame(records).to_parquet(OUT, index=False)
    log.info("Wrote %s (%d rows)", OUT, len(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
