"""Pollinations.ai free image-generation backend.

Pollinations (https://pollinations.ai) is a public, no-token relay that
serves FLUX and a few other open-weights image models over HTTP. We use
it because the Hugging Face Inference Providers free tier stopped
covering the proposal's image models for non-Pro accounts during 2025
(see DECISIONS.md D-013).

The endpoint is a plain GET:
    https://image.pollinations.ai/prompt/{url-encoded prompt}
        ?model={flux|flux-realism|turbo|...}
        &seed={int}
        &width={int}  &height={int}
        &nologo=true
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import urllib.parse

import httpx
import requests

from .hf_backend import GenerationResult

logger = logging.getLogger(__name__)

API_TEMPLATE = "https://image.pollinations.ai/prompt/{prompt}"
DEFAULT_TIMEOUT_S = 180
MAX_RETRIES = 4


def _build_url_and_params(
    prompt: str, *, model: str, seed: int, width: int, height: int
) -> tuple[str, dict[str, str]]:
    """Shared URL + params builder for the sync and async Pollinations
    backends. Keeps the request signature byte-identical across both
    code paths so the panel cannot fork on which backend issued a cell."""
    encoded = urllib.parse.quote(prompt)
    url = API_TEMPLATE.format(prompt=encoded)
    params = {
        "model": model,
        "seed": str(int(seed)),
        "width": str(int(width)),
        "height": str(int(height)),
        "nologo": "true",
        "private": "true",  # don't surface to the public feed
    }
    return url, params


_RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


class PollinationsBackend:
    name = "pollinations"

    # Model identifiers Pollinations recognises. The default is plain
    # ``flux`` which routes to FLUX.1 schnell weights; ``turbo`` is the
    # SDXL Turbo variant; ``flux-realism`` adds a photorealism fine-tune.
    def __init__(
        self,
        model: str = "flux",
        width: int = 512,
        height: int = 512,
    ) -> None:
        self.model = model
        self.width = int(width)
        self.height = int(height)

    def generate(self, prompt: str, seed: int) -> GenerationResult:
        url, params = _build_url_and_params(
            prompt,
            model=self.model,
            seed=seed,
            width=self.width,
            height=self.height,
        )
        backoff = 4
        started = time.time()
        last_status: int | None = None
        last_body: str = ""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT_S)
            except requests.RequestException as exc:
                logger.warning("Pollinations network error: %s (attempt %d)", exc, attempt)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            last_status = r.status_code
            ctype = r.headers.get("content-type", "")
            if r.status_code == 200 and ctype.startswith("image/"):
                content = r.content
                return GenerationResult(
                    image_bytes=content,
                    sha256=hashlib.sha256(content).hexdigest(),
                    backend=self.name,
                    duration_s=time.time() - started,
                )
            if r.status_code in _RETRYABLE_STATUSES:
                logger.warning(
                    "Pollinations %s (attempt %d/%d), sleeping %ss",
                    r.status_code,
                    attempt,
                    MAX_RETRIES,
                    backoff,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            last_body = r.text[:300]
            logger.error("Pollinations unexpected %s: %s", r.status_code, last_body)
            r.raise_for_status()
        raise RuntimeError(
            f"Pollinations generation failed after {MAX_RETRIES} attempts "
            f"(last status={last_status}, body={last_body!r})",
        )


class AsyncPollinationsBackend:
    """Async sibling of :class:`PollinationsBackend` for the local async
    worker (Layer 2) and the GitHub Actions cron (Layer 1).

    A single ``httpx.AsyncClient`` is reused across calls via the
    optional ``client`` argument so the worker pool can share TCP
    connections and HTTP/2 multiplexing where supported. If no client
    is passed, a short-lived one is created per call (acceptable for
    low-frequency probes; not for sustained shifts).

    The retry contract matches the sync class byte-for-byte:

    * up to ``MAX_RETRIES`` attempts;
    * exponential backoff starting at 4 s, capped at 60 s;
    * retryable on 429 / 5xx; raises on any other non-200.

    The async sleep is ``asyncio.sleep`` so the worker's other concurrent
    streams keep making progress while one stream is in backoff.
    """

    name = "pollinations"

    def __init__(
        self,
        model: str = "flux",
        width: int = 512,
        height: int = 512,
    ) -> None:
        self.model = model
        self.width = int(width)
        self.height = int(height)

    async def generate(
        self,
        prompt: str,
        seed: int,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> GenerationResult:
        url, params = _build_url_and_params(
            prompt,
            model=self.model,
            seed=seed,
            width=self.width,
            height=self.height,
        )
        own_client = client is None
        async_client = client or httpx.AsyncClient(follow_redirects=True)
        try:
            backoff = 4
            started = time.time()
            last_status: int | None = None
            last_body: str = ""
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    r = await async_client.get(url, params=params, timeout=DEFAULT_TIMEOUT_S)
                except httpx.HTTPError as exc:
                    logger.warning(
                        "Pollinations async network error: %s (attempt %d)", exc, attempt
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    continue
                last_status = r.status_code
                ctype = r.headers.get("content-type", "")
                if r.status_code == 200 and ctype.startswith("image/"):
                    content = r.content
                    return GenerationResult(
                        image_bytes=content,
                        sha256=hashlib.sha256(content).hexdigest(),
                        backend=self.name,
                        duration_s=time.time() - started,
                    )
                if r.status_code in _RETRYABLE_STATUSES:
                    logger.warning(
                        "Pollinations async %s (attempt %d/%d), sleeping %ss",
                        r.status_code,
                        attempt,
                        MAX_RETRIES,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    continue
                last_body = r.text[:300]
                logger.error("Pollinations async unexpected %s: %s", r.status_code, last_body)
                r.raise_for_status()
            raise RuntimeError(
                f"Pollinations async generation failed after {MAX_RETRIES} attempts "
                f"(last status={last_status}, body={last_body!r})",
            )
        finally:
            if own_client:
                await async_client.aclose()
