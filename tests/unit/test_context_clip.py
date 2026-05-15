"""Unit tests for the CLIP context-classifier wrapper.

Tests that don't require torch + transformers pass unconditionally; the
ones that actually run CLIP are skipped if the ``ml`` extras are not
installed (CI / lightweight environments).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from apd.classify.context_clip import (
    DEFAULT_CONTEXT_LABELS,
    DEFAULT_MODEL_NAME,
    CLIPContextScorer,
    ContextScore,
    is_available,
)


class TestModuleSurface:
    def test_default_labels_match_proposal(self) -> None:
        # Proposal §6.2 step 5 — six contextual labels.
        assert len(DEFAULT_CONTEXT_LABELS) == 6
        joined = " | ".join(DEFAULT_CONTEXT_LABELS).lower()
        for required in ("rural", "urban", "office", "workshop", "folkloric", "neutral"):
            assert required in joined, f"missing concept {required!r}"

    def test_default_model_is_openai_clip_b32(self) -> None:
        assert DEFAULT_MODEL_NAME == "openai/clip-vit-base-patch32"


class TestScorerInstantiation:
    def test_no_torch_imported_on_construct(self) -> None:
        """Instantiation must not trigger the heavy torch import."""
        # The constructor only stores attributes; it does not touch torch.
        scorer = CLIPContextScorer()
        assert scorer.labels == DEFAULT_CONTEXT_LABELS
        assert scorer._model is None
        assert scorer._processor is None

    def test_custom_labels_round_trip(self) -> None:
        custom = ["a city", "a forest"]
        scorer = CLIPContextScorer(labels=custom)
        assert scorer.labels == tuple(custom)

    def test_score_raises_clear_error_without_ml_extras(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """If torch / transformers are absent, ``score`` must explain how
        to install them rather than producing an obscure ImportError."""
        import builtins

        original_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name in ("torch", "transformers"):
                raise ImportError(f"simulated missing {name}")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _fake_import)
        scorer = CLIPContextScorer()
        with pytest.raises(RuntimeError, match="uv sync --extra ml"):
            scorer.score(tmp_path / "anything.png")


class TestContextScoreDataclass:
    def test_dominant_label_is_argmax(self) -> None:
        score = ContextScore(
            image_id="x",
            probs={"rural": 0.7, "urban": 0.2, "office": 0.1},
        )
        assert score.dominant_label == "rural"
        assert score.dominant_prob == pytest.approx(0.7)


@pytest.mark.skipif(not is_available(), reason="ml extras (torch+transformers) not installed")
class TestCLIPIntegration:
    """End-to-end tests that actually load the CLIP model.

    These tests are skipped on environments without the ml extras to
    keep ``pytest`` fast on a base install. To run them locally::

        uv sync --extra ml
        uv run pytest tests/unit/test_context_clip.py -k Integration
    """

    @pytest.fixture(scope="class")
    def synthetic_office_image(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        """A solid-colour 64x64 image standing in for an office wall."""
        import cv2

        tmp = tmp_path_factory.mktemp("clip")
        path = tmp / "office.png"
        img = np.full((64, 64, 3), (210, 200, 195), dtype=np.uint8)  # off-white BGR
        cv2.imwrite(str(path), img)
        return path

    def test_score_returns_normalised_probabilities(
        self, synthetic_office_image: Path,
    ) -> None:
        scorer = CLIPContextScorer()
        score = scorer.score(synthetic_office_image, image_id="office")
        assert isinstance(score, ContextScore)
        assert set(score.probs) == set(DEFAULT_CONTEXT_LABELS)
        # Softmax → sums to 1, every value in [0, 1].
        s = sum(score.probs.values())
        assert 0.99 < s < 1.01
        for p in score.probs.values():
            assert 0.0 <= p <= 1.0
