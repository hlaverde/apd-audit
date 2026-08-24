"""04 — Classify generated images.

Three phenotype classifiers run in parallel on every face crop:
    * CASCo (Rejón Piña & Ma 2023) via the ``skin-tone-classifier`` lib.
    * ITA in CIE-Lab → PERLA (Chardon 1991).
    * MST nearest reference RGB → PERLA (Google Research 2023).

The 2-of-3 concordance rule from proposal §6.2 collapses the three
outputs into a single ``perla_consensus`` plus a ``concordant_2of3``
quality flag. Production analysis restricts to ``concordant_2of3 = True``
when robustness specifications require it.
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
    casco_on = casco_available()
    log.info(
        "Classifying %d images (CASCo=%s, ITA=on, MST=on)",
        len(meta), "on" if casco_on else "OFF",
    )

    records: list[dict] = []
    for _, row in meta.iterrows():
        records.append(_classify_one(row, casco_on=casco_on))
    pd.DataFrame(records).to_parquet(OUT, index=False)
    log.info("Wrote %s (%d rows)", OUT, len(records))
    return 0


def _classify_one(row: pd.Series, *, casco_on: bool) -> dict:
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

    # ITA + MST from the face patch.
    patch = face.cropped_bgr
    ita = compute_ita(patch)
    mst = compute_mst(patch)
    ita_p = ita_to_perla(ita)
    mst_p = mst_to_perla(mst)

    # CASCo from the full image (it does its own face detection internally).
    casco_p = compute_casco_perla(path) if casco_on else None

    consensus = consensus_perla([ita_p, mst_p, casco_p])

    rec.update(
        {
            "ita_value": float(ita),
            "ita_label": ita_to_label(ita),
            "ita_perla": float(ita_p) if ita_p is not None else np.nan,
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


if __name__ == "__main__":
    sys.exit(main())
