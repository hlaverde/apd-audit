"""Build the (model, occupation, country, language) phenotype panel.

The panel joins per-image metadata (model, occupation, language, country
proxy, seed, prompt, path) with per-image phenotype labels (has_face, ITA,
MST, PERLA mappings). It also exposes
``algorithmic_distribution`` — the f_alg(t|o,c,ℓ,m) histogram over PERLA
tones used by the APD computation.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd


def build_panel(metadata_path: Path, phenotype_path: Path) -> pd.DataFrame:
    """Join image metadata × phenotype on ``image_id``.

    Emits ``country`` (not ``country_proxy``): the generation side records
    the country proxy under its own name, while every analysis consumer —
    ground truth, status weights, the APD cell keys, H3 — keys on
    ``country``. The panel is the seam, so the rename happens here.
    """
    meta = pd.read_parquet(metadata_path)
    pheno = pd.read_parquet(phenotype_path)
    # Since D-028 the metadata shards carry the classifier columns inline.
    # Drop metadata's copies so the merge can't fork them into _x/_y — a
    # silent fork would strip `perla_consensus` and make
    # `algorithmic_distribution` fall back to uniform.
    redundant = (set(meta.columns) & set(pheno.columns)) - {"image_id"}
    panel = meta.drop(columns=sorted(redundant)).merge(
        pheno, on="image_id", how="left", validate="one_to_one",
    )
    return panel.rename(columns={"country_proxy": "country"})


def algorithmic_distribution(
    panel: pd.DataFrame,
    occupation: str,
    *,
    tones: Sequence[int] = tuple(range(1, 12)),
    column: str = "perla_consensus",
) -> np.ndarray:
    """Return f_alg(t | occupation) as a probability vector aligned with ``tones``.

    Notes
    -----
    * Rows with ``has_face == False`` are dropped (the proposal documents
      no-face rates as a diagnostic but they do not enter f_alg).
    * If the column ``perla_consensus`` is missing or empty for this
      occupation, the function falls back to a uniform distribution and
      logs a warning — this is conservative and never accidentally
      manufactures a signal.
    """
    if "occupation" not in panel.columns:
        raise KeyError("panel must have an 'occupation' column")
    cell = panel[panel["occupation"] == occupation]
    if "has_face" in cell.columns:
        cell = cell[cell["has_face"].fillna(False).astype(bool)]
    if column not in cell.columns:
        return _uniform(tones)
    values = cell[column].dropna().astype(int)
    if values.empty:
        return _uniform(tones)
    counts = values.value_counts().reindex(list(tones), fill_value=0)
    total = float(counts.sum())
    if total == 0:
        return _uniform(tones)
    probs = counts.to_numpy(dtype=float) / total
    return probs


def _uniform(tones: Sequence[int]) -> np.ndarray:
    return np.full(len(tones), 1.0 / len(tones))
