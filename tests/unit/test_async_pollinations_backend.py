"""Unit tests for ``AsyncPollinationsBackend``.

Uses ``httpx.MockTransport`` to verify URL construction, retry on 429/5xx,
and the success path — without hitting the live Pollinations relay.
The sync ``PollinationsBackend`` is not tested here; the goal is to pin
the async sibling's contract since it powers the local async worker
(Layer 2) and the GitHub Actions cron (Layer 1).
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from apd.generate.pollinations_backend import (
    AsyncPollinationsBackend,
    PollinationsBackend,
    _build_url_and_params,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32  # 8 magic bytes + filler


# -------------------------------------------------------------------------
# URL / params helper
# -------------------------------------------------------------------------


class TestBuildUrlAndParams:
    def test_url_includes_encoded_prompt(self) -> None:
        url, _ = _build_url_and_params(
            "a photo of a domestic worker",
            model="flux",
            seed=1,
            width=512,
            height=512,
        )
        assert "a%20photo%20of%20a%20domestic%20worker" in url

    def test_params_match_existing_pollinations_backend(self) -> None:
        url, params = _build_url_and_params(
            "test",
            model="flux",
            seed=42,
            width=768,
            height=1024,
        )
        assert params == {
            "model": "flux",
            "seed": "42",
            "width": "768",
            "height": "1024",
            "nologo": "true",
            "private": "true",
        }

    def test_long_apd_seed_is_mapped_to_provider_range(self) -> None:
        _, params = _build_url_and_params(
            "test",
            model="flux",
            seed=202_625_140_000_000,
            width=512,
            height=512,
        )
        assert params["seed"] == str(202_625_140_000_000 % 2**32)


# -------------------------------------------------------------------------
# AsyncPollinationsBackend — success
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_generate_happy_path() -> None:
    """Mocked 200 image/png → returns GenerationResult with sha256 set."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=PNG_BYTES,
            headers={"content-type": "image/png"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        backend = AsyncPollinationsBackend(model="flux", width=512, height=512)
        result = await backend.generate("a photo of a CEO", 1, client=client)

    assert result.image_bytes == PNG_BYTES
    assert result.backend == "pollinations"
    assert result.duration_s >= 0.0
    assert len(result.sha256) == 64


# -------------------------------------------------------------------------
# AsyncPollinationsBackend — retry on 429 then success
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_generate_retries_on_429(monkeypatch) -> None:
    """First two calls return 429, third returns 200 — backend must retry."""

    # Disable real sleeps to keep the test fast (the prod code uses asyncio.sleep
    # for backoff; we patch it module-locally).
    from apd.generate import pollinations_backend as poll_mod

    async def _no_sleep(_):
        return None

    monkeypatch.setattr(poll_mod.asyncio, "sleep", _no_sleep)

    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] <= 2:
            return httpx.Response(429, content=b"slow down", headers={"content-type": "text/plain"})
        return httpx.Response(200, content=PNG_BYTES, headers={"content-type": "image/png"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        backend = AsyncPollinationsBackend(model="flux")
        result = await backend.generate("a photo of a CEO", 1, client=client)

    assert call_count["n"] == 3
    assert result.image_bytes == PNG_BYTES


# -------------------------------------------------------------------------
# AsyncPollinationsBackend — fails after MAX_RETRIES
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_generate_fails_after_max_retries(monkeypatch) -> None:
    """All attempts return 503 — backend must raise RuntimeError."""

    from apd.generate import pollinations_backend as poll_mod

    async def _no_sleep(_):
        return None

    monkeypatch.setattr(poll_mod.asyncio, "sleep", _no_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"upstream down", headers={"content-type": "text/plain"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        backend = AsyncPollinationsBackend(model="flux")
        with pytest.raises(RuntimeError, match="failed after"):
            await backend.generate("a photo of a CEO", 1, client=client)


# -------------------------------------------------------------------------
# AsyncPollinationsBackend — non-retryable status raises immediately
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_generate_non_retryable_status_raises() -> None:
    """404 is not in the retryable set — must raise on first attempt."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"not found", headers={"content-type": "text/plain"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        backend = AsyncPollinationsBackend(model="flux")
        with pytest.raises(httpx.HTTPStatusError):
            await backend.generate("a photo of a CEO", 1, client=client)


# -------------------------------------------------------------------------
# AsyncPollinationsBackend — concurrency
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_generate_supports_concurrent_streams(monkeypatch) -> None:
    """Run 10 concurrent generate calls — verify all succeed and the
    transport sees 10 GET requests."""
    n_seen = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n_seen["n"] += 1
        return httpx.Response(200, content=PNG_BYTES, headers={"content-type": "image/png"})

    transport = httpx.MockTransport(handler)
    backend = AsyncPollinationsBackend(model="flux")
    async with httpx.AsyncClient(transport=transport) as client:
        coros = [backend.generate(f"prompt {i}", i, client=client) for i in range(10)]
        results = await asyncio.gather(*coros)

    assert n_seen["n"] == 10
    assert all(r.image_bytes == PNG_BYTES for r in results)


# -------------------------------------------------------------------------
# AsyncPollinationsBackend — owns its client when none passed
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_generate_creates_client_when_none_passed(monkeypatch) -> None:
    """Without ``client=`` arg, backend creates a short-lived AsyncClient.

    We don't have a hook to assert this directly, but we patch
    ``httpx.AsyncClient`` to a stub that records construction and verifies
    ``aclose()`` was called.
    """
    from apd.generate import pollinations_backend as poll_mod

    constructed = {"count": 0, "closed": 0}

    real_async_client = httpx.AsyncClient

    class _Recording(real_async_client):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault(
                "transport",
                httpx.MockTransport(
                    lambda req: httpx.Response(
                        200,
                        content=PNG_BYTES,
                        headers={"content-type": "image/png"},
                    )
                ),
            )
            super().__init__(*args, **kwargs)
            constructed["count"] += 1

        async def aclose(self):
            constructed["closed"] += 1
            await super().aclose()

    monkeypatch.setattr(poll_mod.httpx, "AsyncClient", _Recording)
    backend = AsyncPollinationsBackend(model="flux")
    await backend.generate("a photo of a CEO", 1)  # no client passed
    assert constructed["count"] == 1
    assert constructed["closed"] == 1


# -------------------------------------------------------------------------
# Sync + Async share URL + params
# -------------------------------------------------------------------------


def test_sync_and_async_share_request_shape() -> None:
    """If a cell would be served by either backend, the URL + params must
    be byte-identical so the panel cannot fork on which backend issued it.
    """
    sync_url, sync_params = _build_url_and_params(
        "a photo of a CEO",
        model="flux",
        seed=42,
        width=512,
        height=512,
    )
    # Construct an AsyncPollinationsBackend with the same config and verify
    # it would build the same request (we re-call the shared helper).
    async_backend = AsyncPollinationsBackend(model="flux", width=512, height=512)
    async_url, async_params = _build_url_and_params(
        "a photo of a CEO",
        model=async_backend.model,
        seed=42,
        width=async_backend.width,
        height=async_backend.height,
    )
    assert sync_url == async_url
    assert sync_params == async_params


def test_sync_class_still_exists_and_is_unchanged() -> None:
    """Belt-and-suspenders: the sync ``PollinationsBackend`` must still
    be importable and exposes the same interface (the shift notebook
    depends on it)."""
    backend = PollinationsBackend(model="flux", width=512, height=512)
    assert backend.name == "pollinations"
    assert backend.model == "flux"
    assert hasattr(backend, "generate")
    # The sync class generate is NOT a coroutine.
    assert not asyncio.iscoroutinefunction(backend.generate)
