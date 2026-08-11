"""Typed error taxonomy.

Every error raised by this package derives from :class:`GHotelsError`, and
each class carries a ``retryable`` flag so callers can branch on *behaviour*
instead of matching message strings.
"""

from __future__ import annotations

from typing import ClassVar


class GHotelsError(Exception):
    """Base class for every error this package raises."""

    retryable: ClassVar[bool] = False
    """Whether retrying the same call may plausibly succeed."""


class TransportError(GHotelsError):
    """The request never produced a usable response (network, 5xx, 429).

    Retryable: the failure is on the wire or on Google's side, not in the
    request itself.
    """

    retryable = True


class RateLimitedError(TransportError):
    """Google answered with an anti-bot interstitial or rate-limit page.

    Retryable, but callers should back off substantially before doing so.
    """


class ProtocolError(GHotelsError):
    """The response arrived but did not match the expected wire shape.

    Not retryable: either the request was malformed or Google changed the
    ``batchexecute`` format and the protocol layer needs updating.
    """


class MissingEntityKeyError(GHotelsError):
    """A detail lookup was attempted without a usable entity key."""
