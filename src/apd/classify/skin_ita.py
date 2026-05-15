"""Individual Typology Angle (ITA) in CIE-Lab and its mapping to PERLA.

ITA is the canonical dermatological skin-tone index (Chardon 1991): the
angle, in degrees, between the (L=50, b=0) point and (L_med, b_med) of the
skin patch in the L*a*b* colour space.

    ITA = arctan2(L − 50, b) · 180 / π

Standard ITA bins (Fitzpatrick-aligned), darkest → lightest:
    dark        < -30
    brown   -30 .. 10
    tan      10 .. 28
    intermediate 28 .. 41
    light       41 .. 55
    very light  >  55
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

ITA_BIN_EDGES: tuple[float, ...] = (-90.0, -30.0, 10.0, 28.0, 41.0, 55.0, 90.0)
ITA_BIN_LABELS: tuple[str, ...] = (
    "dark", "brown", "tan", "intermediate", "light", "very_light",
)


def compute_ita(bgr_patch: np.ndarray) -> float:
    """Return ITA (degrees) for a BGR uint8 face patch.

    The patch is filtered to mid-luminance pixels (L ∈ (20, 95)) to drop
    background pixels accidentally included in the bounding box. Returns
    NaN if no in-range pixel is left.
    """
    if bgr_patch is None or bgr_patch.size == 0:
        return float("nan")

    lab = cv2.cvtColor(bgr_patch, cv2.COLOR_BGR2LAB).astype(np.float64)
    # OpenCV's L*a*b* is scaled to 0..255 for L and 0..255 for a/b with
    # offset 128 on a/b. Convert L to 0..100 and a/b to ±127.
    luminance = lab[..., 0] * (100.0 / 255.0)
    b_star = lab[..., 2] - 128.0

    mask = (luminance > 20.0) & (luminance < 95.0)
    if not mask.any():
        return float("nan")
    l_med = float(np.median(luminance[mask]))
    b_med = float(np.median(b_star[mask]))
    if b_med == 0.0:
        return 90.0 if l_med >= 50.0 else -90.0
    return float(np.degrees(np.arctan2(l_med - 50.0, b_med)))


def ita_to_label(ita: float) -> str:
    if np.isnan(ita):
        return "unknown"
    for i in range(len(ITA_BIN_EDGES) - 1):
        if ITA_BIN_EDGES[i] <= ita < ITA_BIN_EDGES[i + 1]:
            return ITA_BIN_LABELS[i]
    return "unknown"


def ita_to_perla(
    ita: float,
    *,
    perla_tones: Sequence[int] = tuple(range(1, 12)),
) -> int:
    """Map ITA (continuous) to PERLA ordinal {1, …, 11}.

    Calibration (linear on the angle scale):
        ITA = +55  → PERLA 1  (very light, lightest tone on the palette)
        ITA = -50  → PERLA 11 (darkest tone)
    Values outside [-50, 55] saturate to the nearest endpoint. NaN ITA
    maps to the central tone (6) so that "no skin pixels found" is a
    conservative neutral rather than a wild outlier.
    """
    if np.isnan(ita):
        return int((perla_tones[0] + perla_tones[-1]) / 2)
    n = len(perla_tones)
    # Fraction towards the dark end (PERLA n) — clamped.
    frac = (55.0 - ita) / (55.0 - (-50.0))
    frac = float(np.clip(frac, 0.0, 1.0))
    idx = int(round(frac * (n - 1)))
    return int(perla_tones[idx])
