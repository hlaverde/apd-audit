"""Unit tests for ``apd.generate.orchestrator.select_backend``.

These tests pin the fail-loud contract introduced after the hl#1 shift
mislabelled 20 SD-1.5 cells with FLUX images (silent fallback to
``PollinationsBackend(model="flux")``). The new behaviour is:

* ``"pollinations/<id>"`` → Pollinations relay.
* HF repo path + ``HF_TOKEN`` → HFBackend.
* HF repo path + ``ml`` extras installed → LocalBackend.
* Otherwise → raise ``BackendUnavailableError``.

Crucially, the function never substitutes a different open-weights model.
"""

from __future__ import annotations

import pytest

from apd.generate.orchestrator import (
    BackendUnavailableError,
    select_backend,
)
from apd.generate.pollinations_backend import PollinationsBackend


class TestPollinationsIdentifier:
    def test_pollinations_flux_identifier_routes_to_pollinations(self) -> None:
        backend = select_backend("pollinations/flux")
        assert isinstance(backend, PollinationsBackend)
        assert backend.model == "flux"

    def test_pollinations_turbo_identifier_passed_through(self) -> None:
        backend = select_backend("pollinations/turbo")
        assert isinstance(backend, PollinationsBackend)
        assert backend.model == "turbo"

    def test_pollinations_flux_realism_identifier(self) -> None:
        backend = select_backend("pollinations/flux-realism")
        assert isinstance(backend, PollinationsBackend)
        assert backend.model == "flux-realism"


class TestHfRepoPathWithoutTokenWithoutMl:
    """The critical regression test: SD-family without HF token AND without
    ml extras must FAIL, not silently fall back to Pollinations FLUX."""

    @pytest.fixture(autouse=True)
    def _clear_hf_token(self, monkeypatch):
        # Force settings.hf_token to falsy regardless of env.
        from apd import config as apd_config

        monkeypatch.setattr(apd_config.settings, "hf_token", "")
        yield

    @pytest.fixture(autouse=True)
    def _ml_extras_not_available(self, monkeypatch):
        """Pretend ml extras are not installed."""
        from apd.generate import local_backend

        monkeypatch.setattr(local_backend, "is_available", lambda: False)
        yield

    def test_sd_15_raises(self) -> None:
        with pytest.raises(BackendUnavailableError) as exc_info:
            select_backend("runwayml/stable-diffusion-v1-5")
        msg = str(exc_info.value)
        assert "runwayml/stable-diffusion-v1-5" in msg
        # The error must mention the three remediation paths.
        assert "pollinations/" in msg
        assert "HF_TOKEN" in msg
        assert "ml" in msg

    def test_sd_xl_raises(self) -> None:
        with pytest.raises(BackendUnavailableError):
            select_backend("stabilityai/stable-diffusion-xl-base-1.0")

    def test_sd_35_raises(self) -> None:
        with pytest.raises(BackendUnavailableError):
            select_backend("stabilityai/stable-diffusion-3.5-medium")

    def test_unknown_repo_path_raises(self) -> None:
        with pytest.raises(BackendUnavailableError):
            select_backend("vendor/some-model")

    def test_no_silent_pollinations_fallback(self) -> None:
        """Belt-and-suspenders: the bug we are guarding against was the
        old code returning ``PollinationsBackend(model="flux")`` for SD-1.5.
        Verify that NO PollinationsBackend is ever returned for an SD model."""
        with pytest.raises(BackendUnavailableError):
            select_backend("runwayml/stable-diffusion-v1-5")
        # If select_backend ever silently returned PollinationsBackend
        # instead of raising, this assertion would never be reached.


class TestHfRepoPathWithMlExtras:
    """When ml extras *are* installed, SD-family identifiers route to
    LocalBackend with the *same* model. No architecture substitution."""

    @pytest.fixture(autouse=True)
    def _clear_hf_token(self, monkeypatch):
        from apd import config as apd_config

        monkeypatch.setattr(apd_config.settings, "hf_token", "")
        yield

    def test_ml_available_routes_to_local_backend(self, monkeypatch) -> None:
        from apd.generate import local_backend

        monkeypatch.setattr(local_backend, "is_available", lambda: True)

        # Substitute LocalBackend with a stub that doesn't try to load torch.
        class _StubLocalBackend:
            name = "local"

            def __init__(self, model: str) -> None:
                self.model = model

        monkeypatch.setattr(local_backend, "LocalBackend", _StubLocalBackend)

        backend = select_backend("runwayml/stable-diffusion-v1-5")
        assert backend.name == "local"
        # Model identifier preserved verbatim — no substitution.
        assert backend.model == "runwayml/stable-diffusion-v1-5"


class TestPreferLocal:
    def test_prefer_local_with_ml_unavailable_raises(self, monkeypatch) -> None:
        from apd.generate import local_backend

        monkeypatch.setattr(local_backend, "is_available", lambda: False)
        with pytest.raises(BackendUnavailableError):
            select_backend("runwayml/stable-diffusion-v1-5", prefer_local=True)
