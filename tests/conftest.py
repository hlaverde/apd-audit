"""Shared pytest fixtures."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def perla_tones() -> np.ndarray:
    return np.arange(1, 12)


@pytest.fixture
def light_skin_patch() -> np.ndarray:
    """64x64 BGR patch of a light skin tone (≈ MST 2)."""
    # BGR order — OpenCV convention.
    return np.full((64, 64, 3), (219, 231, 243), dtype=np.uint8)


@pytest.fixture
def dark_skin_patch() -> np.ndarray:
    """64x64 BGR patch of a dark skin tone (≈ MST 9)."""
    return np.full((64, 64, 3), (42, 49, 58), dtype=np.uint8)


@pytest.fixture
def random_noise_image() -> np.ndarray:
    """64x64 BGR random-noise image — used as a no-face smoke test."""
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8)
