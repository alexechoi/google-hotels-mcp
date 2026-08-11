"""Request builders: domain models in, ``batchexecute`` payloads out.

One RPC (``AtySUc``) serves both modes: a *search* request leaves the entity
key null, a *detail* request places the hotel's entity key into the request
meta block. The full slot map is documented in ``docs/PROTOCOL.md``.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import TYPE_CHECKING, Any, Final

from ghotels.errors import MissingEntityKeyError
from ghotels.models.enums import Currency
from ghotels.models.filters import Guests, Location, SearchFilters
from ghotels.protocol.ids import (
    ADULT_MARKER,
    AMENITY_IDS,
    BRAND_IDS,
    BRAND_SUB_IDS,
    MIN_RATING_IDS,
    PROPERTY_TYPE_IDS,
    SORT_IDS,
    child_age_bucket,
)

if TYPE_CHECKING:
    from datetime import date

    from ghotels.models.filters import StayDates

RPC_ID: Final = "AtySUc"
ENDPOINT: Final = "https://www.google.com/_/TravelFrontendUi/data/batchexecute"

#: Neutral query text used for detail lookups when the caller has no location.
_NEUTRAL_QUERY: Final = "hotels"


def build_search_payload(filters: SearchFilters) -> list[Any]:
    """Build the inner RPC payload for a list-view search."""
    return [
        filters.location.query,
        _search_params(filters),
        _request_meta(entity_key=None),
    ]


def build_detail_payload(
    entity_key: str,
    *,
    dates: StayDates,
    guests: Guests | None = None,
    currency: Currency = Currency.USD,
    location: Location | None = None,
) -> list[Any]:
    """Build the inner RPC payload for a single-hotel detail lookup.

    ``dates`` is required because rate plans are computed for a concrete
    window. ``guests`` affects room pricing and availability; omitting it
    requests the default party of two adults.
    """
    if not entity_key or not entity_key.strip():
        msg = "entity_key must be a non-empty string (take it from a search result)"
        raise MissingEntityKeyError(msg)
    filters = SearchFilters(
        location=location or Location(query=_NEUTRAL_QUERY),
        dates=dates,
        guests=guests or Guests(),
        currency=currency,
    )
    return [
        filters.location.query,
        _search_params(filters),
        _request_meta(entity_key=entity_key),
    ]


def encode_form_body(inner_payload: list[Any], rpc_id: str = RPC_ID) -> bytes:
    """Wrap an inner payload in the ``f.req`` envelope, ready to POST.

    The envelope is ``[[[rpc_id, <inner payload as a JSON string>, null,
    "1"]]]``, JSON-encoded, URL-quoted, and prefixed with ``f.req=``.
    """
    inner_json = json.dumps(inner_payload, separators=(",", ":"))
    envelope = json.dumps([[[rpc_id, inner_json, None, "1"]]], separators=(",", ":"))
    return f"f.req={urllib.parse.quote(envelope, safe='')}".encode()


def _search_params(filters: SearchFilters) -> list[Any]:
    """SearchParams block at payload slot [1]."""
    return [
        PROPERTY_TYPE_IDS[filters.property_type],
        _party_block(filters.guests),
        _place_and_stay(filters),
        None,
        _filters_record(filters),
    ]


def _party_block(guests: Guests) -> list[Any] | None:
    """Party composition at [1][1]; null for the default two adults.

    Each adult contributes a ``[3]`` marker and each child an age-bucket
    pair, followed by a constant ``1``.
    """
    if guests.adults == 2 and not guests.child_ages:  # noqa: PLR2004 - the wire default party
        return None
    party: list[list[int]] = [[ADULT_MARKER]] * guests.adults
    party += [child_age_bucket(age) for age in guests.child_ages]
    return [party, 1]


def _place_and_stay(filters: SearchFilters) -> list[Any] | None:
    """Location pin + stay dates at [1][2]; null when neither is set."""
    place = _place_slot(filters.location)
    stay = _stay_slot(filters.dates, filters.guests)
    if place is None and stay is None:
        return None
    return [place, stay]


def _place_slot(location: Location) -> list[Any] | None:
    """Structural place pin at [1][2][0]; null for free-text-only queries."""
    if not location.is_pinned:
        return None
    pin = [location.kgmid, None, None, None, None, location.fid, location.display_name]
    return [None, [pin], []]


def _stay_slot(dates: StayDates | None, guests: Guests) -> list[Any] | None:
    """Check-in/out dates at [1][2][1]; null requests flexible dates.

    The trailing element carries the child count; adults travel in the
    party block at [1][1].
    """
    if dates is None:
        return None
    return [
        None,
        [_ymd(dates.check_in), _ymd(dates.check_out), dates.nights],
        None,
        None,
        None,
        [None, guests.children],
    ]


def _ymd(day: date) -> list[int]:
    return [day.year, day.month, day.day]


def _filters_record(filters: SearchFilters) -> list[Any]:
    """Filter record at [1][4].

    Base shape is ``[details, null, [], price]``. A minimum-guest-rating id
    appends at position 4; the special-offers flag appends ``1`` at position
    5 (with a null placeholder at 4 when no rating filter is set).
    """
    record: list[Any] = [
        _filter_details(filters),
        None,
        [],
        _price_slot(filters.price_min, filters.price_max),
    ]
    if filters.min_rating is not None:
        record.append(MIN_RATING_IDS[filters.min_rating])
    elif filters.special_offers:
        record.append(None)
    if filters.special_offers:
        record.append(1)
    return record


def _filter_details(filters: SearchFilters) -> list[Any]:
    """Filter details at [1][4][0].

    ``[amenities, star_classes, null, free_cancellation, sort_id, null,
    currency, brands]`` — extended by ``[null, 1]`` when the eco-certified
    chip is on.
    """
    details: list[Any] = [
        [AMENITY_IDS[a] for a in filters.amenities] or None,
        sorted(filters.star_classes) or None,
        None,
        1 if filters.free_cancellation else None,
        SORT_IDS[filters.sort_by],
        None,
        filters.currency.value,
        _brands_slot(filters),
    ]
    if filters.eco_certified:
        details += [None, 1]
    return details


def _brands_slot(filters: SearchFilters) -> list[Any] | None:
    """Brand families at [1][4][0][7] as ``[id, [sub ids]]`` pairs.

    Families without sub-brands (Four Seasons) are sent as a bare ``[id]``
    — the empty-sub-list form is silently ignored by Google.
    """
    if not filters.brands:
        return None
    slot: list[Any] = []
    for brand in filters.brands:
        subs = BRAND_SUB_IDS[brand]
        pair = [BRAND_IDS[brand], list(subs)] if subs else [BRAND_IDS[brand]]
        slot.append(pair)
    return slot


def _price_slot(price_min: int | None, price_max: int | None) -> list[Any]:
    """Per-night price band at [1][4][3], in the preset-chip encoding.

    Dollars are sent directly as ``[[null, min], [null, max], 1]`` with
    either side null when open-ended; ``[null, null, 1]`` means no band.
    """
    low = [None, price_min] if price_min is not None else None
    high = [None, price_max] if price_max is not None else None
    return [low, high, 1]


def _request_meta(*, entity_key: str | None) -> list[Any]:
    """Request meta block at payload slot [2].

    Must always be present — Google silently *ignores* filters when this
    block is missing. Slot [5] routes the RPC: null for search, an entity
    key for a single-hotel detail lookup.
    """
    return [1, None, None, None, None, entity_key, 13, None, 0]
