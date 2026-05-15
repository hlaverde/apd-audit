"""Unit tests for the skin-tone classifiers (ITA + MST).

The classifiers are exercised on synthetic patches of known RGB values.
The MediaPipe face detector is exercised through a smoke test only — a
synthetic noise image legitimately yields ``has_face=False`` and the
test just ensures the call does not raise.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from apd.classify.skin_ita import ita_to_label, ita_to_perla, compute_ita
from apd.classify.skin_mst import compute_mst, mst_to_perla


class TestITA:
    def test_light_patch_yields_high_ita(self, light_skin_patch: np.ndarray) -> None:
        ita = compute_ita(light_skin_patch)
        assert not np.isnan(ita)
        assert ita > 40

    def test_dark_patch_yields_low_ita(self, dark_skin_patch: np.ndarray) -> None:
        ita = compute_ita(dark_skin_patch)
        assert not np.isnan(ita)
        assert ita < 0

    def test_empty_input_returns_nan(self) -> None:
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        assert np.isnan(compute_ita(empty))

    def test_label_classification(self) -> None:
        assert ita_to_label(60.0) == "very_light"
        assert ita_to_label(-45.0) == "dark"
        assert ita_to_label(float("nan")) == "unknown"

    def test_perla_mapping_monotonic(self) -> None:
        # Light → small PERLA; dark → large PERLA.
        assert ita_to_perla(70) < ita_to_perla(0) < ita_to_perla(-50)

    def test_perla_mapping_endpoints_clip(self) -> None:
        assert 1 <= ita_to_perla(200) <= 11
        assert 1 <= ita_to_perla(-200) <= 11

    def test_nan_perla_returns_midpoint(self) -> None:
        # The midpoint for the 11-tone scale is 6.
        assert ita_to_perla(float("nan")) == 6


class TestMST:
    def test_light_patch_yields_low_mst(self, light_skin_patch: np.ndarray) -> None:
        mst = compute_mst(light_skin_patch)
        assert 1 <= mst <= 3

    def test_dark_patch_yields_high_mst(self, dark_skin_patch: np.ndarray) -> None:
        mst = compute_mst(dark_skin_patch)
        assert 8 <= mst <= 10

    def test_empty_input_returns_neutral(self) -> None:
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        assert compute_mst(empty) == 5

    def test_perla_mapping_monotonic(self) -> None:
        prev = None
        for m in range(1, 11):
            p = mst_to_perla(m)
            assert 1 <= p <= 11
            if prev is not None:
                assert p >= prev
            prev = p


def test_face_detect_does_not_crash_on_noise(
    tmp_path: Path,
    random_noise_image: np.ndarray,
) -> None:
    from apd.classify.face_detect import detect_face  # noqa: WPS433

    p = tmp_path / "noise.png"
    cv2.imwrite(str(p), random_noise_image)
    result = detect_face(p)
    # Noise image legitimately has no face. We only require that the call
    # produced a FaceResult-shaped object.
    assert hasattr(result, "has_face")
    assert isinstance(result.has_face, bool)
    assert result.has_face is False  # noise → no face


def test_face_detect_returns_no_face_for_missing_file(tmp_path: Path) -> None:
    from apd.classify.face_detect import detect_face  # noqa: WPS433

    result = detect_face(tmp_path / "does_not_exist.png")
    assert result.has_face is False
    assert result.bbox is None
    assert result.cropped_bgr is None


class TestCASCo:
    def test_module_importable(self) -> None:
        from apd.classify import skin_casco  # noqa: WPS433

        assert hasattr(skin_casco, "compute_casco_perla")
        assert hasattr(skin_casco, "HEX_TO_PERLA")

    def test_hex_to_perla_table_is_well_formed(self) -> None:
        from apd.classify.skin_casco import HEX_TO_PERLA  # noqa: WPS433

        # 11 PERLA tones, lightest = 1, darkest = 11.
        assert set(HEX_TO_PERLA.values()) == set(range(1, 12))
        # All keys are lower-case 7-character hex strings.
        for h in HEX_TO_PERLA:
            assert h.startswith("#") and len(h) == 7 and h == h.lower()

    def test_perla_lightest_is_one(self) -> None:
        from apd.classify.skin_casco import HEX_TO_PERLA  # noqa: WPS433

        # By the project convention, the lightest hex must map to PERLA 1.
        assert HEX_TO_PERLA["#fbf2f3"] == 1
        assert HEX_TO_PERLA["#373028"] == 11

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        from apd.classify.skin_casco import compute_casco_perla  # noqa: WPS433

        assert compute_casco_perla(tmp_path / "missing.png") is None

    def test_contract_on_noise_image(
        self,
        tmp_path: Path,
        random_noise_image: np.ndarray,
    ) -> None:
        from apd.classify.skin_casco import compute_casco_perla  # noqa: WPS433

        p = tmp_path / "noise.png"
        cv2.imwrite(str(p), random_noise_image)
        # CASCo's face detection is permissive; it may return PERLA 1..11 or
        # None on random noise. The contract is that the return type is an
        # int in [1, 11] OR None, never anything else.
        out = compute_casco_perla(p)
        assert out is None or (isinstance(out, int) and 1 <= out <= 11)
