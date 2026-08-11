"""Detail-mode response parsing: one enriched hotel entry.

Detail-only slots (relative to the entry; see ``entry.py`` for the shared
slots):

======  =====================================================================
Slot            Content
======  =====================================================================
[2][1][0][0][0]  street address
[2][2][0]        phone number
[6][2][2]        provider list (per-OTA offers)
[7][3]           sampled guest reviews
[10][0]          grouped amenity label records
[11][0]          short description
======  =====================================================================

Provider entries carry a header row (``[0]`` → name at ``[0][0]``, deeplink
path at ``[0][2]``) followed by room blocks; each room's rates sit at
``room[2]`` with the per-night price at ``rate[4][4]`` and the structured
cancellation tuple at ``rate[2]``.
"""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING, Any, Final

from ghotels.errors import ProtocolError
from ghotels.models.detail import Cancellation, HotelDetail, Rate, Review, Room
from ghotels.parsing._pluck import pluck
from ghotels.parsing.cancellation import cancellation_from_slot
from ghotels.parsing.entry import find_hotel_entries, parse_hotel_entry

if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import date

_HTML_TAG_RE: Final = re.compile(r"<[^>]+>")
_MAX_AMENITY_LABELS: Final = 40
_MAX_REVIEWS: Final = 5
_MIN_REVIEW_BODY_LEN: Final = 40
_MAX_AUTHOR_LEN: Final = 40
_MAX_RATING: Final = 5

#: Sanity band for "this int looks like a nightly price".
_PRICE_MIN: Final = 20
_PRICE_MAX: Final = 100_000


def parse_detail_response(
    inner: Any,  # noqa: ANN401 - decoded JSON
    *,
    requested_currency: str | None = None,
    reference: date | None = None,
) -> HotelDetail:
    """Parse a single-hotel detail payload.

    Detail responses omit the list-view price pair that normally carries the
    currency, so ``requested_currency`` labels rates with the currency the
    request asked for. ``reference`` (the stay's check-in date) anchors
    yearless cancellation deadlines — see :mod:`ghotels.parsing.cancellation`.

    Raises:
        ProtocolError: the payload contains no parseable hotel entry.
    """
    entries = find_hotel_entries(inner)
    if not entries:
        msg = "detail response contains no hotel entry"
        raise ProtocolError(msg)
    entry = entries[0]
    base = parse_hotel_entry(entry)
    if base is None:
        msg = "detail response's hotel entry failed to parse"
        raise ProtocolError(msg)

    currency = (base.price.currency if base.price else None) or requested_currency or "USD"

    return HotelDetail(
        **base.model_dump(),
        description=_string_slot(entry, 11, 0),
        address=_string_slot(entry, 2, 1, 0, 0, 0),
        phone=_string_slot(entry, 2, 2, 0),
        rooms=_rooms(entry, currency, reference),
        amenity_labels=_amenity_labels(entry),
        reviews=_reviews(entry),
    )


def _string_slot(entry: list[Any], *path: int) -> str | None:
    value = pluck(entry, *path)
    return value if isinstance(value, str) and value else None


def _rooms(entry: list[Any], currency: str, reference: date | None) -> tuple[Room, ...]:
    """Build rooms from the provider list.

    Google's provider list is per-OTA, not per-room-type; each provider's
    cheapest rate becomes one offer under a single synthetic room, sorted
    cheapest first.
    """
    providers = pluck(entry, 6, 2, 2)
    if not isinstance(providers, list):
        return ()
    rates = [
        rate
        for provider_entry in providers
        if (rate := _provider_rate(provider_entry, currency, reference)) is not None
    ]
    if not rates:
        return ()
    rates.sort(key=lambda r: r.price)
    return (Room(name="Standard Room", rates=tuple(rates)),)


def _provider_rate(entry: Any, currency: str, reference: date | None) -> Rate | None:  # noqa: ANN401
    """Extract one provider's cheapest offer with its own cancellation terms."""
    if not isinstance(entry, list) or not entry:
        return None
    provider = pluck(entry, 0, 0)
    if not isinstance(provider, str) or not provider:
        return None

    deeplink = pluck(entry, 0, 2)
    booking_url = (
        f"https://www.google.com{deeplink}"
        if isinstance(deeplink, str) and deeplink.startswith("/")
        else None
    )

    best_price, best_cancellation = _cheapest_room_rate(entry, reference)
    if best_price is None:
        best_price = _header_price(pluck(entry, 0))
        if best_price is None:
            return None

    return Rate(
        provider=provider,
        price=best_price,
        currency=currency,
        cancellation=best_cancellation,
        booking_url=booking_url,
    )


