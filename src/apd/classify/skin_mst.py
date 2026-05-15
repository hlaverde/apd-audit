"""Monk Skin Tone Scale (MST) classification and PERLA crosswalk.

The MST scale (Google Research, 2023) has 10 anchor tones with public RGB
reference values. We assign a face patch to the MST tone whose anchor RGB
has minimum Euclidean distance to the patch's median RGB (after dropping
brightness extremes).
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

# Reference RGB values for the 10 MST tones, taken from the Google
# Research publication and the skintone.google reference card.
MST_REFERENCE_RGB: np.ndarray = np.array(
    [
        (246, 237, 228),  # MST 1
        (243, 231, 219),  # MST 2
        (247, 234, 208),  # MST 3
        (234, 218, 186),  # MST 4
        (215, 189, 150),  # MST 5
        (160, 126, 86),   # MST 6
        (130, 92, 67),    # MST 7
        (96, 65, 52),     # MST 8
        (58, 49, 42),     # MST 9
        (41, 36, 32),     # MST 10
    ],
    dtype=np.float64,
)


def compute_mst(bgr_patch: np.ndarray) -> int:
    """Return the nearest MST tone (1..10) for a BGR uint8 face patch."""
    if bgr_patch is None or bgr_patch.size == 0:
        return 5  # middle of scale = safe neutral when no signal

    lab = cv2.cvtColor(bgr_patch, cv2.COLOR_BGR2LAB).astype(np.float64)
    luminance = lab[..., 0] * (100.0 / 255.0)
    # Bounds match the MST anchor range (MST 10 ≈ L 18; MST 1 ≈ L 94)
    # plus a small margin so that solid-color reference patches don't fall
    # outside the filter at the extremes.
    mask = (luminance > 15.0) & (luminance < 97.0)
    if not mask.any():
        return 5

    rgb = cv2.cvtColor(bgr_patch, cv2.COLOR_BGR2RGB).astype(np.float64)
    rgb_flat = rgb.reshape(-1, 3)[mask.reshape(-1)]
    median_rgb = np.median(rgb_flat, axis=0)
    dist = np.linalg.norm(MST_REFERENCE_RGB - median_rgb, axis=1)
    return int(np.argmin(dist) + 1)


def mst_to_perla(
    mst: int,
    *,
    perla_tones: Sequence[int] = tuple(range(1, 12)),
) -> int:
    """Stretch MST 1..10 onto PERLA 1..11 by ordinal interpolation."""
    if mst < 1 or mst > 10:
        return int((perla_tones[0] + perla_tones[-1]) / 2)
    n = len(perla_tones)
    frac = (mst - 1) / 9.0
    idx = int(round(frac * (n - 1)))
    return int(perla_tones[idx])
