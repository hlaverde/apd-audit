"""Stratified sampling of images for blind PERLA labelling.

Default strategy: stratify by ``occupation`` and sample
``n_per_occupation`` images from each stratum, restricted to images
where face detection succeeded (``has_face = True``). Within each
stratum we randomise across language × model so the labellers see a
diverse mix and the inter-rater agreement is not dominated by a single
model's idiosyncrasies.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StratificationPlan:
    """Per-stratum sampling counts and seed for reproducibility."""

    n_per_occupation: int = 12
    seed: int = 20260514
    require_face: bool = True


# Columns the labelling parquet always carries.
LABELLING_SCHEMA: tuple[str, ...] = (
    "image_id",
    "occupation",
    "language",
    "model",
    "country",
    "path",
    "cl_perla",        # labeller CL — to be filled
    "yp_perla",        # labeller YP — to be filled
    "hl_adjudication", # only for disagreements
    "notes",
)


def sample_for_validation(
    panel: pd.DataFrame,
    plan: StratificationPlan = StratificationPlan(),
) -> pd.DataFrame:
    """Return a DataFrame of images to label, with empty PERLA columns.

    Parameters
    ----------
    panel : per-image DataFrame with at least ``image_id``, ``occupation``,
        ``language``, ``model``, ``country``, ``path`` and (if
        ``plan.require_face``) ``has_face``.
    plan : StratificationPlan controlling the per-stratum count, RNG seed
        and face-detection filter.
    """
    needed = {"image_id", "occupation", "language", "model", "country", "path"}
    if plan.require_face:
        needed.add("has_face")
    missing = needed - set(panel.columns)
    if missing:
        raise KeyError(f"panel missing columns: {sorted(missing)}")

    eligible = panel.copy()
    if plan.require_face:
        eligible = eligible[eligible["has_face"].fillna(False).astype(bool)]

    rng = np.random.default_rng(plan.seed)
    sampled_rows: list[pd.DataFrame] = []
    for occ, group in eligible.groupby("occupation", sort=True):
        if len(group) <= plan.n_per_occupation:
            sampled_rows.append(group)
            continue
        idx = rng.choice(len(group), size=plan.n_per_occupation, replace=False)
        sampled_rows.append(group.iloc[sorted(idx)])
    if not sampled_rows:
        return pd.DataFrame(columns=list(LABELLING_SCHEMA))

    sampled = pd.concat(sampled_rows, ignore_index=True)
    # Add empty labelling columns; NaN for integer slots (will become Int64
    # nullable type at parquet write time).
    sampled = sampled.assign(
        cl_perla=pd.NA,
        yp_perla=pd.NA,
        hl_adjudication=pd.NA,
        notes="",
    )
    # Project to the canonical schema in canonical order.
    return sampled[list(LABELLING_SCHEMA)].reset_index(drop=True)
