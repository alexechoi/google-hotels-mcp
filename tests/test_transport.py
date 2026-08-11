"""Transport behavior: status mapping, retries, pacing."""

import asyncio
import json
import time

import pytest

from ghotels.errors import ProtocolError, RateLimitedError, TransportError
from ghotels.protocol.request import RPC_ID
from ghotels.transport import TokenBucket, Transport


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class FakeSession:
    """Stands in for curl_cffi's AsyncSession; replays scripted responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def post(self, url, **kwargs):
        self.calls += 1
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def close(self):
        pass


def ok_response(payload):
    frame = ["wrb.fr", RPC_ID, json.dumps(payload), None, "1"]
    return FakeResponse(200, ")]}'\n\n" + json.dumps([frame]))


def make_transport(responses, **kwargs):
    transport = Transport(rps=10_000, **kwargs)
    transport._session = FakeSession(responses)
    return transport


class TestPostRpc:
    async def test_success_roundtrip(self):
        transport = make_transport([ok_response(["hello"])])
        assert await transport.post_rpc(RPC_ID, ["req"]) == ["hello"]

    async def test_transient_500_retries_then_succeeds(self):
        transport = make_transport([FakeResponse(503), ok_response(["ok"])])
        assert await transport.post_rpc(RPC_ID, ["req"]) == ["ok"]
        assert transport._session.calls == 2

    async def test_429_maps_to_rate_limited_and_retries_out(self):
        transport = make_transport([FakeResponse(429)] * 3)
        with pytest.raises(RateLimitedError):
            await transport.post_rpc(RPC_ID, ["req"])
        assert transport._session.calls == 3

    async def test_400_is_fatal_no_retry(self):
        transport = make_transport([FakeResponse(400)])
        with pytest.raises(ProtocolError, match="request likely malformed"):
            await transport.post_rpc(RPC_ID, ["req"])
        assert transport._session.calls == 1

    async def test_antibot_page_retries(self):
        sorry = FakeResponse(200, "<html>https://www.google.com/sorry/index</html>")
        transport = make_transport([sorry, ok_response(["recovered"])])
        assert await transport.post_rpc(RPC_ID, ["req"]) == ["recovered"]

    async def test_exhausted_retries_reraise_last_error(self):
        transport = make_transport([FakeResponse(503)] * 3)
        with pytest.raises(TransportError):
            await transport.post_rpc(RPC_ID, ["req"])


@pytest.mark.slow
class TestTokenBucket:
    async def test_paces_after_burst(self):
        bucket = TokenBucket(rate=50, capacity=1)
        start = time.monotonic()
        for _ in range(5):
            await bucket.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.07  # 4 waits at 20ms each, minus scheduling slack

    async def test_burst_capacity_is_immediate(self):
        bucket = TokenBucket(rate=1, capacity=5)
        start = time.monotonic()
        for _ in range(5):
            await bucket.acquire()
        assert time.monotonic() - start < 0.05

    async def test_concurrent_acquirers_all_complete(self):
        bucket = TokenBucket(rate=100, capacity=1)
        await asyncio.gather(*(bucket.acquire() for _ in range(10)))
