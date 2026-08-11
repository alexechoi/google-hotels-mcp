"""Response envelope decoding.

A ``batchexecute`` response is an anti-JSON-hijacking prefix (``)]}'``)
followed by length-delimited JSON chunks. Somewhere in those chunks lives a
frame tagged ``wrb.fr`` whose third element is the RPC's actual payload,
double-encoded as a JSON string.

Rather than regex-scanning the raw text, this module walks the chunks with a
real JSON decoder — escapes, unicode, and nesting are handled by ``json``
itself.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

from ghotels.errors import ProtocolError, RateLimitedError, TransportError

if TYPE_CHECKING:
    from collections.abc import Iterator

_ENVELOPE_PREFIX: Final = ")]}'"
_FRAME_TAG: Final = "wrb.fr"
_FRAME_MIN_LEN: Final = 3
_BLOCK_MARKERS: Final = ("/sorry/", "unusual traffic")


def decode_envelope(raw: str, rpc_id: str) -> Any:  # noqa: ANN401 - payload shape is Google's
    """Extract and parse the inner payload of ``rpc_id``'s response frame.

    Raises:
        TransportError: the body is empty.
        RateLimitedError: Google served an anti-bot / rate-limit page.
        ProtocolError: no frame for ``rpc_id``, or the frame has no payload.
    """
    if not raw:
        msg = "empty response body"
        raise TransportError(msg)
    lowered = raw.lower()
    if any(marker in lowered for marker in _BLOCK_MARKERS):
        msg = "Google served an anti-bot interstitial; back off before retrying"
        raise RateLimitedError(msg)

    for frame in _iter_frames(raw.removeprefix(_ENVELOPE_PREFIX)):
        if frame[1] != rpc_id:
            continue
        payload = frame[2]
        if not isinstance(payload, str) or not payload:
            msg = f"frame for {rpc_id} carries a null payload — request likely malformed"
            raise ProtocolError(msg)
        return json.loads(payload)

    msg = f"no {rpc_id} frame in response (head: {raw[:160]!r})"
    raise ProtocolError(msg)


def _iter_frames(body: str) -> Iterator[list[Any]]:
    """Yield every ``wrb.fr`` frame found in the chunked response body."""
    decoder = json.JSONDecoder()
    position = 0
    while (start := body.find("[", position)) != -1:
        try:
            value, end = decoder.raw_decode(body, start)
        except json.JSONDecodeError:
            position = start + 1
            continue
        position = end
        yield from _frames_within(value)


def _frames_within(value: Any) -> Iterator[list[Any]]:  # noqa: ANN401 - arbitrary decoded JSON
    """Yield ``value`` itself and/or its direct children that are frames."""
    if not isinstance(value, list):
        return
    if _is_frame(value):
        yield value
        return
    for item in value:
        if _is_frame(item):
            yield item


def _is_frame(value: Any) -> bool:  # noqa: ANN401 - arbitrary decoded JSON
    return (
        isinstance(value, list)
        and len(value) >= _FRAME_MIN_LEN
        and value[0] == _FRAME_TAG
        and isinstance(value[1], str)
    )
