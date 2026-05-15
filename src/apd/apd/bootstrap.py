"""Bootstrap confidence intervals for APD-derived statistics.

The proposal §6.2 step 7 prescribes 1 000 bootstrap replicates for the
confidence intervals on D, Δ and APD. We implement the standard
**non-parametric bootstrap with replacement** at the image level within
each cell: for each replicate we resample N = 30 image-rows per
(occupation × language × model) cell, recompute f_alg, D and Δ from the
resampled rows, and aggregate to APD with the (fixed) status weights.
Quantiles of the 1 000 replicates give percentile CIs.

The point estimate is the value computed from the *original* sample;
the bootstrap supplies only the CI bounds. This matches the
``bootstrap_percentile_ci`` recommendation in Efron & Tibshirani (1993)
and the convention used by Bianchi 2023 and AlDahoul 2025.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from apd.apd.indicator import apd, compute_occupation_metrics
from apd.panel.build import algorithmic_distribution


@dataclass(frozen=True)
class BootstrapEstimate:
    """Point estimate + percentile CI for a single statistic."""

    name: str
    point: float
    ci_lower: float
    ci_upper: float
    n_replicates: int
    ci_level: float


def bootstrap_apd(
    panel: pd.DataFrame,
    ground_truth: pd.DataFrame,
    *,
    occupations: Sequence[str] | None = None,
    n_replicates: int = 1000,
    ci_level: float = 0.95,
    seed: int = 20260514,
    consensus_column: str = "perla_consensus",
) -> dict[str, BootstrapEstimate]:
    """Return percentile CIs for D(o), Δ(o), and aggregate APD.

    Parameters
    ----------
    panel : per-image DataFrame (one row per generated image) with at least
        ``occupation``, ``has_face`` and ``consensus_column`` columns.
    ground_truth : long-form f_emp(t | o, c) with columns
        ``occupation``, ``perla_tone``, ``prob`` and ``weight``.
    occupations : optional restriction; defaults to all occupations in
        ``ground_truth``.
    n_replicates : number of bootstrap samples. 1 000 per proposal §6.2.
    ci_level : nominal confidence level (0.95 for a 95% CI).
    seed : RNG seed for reproducibility.
    consensus_column : column on ``panel`` carrying the per-image PERLA
        consensus value.

    Returns
    -------
    dict keyed by statistic name:
        ``"APD"`` plus ``"D[<occupation>]"`` and ``"delta[<occupation>]"``
        for every occupation in the ground truth.
    """
    if occupations is None:
        occupations = list(ground_truth["occupation"].unique())

    rng = np.random.default_rng(seed)
    alpha = (1.0 - ci_level) / 2.0

    # Pre-index per-occupation views so the bootstrap loop is cheap.
    per_occ_panel: dict[str, pd.DataFrame] = {}
    per_occ_f_emp: dict[str, np.ndarray] = {}
    per_occ_weight: dict[str, float] = {}
    for occ in occupations:
        per_occ_panel[occ] = panel[panel["occupation"] == occ].reset_index(drop=True)
        gt = ground_truth[ground_truth["occupation"] == occ].sort_values("perla_tone")
        per_occ_f_emp[occ] = gt["prob"].to_numpy(dtype=float)
        per_occ_weight[occ] = float(gt["weight"].iloc[0])

    # 1. Point estimate from the original sample.
    point_results = []
    for occ in occupations:
        f_alg = algorithmic_distribution(per_occ_panel[occ], occ, column=consensus_column)
        m = compute_occupation_metrics(occ, f_alg, per_occ_f_emp[occ], per_occ_weight[occ])
        point_results.append(m)
    point_apd = apd(point_results)
    point_d = {r.occupation: r.D for r in point_results}
    point_delta = {r.occupation: r.delta for r in point_results}

    # 2. Bootstrap loop.
    boot_apd = np.empty(n_replicates, dtype=float)
    boot_d = {occ: np.empty(n_replicates, dtype=float) for occ in occupations}
    boot_delta = {occ: np.empty(n_replicates, dtype=float) for occ in occupations}

    for r in range(n_replicates):
        rep_results = []
        for occ in occupations:
            cell = per_occ_panel[occ]
            n = len(cell)
            if n == 0:
                # No images for this occupation — propagate a zero
                rep_results.append(
                    compute_occupation_metrics(
                        occ,
                        per_occ_f_emp[occ],
                        per_occ_f_emp[occ],
                        per_occ_weight[occ],
                    ),
                )
                continue
            idx = rng.integers(0, n, size=n)
            resampled = cell.iloc[idx]
            f_alg = algorithmic_distribution(resampled, occ, column=consensus_column)
            m = compute_occupation_metrics(
                occ, f_alg, per_occ_f_emp[occ], per_occ_weight[occ],
            )
            rep_results.append(m)
            boot_d[occ][r] = m.D
            boot_delta[occ][r] = m.delta
        boot_apd[r] = apd(rep_results)

    # 3. Percentile CIs.
    lo_p, hi_p = 100.0 * alpha, 100.0 * (1.0 - alpha)
    out: dict[str, BootstrapEstimate] = {}
    out["APD"] = BootstrapEstimate(
        name="APD",
        point=point_apd,
        ci_lower=float(np.percentile(boot_apd, lo_p)),
        ci_upper=float(np.percentile(boot_apd, hi_p)),
        n_replicates=n_replicates,
        ci_level=ci_level,
    )
    for occ in occupations:
        out[f"D[{occ}]"] = BootstrapEstimate(
            name=f"D[{occ}]",
            point=point_d[occ],
            ci_lower=float(np.percentile(boot_d[occ], lo_p)),
            ci_upper=float(np.percentile(boot_d[occ], hi_p)),
            n_replicates=n_replicates,
            ci_level=ci_level,
        )
        out[f"delta[{occ}]"] = BootstrapEstimate(
            name=f"delta[{occ}]",
            point=point_delta[occ],
            ci_lower=float(np.percentile(boot_delta[occ], lo_p)),
            ci_upper=float(np.percentile(boot_delta[occ], hi_p)),
            n_replicates=n_replicates,
            ci_level=ci_level,
        )
    return out
