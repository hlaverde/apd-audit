"""Publication-style matplotlib helpers.

Conventions:
    * Default font size 10, title 11, 300 dpi for saved figures.
    * Spines simplified (no top/right) for a cleaner look.
    * No seaborn — we stick to vanilla matplotlib for full editorial control.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless backend — required for CI / Makefile runs
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

plt.rcParams.update(
    {
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
    },
)


def plot_gradient(apd_table: pd.DataFrame, out_path: Path) -> Path:
    """Scatter of Δ(o) against status weight w(o) for POC inspection.

    Expected columns: occupation, weight, delta.
    """
    fig, ax = plt.subplots(figsize=(5.0, 3.5), tight_layout=True)
    ax.axhline(0.0, color="grey", linewidth=0.6)
    ax.scatter(
        apd_table["weight"],
        apd_table["delta"],
        s=60,
        color="#1f77b4",
        zorder=3,
        edgecolor="white",
        linewidth=0.5,
    )
    for _, row in apd_table.iterrows():
        ax.annotate(
            row["occupation"],
            (row["weight"], row["delta"]),
            fontsize=9,
            xytext=(6, 6),
            textcoords="offset points",
        )
    ax.set_xlabel(r"Status weight $w(o)$ (percentile-rank of mean monthly income)")
    ax.set_ylabel(r"$\Delta(o) = E[t\mid f_{alg}] - E[t\mid f_{emp}]$")
    ax.set_title("Pigmentocratic gradient — POC (3 occupations, Colombia)")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def plot_perla_distribution(
    distributions: dict[str, np.ndarray],
    out_path: Path,
    *,
    tones: np.ndarray | None = None,
) -> Path:
    """Bar plot of f_alg / f_emp side by side per occupation."""
    if tones is None:
        tones = np.arange(1, 12)
    n = len(distributions)
    fig, axes = plt.subplots(1, n, figsize=(3.6 * n, 3.2), sharey=True, tight_layout=True)
    if n == 1:
        axes = [axes]
    for ax, (label, dist) in zip(axes, distributions.items(), strict=True):
        ax.bar(tones, dist, color="#1f77b4", width=0.7)
        ax.set_title(label)
        ax.set_xlabel("PERLA tone (1 = lightest, 11 = darkest)")
        ax.set_xticks(tones)
    axes[0].set_ylabel("probability")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path