def _rooms_block(entry: list[Any]) -> list[Any] | None:
    """First post-header element whose head looks like a room-name string."""
    for candidate in entry[1:]:
        if isinstance(candidate, list) and isinstance(pluck(candidate, 0, 0), str):
            return candidate
    return None


def _cheapest_room_rate(
    entry: list[Any], reference: date | None
) -> tuple[int | None, Cancellation]:
    """Scan a provider's room blocks for the lowest per-night rate."""
    best_price: int | None = None
    best_cancellation = Cancellation()
    for room in _rooms_block(entry) or []:
        rates = pluck(room, 2, default=[])
        if not isinstance(rates, list):
            continue
        for rate in rates:
            per_night = pluck(rate, 4, 4)
            if not isinstance(per_night, int) or not _PRICE_MIN <= per_night <= _PRICE_MAX:
                continue
            if best_price is None or per_night < best_price:
                best_price = per_night
                best_cancellation = cancellation_from_slot(pluck(rate, 2), reference)
    return best_price, best_cancellation


def _header_price(header: Any) -> int | None:  # noqa: ANN401 - decoded JSON
    """Fallback: the first price-like integer in the provider header row."""
    if not isinstance(header, list):
        return None
    for element in header:
        if isinstance(element, int) and _PRICE_MIN <= element <= _PRICE_MAX:
            return element
    return None


def _amenity_labels(entry: list[Any]) -> tuple[str, ...]:
    """Read the grouped label records at [10][0].

    Only the documented record positions are read — sibling branches carry
    search snippets and nearby business names that a naive string sweep
    would misreport as amenities.
    """
    groups = pluck(entry, 10, 0)
    if not isinstance(groups, list):
        return ()
    labels: list[str] = []
    seen: set[str] = set()
    for group in groups:
        records = pluck(group, 1)
        if not isinstance(records, list):
            continue
        for record in records:
            raw = pluck(record, 0)
            if not isinstance(raw, str):
                continue
            label = " ".join(_HTML_TAG_RE.sub("", html.unescape(raw)).split())
            if not label or label.casefold() in seen:
                continue
            seen.add(label.casefold())
            labels.append(label)
            if len(labels) == _MAX_AMENITY_LABELS:
                return tuple(labels)
    return tuple(labels)


def _reviews(entry: list[Any]) -> tuple[Review, ...]:
    block = pluck(entry, 7, 3)
    if not isinstance(block, list):
        return ()
    return tuple(
        review for review_entry in block[:_MAX_REVIEWS] if (review := _review(review_entry))
    )


def _flatten(node: object) -> Iterator[object]:
    """Depth-first scalars of a nested list (booleans excluded)."""
    if isinstance(node, list):
        for child in node:
            yield from _flatten(child)
    elif not isinstance(node, bool):
        yield node


def _segmented_body(node: object) -> str | None:
    """Join a ``[[text, highlighted], ...]`` segment list into one string.

    This is the shape live responses use for sampled review text; the
    boolean marks Google's keyword highlighting.
    """
    if not isinstance(node, list) or not node:
        return None
    segments: list[str] = []
    for item in node:
        if not (
            isinstance(item, list)
            and len(item) == 2  # noqa: PLR2004 - [text, flag] pair
            and isinstance(item[0], str)
            and isinstance(item[1], bool)
        ):
            return None
        segments.append(item[0])
    return "".join(segments).strip()


def _review(entry: object) -> Review | None:
    """Extract one sampled review.

    The live shape is ``[segmented_body, [avatar...], author]``; older
    captures carry a flat mix of scalars, so a heuristic sweep backs up the
    structured read.
    """
    if not isinstance(entry, list):
        return None
    body = _segmented_body(pluck(entry, 0))
    author = entry[2] if len(entry) > 2 and isinstance(entry[2], str) else None  # noqa: PLR2004
    rating: int | None = None

    for scalar in _flatten(entry):
        if rating is None and isinstance(scalar, int) and 1 <= scalar <= _MAX_RATING:
            rating = scalar
        elif isinstance(scalar, str):
            if body is None and len(scalar) > _MIN_REVIEW_BODY_LEN:
                body = scalar
            elif (
                author is None
                and 2 <= len(scalar) <= _MAX_AUTHOR_LEN  # noqa: PLR2004 - plausible name length
                and scalar[0].isupper()
            ):
                author = scalar

    if body is None:
        return None
    return Review(author=author, rating=rating, body=body)
