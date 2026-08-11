"""Async HTTP transport: Chrome-impersonated, rate-limited, retrying.

The whole package funnels through :meth:`Transport.post_rpc`:

- **TLS impersonation** — plain HTTP clients get blocked quickly;
  ``curl_cffi``'s Chrome fingerprint does not.
- **Token bucket** — a genuine async token bucket (not a fixed window)
  paces requests at ``GHOTELS_RPS`` (default 10/s).
- **Retries** — transient failures (429/5xx/network/anti-bot) retry with
  exponential backoff; protocol errors fail fast.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from curl_cffi import CurlError
from curl_cffi.requests import AsyncSession
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from typing_extensions import Self

from ghotels.config import Settings
from ghotels.errors import ProtocolError, RateLimitedError, TransportError
from ghotels.protocol import ENDPOINT, decode_envelope, encode_form_body

logger = logging.getLogger(__name__)

_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_CLIENT_ERROR_FLOOR = 400

_HEADERS = {"content-type": "application/x-www-form-urlencoded;charset=UTF-8"}


class TokenBucket:
    """Classic token bucket: ``rate`` tokens/second, bursts up to ``capacity``."""

    def __init__(self, rate: float, capacity: float | None = None) -> None:
        self._rate = rate
        self._capacity = capacity if capacity is not None else max(1.0, rate)
        self._tokens = self._capacity
        self._stamp = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Take one token, sleeping until one is available."""
        async with self._lock:
            while True:
                now = time.monotonic()
                self._tokens = min(self._capacity, self._tokens + (now - self._stamp) * self._rate)
                self._stamp = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                await asyncio.sleep((1 - self._tokens) / self._rate)


class Transport:
    """One shared HTTP session with pacing and retry policy."""

    def __init__(
        self,
        *,
        rps: float | None = None,
        timeout: float | None = None,
        impersonate: str = "chrome",
    ) -> None:
        settings = Settings()
        self._timeout = timeout if timeout is not None else settings.timeout
        self._impersonate = impersonate
        self._bucket = TokenBucket(rps if rps is not None else settings.rps)
        self._session: AsyncSession[Any] | None = None

    def _ensure_session(self) -> AsyncSession[Any]:
        if self._session is None:
            self._session = AsyncSession(headers=dict(_HEADERS))
        return self._session

    async def aclose(self) -> None:
        """Release the underlying HTTP session."""
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type(TransportError),
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def post_rpc(self, rpc_id: str, payload: list[Any]) -> Any:  # noqa: ANN401 - Google's shape
        """POST one RPC and return its decoded inner payload.

        Every attempt (including retries) takes a token from the bucket, so
        backoff never bypasses the rate limit.
        """
        await self._bucket.acquire()
        session = self._ensure_session()
        try:
            response = await session.post(
                ENDPOINT,
                data=encode_form_body(payload, rpc_id),
                timeout=self._timeout,
                impersonate=self._impersonate,
            )
        except CurlError as exc:
            msg = f"network error calling {rpc_id}: {exc}"
            raise TransportError(msg) from exc

        status = response.status_code
        if status in _RETRYABLE_STATUSES:
            msg = f"HTTP {status} from endpoint"
            raise RateLimitedError(msg) if status == 429 else TransportError(msg)  # noqa: PLR2004
        if status >= _CLIENT_ERROR_FLOOR:
            msg = f"HTTP {status} from endpoint — request likely malformed"
            raise ProtocolError(msg)
        return decode_envelope(response.text, rpc_id)
