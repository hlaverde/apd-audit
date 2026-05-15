"""Hugging Face Inference API backend (free tier).

The token is read from ``settings.hf_token`` (``HF_TOKEN`` in ``.env``).
Rate-limit responses (HTTP 429/503) honour the ``Retry-After`` header with
exponential backoff. Cold-start 503s from ``wait_for_model=True`` are
treated the same way.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass

import requests

from apd.config import settings

logger = logging.getLogger(__name__)

API_URL = "https://api-inference.huggingface.co/models/{model}"
DEFAULT_TIMEOUT_S = 180
MAX_RETRIES = 6


class HFGenerationError(RuntimeError):
    """Raised when HF generation fails after retries."""


@dataclass(frozen=True)
class GenerationResult:
    image_bytes: bytes
    sha256: str
    backend: str
    duration_s: float


class HFBackend:
    name = "hf"

    def __init__(self, model: str, token: str | None = None) -> None:
        resolved_token = token if token is not None else settings.hf_token
        if not resolved_token:
            raise HFGenerationError(
                "HF_TOKEN missing. Copy .env.example to .env and paste your "
                "Hugging Face token there (https://huggingface.co/settings/tokens).",
            )
        self.model = model
        self.token = resolved_token
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "User-Agent": settings.hf_user_agent,
                "Accept": "image/png",
            },
        )

    def generate(self, prompt: str, seed: int) -> GenerationResult:
        url = API_URL.format(model=self.model)
        payload = {
            "inputs": prompt,
            "parameters": {"seed": int(seed), "num_inference_steps": 25},
            "options": {"wait_for_model": True, "use_cache": False},
        }
        backoff = 5
        started = time.time()
        last_status: int | None = None
        last_body: str = ""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = self.session.post(url, json=payload, timeout=DEFAULT_TIMEOUT_S)
            except requests.RequestException as exc:
                logger.warning("HF network error on %s: %s (attempt %d)", self.model, exc, attempt)
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)
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
            if r.status_code in (429, 503):
                retry_after = _retry_after_seconds(r, default=backoff)
                logger.warning(
                    "HF %s on %s, sleeping %ss (attempt %d/%d)",
                    r.status_code, self.model, retry_after, attempt, MAX_RETRIES,
                )
                time.sleep(retry_after)
                backoff = min(backoff * 2, 120)
                continue
            last_body = r.text[:500]
            logger.error("HF unexpected %s on %s: %s", r.status_code, self.model, last_body)
            r.raise_for_status()
        raise HFGenerationError(
            f"HF generation failed after {MAX_RETRIES} attempts "
            f"(last status={last_status}, body={last_body!r})",
        )


def _retry_after_seconds(response: requests.Response, *, default: int) -> int:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return default
    try:
        return max(1, int(float(raw)))
    except ValueError:
        return default
