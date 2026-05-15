"""End-to-end integration test for the POC math pipeline.

Exercises ground-truth construction → synthetic per-image phenotype panel
→ algorithmic distribution → APD computation → CSV emission, with no
network calls. This proves the maths plumbing is wired up correctly
independent of the (slow, rate-limited) generation and classification
stages.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apd.apd.indicator import apd, compute_occupation_metrics
from apd.ground_truth.build import build_poc_ground_truth
from apd.panel.build import algorithmic_distribution


@pytest.mark.integration
def test_poc_math_pipeline_end_to_end(tmp_path: Path) -> None:
    # 1. Ground truth.
    gt = build_poc_ground_truth()
    assert set(gt.columns) >= {
        "country", "occupation", "perla_tone", "prob", "weight", "is_synthetic",
    }
    assert set(gt["occupation"].unique()) == {"CEO", "nurse", "domestic worker"}
    # Probabilities sum to 1 per occupation.
    for occ, group in gt.groupby("occupation"):
        assert group["prob"].sum() == pytest.approx(1.0, abs=1e-6)
    # Weights sum to 1.
    weights = gt[["occupation", "weight"]].drop_duplicates()
    assert weights["weight"].sum() == pytest.approx(1.0, abs=1e-6)

    # 2. Synthesise a tiny algorithmic panel: 10 images per occupation with
    #    PERLA values drawn from a known concentrated distribution at the
    #    light end (PERLA 2 or 3). This represents a model that systematically
    #    lightens *every* occupation, so APD should come out strongly negative
    #    on the high-status occupations and weakly positive on low-status.
    rng = np.random.default_rng(0)
    rows = []
    for occ in ("CEO", "nurse", "domestic worker"):
        for i in range(10):
            rows.append(
                {
                    "image_id": f"x__{occ}__{i}",
                    "occupation": occ,
                    "has_face": True,
                    "perla_consensus": int(rng.integers(2, 4)),
                },
            )
    panel = pd.DataFrame(rows)

    # 3. Algorithmic distribution per occupation.
    f_emp_by_occ = {
        occ: gt[gt["occupation"] == occ].sort_values("perla_tone")["prob"].to_numpy()
        for occ in ("CEO", "nurse", "domestic worker")
    }
    weight_by_occ = {
        occ: float(gt[gt["occupation"] == occ]["weight"].iloc[0])
        for occ in f_emp_by_occ
    }

    occ_results = []
    for occ in ("CEO", "nurse", "domestic worker"):
        f_alg = algorithmic_distribution(panel, occ)
        f_emp = f_emp_by_occ[occ]
        occ_results.append(
            compute_occupation_metrics(
                occupation=occ,
                f_alg=f_alg,
                f_emp=f_emp,
                weight=weight_by_occ[occ],
            ),
        )

    apd_value = apd(occ_results)

    # The CEO row (high weight, big lightening Δ<0) dominates → APD strictly negative.
    assert apd_value < 0

    # 4. Emit a CSV with the expected schema.
    out_path = tmp_path / "apd_poc.csv"
    pd.DataFrame(
        [
            {
                "occupation": r.occupation,
                "D": r.D,
                "delta": r.delta,
                "weight": r.weight,
                "signed_D": r.signed_D,
            }
            for r in occ_results
        ],
    ).to_csv(out_path, index=False)
    assert out_path.exists()
    written = pd.read_csv(out_path)
    assert len(written) == 3
    assert set(written.columns) >= {"occupation", "D", "delta", "weight", "signed_D"}
