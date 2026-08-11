"""Envelope decoding tests over synthetic batchexecute responses."""

import json

import pytest

from ghotels.errors import ProtocolError, RateLimitedError, TransportError
from ghotels.protocol import decode_envelope
from ghotels.protocol.request import RPC_ID


def wrap(payload, rpc_id=RPC_ID) -> str:
    """Build a realistic chunked batchexecute response around a payload."""
    frame = ["wrb.fr", rpc_id, json.dumps(payload), None, None, None, "1"]
    chunk = json.dumps([frame, ["di", 59], ["af.httprm", 59, "7364528437", 12]])
    return f')]}}\'\n\n{len(chunk)}\n{chunk}\n25\n[["e",4,null,null,131]]\n'


class TestDecodeEnvelope:
    def test_roundtrip(self):
        payload = [["hotels", [1, 2, 3]], None, {"nested": True}]
        assert decode_envelope(wrap(payload), RPC_ID) == payload

    def test_unicode_survives(self):
        payload = ["Hôtel Père-Lachaise — 東京", ["¥12,800"]]
        assert decode_envelope(wrap(payload), RPC_ID) == payload

    def test_picks_the_right_frame_among_many(self):
        target = ["the", "payload"]
        other = ["wrb.fr", "OtherRpc", json.dumps(["decoy"]), None, "1"]
        mine = ["wrb.fr", RPC_ID, json.dumps(target), None, "1"]
        chunk = json.dumps([other, mine])
        raw = f")]}}'\n\n{len(chunk)}\n{chunk}"
        assert decode_envelope(raw, RPC_ID) == target

    def test_empty_body_is_transport_error(self):
        with pytest.raises(TransportError, match="empty response body"):
            decode_envelope("", RPC_ID)

    def test_antibot_page_is_rate_limited_error(self):
        for page in (
            "<html>https://www.google.com/sorry/index</html>",
            "<html>Our systems have detected unusual traffic</html>",
        ):
            with pytest.raises(RateLimitedError):
                decode_envelope(page, RPC_ID)

    def test_missing_frame_is_protocol_error(self):
        raw = wrap(["data"], rpc_id="SomeOtherRpc")
        with pytest.raises(ProtocolError, match=f"no {RPC_ID} frame"):
            decode_envelope(raw, RPC_ID)

    def test_null_payload_is_protocol_error(self):
        frame = ["wrb.fr", RPC_ID, None, None, "1"]
        chunk = json.dumps([frame])
        raw = f")]}}'\n\n{len(chunk)}\n{chunk}"
        with pytest.raises(ProtocolError, match="null payload"):
            decode_envelope(raw, RPC_ID)

    def test_garbage_between_chunks_is_tolerated(self):
        payload = ["ok"]
        frame = ["wrb.fr", RPC_ID, json.dumps(payload), None, "1"]
        raw = ")]}'\n\n[not-json![\n" + json.dumps([frame])
        assert decode_envelope(raw, RPC_ID) == payload
